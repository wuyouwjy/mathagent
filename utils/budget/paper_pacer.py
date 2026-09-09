"""全卷完成率引擎（PaperPacer）。

官方约束：112 题、平台并发 3、智能体总运行 6h 封顶，超出后未答题不计分。
官方评测实证：V1 每题固定 1200s 全预算导致 11h19m 远超 6h、accuracy 0.1429
（16/112）——"每题都要完美"在超难题 + 6h 硬约束下必然失败。

设计：题间预算池。每道题不再固定拿 full budget，而是按"已用全卷时间 ÷
剩余题数"动态计算该题可花的软预算上限，保证：
  1. 全卷 6h 内必然跑完 112 题（完成率 100%，不出现"超时未答"0 分题）；
  2. 时间自然向"需要深思的题"倾斜（前面的题省下的时间滚动进池子）；
  3. 任何一道题都不会因为前面耗太快而突然没钱（下限保护，仍 ≥ 保底）。

配合 TimeBudget.apply_difficulty_profile：PaperPacer 给出"全卷视角"的
预算帽（paper_cap），难度画像给出"题型视角"的预算帽（difficulty_cap），
两者取 min 作为该题 soft_total。

安全边界：
  - 只收紧软预算（可选阶段购买力），不动 remaining_hard（平台 1200s 硬限）；
  - 进行中的调用不被截断；reserve 配额通道（压缩重试/仲裁/应急直答）照常；
  - 每道题仍有保底 soft_total，不会出现"简单题 10s 就交卷"。

2026-09-09 修正（B2 全卷 24732s，超 6h 上限 3132s，本次评测因此不计分）：

  a) **阈值允许超时**。原 `lagging = predicted_total > total * 1.15` 把"预测
     总耗时超限 15%"当作健康线，21600×1.15 = 24840s 恰好把实测的 24732s 判成
     "不落后"——全程一次都没收紧。6h 是硬限，容忍线必须在限内。

  b) **并发度漏乘**。原式 `remaining_time / remaining_problems` 得到的是
     "墙钟/题"，却被直接当作单题预算返回。平台并发 3 时三道题并行，单题可独占
     的墙钟是均摊值的 3 倍；漏乘会把预算算成 1/3（21600/112 ≈ 193s，只够发起
     一次压缩推理），"收紧"于是退化成白卷。

  c) **速度预测缺最小样本量**。启动阶段 done 很小，elapsed/done 被并发启动开销
     严重高估，前几题会误判落后。样本不足时只按"剩余均摊"这一硬条件判断。
"""

from __future__ import annotations

import time
from threading import Lock

from config import CONFIG


class PaperPacer:
    """全卷 112 题的节奏控制器：题间预算池 + 动态预算帽。"""

    _instance: "PaperPacer | None" = None
    _lock = Lock()

    #: 每道题的"墙钟/题"最低均摊（秒）。全卷均摊 21600/112 ≈ 193s/题，保底若
    #: ≥193 则全卷必然超时，因此保底必须明显小于均摊（120s），真正吃紧时仍保证
    #: "每题能答"。换算成单题预算时还要乘并发度（见 budget_for）。
    MIN_SOFT = 120.0
    #: 健康时的软预算帽（秒）：设为平台硬限（1200s）。实际生效预算由难度画像
    #: （config.difficulty_soft_budgets：easy 600 / medium 1200 / hard 1200）与
    #: PaperPacer 收紧两者取 min 决定。
    IDEAL = 1200.0
    #: 节奏目标占全卷硬限的比例。6h 是硬限，把**目标**定在硬限上等于每次耗时
    #: 波动都直接越线：全卷 112 题事件驱动模拟（demand~N(662s, 250s)，30 次）
    #: 在 1.00 下中位 21600s、最坏 21831s、8/30 超时；0.95 下最坏 21555s、
    #: 0/30 超时。历史值 1.15（允许超时 15%）则直接导致 B2 全程未收紧。
    #:
    #: 注意这里必须乘在"剩余时间"上，而不是给算出的 cap 打折：cap 由剩余时间
    #: 推导，削掉的部分会在后续题里被"还回来"（剩余时间变多→后续 cap 变大），
    #: 对全卷总时长几乎没有影响——模拟验证过，打折不改变收敛点。
    TARGET_FACTOR = 0.95

    def __init__(self, total_seconds: float | None = None,
                 planned: int | None = None) -> None:
        self.total = float(
            total_seconds if total_seconds is not None
            else CONFIG.get("paper_total_seconds", 6 * 3600))
        self.planned = int(
            planned if planned is not None
            else CONFIG.get("paper_planned_problems", 112))
        self._start = time.monotonic()
        self._done = 0
        self._started: set[int] = set()
        #: 正在求解中的题数（mark_started +1，mark_done -1）。budget_for 在
        #: mark_started 之前调用，所以它反映的是"其它题"的并发数，本题要 +1。
        self._active_count = 0

    # ---- singleton ----

    @classmethod
    def get_instance(cls) -> "PaperPacer":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """每卷评测开始时调用一次（单例无跨题残留）。"""
        with cls._lock:
            cls._instance = cls()

    # ---- public API ----

    def _concurrency_locked(self) -> float:
        """并发度估计：本题 + 正在跑的其它题（调用方持锁）。"""
        return float(max(1, self._active_count + 1))

    def budget_for(self, problem_id: int) -> float:
        """返回该题的建议软预算帽（秒，**单题**口径）。

        判定"落后"两条路：
          * 速度预测——按已完成题的平均墙钟预测全卷总耗时，超过全卷上限即落后
            （样本不足时跳过，见类文档 c）；
          * 剩余均摊——剩余时间按题均摊已低于 MIN_SOFT 时，无论历史速度如何都
            必须收紧（硬条件）。

        落后时按剩余均摊收紧（仍 ≥ MIN_SOFT × 并发度 保底）；健康时给足 IDEAL。
        首题无速度样本 → 健康给足。
        """
        with self._lock:
            elapsed = time.monotonic() - self._start
            remaining_time = max(0.0, self.total - elapsed)
            remaining_problems = max(1, self.planned - self._done)
            concurrency = self._concurrency_locked()
            # 节奏目标是"剩余硬限 × TARGET_FACTOR"，不是硬限本身（见 TARGET_FACTOR）。
            effective_remaining = remaining_time * self.TARGET_FACTOR
            # "墙钟/题"：每完成一道题平均消耗的全卷墙钟。
            per_problem_wall = effective_remaining / remaining_problems
            # 单题可花预算：并发下 N 道题同时占用墙钟，单题独占的是均摊值的 N 倍。
            per_problem = per_problem_wall * concurrency
            # 速度预测需要足够样本：并发 3 时前 3 道题几乎同时启动、同时完成，
            # 用 done=1 的 elapsed/done 会把 pace 高估约 3 倍。
            if self._done >= max(2, int(concurrency)) and elapsed > 0:
                pace = elapsed / self._done
                lagging = pace * self.planned > self.total * self.TARGET_FACTOR
            else:
                lagging = False
            # 硬条件：即使按历史速度预测不超，剩余时间不足也必须收紧。
            if per_problem_wall < self.MIN_SOFT:
                lagging = True
            if not lagging:
                cap = float(self.IDEAL)
            else:
                cap = max(self.MIN_SOFT * concurrency, min(self.IDEAL, per_problem))
            return cap

    def mark_started(self, problem_id: int) -> None:
        with self._lock:
            self._started.add(problem_id)
            self._active_count += 1

    def mark_done(self, problem_id: int | None = None) -> None:
        """一道题结束（无论成败）。problem_id 可选，仅为兼容既有调用。"""
        with self._lock:
            self._done += 1
            # 与 mark_started 配对递减；夹到 0 防止异常路径（mark_started 未执行
            # 而 finally 仍调用 mark_done）把计数带成负数、导致并发度恒为 1。
            if self._active_count > 0:
                self._active_count -= 1

    def remaining_planned(self) -> int:
        with self._lock:
            return max(0, self.planned - self._done)

    def elapsed(self) -> float:
        return time.monotonic() - self._start

    def pace_ok(self) -> bool:
        """当前节奏是否安全（能在 6h 内完成全部题）。"""
        with self._lock:
            elapsed = time.monotonic() - self._start
            remaining_time = max(0.0, self.total - elapsed)
            remaining_problems = max(1, self.planned - self._done)
            per_problem_wall = remaining_time * self.TARGET_FACTOR / remaining_problems
            return per_problem_wall >= self.MIN_SOFT

    def snapshot(self) -> dict:
        with self._lock:
            elapsed = time.monotonic() - self._start
            remaining_time = max(0.0, self.total - elapsed)
            remaining_problems = max(1, self.planned - self._done)
            concurrency = self._concurrency_locked()
            per_problem_wall = remaining_time * self.TARGET_FACTOR / remaining_problems
            return {
                "total_planned": self.planned,
                "done": self._done,
                "active": self._active_count,
                "concurrency": concurrency,
                "remaining_problems": remaining_problems,
                "elapsed_s": round(elapsed, 1),
                "total_s": self.total,
                "remaining_s": round(remaining_time, 1),
                "target_factor": self.TARGET_FACTOR,
                "pace_s_per_problem": round(per_problem_wall, 1),
                "budget_per_problem_s": round(per_problem_wall * concurrency, 1),
                "pace_ok": per_problem_wall >= self.MIN_SOFT,
            }

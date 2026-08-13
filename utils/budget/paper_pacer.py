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
"""

from __future__ import annotations

import time
from threading import Lock

from config import CONFIG


class PaperPacer:
    """全卷 112 题的节奏控制器：题间预算池 + 动态预算帽。"""

    _instance: "PaperPacer | None" = None
    _lock = Lock()

    #: 每道题的最低软预算（秒）。全卷均摊 21600/112 ≈ 193s/题，保底若 ≥193
    #: 则全卷必然超时，因此保底必须明显小于均摊（120s），真正吃紧时仍保证
    #: "每题能答"。
    MIN_SOFT = 120.0
    #: 健康时的软预算帽（秒）：设为平台硬限（1200s）的宽松值——实际生效预算
    #: 由难度画像主导（easy 480 / medium 840 / hard 1200），PaperPacer 只在
    #: "落后"时收紧。
    IDEAL = 1200.0

    def __init__(self, total_seconds: float | None = None,
                 planned: int | None = None) -> None:
        self.total = float(
            total_seconds if total_seconds is not None
            else CONFIG.get("paper_total_seconds", 6 * 3600))
        self.planned = int(planned if planned is not None else 112)
        self._start = time.monotonic()
        self._done = 0
        self._started: set[int] = set()

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

    def budget_for(self, problem_id: int) -> float:
        """返回该题的建议软预算帽（秒）。

        判定"落后"用实际速度预测：若按已完成题的平均速度预测总耗时超过
        全卷上限的 1.15 倍 → 落后 → 按剩余均摊收紧（仍 ≥ MIN_SOFT 保底）；
        否则健康 → 给足理想预算（IDEAL）。首题无速度样本 → 健康给足。
        """
        with self._lock:
            elapsed = time.monotonic() - self._start
            remaining_time = max(0.0, self.total - elapsed)
            remaining_problems = max(1, self.planned - self._done)
            if self._done > 0 and elapsed > 0:
                pace = elapsed / self._done
                predicted_total = pace * self.planned
                lagging = predicted_total > self.total * 1.15
            else:
                lagging = False
            # 硬条件：即使按历史速度预测不超，剩余时间不足也必须收紧。
            per_problem = remaining_time / remaining_problems
            if per_problem < self.MIN_SOFT:
                lagging = True
            if not lagging:
                cap = float(self.IDEAL)
            else:
                cap = max(self.MIN_SOFT, per_problem)
            return cap

    def mark_started(self, problem_id: int) -> None:
        with self._lock:
            self._started.add(problem_id)

    def mark_done(self) -> None:
        with self._lock:
            self._done += 1

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
            per_problem = remaining_time / remaining_problems
            return per_problem >= self.MIN_SOFT

    def snapshot(self) -> dict:
        with self._lock:
            elapsed = time.monotonic() - self._start
            remaining_time = max(0.0, self.total - elapsed)
            remaining_problems = max(1, self.planned - self._done)
            per_problem = remaining_time / remaining_problems
            return {
                "total_planned": self.planned,
                "done": self._done,
                "remaining_problems": remaining_problems,
                "elapsed_s": round(elapsed, 1),
                "total_s": self.total,
                "remaining_s": round(remaining_time, 1),
                "pace_s_per_problem": round(per_problem, 1),
                "pace_ok": per_problem >= self.MIN_SOFT,
            }

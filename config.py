CONFIG = {
    "model": "intern-s2-preview-397b",
    "max_retries_per_node": 2, "llm_max_retries": 3, "backoff_factor": 2.0,
    # Ceilings are a hang detector of LAST resort; TimeBudget.timeout_for() clamps
    # each to whatever the problem deadline still allows, and that clamp is the real
    # bound. They are near the full budget on purpose.
    #
    # Learned the hard way (2026-07-29 run): tighter ceilings of 720s/300s KILLED
    # healthy work — Q1's reasoning was cut at 720s and returned nothing, Q2's Python
    # at exactly 300.0s likewise. A severed node yields an empty answer, while a slow
    # node still yields a usable one, so a ceiling that fires before the deadline is
    # strictly worse than no ceiling at all. Only the deadline may stop real work.
    # `classifier` must exceed nodes.classifier_node._PLAIN_CALL_SECONDS (150): the
    # unprefilled fallback measured 129.5s and 133.3s on a hard problem, so a 120s
    # ceiling killed a call that had already been paid for and discarded the usable
    # prefill result with it (game-theory olympiad problem, 2026-07-29).
    "node_timeouts": {"input": 5, "classifier": 200, "solving": 1150,
                      "reasoning_agent": 1100, "python_agent": 1100,
                      "python_mcp_execute": 60, "cross_validator": 15,
                      "reconciliation": 10, "semantic_arbiter": 150, "coordinator": 420,
                      "critic": 120, "playoff": 300},
    "classifier_confidence_threshold": 0.85,
    # 置信门控：最少资源高准确率。high(≥0.90)→fast 单路径；low(<0.70)→deep；
    # 中间→standard 双路验证。
    "confidence_gate": {"high": 0.90, "low": 0.70},
    "deep_solver_domains": ["数论", "组合数学", "高等代数", "抽象代数"],
    # Zero-cost deterministic ranking is retained purely as a fallback for a
    # failed/unparseable LLM classification; it no longer narrows the LLM's
    # candidate list (all 18 domains go in one prefilled call).
    "classifier_top_k": 3,
    # 题库检索（RAG）：解题前用原题检索相似竞赛题，把 top-k 条题面+解答作为
    # few-shot 参考注入推理与验证两个子代理（ICMAnew 的差异化能力）。检索条数
    # 2：两条全部同时进两个子代理；更多条数会挤占 prompt 预算且引入更多近似题
    # 误导风险（反锚定说明见 utils/retrieval/reference_block.py）。
    "db_retrieval_top_k": 2,
    "computation_tolerance": 1e-6, "proof_confidence_threshold": 0.7,
    # 2026-08-13 主办方确认 temperature 生效。下调推理/代码温度以压随机性：
    # reasoning 0.8→0.3、python 0.6→0.2——本系统强依赖四章节结构化输出 + 下游
    # 解析（extractor/formatter/cleanliness），高温会放大格式偏离、CoT 泄漏与
    # 英文元叙述（v5 白卷诱因）；深度推理模型的探索主要发生在私有 CoT，低温对
    # 正确率的边际损失可忽略。coordinator 保持 0.4（成稿留表达余地）。
    "temperatures": {"classifier": 0.1, "reasoning": 0.3, "objective_reasoning": 0.2,
                     "python": 0.2,
                     "reconciliation": 0.2, "semantic_arbiter": 0.1, "coordinator": 0.4},
    # Prefilled selection calls (classifier/semantic_arbiter) emit 4-12 completion
    # tokens because the assistant seed suppresses reasoning entirely. The small
    # caps below are safe ONLY with prefill: without it, this reasoning model bills
    # CoT against max_tokens and a small cap truncates before any answer appears.
    # The *_fallback budgets fund the non-prefill retry, which must fit full CoT.
    #
    # 2026-08-09 评委报告模式 A（约 35 题）：32768 的单次额度在奥赛题上被私有
    # reasoning_content 整体耗尽（~600s），四章节全空，且耗尽后重试"常已无时间"。
    # 现改为分级熔断：首轮 24576（~450s 封顶），耗尽后改发 prefill 压缩重试
    # （*_compressed，助手种子抑制私有推理，全部 token 用于可见章节，~150s）。
    # 首轮 24576-32768 区间的成功解极少（中档题实测 5-7k token，奥赛题贴 32768
    # 也多为耗尽），降低上限牺牲的成功区间可忽略，换来的重试窗口是净收益。
    # 2026-08-13 主办方新规：max_tokens 被评测环境 cap 到 8192（不传默认 4096）。
    # 故完整推理/生成场景统一设 8192 上限（max_tokens 只截断不加速，设大不增耗时）；
    # 超过 8192 的旧值（reconciliation 32768、coordinator 16384）会被静默 cap，
    # 已显式归一到 8192 以免误导预算预留。prefill 选择题（96）与应急直答（1280）
    # 仍用刻意小 cap 抑制私有 CoT。
    "max_tokens": {"classifier": 96, "classifier_fallback": 8192,
                   "objective_reasoning": 8192,
                   "reasoning": 8192, "python": 8192,
                   "reasoning_compressed": 8192, "python_compressed": 8192,
                   "reconciliation": 8192,
                   "semantic_arbiter": 96, "semantic_arbiter_fallback": 8192,
                   "coordinator": 8192, "emergency_answer": 1280},
    "reconciliation_max_rounds": 2,
    "token_budget_max": 256000, "token_budget_warn_ratio": 0.9,
    # Wall-clock budget per problem. The platform's hard limit is 20 min; the
    # reserve is what guarantees we still emit a real answer instead of being
    # killed mid-call, and fast_path_threshold is the room needed for one more
    # full LLM round trip before optional stages are skipped.
    #
    # The reserve must exceed one full in-flight call: a call already issued when the
    # soft deadline passes cannot be cancelled. The forced-budget stress run
    # (2026-07-29) overshot the soft deadline by 27-42s for exactly that reason.
    # Worst cases measured under four-way parallel load: reasoning 225s, Python 236s,
    # coordinator 98s. 300s absorbs the slowest observed call and still leaves the
    # coordinator room to emit an answer.
    "problem_time_budget_s": 1200,
    "time_reserve_s": 300,
    "time_fast_path_threshold_s": 300,
    # 评委建议 5：reserve 划出固定配额给语义仲裁与应急直答，杜绝
    # `arbiter=skipped(0.0s)`。含义：硬上限前剩余 ≥ 该值时，prefill 仲裁
    # （~10s）与应急直答（~30s）仍然放行；再低则只做确定性兜底。
    "arbiter_reserve_quota_s": 75,
    "emergency_reserve_quota_s": 90,
    # 2026-08-10 评委建议 2：压缩重试（prefill，~150s）与完整重试（~700s）
    # 分开定价。压缩重试按 reserve_margin 模式放行——软预算已尽也可执行，
    # 只要求硬上限前剩余 ≥ 压缩估时 + 本余量（余量覆盖仲裁 prefill、应急
    # 直答与确定性拼装；node_wrapper 的硬超时兜底最坏情况）。评委实测：按
    # 软预算定价时压缩重试 30 题 0 次放行，6 题以捞回残片出厂。
    "compressed_reserve_margin_s": 150,
    # 首轮推理的单次墙钟上限（断点续写三件套之一，移植自 math_agent）。8192 token
    # 首轮 @ ~50 tok/s ≈ 164s，550s 只在并发拥堵/模型变慢时才触发；一旦触发就
    # 就地转入压缩续写（复用首轮已算结论 + 答案前置 prefill），而不是让 node_wrapper
    # 的 1100s 掐死整条分支（math_agent 实测 idx 0/7/11/12/13 无压缩重试记录、落
    # emergency_direct_answer 错答）。
    "first_attempt_timeout_s": 550,
    # 完整二次推理/重生成的估时（秒）：首轮 8192 token 耗尽后，若时间充裕先做一次
    # 完整 8192 推理（复用首轮结论续写），而非直接 prefill 压缩硬写。8192 token
    # @ ~50 tok/s ≈ 164s，220s 覆盖拥堵余量。只作 can_afford 估时，实测成本仍以
    # last_attempt_cost 为准。
    "full_retry_estimate_s": 220,
    # ==================== 移植自第三名（VeritasMath）的升级配置 ====================
    # 全卷完成率引擎（PaperPacer）：平台 6h 全卷硬限。官方实证 V1 每题固定 1200s
    # 软预算导致 112 题只完成 16 题（14.29%）。按"剩余全卷时间÷剩余题数"动态
    # 收紧每题软预算，保证 6h 内 112 题全部产出答案（完成率 100% > 单题完美）。
    "paper_total_seconds": 21600,
    # PaperPacer 收紧软预算的下限余量（秒）：soft_total 一旦低于 reserve(300s)，
    # remaining() = soft_total - reserve - elapsed 开局即为负，第一轮
    # reasoning/python 会被 DeadlineExceeded 直接拒绝——"落后"退化成白卷。
    # 故收紧后的软预算下限 = reserve + 此余量，保证至少一轮核心推理能发起。
    "paper_min_work_s": 180,
    # 难度感知软预算：分类节点顺带输出难度，据此收紧 soft_total（只收紧不放宽）。
    # medium 840→1000：给计算题「首轮 164s + 完整二次推理 220s + Critic 120s +
    # coordinator」留足可选工作购买力（A1 评测 242 次截断、全卷仅用 3h40min，
    # medium 软预算剩 400-800s 被浪费）。easy 微调余量，hard 已是 1200 上限。
    "difficulty_soft_budgets": {"easy": 600, "medium": 1000, "hard": 1200},
    # 过程审计智能体：定稿前审计题面契约完整性 + 关键计算抽核。
    "enable_critic": True,
    "critic_reserve_margin_s": 60,
    # 确定性复算季后赛：两路冲突时代回复算，替代"只能二选一"的仲裁。
    # （季后赛代码执行的超时复用 node_timeouts.python_mcp_execute，无需单独配置。）
    "enable_playoff": True,
    # 判断题双向确认（Intern-S2 对"是否"题系统性偏"否"）。
    "enable_judge_confirm": True,
    # 计数题枚举对照守护（组合计数是 LLM 最弱项）。
    "enable_counting_guard": True,
    # 模结构守护：F_2/Z_m 语境注入"结构内聚合"条款 + 代码静态核查。
    "enable_modular_guard": True,
    # 答案形式对齐 + 证明结构补强。
    "enable_form_align": True,
    "enable_proof_deepener": True,
    "log_level": "INFO", "log_dir": "logs",
}

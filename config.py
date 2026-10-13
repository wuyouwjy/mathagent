CONFIG = {
    "model": "intern-s2",
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
    "node_timeouts": {"input": 5, "classifier": 200, "solving": 3600,
                      "reasoning_agent": 3600, "python_agent": 1100,
                      "python_mcp_execute": 60, "cross_validator": 15,
                      "reconciliation": 10, "semantic_arbiter": 150, "coordinator": 420,
                      "critic": 120, "playoff": 300},
    "classifier_confidence_threshold": 0.85,
    # 置信门控：最少资源高准确率。high(≥0.90)→fast 单路径；low(<0.70)→deep；
    # 中间→standard 双路验证。
    "confidence_gate": {"high": 0.90, "low": 0.70},
    # 深解领域（category 已被 classifier._resolve_category 归一到 skills/ 真实文件夹名）。
    # 注意：skills/ 无「数论」「组合数学」文件夹——这两类题经 _resolve_category 归一到
    # 「离散数学」（number_theory_floor 关键词）或 fallback「非基础及进阶课程」。旧值
    # ["数论","组合数学","高等代数","抽象代数"] 里的「数论/组合数学」是永不匹配的幽灵
    # 领域，致深思考门槛/难度判定对数论组合题失效（深思考全卷 0 触发的直接根因之一）。
    "deep_solver_domains": ["离散数学", "高等代数", "抽象代数"],
    # A3：证明题与深解领域（deep_solver_domains）首轮直接压缩 prefill（答案前置 +
    # 抑制私有 CoT），跳过"几乎必超 8192"的完整 CoT（A2 实测完整二次推理 80% 也
    # 截断）。压缩产出不完整时回退完整 CoT 兜底，不损失深度思考。设 false 可整体
    # 关闭此优化（回退到 A2 的「完整 CoT → 完整二次推理 → 压缩重试」三级路径）。
    "enable_deep_direct_compressed": True,
    # Zero-cost deterministic ranking is retained purely as a fallback for a
    # failed/unparseable LLM classification; it no longer narrows the LLM's
    # candidate list (all 18 domains go in one prefilled call).
    "classifier_top_k": 3,
    # 题库检索（RAG）：解题前用原题检索相似竞赛题，把 top-k 条题面+解答作为
    # few-shot 参考注入推理与验证两个子代理（差异化能力）。检索条数
    # 2：两条全部同时进两个子代理；更多条数会挤占 prompt 预算且引入更多近似题
    # 误导风险（反锚定说明见 utils/retrieval/reference_block.py）。
    "db_retrieval_top_k": 2,
    "computation_tolerance": 1e-6, "proof_confidence_threshold": 0.7,
    # S1 回滚：reasoning 0.8 / python 0.6 是照搬 ICMAnew-9911（99 分）的配置，但
    # ICMAnew 用的是 intern-s2-preview-397b（Preview 模型）+ objective_review /
    # card_authority 补偿，而本系统是 intern-s2（非 Preview），高温下采样随机性大、
    # 答案飘，S1 决赛 83→75 掉 8 分。恢复 G9 的 0.3/0.2 低温稳定基线。
    # coordinator 保持 0.4（成稿留表达余地）。
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
    # S1 回滚：coordinator 16384 / reconciliation 32768 与 temperature 0.8/0.6 一起
    # 引入，S1 决赛 75 分（truncated 69、token 177万，比 G9 的 61/166万略高）。为
    # 完全回到 G9 的 83 分已知基线，一并恢复 8192（分级熔断 + 断点续写兜底截断，
    # 不损失答案完整性）。
    "max_tokens": {"classifier": 96, "classifier_fallback": 8192,
                   "objective_reasoning": 8192,
                   "reasoning": 8192, "python": 8192,
                   "reasoning_compressed": 8192, "python_compressed": 8192,
                   "reconciliation": 8192,
                   "semantic_arbiter": 96, "semantic_arbiter_fallback": 8192,
                   "coordinator": 8192, "emergency_answer": 1280},
    "reconciliation_max_rounds": 2,
    "token_budget_max": 256000, "token_budget_warn_ratio": 0.9,
    # Wall-clock budget per problem. 官方约束明文只限「全卷 6h 封顶 + 并发 3」，
    # 单题并不限时（用户 2026-10-13 确认）——旧值 1200（20 分钟）是 V1「每题固定
    # 1200s 预算」的遗留自缚，它把「构造/博弈超难题」所需的 65536 深思考（~30-40min）
    # 物理拒之门外，正是「别人同模型 90+ 而我卡 82」的单题侧根因。放开到 3600（60min）
    # 后：软预算（easy 480 / medium 840 / hard 1200）不变、普通题不受影响，只有
    # reserve_margin 模式的深思考能超越软预算用满单题 60min。全卷仍由 PaperPacer 的
    # surplus 门槛 + 65536 配额计数器兜底，不会击穿 6h。
    #
    # The reserve must exceed one full in-flight call: a call already issued when the
    # soft deadline passes cannot be cancelled. The forced-budget stress run
    # (2026-07-29) overshot the soft deadline by 27-42s for exactly that reason.
    # Worst cases measured under four-way parallel load: reasoning 225s, Python 236s,
    # coordinator 98s. 300s absorbs the slowest observed call and still leaves the
    # coordinator room to emit an answer.
    "problem_time_budget_s": 3600,
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
    # 首轮推理的单次墙钟上限（断点续写三件套之一）。8192 token
    # 首轮 @ ~50 tok/s ≈ 164s，550s 只在并发拥堵/模型变慢时才触发；一旦触发就
    # 就地转入压缩续写（复用首轮已算结论 + 答案前置 prefill），而不是让 node_wrapper
    # 的 1100s 掐死整条分支（实测 idx 0/7/11/12/13 无压缩重试记录、落
    # emergency_direct_answer 错答）。
    "first_attempt_timeout_s": 550,
    # 完整二次推理/重生成的估时（秒）：首轮 8192 token 耗尽后，若时间充裕先做一次
    # 完整 8192 推理（复用首轮结论续写），而非直接 prefill 压缩硬写。8192 token
    # @ ~50 tok/s ≈ 164s，220s 覆盖拥堵余量。只作 can_afford 估时，实测成本仍以
    # last_attempt_cost 为准。
    "full_retry_estimate_s": 220,
    # 截断后续写的最大轮数（断点续写多轮升级）：首轮 token 耗尽后，只要全卷
    # surplus 充足就逐轮续写（第 1 轮完整二次推理，后续轮压缩续写），把已经
    # 多出来的墙钟继续换成准确率。放行只看全卷余量，不碰 100% 完成率底线。
    "max_continuation_rounds": 3,
    # ==================== 升级配置 ====================
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
    # A3：medium 1000→1200——A2 瓶颈已从「时间浪费」转为「8192 token 截断」
    # （truncated_count 328 / 41.7%，完整二次推理 80% 也截断）。给计算题的首轮
    # 完整 CoT + 完整二次推理 + 压缩续写三级熔断留足购买力，把剩余空余墙钟换成
    # 准确率。风险是更接近 6h 红线，由 PaperPacer 落后收紧 + can_afford_retry
    # 双重兜底。easy 微调余量，hard 已是 1200 上限不变。
    "difficulty_soft_budgets": {"easy": 600, "medium": 1200, "hard": 1200},
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
    # 裸判断词回填：判断+求值/求类型复合题（idx 38/90）answer 被压成"正确/错误"
    # 时，从 reasoning 结论文本回填具体结论（积分值/稳定性类型），杜绝
    # "最终答案：正确" 这种丢信息裸布尔输出。纯确定性零成本。
    "enable_bare_verdict_enrich": True,
    "enable_proof_deepener": True,
    # 选择性多采样投票（self-consistency）：对低置信题用全卷剩余 surplus 做
    # N=3 独立采样取多数票。
    #
    # 2026-10-11 实测（20 题子集）：触发 13 题、覆盖 2 次、改对 0 改错 0，净收益 0，
    # 且暴露两个致命问题，故回滚 False：
    #   1. invoke 仍吃满软预算（idx 4 实测 reasoning 230s + python 551s + coordinator
    #      258s ≈ 1011s），20min 硬限只剩 ~188s，采样需 240s+，3 次采样只发成功 1 次
    #      （「Consistency sample failed: -112s left」）——低温回滚只让 reasoning 快，
    #      没让 python/coordinator 快，「采样空间重新出现」的假设不成立。
    #   2. 低温 0.3 下采样答案高度一致（idx 2 三次采样全同），形不成「不同于原答案的
    #      共识」；唯一 2 次覆盖里 idx 12 还是「留数 -1/8」等价表述误覆盖（_answers_equivalent
    #      没识别 sympy 等价）。
    # 结论：直接开 self-consistency 不 work——采样「发不出」且「无多样性」。真正「用满
    # 时间换正确率」需把采样前置（采样替代 python+仲裁+coordinator 的 ~800s 开销），
    # 而非 invoke 后追加，见 memory same-model-90-gap-is-time。
    "enable_consistency_vote": False,
    # 深度重解（deep_rethink，**前置**）：reasoning 首轮成功后用「换方法 + 检查
    # 漏洞」单次重解（注入首轮答案、低温 0.3），试图靠「定向换方法」而非「采样
    # 多样性」纠正首轮漏解。
    #
    # 2026-10-11 实测（6 错题 idx 3/6/7/9/10/12 子集）：**同样失败，已回滚 False**。
    #   - 触发 4 次（idx 3/6/9/10，deep_rethink 每次 280-362s），其中 idx 6/9 覆盖了
    #     首轮答案（answer_source=deep_rethink），但覆盖后仍 wrong（idx 6 还把 baseline
    #     实际正确的「=1」覆盖成「0」，净负；idx 9 覆盖成另一个错答案 0，标准 2）。
    #   - idx 3/10 触发但「收敛零覆盖」（_answers_equivalent 判定换方法答案与首轮等价）。
    #   - 判分「改对」的 idx 7/10 是**首轮随机性**（idx 7 深度重解根本没触发、idx 10
    #     触发但收敛没覆盖），与深度重解无关。
    #   - 副作用：280-362s 的深度重解挤占单题软预算，导致 coordinator 被跳过 3 次
    #     （"Coordinator skipped ... 244/134/91s left"）。
    # 结论：与 self-consistency 多采样同根——intern-s2 非 Preview 对同一题的重复求解
    # （无论独立采样还是换方法复核）都收敛到同一答案，「第 2 次 reasoning 边际≈0」
    # （见 memory proof-retry-convergence / same-model-90-gap-is-time）。多出来的
    # 时间产出的答案没有新信息，「用满 6h 换正确率」不能靠重复求解。
    "enable_deep_rethink": False,
    # ==================== 深思考升级（deep_think，实测真杠杆：16384 首调 + 截断续写） ====================
    # intern-s2 默认 thinking_mode=True（深思考始终开启），「思考深度」不是由 max_tokens
    # 开关、而是由 max_tokens 决定「是否截断」：8192 时 CoT 写在 content 里很早被截断
    # （答不出）；16384 时模型已推出正确答案、只是没写出 \boxed 就被 length 截断（idx 9
    # 推出 "exactly 2" 差最后一步）；32768 时返回 reasoning_content + 完整 content（stop
    # 答对）。32768 一次答完每题 ~15-20min、全卷 6h 耗尽（78 分掉分根因）。因此改为
    # 「16384 首调（~5min 想清楚）+ 截断续写（thinking_mode=False + 2048 直接写 \boxed，
    # ~30s）」——与第三名框架同款策略，深思考每题 ~6min 而非 20min，全卷能覆盖更多错题。
    # 深思考仍会拖垮「对题」（idx 8/16/18 陷入逐一验证/博弈分析），故保持「浅思考优先
    # → 领域选择性升级深思考」；深思考截断续写失败才回退浅思考答案。
    # 见 memory same-model-90-gap-is-time。
    "enable_deep_think": True,
    # 触发面：True=调用点 1（浅思考成功后升级）只对 deep_solver_domains 深思考，防
    # 「压缩首答已答对的对题」被深思考 stop 答错覆盖（防掉回 75）。调用点 2（浅思考
    # 失败救题）已用 allow_all_domains=True 放开到全部 18 领域——S3 全卷 2h46min 交卷、
    # 剩 3h 冗余没花的直接根因就是这道门槛把「救错题」的深思考限制在 3/18 领域。
    "deep_think_domains_only": True,
    # 深思考首调 max_tokens：32768 让 deep-thinking 跑满并 stop 完整（idx 13 坐实：
    # baseline 答 3 错 → 深思考 stop 完整答 2，生成 812s）。16384 必 length 截断、
    # 截断续写不可靠（只采信 stop 完整 → 16384 对难题净收益归零），故用 32768 换
    # 「stop 完整」而非「快」。成本由「浅思考失败才触发」的选择性 + 中途超时保护兜住。
    "deep_think_max_tokens": 32768,
    # 深思考首调估时，只作放行/定价估时。实测 ~26 tok/s（非注释旧值 50 tok/s）：
    # idx 13 深思考 812s stop 完整、idx 16 625s、idx 14 674s 截断，取 650 乐观估时；
    # reserve_margin 门槛 remaining_hard ≥ estimate+150，压缩首答失败后必然放行。
    # 全卷跑时它还充当 PaperPacer surplus 门槛（surplus ≥ 650 才升级深思考），单题
    # 验证场景才临时置 0。
    "deep_think_estimate_s": 650,
    # 深思考单次墙钟上限：socket 已放宽到 1100s 容纳 stop 完整的深思考（idx 13 ~812s），
    # 但超难题 CoT 用满 32768 会 >1150s 拖死整个 reasoning 节点（浅思考答案也丢，idx 19
    # 实测）。900s 就地截断：中等偏难题（812s）能 stop 完整、超难题超时回退浅思考。
    "deep_think_timeout_s": 900,
    # ==================== 65536 深思考分级（救「32768 也截断」的构造/博弈超难题） ====================
    # 单题不限时（官方只限全卷 6h）后，「32768 也 length 截断」的超难构造题（idx 3 三角形
    # 构造 / idx 12 子集和）可升级 65536 从头深思考——memory same-model-90-gap-is-time 实测
    # 32768 截断 → 65536 stop 答对（idx 3→2024、idx 12→48）。这是「别人同模型 99 分」的
    # 超难题侧差距：别人没有 20min 单题自缚，超难题能花 30-40min 深思考。
    # 触发只在「浅思考失败（调用点 2）+ 32768 截断」后，且受全卷配额（quota）兜底防超时。
    "deep_think_max_tokens_extreme": 65536,
    # 65536 单次墙钟上限：idx 3/12 的 CoT 在 32768~65536 之间（~4-5 万 token @ ~26 tok/s
    # ≈ 26-32min），2400s（40min）留足余量；超时回退 32768 截断续写/浅思考。
    "deep_think_extreme_timeout_s": 2400,
    # 65536 估时（reserve_margin 定价 + PaperPacer surplus 门槛）：1800s（30min）。surplus
    # ≥ 1800 才升级，天然限制全卷最多 2-3 次（每次花 ~26min，6h 内用不完的 surplus 才够）。
    "deep_think_extreme_estimate_s": 1800,
    # 65536 全卷配额：无论 surplus 多充裕，全卷最多触发 N 次（防并发下多道超难题同时 65536
    # 击穿 6h）。2 次 × ~26min ≈ 52min，叠加 S4 扩领域后全卷仍留足余量。
    "deep_think_extreme_quota": 2,
    # reserve_margin 模式：深思考允许动用 reserve（软预算已尽也放行），仅要求单题
    # 硬上限前仍容得下本次调用 + 此余量（给下游 python/coordinator 留硬时限）。
    "deep_think_reserve_margin_s": 150,
    # 深思考截断续写：首调 finish=length 时，thinking_mode=False + 小 token 让模型复用
    # 首调完整推导直接写 \boxed 答案（~30s）。验证 idx 9 @16384 截断 → 续写答出 2。
    "deep_think_continuation_max_tokens": 2048,
    # 续写温度 0.0（确定性输出：答案已想清楚，只需写出，不需要探索性采样）。
    "deep_think_continuation_temperature": 0.0,
    # ==================== 采样前置（self-consistency 前置版，实测回滚 False） ====================
    # 与上面 invoke 后追加的 consistency_vote 不同：采样前置在 reasoning 首轮成功后
    # 立即采样（此刻软预算还剩 ~670s，采样发得出），用 N 次高温采样取多数票纠正首轮
    # 低温 0.3 的孤立错误。
    #
    # 2026-10-11 实测（20 题子集）：采样前置**真的触发**了（idx 0/2/4/5 各采样 2 次，
    # 每次完整 CoT ~285s、共 ~570s），但 answer_source 全部保持首轮
    # （parsed_sections/quick_conclusion），**无一覆盖**——采样答案与首轮高度一致
    # （intern-s2 非 Preview 在 0.7 温度下多样性不足），形不成「不同于首轮的共识」。
    # 净效果：每道 computation 题多花 ~570s（idx 0 从 baseline ~290s → 630s），答案
    # 零变化，改对 0 改错 0。与 consistency_vote 的实测结论完全一致：self-consistency
    # 无论前置还是后置，在本模型上都不 work（采样「发得出」但没有「多样性」）。
    #
    # 结论：回滚 False。真正「用满 6h 换正确率」不能靠多采样（模型采样多样性不足），
    # 见 memory same-model-90-gap-is-time 的更新。
    "enable_sample_first": False,
    # 采样次数（多数票：≥2 采样一致且不同于首轮才覆盖首轮）。随 enable_sample_first 回滚。
    "sample_first_n": 2,
    # 采样温度：高于首轮 0.3。随 enable_sample_first 回滚（0.7 下仍无多样性）。
    "sample_first_temperature": 0.7,
    # Python 完整生成次数上限（采样前置的配套，已随之一并回滚删除，恢复默认 2 次）：
    # 采样前置失败后，无理由再无条件砍 python 重试（只降质量无补偿）。
    "log_level": "INFO", "log_dir": "logs",
}

<p align="center">
  <h1 align="center">🧮 Math-Agent-System A9</h1>
  <p align="center">基于 <b>Intern-S 系列大模型</b> 的 LangGraph 多智能体数学推理系统 — 2026 挑战杯·书生赛道</p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python">
    <img src="https://img.shields.io/badge/LLM-Intern--S-orange" alt="Intern-S">
    <img src="https://img.shields.io/badge/version-A9-purple" alt="A9">
    <img src="https://img.shields.io/badge/framework-LangGraph-green" alt="LangGraph">
    <img src="https://img.shields.io/badge/score-target-75%2B-brightgreen" alt="Target">
  </p>
</p>

---

## 📖 简介

**Math-Agent-System A9** 是为 2026 年度中国青年科技创新"揭榜挂帅"擂台赛·书生赛道设计的数学推理智能体。

T3 版本基于 ICMAnew-main 架构（50 分 / 56 correct / 112 题）完成了从 T2 svragent 到 **LangGraph 多智能体图编排**的重构。T4 在 T3 基础上，参照 VeritasMath 前三名架构补齐了四块**正确性与完成率**短板：

1. **全卷完成率引擎（PaperPacer）**：按"剩余全卷时间 ÷ 剩余题数"动态收紧每题软预算，保证 6h 内 112 题全部产出答案（消除"超时未答"整题 0 分）；
2. **过程审计门（Critic）+ 确定性复算季后赛（Playoff）**：定稿前审计题面契约完整性，冲突时用"候选代回复算"的确定性证据裁决，而非只能二选一；
3. **扇出门控 + 确定性守卫（Guard 组）**：置信门控按资源档位扇出（实算填空升级双路），计数题/模结构/判断题/证明题/答案形式各有零成本确定性守卫兜底；
4. **平台防线（response_normalize + sys.path 自举）**：响应归一化 + chat 签名三级降级探测 + 接口签名兼容，杜绝平台加载/调用形态变化导致的整批 0 分。

A1 在 T4 基础上，融合两份高分作品（ICMAnew 66.96 分 / math_agent 69 分）的差异化能力，补齐两块**正确率**短板（A1 官方评测 64.29 分：72 correct / 40 incorrect，112 题全完成）：

5. **RAG 题库检索（参照 ICMAnew 66.96 分）**：解题前用原题检索相似竞赛题，把 top-k 条题面+解答作为 few-shot 参考注入推理与验证两个子代理；TF-IDF 轻量检索（char_wb n-gram 2-5）替代 chroma+embedding，评测环境可复现；配套**反锚定机制**防止近似题结论误迁移（近似题结论不可直接照抄，数值参数差异需显式对比）；
6. **断点续写 / 答案前置（参照 math_agent 69 分）**：压缩重试用"结论速览"prefill 让结论先落盘（答案前置，截断也不丢答案）；复用首轮已算结论作为续写线索（断点续写）；首轮加 550s 墙钟上限，触发即就地转入压缩续写而非被掐死。

A2 针对 A1 评测暴露的「时间浪费」瓶颈做定向优化——A1 全卷实际只跑 **3h40min**（空余 2h20min），却有 **242 次请求被 max_tokens=8192 截断**（679 请求的 35.6%）。medium/hard 难题是「首轮推理 ~164s 被截断 → 150s prefill 压缩重试（抑制私有思考，硬写）→ 交卷」，软预算剩 400-800s 被浪费。A2 把空余墙钟转化为「截断难题的第二次完整思考」：

7. **完整二次推理（full reasoning retry）**：把「首轮截断 → 压缩重试」两级升级为「首轮截断 → **完整二次推理**（复用首轮结论断点续写、保留私有思考）→ 仍失败才压缩重试」三级；reasoning 与 python 两侧对称实现，Python 侧用 `full_retried` 标志保证完整重生成只做一次；
8. **难度软预算上调**：medium 840→1000（给计算题「首轮 164s + 完整二次推理 220s + Critic + coordinator」留足购买力），easy 480→600 微调余量。完整二次推理只在 `can_afford_retry` 放行时触发，时间不足自动退回压缩重试，PaperPacer 落后收紧仍是最后防线，不会击穿 6h。

A3 针对 A2 评测暴露的「8192 token 截断」瓶颈做定向优化——A2 官方评测 **67.86 分**（76 correct），瓶颈已从「时间浪费」转移到「8192 token 截断」：`truncated_count = 328`（占 41.7%），完整二次推理 80% 也截断。深解领域（数论/组合/高代/抽代）与证明题的完整 CoT 几乎必超 8192，首轮完整 CoT + 完整二次推理（~384s）是"注定截断"的浪费。A3 在 8192 token 内更高效地思考，并把剩余空余墙钟继续换成准确率：

9. **紧凑输出（先锁定结论、少铺陈）**：推理提示追加"紧凑输出要求"——先在心里锁定最终结论再倒推最简推导链，"问题分析"≤3 行、"详细步骤"一行公式一行结论，把额度留给"最终答案"，减少"耗尽前没写出结论"的截断；
10. **深解题首轮直接压缩 prefill**：证明题与深解领域（`deep_solver_domains`）首轮直接走压缩 prefill（答案前置 + 抑制私有 CoT，~150s），跳过"几乎必超 8192"的完整 CoT + 完整二次推理（~384s）；压缩产出不完整则回退完整 CoT 兜底，不损失深度思考（`enable_deep_direct_compressed` 可整体关闭）；
11. **medium 软预算 1000→1200**：给计算题三级熔断（首轮 → 完整二次推理 → 压缩续写）留足购买力，把剩余空余墙钟继续换成准确率（风险是更接近 6h，由 PaperPacer 落后收紧 + `can_afford_retry` 双重兜底）；
12. **Python 侧深解领域对称压缩**：`python_exec` 对深解领域（数论/组合/高代/抽代；A9 移除运筹学）首轮直接压缩重生成（代码前置 prefill，~200s），跳过"几乎必超 8192"的完整代码生成，与推理分支第 10 点对称；产出有效代码并执行出答案则直接返回，否则回退完整生成兜底；
13. **深解题压缩后二次验证**：压缩 prefill 成功但低置信（抑制了私有思考）时，时间充裕（`can_afford_retry` 放行）则复用压缩答案续写做一次完整 CoT 二次确认（保留私有思考），把省下的时间换成置信度；
14. **medium 计算题答案前置**：medium 计算题（computation 且非深解领域）先锁定数值再先写 "## 最终答案" 后倒推步骤——步骤是佐证而非重新探索，进一步降低"耗尽前没写出结论"的截断；
15. **中间等式线索增强**：`_extract_key_equations` 从首轮残片提取"已算出的关键等式"（右端含数字）作为续写线索，让二次推理/压缩重试带精确中间值续写。

A7 官方评测 **68.75 分**（77/112），比 A4 基线（73.21，82/112）倒退 5 题——A7 的「提上限 + 减调用」两条假设双双证伪：① `max_tokens` 提 12288 被评测环境**静默 cap 8192**（token 反推铁证：214 次截断 × 12288 ≈ 263 万 > 总 completion 221.7 万，截断实际发生在 ~8192），截断率 39.3% 与 A4 的 40% 几乎无差；② 关闭 critic + modular_guard 把 request 890→544，却换来 82→77 的 5 题损失。A8 先**回退 A7 恢复 A4 基线**，再针对离线诊断定位的「计算题真错重灾区」（运筹学 3/3 全错、组合 3 错、AIME 计算题 6 错）做架构层面的「计算题工具主解」：

16. **回退 max_tokens 8192 + 恢复 critic / modular_guard**：reasoning / python / compressed 四项上限 12288→8192（环境 cap 8192，提上限是自欺）；`enable_critic` / `enable_modular_guard` 恢复 True——这两个不是"低性价比 verify"，而是交叉验证/仲裁都没有的「契约完整性审计」+「F₂/Z_m 模结构确定性防线」，关掉实测 -5 题；
17. **计算题工具主解（去锚定，`python_independent_solve`）**：Python 分支不再注入 reasoning 候选答案，从题目独立生成求解代码。此前 Python 拿到 reasoning 的 `candidate_answer` 后被「核验候选」锚定——围绕候选复现而非从零求解；而 cross_validator 在 computation + Python 成功时本就优先采纳 Python 答案（第一名实证工具执行 67.25% vs 直接推理 34.50%），去锚定释放工具执行的高正确率，直击计算题真错重灾区；
18. **提交包去冗余**（沿用 A7）：删除本地调试脚手架（`main.py` / `llm_client.py`）、离线构建脚本（`scripts/`）、样例数据与测试（`sample/`、`test/`），提交包只保留竞赛运行时必需文件 + 文档，零答案痕迹。
19. **扩大深解领域压缩覆盖到运筹学**：`deep_solver_domains` 加入「运筹学」——运筹学题（规划/调度/运输/网络流）的正确解靠 Python 建模+算法求解，reasoning 心算基本无用、其完整 CoT 也容易截断；加入后 reasoning/Python 首轮直接压缩 prefill，省时间给 Python 生成正确求解代码（直击离线诊断的运筹学 3/3 全错）。

A9 本版为「回退 A8 负收益 + 两个定向优化」（官方评测待跑）。A8 官方 **67.86 分**（76/112）比 A4 基线（82/112）净 **−6 题**，两条假设双双证伪：① 第一名「工具执行 67% vs 心算 34%」的数据已被验证为错误，去锚定让 Python 在 reasoning 算对的题上也独立重算、经 cross_validator 优先采纳反而带错；② 运筹学加入 `deep_solver_domains` 首轮压缩抑制 CoT，Python 代码生成质量下降、3 题仍全错。A9 先回退这两条，再做两个**严格非负、零额外 LLM 调用**的定向优化（直击离线诊断的「计算题真错重灾区」）：

20. **回退 A8 负收益**：`python_independent_solve` True→False（Python 恢复「注入候选核验」的验证器定位，A8 去锚定负收益 −6 题）；`deep_solver_domains` 移除「运筹学」（首轮压缩只保留数论/组合/高代/抽代）。回到 A4 基线（82/112）；
21. **条件求解器框架（`enable_python_solver_fallback`）**：仅当推理侧候选为空（reasoning 截断/未算出答案）时，Python 分支改用独立求解器 prompt（`PYTHON_SOLVER_PROMPT`，去掉「验证状态/验证证据/待核验候选」契约），聚焦「直接算出答案」而非「验证不存在的候选」。与去锚定的本质区别：去锚定「有候选也独立算」覆盖了正确推理（A8 负收益根因），本开关只在「无候选」时独立求解——无正确推理可被覆盖，Python 算对即净赚、算错也不损失（推理侧本就无答案，下游走兜底）；
22. **运筹学确定性求解守卫（`enable_operations_research_guard`）**：运筹学 3/3 全错是「缺对口求解范式」而非「偶尔算错」。仿照 modular_guard/counting_guard 的「领域守卫」模式，命中运筹学题（分类器 category 或题面关键词）时向 Python 注入 scipy.optimize.linprog/minimize/milp 求解器建模模板，生成后静态核查代码必须真调用求解器或枚举穷举，纯手算闭式则打回修复。

### A2 vs A1 核心增量

| 维度 | A1（实测 64.29 分） | A2（实测 67.86 分） |
|---|---|---|
| **截断难题兜底** | 首轮截断 → prefill 压缩重试（抑制私有思考，硬写） | **三级兜底**：首轮截断 → 完整二次推理（复用结论续写、保留私有思考）→ 仍失败才压缩重试 |
| **Python 侧截断/失败** | 直接落压缩重生成 | **完整重生成**：先完整重生成一次（`full_retried` 只触发一次），失败再压缩 |
| **medium 软预算** | 840s（截断后剩 400-800s 浪费） | **1000s**：给「首轮 164s + 二次推理 220s + Critic + coordinator」留足购买力 |
| **时间利用** | 全卷 3h40min，空余 2h20min | 把空余墙钟转化为第二次完整思考（预计 ~5.2h，仍 < 6h 硬限） |

### A3 vs A2 核心增量

| 维度 | A2（实测 67.86 分） | A3（目标 70 分+） |
|---|---|---|
| **截断根因** | 完整 CoT（首轮/二次）私有 reasoning_content 吃满 8192（328 次截断 / 41.7%） | **紧凑输出**：先锁定结论、少铺陈，额度留给可见章节 |
| **深解题首轮** | 首轮完整 CoT（~164s 必截断）→ 完整二次推理（80% 也截断）→ 压缩重试 | **首轮直接压缩 prefill**（~150s），省下"注定截断"的完整 CoT + 二次推理（~384s），不完整回退完整 CoT 兜底 |
| **medium 软预算** | 1000s | **1200s**：三级熔断留足购买力，把剩余空余墙钟换成准确率 |
| **Python 侧对称压缩** | 深解领域完整代码生成（几乎必超 8192） | **首轮直接压缩重生成**（代码前置 prefill，~200s），与推理分支对称，产出有效则返回 |
| **压缩后二次验证** | 压缩 prefill 成功即交卷（抑制私有思考、低置信） | **时间充裕时完整 CoT 二次确认**：复用压缩答案续写、保留私有思考，把省下的时间换成置信度 |
| **计算题答案前置** | 步骤在前、结论在后（易耗尽前没写出结论） | **medium 计算题先写 "## 最终答案" 再倒推步骤**：先锁数值，步骤是佐证不是重新探索 |
| **续写线索** | 复用首轮结论句 | **补充中间等式**：`_extract_key_equations` 提取"已算出的关键等式"（右端含数字）带精确中间值续写 |

### A3 图架构总览

```
solve(problem, metadata)
  └── MathAgentGraph.run(initial_state)          # PaperPacer 接入 + 难度软预算
       ├── input_node: 提取 idx，问题锚定
       ├── classifier_node: 18 领域 LLM 预填充分类（~1s）+ 难度画像
       ├── database_retrieval_node: TF-IDF 题库检索 → top-k 相似题 + 反锚定 reference_block
       ├── solving_subgraph: 置信门控扇出（实算填空升级双路；纯概念客观题单路径）
       │    ├── reasoning_agent: 加载领域 skill → 四章节结构化输出（深解题首轮压缩 prefill；截断→完整二次推理→压缩重试三级兜底）
       │    ├── python_agent: 候选核验生成 SymPy 验证代码（候选空则独立求解）→ 执行 → 答案（失败/截断→完整重生成→压缩三级兜底）
       │    └── cross_validator: 两路答案匹配 → 路由决策
       │         ├── match → critic
       │         ├── mismatch / contradict → playoff（确定性复算裁决）
       │         ├── mismatch + retry → reconciliation → solving
       │         └── uncertain → semantic_arbiter
       ├── playoff_node (条件): 冲突候选代回复算 → A/B/BOTH 锁定 / NEITHER 换方法重算
       ├── reconciliation_node (条件): 生成定向重试提示
       ├── semantic_arbiter_node (条件): prefill 仲裁选择最佳候选
       ├── critic_node: 定稿前过程审计（契约完整性 + 计算抽核 + 推导矛盾自检）
       └── coordinator_node: 格式化 final_response
```

---

## 🏆 比赛接口

```python
from user_agent import ReasoningAgent

# 平台初始化（不可修改此调用格式）
agent = ReasoningAgent(client=official_client)

# 求解单题
result = agent.solve(
    problem="设$\\mathbb{F}_{81}$为$81$元的有限域...",
    metadata={"idx": 0}
)

# 返回格式
# {
#   "final_response": "最终答案：<答案>",
#   "trace": [
#     {"step": "classification", "category": "抽象代数", ...},
#     {"step": "reasoning", "answer": "<答案>", "steps_count": 3, ...},
#     {"step": "python_verification", "success": true, "answer": "<答案>", ...},
#     {"step": "validation", "status": "match", "validated_answer": "<答案>", ...},
#     {"step": "coordination", "response_length": 8, ...}
#   ]
# }
```

接口防御（A3）：`solve` 兼容 `metadata=None` / 位置参数 / 额外参数；额外暴露
`agent(problem)` 与 `agent.run(problem)` 别名；文件被 importlib 按路径加载时
自动 `sys.path` 自举，任何加载形态都能找到 `graph`/`utils` 包。

---

## 📂 项目结构

```
Math-Agent-System/
├── user_agent.py              # 【必填】ReasoningAgent 入口（平台调用接口 + 防线）
├── config.py                  # 全局配置（模型/超时/温度/token 预算/墙钟预算/PaperPacer）
├── requirements.txt           # 项目依赖清单
│
├── data/                      # 题库检索语料（离线构建，评测可复现）
│   └── retrieval_corpus.json  # 相似题面+解答语料库（TF-IDF 检索源）
│
├── graph/                     # LangGraph 图编排（主图 + 子图 + 节点 + 状态）
│   ├── main_graph.py          # 主图构建 + MathAgentGraph 运行器（PaperPacer 接入）
│   ├── solving_subgraph.py    # solving 子图：reasoning + python 并行扇出
│   ├── state.py               # MathAgentState TypedDict（全图共享状态）
│   └── nodes/                 # 图节点（每个节点一个文件）
│       ├── input.py           # 提取 idx，问题锚定
│       ├── classifier.py      # 18 领域 LLM 预填充分类 + 难度画像 + 确定性回退
│       ├── database_retrieval.py # RAG 题库检索：TF-IDF 相似题 + 反锚定 reference_block
│       ├── reasoning.py       # LLM 四章节结构化推理 + 深解题首轮压缩 prefill + 截断三级兜底（完整二次推理→压缩重试）+ 断点续写/答案前置
│       ├── python_exec.py     # SymPy 求解/验证代码生成（候选空则独立求解）+ 子进程安全执行 + 失败/截断完整重生成
│       ├── cross_validator.py # 双路答案交叉验证 + 路由决策（含 playoff 路由）
│       ├── playoff.py         # 确定性复算季后赛：冲突候选代回复算裁决
│       ├── critic.py          # 过程审计门：契约完整性 + 计算抽核 + 推导矛盾自检
│       ├── reconciliation.py  # 冲突时生成重试提示 + 轮次控制
│       ├── semantic_arbiter.py# prefill 仲裁：从既有候选中选择完整答案
│       └── coordinator.py     # 汇总上下文，格式化 final_response
│
├── skills/                    # 18 个数学领域 skill 文档 + 验证代码片段
│   ├── 数学分析/ 高等代数/ 抽象代数/ 概率论/ ...
│   └── 每个领域：skill.md + 验证示例.md
│
└── utils/                     # 工具库（按功能分包）
    ├── deps.py                # LangGraph configurable 依赖注入
    ├── error_handler.py       # 节点异常包装 + fallback 状态
    ├── logger.py              # 日志
    ├── answer/                # 答案管线：抽取→匹配→契约→格式化→洁净度→结论捞回
    │   ├── extractor.py, matcher.py, contract.py
    │   ├── formatter.py, cleanliness.py, structured.py
    │   ├── cot_stripper.py    # CoT 前缀去除 + 占位答案检测
    │   └── conclusion_salvage.py # 无章节输出时从散文中捞回结论句
    ├── verify/                # 验证/守卫/审计：路由 + 确定性守卫 + 证据解析
    │   ├── verify_router.py   # 验证路由：实算填空升级双路（纯概念填空除外）
    │   ├── confidence_gate.py # 置信门控：fast/standard/deep 资源档位
    │   ├── counting_guard.py  # 计数题枚举对照守护（闭式强制枚举核查）
    │   ├── modular_guard.py   # 模结构守护（F_2/Z_m 结构内聚合核查）
    │   ├── critic_audit.py    # Critic 判定解析 + 契约合并 + 修复提示
    │   ├── derivation_conflict.py # 推导矛盾自检（纯正则零 API）
    │   ├── form_align.py      # 答案形式对齐（单值/区间/判断/枚举形态）
    │   ├── proof_deepener.py  # 证明结构补强（三段式模板 + 结论标记）
    │   ├── judge_confirm.py   # 判断题双向确认（是/否偏向纠偏）
    │   ├── reconciliation_policy.py # 调解轮次策略
    │   ├── evidence.py        # Python 输出证据解析
    │   ├── authenticity.py    # 反伪造检查
    │   └── stdout_miner.py    # stdout 答案挖掘
    ├── budget/                # 资源预算：token + 墙钟 + 重试可行性 + 超时
    │   ├── token.py, time.py, affordability.py, timeout.py
    │   └── paper_pacer.py     # 全卷完成率引擎（题间预算池 + 动态软预算帽）
    ├── llm/                   # LLM 交互：重试退避 + prefill + 响应归一化 + Prompt 模板
    │   ├── retry.py, prefill.py, response_normalize.py, templates.py
    │   └── client_tuning.py   # 尽力提升平台 client socket 超时
    ├── skills_util/           # 领域技能：文档加载 + 主题摘取 + TF-IDF 索引
    │   ├── loader.py, excerpt.py, embedding.py
    ├── retrieval/             # 题库检索（RAG）：TF-IDF 检索 + 反锚定 reference_block
    │   ├── tfidf_client.py    # char_wb n-gram 2-5 轻量检索
    │   └── reference_block.py # 反锚定提示块 + 参数差异对比
    ├── problem/               # 题目分析：题型画像 + SHA256 锚定
    │   ├── profile.py, anchor.py
    └── executor/              # Python 代码执行：子进程隔离 + FastMCP 服务
        ├── client.py, server.py
```

---

## 🚀 本地调试

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥

```bash
export INTERN_API_KEY="sk-xxxx你的密钥xxxx"
export INTERN_MODEL="intern-s2-preview"  # 可选，默认 intern-s2-preview-397b
```

### 3. 导入自检

```bash
python -c "from user_agent import ReasoningAgent; print('import OK')"
```

### 4. 最小 solve 冒烟

```python
from user_agent import ReasoningAgent

class MockClient:
    def chat(self, *a, **k):
        return "## 结论速览\n\\boxed{6}\n\n## 最终答案\n6"

agent = ReasoningAgent(client=MockClient())
r = agent.solve("求 1+1", {"idx": 0})
assert isinstance(r, dict) and r["final_response"].strip()
```

注：提交包已删除本地批量 Runner（`main.py`）与样例数据（`sample/`），本地完整跑题请通过平台评测。

---

## 🔧 核心特性详解

### 1. 18 领域 skill 文档系统

每个学科目录包含：
- `<领域>skill.md`：领域概念、典型题型、解题流程和注意事项
- `<领域>验证示例.md`：按知识模块组织的验证提示和 SymPy 代码片段

分类采用 **prefill 调用**（~1s/12 tokens），覆盖全部 18 个领域。skill 文档按题目主题选取相关模块（而非简单截断头部），验证提示同理。

### 2. 并行双路验证

- **LLM 推理分支**：加载领域 skill → 四章节结构化输出（问题分析/详细解题步骤/最终答案/关键验证点）
- **Python/SymPy 分支**：注入 reasoning 候选做核验（候选为空时切换独立求解器框架，A9）——从题目生成 SymPy 求解/验证代码 → 子进程隔离执行 → 抽取答案

两路并行执行，交叉验证节点汇总结果，按 match/mismatch/uncertain 路由。
**证明题例外**：抽象证明（同构/整环等）无法数值验证，Python 分支 answer 恒为空却并行耗数百秒，故证明题直接走推理单路径（零准确率损失，省下软预算给 coordinator 成稿）。此外证明题 critic 判缺项后**不再重试完整 reasoning**——实测第 2 次 reasoning 仍被判缺项、其产出从未被采纳（`validated_answer` 保持第 1 次值，最终靠 `coordinator_llm` 独立成稿才正确），故直接成稿，省一次完整推理（~280-527s），几乎不损正确率。

### 3. 分级熔断、完整二次推理与压缩重试（三级兜底）

`intern-s2-preview-397b` 的 CoT（私有 `reasoning_content`）与可见 `content` 都计入
`max_tokens`。难题可能耗完整份额度却没产出任何章节。A2 把「截断 → 压缩重试」两级升级为三级：
- 首轮 `max_tokens=8192`（约 160s）——原 24576 首轮在奥赛题上几乎总被私有推理耗尽，成功解极少，降上限换来的是重试窗口；A8 从 12288 回退 8192（环境 cap 8192，提上限无效）
- **Token 耗尽时先做完整二次推理**（`reasoning_full_retry`）：`can_afford_retry` 放行且时间充裕时，用普通 `chat_with_retry`（保留私有思考）复用首轮 `_extract_clues` 结论断点续写，先给"## 最终答案"明确结论再补步骤；Python 侧对称地做一次完整重生成（`full_retried` 只触发一次）
- 完整二次推理仍失败/截断才转入 **prefill 压缩重试**（`max_tokens=8192`）：assistant 种子抑制私有推理，全部额度用于可见章节
- 压缩按 **reserve_margin 定价**：软预算耗尽后仍可动用 hard reserve
- 偶发地，私有 CoT 会**泄到可见 `content`**（同题两次跑一次正常一次白卷）：reasoning 无四章节 → 捞回层可能误捞 "Okay, I will..." 这类英文推理引导句当答案（其常混入 `$n_5=6$` 等式，躲过「含等式即放行」豁免）。`cleanliness.py` 在洁净度门最前拒收句首英文 CoT 引导词，避免英文残片出厂

### 4. 全卷完成率引擎（PaperPacer）

官方约束：112 题、平台并发 3、智能体总运行 6h 封顶，超出后未答题不计分。
PaperPacer 用**题间预算池**动态计算每题软预算帽：已用全卷时间 ÷ 剩余题数超速时收紧
（仍 ≥ 120s 保底），健康时给足理想预算。与难度画像（easy 600 / medium 1200 / hard 1200）
取 min 作为该题软预算。只收紧软预算（可选阶段购买力），不动 1200s 平台硬限。

### 5. 过程审计门（Critic）

> ⚠️ A7 曾关闭 `enable_critic`（对冲提上限的时间增量），实测关掉 -5 题；A8 恢复开启。

定稿前最后一道质量门，两级审计：
1. **确定性契约**（`answer_contract`，零成本）+ **LLM 契约审计**（prefill，~15s）合并判定；
2. **推导矛盾自检**（纯正则零 API）：同一变量出现两个不同数值即判 calc_error。

审计不制造答案，只产生定向修复提示——缺口明确且预算可负担时回调解做定点补算，
否则带缺口标记进 coordinator（formatter 仍可回捞）。最多触发 1 次修复，杜绝死循环。

### 6. 确定性复算季后赛（Playoff）

两路答案冲突时，不再只能"整轮重跑"或"二选一仲裁"。Playoff 不解原题，只做
**候选代回核验**：方程回代残差、极值比较目标值、计数缩小规模枚举对照、存在性
实际搜索。裁决 A/B/BOTH（锁定被支持方）/ NEITHER（双证伪换方法重算）/ INCONCLUSIVE
（退回仲裁）。产出的是确定性证据，而非又一次采样判断。

### 7. 语义仲裁

确定性 matcher 无法判定时，prefill 仲裁器从既有候选中选择完整答案。安全边界：
- 只能选择或弃权，不能生成/改写/拼接
- 隐藏来源标签，随机 ID + 随机顺序
- 字段契约兜底：仲裁锁定前用确定性契约复核

### 8. 客观题快速路径

选择/判断/填空走两行契约（`答案：` + `依据：`），在 40-100s 内完成。需要实算的客观题自动切换为三行先算后答契约。

### 9. 扇出门控与确定性守卫（Guard 组）

参照 VeritasMath 冲刺满分机制，在既有图内嵌入 7 个低风险守卫，全部默认开启、可独立关闭，任一守卫失败都保守回退不拖垮：

- **置信门控（confidence_gate）**：按分类置信度把题分为 fast（≥0.90）/ standard / deep（<0.70）三档。fast 档客观题走单路径快速答，省下 Python/critic 时间给难题；
- **验证路由（verify_router）**：把填空题细分——纯概念填空（填术语/定义）保持单路径；实算填空（要算数值/计数/最值）升级完整双路验证，机器计算给第二证据，不再单采样定生死（治本 idx=13/40）；
- **证明题单路径**：证明题跳过 Python 验证（抽象命题无法数值验证，实测 Python answer 恒空）；critic 判缺项后不重试完整 reasoning 而直接 coordinator 成稿（第 2 次 reasoning 边际≈0，产出从未被采纳）；Python 代码执行失败后的重试改用压缩 prefill（~150s 而非 ~200s 完整重生成），省时且保留修复 bug 的机会；
- **计数题枚举对照（counting_guard）**：检出组合计数题后，向代码提示注入"小规模暴力枚举对照"强制条款，并静态核查生成代码必须含 for/range/itertools 枚举，只写闭式则打回修复（闭式极易重数/漏数）；
- **模结构守护（modular_guard）**：检出 F_2/Z_m/同余语境后注入"结构内聚合"条款，并静态核查最终求和/计数必须在结构内取模/异或（治本 idx=7 六个 F_2 值被按整数相加）；A7 曾关闭（实测 -5 题），A8 恢复开启；
- **判断题双向确认（judge_confirm）**：Intern-S2 对"是否"题系统性偏"否"（启元实测 90% 判断错题同根因）。判断题加一轮温度 0 独立自证，方向一致才采纳，反向则温度 0 重解取第三票；
- **证明结构补强（proof_deepener）**：L3/L4 证明题"内容对但结构不被 judger 认可"。成稿前强制三段式（定理陈述→编号步骤链→显式结论），结构缺陷用一次低成本 LLM 补写；
- **答案形式对齐（form_align）**：题面问"区间长度的一半"却答完整区间（数学对、形式错）会判 partial。成稿前零成本正则提取期望形态（单值/区间/判断/枚举），错配且时间充裕时用一次 ~256 token 重述修正。证明题跳过此门——"设 G **为** 60 阶单群"里的"为"会误命中单值形态，把中间结论重述成孤值丢掉结论语义。

### 10. 平台防线（response_normalize + sys.path 自举）

- **响应归一化**：`normalize_chat_response` 归一化任意形态返回值（str/dict/Message/choices 嵌套）；
- **签名三级降级探测**：`chat_compatible` 依次尝试 kwargs → positional → messages_only，适配平台 client 的任意签名，缓存探测结果；
- **限流退避**：429 / quota 特征时退避 ≥10s，避免在平台限流窗口反复撞墙；
- **sys.path 自举 + 调用别名**：`user_agent` 自举加载路径，暴露 `__call__`/`run` 别名，任何加载/调用形态不抛异常。

### 11. RAG 题库检索（参照 ICMAnew）

解题前用原题检索竞赛题库，把最相似的题目与解答作为 few-shot 参考注入推理与验证两个子代理（`database_retrieval` 节点）：

- **TF-IDF 轻量检索**：`char_wb` n-gram 2-5 特征，替代 chroma+embedding——评测环境无 GPU/额外依赖即可复现，语料离线构建为 `data/retrieval_corpus.json`；
- **注入两个子代理**：top-k 条题面+解答随 skill 文档一并进入 reasoning 与 python 提示词（`db_retrieval_top_k=2`），检索内容与注入字符数均写入 trace 留证；
- **反锚定机制（reference_block）**：近似题结论不可直接迁移——提示块显式声明"参考题与本题参数不同"，要求数值参数差异对比、只借鉴解题方法不照抄结论，防误抄近似题。

### 12. 断点续写 / 答案前置 / 完整二次推理（参照 math_agent）

针对深度推理模型 token 耗尽 / 首轮超时导致白卷的完整兜底链：

- **答案前置 prefill**：压缩重试以 `## 结论速览\n\boxed{` 开头，让结论先落盘——即便再次截断，`\boxed{}` 内容仍可被 `_distill_answer` 策略 2.5 提炼，不丢答案；
- **结论速览兜底**：四章节解析失败时，从"结论速览"章节兜底提炼（`answer_source="quick_conclusion"`）；
- **断点续写（`_extract_clues`）**：复用首轮已算结论作为续写线索注入二次/压缩重试，而非从零重生成；
- **完整二次推理（A2 新增）**：首轮截断后、压缩重试前，若时间充裕先用普通 `chat_with_retry`（保留私有思考）带结论续写一次完整推理，把"没想清楚就硬写"升级为"想清楚了再写"；被拒/失败/再截断才降级到压缩重试；
- **首轮墙钟上限（550s）**：`first_attempt_timeout_s=550` 触发即就地转入续写，而非让 node_wrapper 的 1100s 掐死整条分支（reasoning 与 python 两侧均生效）。

### 13. 8192 token 内更高效思考（A3 新增）

A2 瓶颈是 8192 token 截断（`truncated_count=328` / 41.7%，完整二次推理 80% 也截断）——深解领域的完整 CoT（私有 `reasoning_content`）几乎必超 8192，首轮完整 CoT + 完整二次推理（~384s）是"注定截断"的浪费。A3 六条手段治截断：

- **紧凑输出（先锁定结论、少铺陈）**：推理提示追加"紧凑输出要求"——先在思考中锁定最终结论再倒推最简推导链，"问题分析"≤3 行、"详细步骤"一行公式一行结论，把额度留给"最终答案"，减少"耗尽前没写出结论"的截断；
- **深解题首轮直接压缩 prefill**：`question_mode == "proof"` 或 `category ∈ deep_solver_domains`（数论/组合/高代/抽代；A9 移除运筹学）的题，首轮直接走压缩 prefill（`## 结论速览\n\boxed{` 答案前置 + 抑制私有 CoT，~150s），成功即省下"注定截断"的完整 CoT + 完整二次推理（~384s）；压缩产出不完整则回退完整 CoT 兜底，不损失深度思考。`fast_path`（时间紧张）跳过，`enable_deep_direct_compressed=false` 可整体关闭回退 A2 三级路径。
- **Python 侧深解领域对称压缩**：`category ∈ deep_solver_domains` 的题，Python 代码生成首轮直接压缩重生成（代码前置 prefill，~200s），跳过"几乎必超 8192"的完整代码生成，与推理分支对称；产出有效代码并执行出答案则直接返回，否则回退完整生成兜底；
- **深解题压缩后二次验证**：压缩 prefill 成功但低置信时（抑制了私有思考），时间充裕（`can_afford_retry` 放行）则复用压缩答案续写做一次完整 CoT 二次确认，保留私有思考，把省下的时间换成置信度；
- **medium 计算题答案前置**：medium 计算题（computation 且非深解领域）先锁定数值，输出先写 "## 最终答案" 再倒推步骤——步骤是佐证不是重新探索；
- **中间等式线索增强**：`_extract_key_equations` 从首轮残片提取"已算出的关键等式"（右端含数字）作为续写线索，让二次推理/压缩重试带精确中间值续写。

---

## 📊 核心配置

| 配置项 | 值 | 说明 |
|---|---|---|
| `model` | `intern-s2-preview-397b` | 默认模型，可由 `INTERN_MODEL` 覆盖 |
| `problem_time_budget_s` | `1200` | 单题墙钟预算（平台硬限制 20 分钟） |
| `time_reserve_s` | `300` | 预留时间：越过后不再购买可选 LLM 阶段 |
| `paper_total_seconds` | `21600` | 全卷 6h 硬限（PaperPacer 预算池） |
| `paper_min_work_s` | `180` | 软预算下限余量：收紧后 soft_total ≥ reserve + 此值，避免"落后"时 `remaining()` 开局为负导致 LLM 全拒 |
| `difficulty_soft_budgets` | `{easy:600, medium:1200, hard:1200}` | 难度画像软预算（A3 上调 medium 1000→1200，三级熔断留足购买力） |
| `reconciliation_max_rounds` | `2` | 调解轮次上限 |
| `temperatures.reasoning` | `0.3` | 推理温度（0.8→0.3 压随机性，防 CoT 泄漏/格式偏离） |
| `temperatures.python` | `0.2` | 代码生成温度（0.6→0.2 求确定性） |
| `temperatures.semantic_arbiter` | `0.1` | 仲裁温度（低温保证一致性） |
| `max_tokens.reasoning` | `8192` | 推理首轮上限（A8：12288 → 8192，环境 cap 8192 提上限无效） |
| `max_tokens.reasoning_compressed` | `8192` | 压缩重试上限（prefill 抑制私有推理） |
| `max_tokens` 上限 | `8192` | A8：reasoning/python/compressed 回退 8192（A7 提 12288 被环境静默 cap 8192）；classifier/semantic_arbiter 96、emergency_answer 1280 仍用小 cap 抑制私有 CoT |
| `enable_critic` | `true` | 过程审计门开关（A7 曾关闭实测 -5 题，A8 恢复） |
| `enable_playoff` | `true` | 确定性复算季后赛开关 |
| `confidence_gate` | `{high:0.90, low:0.70}` | 置信门控资源档位阈值 |
| `enable_judge_confirm` | `true` | 判断题双向确认（是/否偏向纠偏） |
| `enable_counting_guard` | `true` | 计数题枚举对照守护 |
| `enable_modular_guard` | `true` | 模结构守护（F_2/Z_m 结构内聚合；A7 曾关闭实测 -5 题，A8 恢复） |
| `python_independent_solve` | `false` | 计算题工具主解（去锚定）：A8 新增、A9 回退 false（去锚定负收益 −6 题，Python 恢复注入候选核验） |
| `enable_python_solver_fallback` | `true` | 条件求解器框架（A9）：候选为空时 Python 改用独立求解器 prompt，候选非空仍核验 |
| `enable_operations_research_guard` | `true` | 运筹学确定性求解守卫（A9）：命中运筹学题注入 linprog/minimize/milp 模板 + 静态核查 |
| `enable_form_align` | `true` | 答案形式对齐 |
| `enable_proof_deepener` | `true` | 证明结构补强 |
| `db_retrieval_top_k` | `2` | 题库检索 top-k 条数（2 条同时进推理/验证两个子代理） |
| `first_attempt_timeout_s` | `550` | 首轮推理/Python 单次墙钟上限（触发即转续写） |
| `full_retry_estimate_s` | `220` | 完整二次推理/重生成估时（A8 首轮 8192 token @ ~50 tok/s + 164s 余量，只作 can_afford 估时） |
| `enable_deep_direct_compressed` | `true` | 深解题（proof + deep_solver_domains）首轮直接压缩 prefill 开关（A3；false 回退 A2 三级路径） |

---

## 📋 提交前自检清单

- [ ] 提交根目录包含 `user_agent.py`
- [ ] `ReasoningAgent.__init__` 接受 `client` 参数
- [ ] `solve(problem, metadata)` 返回 `dict` 且包含非空 `final_response`
- [ ] `python -c "from user_agent import ReasoningAgent"` 可正常导入
- [ ] 返回值可 JSON 序列化
- [ ] 代码中无硬编码 API Key / 绝对路径
- [ ] `skills/` 下 18 个领域完整
- [ ] trace 中无敏感信息
- [ ] 不依赖题目顺序或多个题目共用同一进程
- [ ] 不依赖样例数据中的 `answer` 字段

---

## 📈 版本演进

| 版本 | 得分 | 架构 | 核心改进 |
|---|---|---|---|
| A1 | 64.29 分（72/112） | LangGraph 多智能体图 + RAG 题库检索 + 断点续写/答案前置 | TF-IDF 相似题检索 + 反锚定参考块；结论速览 prefill + 线索复用续写 + 550s 首轮墙钟上限 |
| A2 | 67.86 分（76/112） | + 完整二次推理 + 难度软预算上调 | 截断难题三级兜底（首轮→完整二次推理→压缩重试）；medium 软预算 840→1000；把 A1 空余 2h20min 转化为第二次完整思考 |
| **A3** | 73.21 分（82/112） | + 紧凑输出 + 深解题首轮压缩 prefill + Python 对称压缩 + 二次验证 + 答案前置 + 线索增强 | 8192 内更高效思考（先锁定结论少铺陈）；证明/深解题首轮直接压缩 prefill（~150s 替代 ~384s 完整 CoT）；medium 软预算 1000→1200；Python 侧深解领域首轮压缩、压缩后完整 CoT 二次验证、计算题答案前置、中间等式线索增强 |
| A7 | 68.75 分（77/112） | + max_tokens 8192→12288 + 减调用（关 critic / modular_guard） | 提上限 12288（无效：环境 cap 8192）+ 关 critic/modular_guard（-5 题）；提交包去冗余。**被 A8 回退** |
| **A8** | 目标 75 分+ | 回退 A7 恢复 A4 基线 + 计算题工具主解（去锚定） | max_tokens 回退 8192 + 恢复 critic/modular_guard；Python 分支去锚定独立求解（`python_independent_solve`），释放工具执行 67% vs 心算 34% |
| **A9** | 目标 75 分+ | 回退 A8 恢复 A4 基线 + 条件求解器 + 运筹学守卫 | 回退去锚定/运筹学压缩（A8 负收益 −6 题）；候选空时 Python 独立求解（条件求解器框架）；运筹学题注入 scipy.optimize 求解器模板 + 静态核查 |

---

## 📄 License

MIT

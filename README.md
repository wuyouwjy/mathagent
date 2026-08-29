<p align="center">
  <h1 align="center">🧮 Math-Agent-System A1</h1>
  <p align="center">基于 <b>Intern-S 系列大模型</b> 的 LangGraph 多智能体数学推理系统 — 2026 挑战杯·书生赛道</p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python">
    <img src="https://img.shields.io/badge/LLM-Intern--S-orange" alt="Intern-S">
    <img src="https://img.shields.io/badge/version-A1-purple" alt="A1">
    <img src="https://img.shields.io/badge/framework-LangGraph-green" alt="LangGraph">
    <img src="https://img.shields.io/badge/score-target-70%2B-brightgreen" alt="Target">
  </p>
</p>

---

## 📖 简介

**Math-Agent-System A1** 是为 2026 年度中国青年科技创新"揭榜挂帅"擂台赛·书生赛道设计的数学推理智能体。

T3 版本基于 ICMAnew-main 架构（50 分 / 56 correct / 112 题）完成了从 T2 svragent 到 **LangGraph 多智能体图编排**的重构。T4 在 T3 基础上，参照 VeritasMath 前三名架构补齐了四块**正确性与完成率**短板：

1. **全卷完成率引擎（PaperPacer）**：按"剩余全卷时间 ÷ 剩余题数"动态收紧每题软预算，保证 6h 内 112 题全部产出答案（消除"超时未答"整题 0 分）；
2. **过程审计门（Critic）+ 确定性复算季后赛（Playoff）**：定稿前审计题面契约完整性，冲突时用"候选代回复算"的确定性证据裁决，而非只能二选一；
3. **扇出门控 + 确定性守卫（Guard 组）**：置信门控按资源档位扇出（实算填空升级双路），计数题/模结构/判断题/证明题/答案形式各有零成本确定性守卫兜底；
4. **平台防线（response_normalize + sys.path 自举）**：响应归一化 + chat 签名三级降级探测 + 接口签名兼容，杜绝平台加载/调用形态变化导致的整批 0 分。

A1 在 T4 基础上，融合两份高分作品（ICMAnew 66.96 分 / math_agent 69 分）的差异化能力，补齐两块**正确率**短板：

5. **RAG 题库检索（参照 ICMAnew 66.96 分）**：解题前用原题检索相似竞赛题，把 top-k 条题面+解答作为 few-shot 参考注入推理与验证两个子代理；TF-IDF 轻量检索（char_wb n-gram 2-5）替代 chroma+embedding，评测环境可复现；配套**反锚定机制**防止近似题结论误迁移（近似题结论不可直接照抄，数值参数差异需显式对比）；
6. **断点续写 / 答案前置（参照 math_agent 69 分）**：压缩重试用"结论速览"prefill 让结论先落盘（答案前置，截断也不丢答案）；复用首轮已算结论作为续写线索（断点续写）；首轮加 550s 墙钟上限，触发即就地转入压缩续写而非被掐死。

### T4 vs T3 核心增量

| 维度 | T3（50 分） | T4（目标 60 分+） |
|---|---|---|
| **完成率** | 每题固定 1200s 软预算，难题易超 6h | **PaperPacer 题间预算池** + 难度软预算（easy/medium/hard），6h 内全卷跑完 |
| **定稿质量门** | 无——残缺答案直接进 coordinator | **Critic 过程审计**：确定性契约 + LLM 审计 + 推导矛盾自检，缺口定向修复 |
| **冲突裁决** | 只能"重跑"或"二选一"仲裁 | **Playoff 确定性复算**：候选代回/枚举对照，A/B/BOTH/NEITHER 裁决 |
| **确定性守卫** | 计数/模结构/判断/证明/形式全靠提示层自觉 | **7 守卫**：计数枚举对照、模结构聚合、判断双向确认、证明结构补强、形式对齐、实算填空双路、置信门控 |
| **单题 token 熔断** | 首轮 24576（约 450s），奥赛题易耗尽 | **首轮 8192**（约 150s）+ prefill 压缩重试，换出重试窗口 |
| **平台兼容** | 依赖平台返回格式固定 | **response_normalize** 三级签名探测 + **sys.path 自举** + 调用别名 |

### A1 vs T4 核心增量

| 维度 | T4（目标 60 分+） | A1（目标 70 分+） |
|---|---|---|
| **外部知识** | 无——仅靠 skill 文档内建知识 | **RAG 题库检索**：原题检索相似竞赛题，top-k 题面+解答作为 few-shot 参考注入推理/验证两个子代理 |
| **检索实现** | — | **TF-IDF**（char_wb n-gram 2-5）轻量检索，替代 chroma+embedding，评测环境可复现、零额外依赖 |
| **检索安全** | — | **反锚定机制**：近似题结论不可直接迁移，数值参数差异显式对比，防止误抄近似题 |
| **截断鲁棒性** | 首轮 8192 token 耗尽 → 压缩重试重头生成 | **答案前置 prefill**：`## 结论速览` 先落盘结论，截断也不丢答案；`\boxed{}` 提炼策略 2.5 配套 |
| **续写复用** | 首轮残片丢弃 | **断点续写**：`_extract_clues` 复用首轮已算结论，压缩重试带线索续写 |
| **首轮超时** | 只有 node_wrapper 1100s 掐死 | **550s 墙钟上限**：触发即就地转入压缩续写，而非让整条分支被掐死 |

### A1 图架构总览

```
solve(problem, metadata)
  └── MathAgentGraph.run(initial_state)          # PaperPacer 接入 + 难度软预算
       ├── input_node: 提取 idx，问题锚定
       ├── classifier_node: 18 领域 LLM 预填充分类（~1s）+ 难度画像
       ├── database_retrieval_node: TF-IDF 题库检索 → top-k 相似题 + 反锚定 reference_block
       ├── solving_subgraph: 置信门控扇出（实算填空升级双路；纯概念客观题单路径）
       │    ├── reasoning_agent: 加载领域 skill → 四章节结构化输出
       │    ├── python_agent: 生成 SymPy 验证代码 → 执行 → 独立答案
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

接口防御（A1）：`solve` 兼容 `metadata=None` / 位置参数 / 额外参数；额外暴露
`agent(problem)` 与 `agent.run(problem)` 别名；文件被 importlib 按路径加载时
自动 `sys.path` 自举，任何加载形态都能找到 `graph`/`utils` 包。

---

## 📂 项目结构

```
Math-Agent-System/
├── user_agent.py              # 【必填】ReasoningAgent 入口（平台调用接口 + 防线）
├── config.py                  # 全局配置（模型/超时/温度/token 预算/墙钟预算/PaperPacer）
├── llm_client.py              # 本地调试用 OpenAI-compatible HTTP Client
├── main.py                    # 本地批量测试 Runner
├── requirements.txt           # 项目依赖清单
│
├── data/                      # 题库检索语料（离线构建，评测可复现）
│   └── retrieval_corpus.json  # 相似题面+解答语料库（TF-IDF 检索源）
├── scripts/                   # 离线脚本
│   └── build_retrieval_corpus.py # 从 sample_data 构建检索语料
│
├── graph/                     # LangGraph 图编排（主图 + 子图 + 节点 + 状态）
│   ├── main_graph.py          # 主图构建 + MathAgentGraph 运行器（PaperPacer 接入）
│   ├── solving_subgraph.py    # solving 子图：reasoning + python 并行扇出
│   ├── state.py               # MathAgentState TypedDict（全图共享状态）
│   └── nodes/                 # 图节点（每个节点一个文件）
│       ├── input.py           # 提取 idx，问题锚定
│       ├── classifier.py      # 18 领域 LLM 预填充分类 + 难度画像 + 确定性回退
│       ├── database_retrieval.py # RAG 题库检索：TF-IDF 相似题 + 反锚定 reference_block
│       ├── reasoning.py       # LLM 四章节结构化推理 + Token 耗尽压缩重试 + 断点续写/答案前置
│       ├── python_exec.py     # SymPy 验证代码生成 + 子进程安全执行
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
├── sample/                    # 测试/数据/结果（临时数据统一放这里）
│   ├── sample_tests/          # 测试
│   │   └── mock_test.py       # 无 API Key 模拟集成测试
│   ├── sample_data/           # 样例输入数据（dev.jsonl）
│   └── sample_outputs/        # 本地运行结果输出
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

### 3. 批量测试

```bash
# 首次试跑建议并发=1
export LOCAL_MAX_CONCURRENCY=1
python main.py --input_file sample/sample_data/dev.jsonl --output_dir sample/sample_outputs
```

### 4. 验证输出

```bash
python - <<'PY'
import json
from pathlib import Path
for path in sorted(Path("sample/sample_outputs").glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    fr = data.get("final_response", "")
    print(f"{path.name}: status={data.get('status')} answer={repr(fr)[:120]}")
PY
```

支持 **断点续跑**：若对应 `idx` 的 json 文件已存在且非空，Runner 自动跳过。

---

## 🔧 核心特性详解

### 1. 18 领域 skill 文档系统

每个学科目录包含：
- `<领域>skill.md`：领域概念、典型题型、解题流程和注意事项
- `<领域>验证示例.md`：按知识模块组织的验证提示和 SymPy 代码片段

分类采用 **prefill 调用**（~1s/12 tokens），覆盖全部 18 个领域。skill 文档按题目主题选取相关模块（而非简单截断头部），验证提示同理。

### 2. 并行双路验证

- **LLM 推理分支**：加载领域 skill → 四章节结构化输出（问题分析/详细解题步骤/最终答案/关键验证点）
- **Python/SymPy 分支**：独立生成验证代码 → 子进程隔离执行 → 抽取答案

两路并行执行，交叉验证节点汇总结果，按 match/mismatch/uncertain 路由。
**证明题例外**：抽象证明（同构/整环等）无法数值验证，Python 分支 answer 恒为空却并行耗数百秒，故证明题直接走推理单路径（零准确率损失，省下软预算给 coordinator 成稿）。此外证明题 critic 判缺项后**不再重试完整 reasoning**——实测第 2 次 reasoning 仍被判缺项、其产出从未被采纳（`validated_answer` 保持第 1 次值，最终靠 `coordinator_llm` 独立成稿才正确），故直接成稿，省一次完整推理（~280-527s），几乎不损正确率。

### 3. 分级熔断与压缩重试

`intern-s2-preview-397b` 的 CoT（私有 `reasoning_content`）与可见 `content` 都计入
`max_tokens`。难题可能耗完整份额度却没产出任何章节。对策：
- 首轮 `max_tokens=8192`（约 150s）——原 24576 首轮在奥赛题上几乎总被私有推理耗尽，成功解极少，降上限换来的是重试窗口
- Token 耗尽时自动转入 **prefill 压缩重试**（`max_tokens=8192`）：assistant 种子抑制私有推理，全部额度用于可见章节
- 压缩按 **reserve_margin 定价**：软预算耗尽后仍可动用 hard reserve
- 偶发地，私有 CoT 会**泄到可见 `content`**（同题两次跑一次正常一次白卷）：reasoning 无四章节 → 捞回层可能误捞 "Okay, I will..." 这类英文推理引导句当答案（其常混入 `$n_5=6$` 等式，躲过「含等式即放行」豁免）。`cleanliness.py` 在洁净度门最前拒收句首英文 CoT 引导词，避免英文残片出厂

### 4. 全卷完成率引擎（PaperPacer）

官方约束：112 题、平台并发 3、智能体总运行 6h 封顶，超出后未答题不计分。
PaperPacer 用**题间预算池**动态计算每题软预算帽：已用全卷时间 ÷ 剩余题数超速时收紧
（仍 ≥ 120s 保底），健康时给足理想预算。与难度画像（easy 480 / medium 840 / hard 1200）
取 min 作为该题软预算。只收紧软预算（可选阶段购买力），不动 1200s 平台硬限。

### 5. 过程审计门（Critic）

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
- **模结构守护（modular_guard）**：检出 F_2/Z_m/同余语境后注入"结构内聚合"条款，并静态核查最终求和/计数必须在结构内取模/异或（治本 idx=7 六个 F_2 值被按整数相加）；
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

### 12. 断点续写 / 答案前置（参照 math_agent）

针对深度推理模型 token 耗尽 / 首轮超时导致白卷的三件套：

- **答案前置 prefill**：压缩重试以 `## 结论速览\n\boxed{` 开头，让结论先落盘——即便再次截断，`\boxed{}` 内容仍可被 `_distill_answer` 策略 2.5 提炼，不丢答案；
- **结论速览兜底**：四章节解析失败时，从"结论速览"章节兜底提炼（`answer_source="quick_conclusion"`）；
- **断点续写（`_extract_clues`）**：复用首轮已算结论作为续写线索注入压缩重试，而非从零重生成；
- **首轮墙钟上限（550s）**：`first_attempt_timeout_s=550` 触发即就地转入压缩续写，而非让 node_wrapper 的 1100s 掐死整条分支（reasoning 与 python 两侧均生效）。

---

## 📊 核心配置

| 配置项 | 值 | 说明 |
|---|---|---|
| `model` | `intern-s2-preview-397b` | 默认模型，可由 `INTERN_MODEL` 覆盖 |
| `problem_time_budget_s` | `1200` | 单题墙钟预算（平台硬限制 20 分钟） |
| `time_reserve_s` | `300` | 预留时间：越过后不再购买可选 LLM 阶段 |
| `paper_total_seconds` | `21600` | 全卷 6h 硬限（PaperPacer 预算池） |
| `paper_min_work_s` | `180` | 软预算下限余量：收紧后 soft_total ≥ reserve + 此值，避免"落后"时 `remaining()` 开局为负导致 LLM 全拒 |
| `difficulty_soft_budgets` | `{easy:480, medium:840, hard:1200}` | 难度画像软预算 |
| `reconciliation_max_rounds` | `2` | 调解轮次上限 |
| `temperatures.reasoning` | `0.3` | 推理温度（0.8→0.3 压随机性，防 CoT 泄漏/格式偏离） |
| `temperatures.python` | `0.2` | 代码生成温度（0.6→0.2 求确定性） |
| `temperatures.semantic_arbiter` | `0.1` | 仲裁温度（低温保证一致性） |
| `max_tokens.reasoning` | `8192` | 推理首轮上限（T3 为 24576） |
| `max_tokens.reasoning_compressed` | `8192` | 压缩重试上限（prefill 抑制私有推理） |
| `max_tokens` 上限 | `8192` | 主办方规则：max_tokens 被 cap 到 8192、不传默认 4096；完整推理/生成场景统一设 8192（reconciliation/coordinator 原 32768/16384 已归一），prefill 选择题 96、应急直答 1280 |
| `enable_critic` | `true` | 过程审计门开关 |
| `enable_playoff` | `true` | 确定性复算季后赛开关 |
| `confidence_gate` | `{high:0.90, low:0.70}` | 置信门控资源档位阈值 |
| `enable_judge_confirm` | `true` | 判断题双向确认（是/否偏向纠偏） |
| `enable_counting_guard` | `true` | 计数题枚举对照守护 |
| `enable_modular_guard` | `true` | 模结构守护（F_2/Z_m 结构内聚合） |
| `enable_form_align` | `true` | 答案形式对齐 |
| `enable_proof_deepener` | `true` | 证明结构补强 |
| `db_retrieval_top_k` | `2` | 题库检索 top-k 条数（2 条同时进推理/验证两个子代理） |
| `first_attempt_timeout_s` | `550` | 首轮推理/Python 单次墙钟上限（触发即转压缩续写） |

---

## 📋 提交前自检清单

- [ ] 提交根目录包含 `user_agent.py`
- [ ] `ReasoningAgent.__init__` 接受 `client` 参数
- [ ] `solve(problem, metadata)` 返回 `dict` 且包含非空 `final_response`
- [ ] 本地 `sample/sample_data/dev.jsonl` 全部输出 `status: success`
- [ ] 返回值可 JSON 序列化
- [ ] 代码中无硬编码 API Key
- [ ] `skills/` 下 18 个领域完整
- [ ] trace 中无敏感信息
- [ ] 不依赖题目顺序或多个题目共用同一进程
- [ ] 不依赖样例数据中的 `answer` 字段
- [ ] `python sample/sample_tests/mock_test.py` 三个 Part（utils/pipeline/contract）全 PASS

---

## 📈 版本演进

| 版本 | 得分 | 架构 | 核心改进 |
|---|---|---|---|
| v5 | ~8% | 单路线 + 多 agents 目录 | 基础的 solver/classifier/evaluator |
| v6 | 10.71% | 单路线 + 工具调用 | 30+ 数学工具、max_tokens=8192 |
| T2 | 15.18% | svragent 多路线并行 | 4 路线共识投票、131K token、答案管线 |
| T3 | 50 分（56/112） | LangGraph 多智能体图 | skill 文档、Python 验证、交叉校验、语义仲裁、时间预算 |
| T4 | 目标 60 分+ | + Critic + Playoff + PaperPacer + Guards | 全卷完成率引擎、过程审计门、确定性复算季后赛、扇出门控、7 确定性守卫、响应归一化防 0 分 |
| **A1** | **目标 70 分+** | + RAG 题库检索 + 断点续写/答案前置 | TF-IDF 相似题检索 + 反锚定参考块；结论速览 prefill + 线索复用续写 + 550s 首轮墙钟上限 |

---

## 📄 License

MIT

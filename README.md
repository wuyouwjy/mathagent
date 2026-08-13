<p align="center">
  <h1 align="center">🧮 Math-Agent-System T3</h1>
  <p align="center">基于 <b>Intern-S 系列大模型</b> 的 LangGraph 多智能体数学推理系统 — 2026 挑战杯·书生赛道</p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python">
    <img src="https://img.shields.io/badge/LLM-Intern--S-orange" alt="Intern-S">
    <img src="https://img.shields.io/badge/version-T3.0-purple" alt="T3">
    <img src="https://img.shields.io/badge/framework-LangGraph-green" alt="LangGraph">
    <img src="https://img.shields.io/badge/score-target-50%2B-brightgreen" alt="Target">
  </p>
</p>

---

## 📖 简介

**Math-Agent-System T3** 是为 2026 年度中国青年科技创新"揭榜挂帅"擂台赛·书生赛道设计的数学推理智能体。

T3 版本基于 ICMAnew-main 架构（50+ 分）进行了全面重构：从 T2 的 svragent 多路线并行方案升级为 **LangGraph 多智能体图编排系统**，引入领域分类、并行推理+Python/SymPy 验证、答案交叉校验、语义仲裁、冲突调解等完整流水线。

### T3 vs T2 架构对比

| 维度 | T2（15.18 分） | T3（目标 50+ 分） |
|---|---|---|
| **编排框架** | svragent 轻量包（6 模块） | **LangGraph**（主图+子图条件路由） |
| **领域知识** | 无分类，通用 prompt | **18 个数学领域 skill 文档** + 验证代码片段 |
| **求解管线** | 4 路线并行 LLM → 共识投票 → 复核 | **LLM 推理 + Python/SymPy 并行验证 → 交叉校验** |
| **答案选择** | 符号等价判定 + 共识投票 | **符号/数值匹配 + 语义仲裁 + 契约字段检查** |
| **错误恢复** | 兜底单路线 | **压缩 prefill 重试 + 调解重跑 + 应急直答** |
| **时间管理** | 墙钟门控（简单） | **三级时间预算**（软预算/预留/硬限制）+ 按实测耗时定价 |
| **答案格式化** | FINAL: 标记提取 + LaTeX 标准化 | **多层级提取**（boxed→结论标签→散文捞回→stdout 挖掘）+ 契约回捞 |
| **客观题** | 与解答题相同处理 | **短路径契约**（选择/判断/填空两行应答，含归一化） |
| **证明题** | 4 条证明路线 | **结论+必要过程写入** final_response（满足 §6.2 判分标准） |

### T3 图架构总览

```
solve(problem, metadata)
  └── MathAgentGraph.run(initial_state)
       ├── input_node: 提取 idx，问题锚定
       ├── classifier_node: 18 领域 LLM 预填充分类（~1s）
       ├── solving_subgraph: 并行扇出
       │    ├── reasoning_agent: 加载领域 skill → 四章节结构化输出
       │    ├── python_agent: 生成 SymPy 验证代码 → 执行 → 独立答案
       │    └── cross_validator: 两路答案匹配 → 路由决策
       │         ├── match → coordinator
       │         ├── mismatch + retry → reconciliation → solving
       │         └── uncertain → semantic_arbiter
       ├── reconciliation_node (条件): 生成定向重试提示
       ├── semantic_arbiter_node (条件): prefill 仲裁选择最佳候选
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
#   "final_response": "最终答案：72",
#   "trace": [
#     {"step": "classification", "category": "抽象代数", ...},
#     {"step": "reasoning", "answer": "72", "steps_count": 3, ...},
#     {"step": "python_verification", "success": true, "answer": "72", ...},
#     {"step": "validation", "status": "match", "validated_answer": "72", ...},
#     {"step": "coordination", "response_length": 8, ...}
#   ]
# }
```

---

## 📂 项目结构

```
Math-Agent-System/
├── user_agent.py              # 【必填】ReasoningAgent 入口（平台调用接口）
├── config.py                  # 全局配置（模型/超时/温度/token 预算/墙钟预算）
├── llm_client.py              # 本地调试用 OpenAI-compatible HTTP Client
├── main.py                    # 本地批量测试 Runner
├── requirements.txt           # 项目依赖清单
│
├── graph/                     # LangGraph 图编排（主图 + 子图 + 节点 + 状态）
│   ├── main_graph.py          # 主图构建 + MathAgentGraph 运行器
│   ├── solving_subgraph.py    # solving 子图：reasoning + python 并行扇出
│   ├── state.py               # MathAgentState TypedDict（全图共享状态）
│   └── nodes/                 # 图节点（每个节点一个文件）
│       ├── input.py           # 提取 idx，问题锚定
│       ├── classifier.py      # 18 领域 LLM 预填充分类 + 确定性回退
│       ├── reasoning.py       # LLM 四章节结构化推理 + Token 耗尽压缩重试
│       ├── python_exec.py     # SymPy 验证代码生成 + 子进程安全执行
│       ├── cross_validator.py # 双路答案交叉验证 + 路由决策
│       ├── reconciliation.py  # 冲突时生成重试提示 + 轮次控制
│       ├── semantic_arbiter.py# prefill 仲裁：从既有候选中选择完整答案
│       └── coordinator.py     # 汇总上下文，格式化 final_response
│
├── skills/                    # 18 个数学领域 skill 文档 + 验证代码片段
│   ├── 数学分析/ 高等代数/ 抽象代数/ 概率论/ ...
│   └── 每个领域：skill.md + 验证示例.md
│
├── tests/                     # 测试
│   └── mock_test.py           # 无 API Key 模拟集成测试
│
└── utils/                     # 工具库（按功能分包）
    ├── deps.py                # LangGraph configurable 依赖注入
    ├── error_handler.py       # 节点异常包装 + fallback 状态
    ├── client_tuning.py       # 尽力提升平台 client socket 超时
    ├── reconciliation_policy.py # 调解轮次策略
    ├── conclusion_salvage.py  # 无章节输出时从散文中捞回结论句
    ├── cot_stripper.py        # CoT 前缀去除 + 占位答案检测
    ├── logger.py              # 日志
    ├── answer/                # 答案管线：抽取→匹配→契约→格式化→洁净度
    │   ├── extractor.py, matcher.py, contract.py
    │   ├── formatter.py, cleanliness.py, structured.py
    ├── verification/          # 验证：Python 输出证据解析 + 反伪造 + stdout 挖掘
    │   ├── evidence.py, authenticity.py, stdout_miner.py
    ├── budget/                # 资源预算：token + 墙钟 + 重试可行性 + 超时
    │   ├── token.py, time.py, affordability.py, timeout.py
    ├── llm/                   # LLM 交互：重试退避 + prefill 预填充 + Prompt 模板
    │   ├── retry.py, prefill.py, templates.py
    ├── skills_util/           # 领域技能：文档加载 + 主题摘取 + TF-IDF 索引
    │   ├── loader.py, excerpt.py, embedding.py
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
python main.py --input_file sample_data/dev.jsonl --output_dir sample_outputs
```

### 4. 验证输出

```bash
python - <<'PY'
import json
from pathlib import Path
for path in sorted(Path("sample_outputs").glob("*.json")):
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

### 3. 分级熔断与压缩重试

`intern-s2-preview-397b` 的 CoT 计入 `max_tokens`，难题可能耗完整份额度却没产出任何章节。对策：
- 首轮 `max_tokens=24576`（约 450s）
- Token 耗尽时自动转入 **prefill 压缩重试**（`max_tokens=8192`，约 150s）：assistant 种子抑制私有推理，全部额度用于可见输出
- 压缩按 **reserve_margin 定价**：软预算耗尽后仍可动用 hard reserve

### 4. 答案契约与完整性检查

`answer_contract.py` 从题面推断必须字段：
- 假设检验 → 拒绝/不拒绝结论
- 置信区间 → 双端点
- 运输问题 → 基变量分配
- 枚举题 → 全部对象
- 极值题 → 最优值+最优解

### 5. 语义仲裁

确定性 matcher 无法判定时，prefill 仲裁器从既有候选中选择完整答案。安全边界：
- 只能选择或弃权，不能生成/改写/拼接
- 隐藏来源标签，随机 ID + 随机顺序
- 字段契约兜底：仲裁锁定前用确定性契约复核

### 6. 客观题快速路径

选择/判断/填空走两行契约（`答案：` + `依据：`），在 40-100s 内完成。需要实算的客观题自动切换为三行先算后答契约。

---

## 📊 核心配置

| 配置项 | 值 | 说明 |
|---|---|---|
| `model` | `intern-s2-preview-397b` | 默认模型，可由 `INTERN_MODEL` 覆盖 |
| `problem_time_budget_s` | `1200` | 单题墙钟预算（平台硬限制 20 分钟） |
| `time_reserve_s` | `300` | 预留时间：越过后不再购买可选 LLM 阶段 |
| `reconciliation_max_rounds` | `2` | 调解轮次上限（默认最多重跑 solving 1 次） |
| `temperatures.reasoning` | `0.8` | 推理温度 |
| `temperatures.python` | `0.6` | 代码生成温度 |
| `temperatures.semantic_arbiter` | `0.1` | 仲裁温度（低温保证一致性） |
| `max_tokens.reasoning` | `24576` | 推理首轮上限 |
| `max_tokens.reasoning_compressed` | `8192` | 压缩重试上限 |

---

## 📋 提交前自检清单

- [ ] 提交根目录包含 `user_agent.py`
- [ ] `ReasoningAgent.__init__` 接受 `client` 参数
- [ ] `solve(problem, metadata)` 返回 `dict` 且包含非空 `final_response`
- [ ] 本地 `sample_data/dev.jsonl` 全部输出 `status: success`
- [ ] 返回值可 JSON 序列化
- [ ] 代码中无硬编码 API Key
- [ ] `skills/` 下 18 个领域完整
- [ ] trace 中无敏感信息
- [ ] 不依赖题目顺序或多个题目共用同一进程
- [ ] 不依赖样例数据中的 `answer` 字段

---

## 📈 版本演进

| 版本 | 得分 | 架构 | 核心改进 |
|---|---|---|---|
| v5 | ~8% | 单路线 + 多 agents 目录 | 基础的 solver/classifier/evaluator |
| v6 | 10.71% | 单路线 + 工具调用 | 30+ 数学工具、max_tokens=8192 |
| T2 | 15.18% | svragent 多路线并行 | 4 路线共识投票、131K token、答案管线 |
| **T3** | **目标 50%+** | **LangGraph 多智能体图** | **skill 文档、Python 验证、交叉校验、语义仲裁、时间预算** |

---

## 📄 License

MIT

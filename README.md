<p align="center">
  <h1 align="center">🧮 Math-Agent-System v6</h1>
  <p align="center">基于 <b>Intern-S 系列大模型</b> 的数学推理智能体 — 2026 挑战杯·书生赛道</p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python">
    <img src="https://img.shields.io/badge/LLM-Intern--S-orange" alt="Intern-S">
    <img src="https://img.shields.io/badge/version-v6.0-green" alt="v5">
    <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License">
  </p>
</p>

---

## 📖 简介

**Math-Agent-System v6** 是一个为 2026 年度中国青年科技创新"揭榜挂帅"擂台赛·书生赛道设计的数学推理智能体。采用 **多阶段推理 + 自验证** 架构，核心逻辑自包含于 `user_agent.py`，零外部模块依赖风险。

### v6 核心改进（相比 v5）

| 改进项 | v5 | v6 |
|--------|----|----|
| Solver 导入 | 无条件全部导入，单文件语法错误导致全部挂掉 | **逐文件安全导入 + 自动回退**，单文件故障不影响全局 |
| f-string 安全性 | 复杂 f-string 三元嵌套+隐式拼接，Python 3.11 下易出错 | **提取为独立变量**，避免解析器歧义 |
| 容错能力 | Solver 创建失败 → 整个求解崩溃 | **多层 fallback：回退 Solver → LLM 直接求解** |
| 评测稳定性 | 0 分（所有题目 status=error） | **语法修正 + 导入加固，保证可跑出结果** |

### 推理流程

```
Problem → [结构化思考 Prompt]
       → 模型求解（max 8192 tokens）
       → 截断检测 → 自动续写（如需要）
       → 英文泄露检测 → 中文重试（如需要）
       → 5 层答案提取
       → 自验证（弱答案触发）
       → final_response
```

### 核心特性

- **自包含架构**：核心 Prompt 和逻辑全部内联在 `user_agent.py`，外部模块通过 `try/except` 安全导入，平台环境不会因 `ModuleNotFoundError` 得零分
- **18 Solver 安全导入**：每个 Solver 独立 `try/except` 导入 + 自动回退，单个 solver 文件语法错误不会导致全局崩溃
- **6 阶段推理管线**：结构化思考 → 求解 → 截断续写 → 泄露重试 → 自验证 → 答案提取
- **5 层答案提取**：`ANSWER:` 标记 → `\boxed{}` LaTeX → 中文结论标记 → 数学内容末行 → 末行兜底
- **智能自验证**：仅当答案可疑时触发验证轮（节省 API 配额），验证通过后更新答案
- **比赛约束适配**：并发 3、单题 20 分钟、总时长 6 小时，推理策略已调优

---

## 🏆 比赛接口

```python
from user_agent import ReasoningAgent

# 平台初始化（不可修改此调用格式）
agent = ReasoningAgent(client=official_client)

# 求解单题
result = agent.solve(problem="设$\\mathbb{F}_{81}$为$81$元的有限域...", metadata={"idx": 0})

# 返回格式
# {
#   "final_response": "72",
#   "trace": [
#     {"step": "solve", "content": "..."},
#     {"step": "verify", "content": "..."},
#     {"step": "finalize", "content": "最终答案: 72"}
#   ]
# }
```

### 平台 client 接口

```python
# client 由评测平台统一注入，禁止硬编码 API Key
response = client.chat(
    messages=[{"role": "user", "content": problem}],
    temperature=0.2,
    max_tokens=4096
)
# 返回 str 或 {"content": "..."}，v5 同时兼容两种格式
```

### 最新比赛规则（2026-08）

| 规则项 | 限制值 |
|--------|--------|
| Agent 并发数 | **3** |
| 单题最长运行时间 | **20 分钟** |
| Agent 最长运行时间 | **6 小时** |
| 超时未答题目 | **不计分** |
| 评分依据 | `final_response` 答案正确率（同分参考 trace 设计优劣） |

---

## 📂 项目结构

```
Math-Agent-System/
├── user_agent.py              # 【必填】智能体主入口（ReasoningAgent，自包含核心逻辑）
├── agents/
│   ├── __init__.py             # 模块导出（MathClassifier + MathSolver）
│   ├── classifier.py           # 数学领域分类器（可选，20+ 领域关键词匹配）
│   └── solver.py               # 统一求解器（可选，多阶段推理管线）
├── prompts/
│   └── __init__.py             # 可选 Prompt 模板（user_agent.py 有内联回退）
├── requirements.txt            # 项目依赖清单
├── main.py                     # 本地批量测试 Runner
├── llm_client.py               # 本地调试用 LLM 客户端（需 INTERN_API_KEY）
└── quick_test.py               # 快速自测脚本
```

> ⚠️ 正式评测仅校验 `user_agent.py` 中的 `ReasoningAgent` 类和方法签名。`agents/` 和 `prompts/` 为可选的辅助模块。

---

## 🚀 本地调试

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥

```bash
export INTERN_API_KEY="sk-xxxx你的密钥xxxx"
export INTERN_MODEL="intern-s2-preview"  # 可选，默认 intern-s2-preview
```

> ⚠️ API Key 只能通过环境变量传入，**禁止硬编码在代码中**。平台评测时由官方 Client 统一注入。

### 3. 单题快速测试

```bash
python quick_test.py
```

### 4. 批量测试（比赛 JSONL 格式）

```bash
python main.py --input_file sample_data/dev.jsonl --output_dir sample_outputs
```

并发控制（默认 4，比赛实际为 3）：

```bash
export LOCAL_MAX_CONCURRENCY=4
```

### 5. 本地输出格式

```json
{
  "idx": 0,
  "status": "success",
  "final_response": "72",
  "trace": [
    {"step": "solve", "content": "…"},
    {"step": "finalize", "content": "最终答案: 72"}
  ]
}
```

支持 **断点续跑**：若对应 `idx` 的 json 文件已存在且非空，Runner 自动跳过。

---

## 🔧 可用基座模型

| 模型 | 说明 |
|------|------|
| `intern-s1` | 基础模型 |
| `intern-s1-pro` | 增强模型 |
| `intern-s2-preview` | 最新预览版（推荐） |

API 控制台：https://internlm.intern-ai.org.cn/api/document

---

## 📋 零分常见原因 & 防范措施

| 原因 | v6 防范措施 |
|------|------------|
| `user_agent.py` 不存在 | ✅ 仓库根目录已放置 |
| `ModuleNotFoundError` | ✅ 核心逻辑自包含，外部模块 try/except 安全导入 |
| Solver 语法错误导致全挂 | ✅ 逐文件安全导入 + 自动回退到可用 Solver |
| f-string Python 3.11 兼容性 | ✅ 复杂表达式提取为独立变量，消除解析器歧义 |
| `final_response` 为空 | ✅ 5 层答案提取 + 末位兜底扫描，确保非空输出 |
| 超时（单题 >20min / 总 >6h） | ✅ 单次调用 max_tokens=8192，验证轮仅按需触发 |
| JSON 序列化失败 | ✅ trace 结构确保 JSON 兼容 |

---

## 📄 License

MIT

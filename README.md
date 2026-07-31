<p align="center">
  <h1 align="center">🧮 Math-Agent-System</h1>
  <p align="center">基于 <b>Intern-S 系列大模型</b> 的数学推理智能体 — 挑战杯 2026 赛道</p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python">
    <img src="https://img.shields.io/badge/LLM-Intern--S-orange" alt="Intern-S">
    <img src="https://img.shields.io/badge/deps-stdlib%20only-brightgreen" alt="deps">
    <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License">
  </p>
</p>

---

## 📖 简介

**分类 + 求解 + 兜底提取** 的数学推理智能体，专为挑战杯 2026 Intern-S 赛道设计。零额外依赖，仅使用 Python 标准库。

### 推理流程

```
Problem → MathClassifier（20+领域分类 + 题型检测）
       → ComputeSolver（计算题）/ ProofSolver（证明题）
         → 截断检测续写 → 英文泄露追问 → ANSWER提取
       → 兜底答案提取 → final_response
```

### 核心特性

- **中文结构化 Prompt**：强制输出 `【策略规划】→【解题过程】→【关键洞察】→ANSWER:→【启发性总结】`
- **20+ 数学领域分类**：关键词匹配，自动选择计算/证明求解器
- **5 层答案提取**：`ANSWER:` → `\boxed{}` → 结论标记 → 末尾兜底 → 未能求解
- **防截断自动续写**：检测未闭合 LaTeX/逗号结尾/转折词等，自动发送续写请求
- **防英文泄露追问**：检测 Intern-S 英文思考链泄露，两阶段追问中文答案
- **顶层异常保护**：`solve()` 有 try/except，任何异常都返回合法格式

---

## 🏆 比赛接口

```python
from user_agent import ReasoningAgent
agent = ReasoningAgent(client=official_client)
result = agent.solve(problem="题目文本", metadata={"idx": 0})
# result = {"final_response": "72", "trace": [...], "verification": {...}}
```

### 平台 client 接口

```python
# client.chat() 可返回 str 或 {"content": "..."}
response = client.chat(
    messages=[{"role": "user", "content": problem}],
    temperature=0.2,
    max_tokens=12288
)
```

---

## 📂 项目结构（比赛提交）

```
Math-Agent-System/
├── user_agent.py              # 【必填】比赛智能体主入口（ReasoningAgent）
├── agents/
│   ├── __init__.py             # 模块导出
│   ├── classifier.py           # 20+ 领域分类器
│   ├── compute_solver.py       # 计算题求解器（防截断+追问+答案提取）
│   └── proof_solver.py         # 证明题求解器（防截断+追问+结论提取）
├── prompts/
│   └── __init__.py             # 中文结构化 Prompt 模板 + 检测模式
├── requirements.txt            # 比赛依赖（零额外依赖）
├── main.py                     # 本地批量测试 Runner（本地调试用）
├── llm_client.py               # 本地调试用 LLM 客户端
├── backend/                    # FastAPI 后端（Web 界面，可选）
├── frontend/                   # React 前端（Web 界面，可选）
├── database/datasets/          # 本地评测数据集
└── quick_test.py               # 快速自测脚本
```

---

## 🚀 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置

```bash
# 设置 API 密钥（必须）
export INTERN_API_KEY="your-api-key"

# 可选
export INTERN_MODEL="intern-s2-preview"
```

> ⚠️ API Key 只能通过环境变量传入，禁止硬编码。平台评测时由官方 Client 统一注入。

### 单题测试

```bash
python quick_test.py
```

### 批量测试（比赛格式）

```bash
python main.py --input_file database/datasets/benchmark_v1_dev.jsonl --output_dir sample_outputs
```

并发控制：
```bash
export LOCAL_MAX_CONCURRENCY=4
```

### Web 界面（可选）

```bash
# 后端
cd backend && python main.py

# 前端
cd frontend && npm install && npm run dev
```

---

## 📄 License

MIT

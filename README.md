<p align="center">
  <h1 align="center">🧮 Math-Agent-System</h1>
  <p align="center">基于 <b>Intern-S 系列大模型</b> 的数学推理智能体 — 挑战杯 2026 赛道</p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python">
    <img src="https://img.shields.io/badge/LLM-Intern--S-orange" alt="Intern-S">
    <img src="https://img.shields.io/badge/deps-requests%20only-brightgreen" alt="deps">
    <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License">
  </p>
</p>

---

## 📖 简介

**Plan → Solve → Verify** 三阶段数学推理智能体，专为挑战杯 2026 Intern-S 赛道设计。极简依赖，仅需 `requests`。

**比赛入口**：`user_agent.py` 中的 `ReasoningAgent` 类，平台通过以下方式调用：

```python
from user_agent import ReasoningAgent
agent = ReasoningAgent(client=official_client)
result = agent.solve(problem="题目文本", metadata={"idx": 0})
```

## 🏗️ 推理流程

```
Problem ──→ Plan (策略规划) ──→ Solve (执行求解) ──→ Verify (验证答案) ──→ final_response
```

每次 `solve()` 调用执行 3 次 LLM 请求，答案提取有 5 级 fallback 保障非空。

## 🎯 特性

- **极简依赖** — 只依赖 `requests`，平台安装零风险
- **三阶段推理** — Plan→Solve→Verify，每阶段独立 temperature/max_tokens 配置
- **严谨答案提取** — JSON解析 → 正则兜底 → "Final answer:"行 → 全文回退
- **高容错** — `client.chat()` 直接返回 str，无复杂适配层
- **Web 界面** — React + FastAPI 可视化评测中心（可选，本地使用）

## 📂 项目结构

```
Math-Agent-System/
├── user_agent.py              # 【必填】比赛智能体主入口（ReasoningAgent）
├── main.py                    # 本地批量测试 Runner
├── llm_client.py              # 本地调试用 LLM 客户端
├── requirements.txt           # 比赛依赖（仅 requests）
├── backend/                   # FastAPI 后端（Web 界面）
│   └── api/
├── frontend/                  # React 前端（Web 界面）
│   └── src/
├── database/
│   └── datasets/              # 本地评测数据集
├── quick_test.py              # 快速自测脚本
└── agents/ graph/ rag/ ...    # 实验性模块（比赛不使用）
```

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

## 🏆 比赛接口

```python
class ReasoningAgent:
    def __init__(self, client, *args, **kwargs):
        """client 由评测平台统一注入"""

    def solve(self, problem: str, metadata: dict) -> dict:
        """返回 {"final_response": "答案", "trace": [...]}"""
```

平台 client 接口：
```python
# client.chat() 直接返回 str
response = client.chat(
    messages=[{"role": "user", "content": problem}],
    temperature=0.2,
    max_tokens=12288
)
```

## 📄 License

MIT

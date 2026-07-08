<p align="center">
  <h1 align="center">🧮 Math-Agent-System</h1>
  <p align="center">基于 <b>Intern-S1 + LangGraph</b> 的多领域数学自动求解智能体系统</p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python">
    <img src="https://img.shields.io/badge/LangGraph-0.x-green" alt="LangGraph">
    <img src="https://img.shields.io/badge/LLM-Intern--S1-orange" alt="Intern-S1">
    <img src="https://img.shields.io/badge/tests-78%20passed-brightgreen" alt="Tests">
    <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License">
  </p>
</p>

---

## 📖 简介

Math-Agent-System 是一个面向竞赛级数学问题的自动求解系统。给定一道数学题，系统自动完成**领域分类 → 知识检索 → 专家求解 → 答案验证 → 反思重试**的完整流水线，输出结构化解答。

支持 **18 个数学子领域**，配备专属 Solver Agent，集成 SymPy 符号计算和 ChromaDB 知识库检索增强（RAG）。

## 🏗️ 架构

```
React 前端 (Ant Design + ECharts)
        ↕ REST API
FastAPI 后端
        ↕
┌─ LangGraph 工作流引擎 ───────────────────────────┐
│                                                   │
│  cache_check → parser → classifier → RAG          │
│                    ↓                              │
│  solver_dispatcher → verifier → reflection        │
│       ↑                  ↓            ↓           │
│       └── (retry) ───────┘      formatter → END   │
└───────────────────────────────────────────────────┘
        ↕               ↕              ↕
   Intern-S1 LLM    SymPy 符号    ChromaDB 向量库
```

## 🎯 核心特性

- **18 领域自动分类** — 从抽象代数到偏微分方程，自动识别并路由到专家 Solver
- **多 Agent 协作** — Parser / Classifier / Solver / Verifier / Reflection 五个角色流水线
- **反思重试** — 验证失败后自动分析原因、调整策略、重新求解（最多 N 次）
- **正确答案库** — ChromaDB + 哈希双层缓存，只有 ground-truth 验证过的正确答案才入库
- **模糊答案匹配** — 五级比对策略：LaTeX→Unicode 归一化、数值容差、SymPy 符号等价
- **一键评测** — 112 题数据集并发评测，生成完整报告（分领域统计、错题详情、耗时分布）
- **历史记录** — 每次评测自动存档，支持回溯查看和对比

## 📂 项目结构

```
Math-Agent-System/
├── agents/                   # 智能体
│   ├── solver_experts/       # 18 个领域专家 Solver
│   │   ├── base_solver.py    # Solver 基类
│   │   └── skills/           # 各领域求解策略定义
│   ├── solver_dispatcher.py  # Solver 路由调度
│   ├── classifier_agent.py   # 领域分类器
│   ├── graph_manager_agent.py # 工作流路由管理
│   └── evaluation_agent.py
├── graph/                    # LangGraph 工作流
│   ├── graph_builder.py      # 图构建（节点 + 边 + 条件路由）
│   ├── workflow.py           # 工作流运行器
│   └── nodes/                # 10 个图节点
│       ├── cache_nodes.py    # 缓存检查 / 保存
│       ├── parser_node.py    # 问题解析
│       ├── classifier_node.py # 领域分类
│       ├── solver_node.py    # Solver 调度
│       ├── verifier_node.py  # 答案验证
│       ├── reflection_node.py # 反思重试
│       ├── formatter_node.py  # JSON 格式化
│       ├── rag_node.py       # 知识检索
│       └── error_handler_node.py
├── rag/                      # RAG 检索增强
│   ├── retriever.py
│   ├── theorem_db.py         # 定理库
│   ├── formula_db.py         # 公式库
│   ├── example_db.py         # 例题库
│   └── cache/problem_cache.py # 正确答案库
├── schemas/                  # 数据模型
│   ├── workflow_state.py     # LangGraph 状态
│   ├── output_schema.py      # 输出 Schema
│   └── math_domains.py       # 18 领域映射
├── backend/                  # FastAPI 后端
│   └── api/
│       ├── benchmark.py      # 一键评测 + 历史记录
│       ├── solve.py          # 单题 / 批量求解
│       ├── dashboard.py      # 首页统计
│       └── schemas.py        # API Schema
├── frontend/                 # React 前端
│   └── src/
│       ├── pages/
│       │   ├── BenchmarkCenter.tsx  # 评测中心
│       │   ├── Dashboard.tsx        # 首页
│       │   └── ResultAnalysis.tsx   # 结果分析
│       ├── api/benchmark.ts
│       └── types/index.ts
├── evaluation/evaluator.py   # 批量评测引擎
├── utils/
│   ├── math_match.py         # 模糊答案匹配
│   └── logger.py             # 日志
├── database/
│   ├── datasets/dev.jsonl    # 112 题评测数据集
│   └── outputs/benchmark_runs/ # 评测历史记录
├── tests/                    # 78 个测试
├── run.py                    # 主入口
└── requirements.txt
```

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+（前端）
- ChromaDB（可选，用于正确答案库）

### 安装

```bash
git clone https://github.com/your-username/Math-Agent-System.git
cd Math-Agent-System
pip install -r requirements.txt
```

### 配置

```bash
# 设置 Intern-S1 API
export INTERN_S1_API_KEY="your-api-key"
export INTERN_S1_BASE_URL="https://your-api-endpoint/v1"
```

或直接在 `configs/settings.py` 中修改。

### 启动

```bash
# 后端 (端口 8080)
python run.py --mode api

# 前端开发
cd frontend && npm install && npm run dev
```

浏览器打开 `http://localhost:5173`。

### CLI 批量评测

```bash
python run.py --mode batch --dataset ./database/datasets/dev.jsonl
```

## 🔬 答案比对

系统使用 `utils/math_match.py` 中的五级模糊匹配策略判定答案正确性：

| 级别 | 规则 | 示例 |
|:----:|------|------|
| 1 | **精确匹配**（归一化后字面相等） | `m≤3n-6` = `m≤3n-6` |
| 2 | **包含匹配** | `1.73205` 出现在 `x₃≈1.73205` 中 |
| 3 | **核心公式匹配**（剥离中文描述） | `证明成立：m≤3n-6` ≈ `m≤3n-6` |
| 4 | **数值容差**（±1.5%）+ 非数值匹配 | `1.73205081` ≈ `1.73205`；`y=0.5+1.6x` ≈ `β₀=0.5,β₁=1.6` |
| 5 | **SymPy 符号等价** | `1/2` ≡ `0.5`；`√4` ≡ `2` |

归一化处理：LaTeX→Unicode、中文前缀剥离、`\frac{a}{b}`→`(a)/(b)`、`(n,m)=` 赋值剥离、下标数字排除等。

## 📊 评测中心

1. 点击「**一键运行评测**」对 112 道数学题自动评测
2. 实时查看求解流程（解析→分类→求解→验证）
3. 评测完成后展示：
   - 统计卡片（正确率、平均耗时、总题数）
   - 领域分布柱状图 + 成功率饼图
   - **错题列表**（题号、领域、预测答案 vs 标准答案）
4. **历史记录**面板可回溯所有历史评测

### 配置选项

| 选项 | 说明 |
|------|------|
| **正确答案库** | 开启：命中直接返回；关闭：每题重新 LLM 求解 |
| **反思次数** | 0（快速模式）~ 5（最高精度，较慢） |

## 📋 评测记录

```json
{
  "run_id": "run_20260708_153000",
  "status": "completed",
  "total": 112, "solved": 45, "accuracy": 40.18,
  "total_time_ms": 4500000,
  "domain_stats": {
    "abstract_algebra": {"total": 8, "solved": 5, "accuracy": 62.5}
  },
  "wrong_questions": [
    {"question_id": "27", "domain": "number_theory",
     "predicted": "(2,1),(3,2)", "ground_truth": "(1,1),(3,2)"}
  ]
}
```

## 🧪 测试

```bash
pytest tests/ -v    # 78 tests
```

## 📄 License

MIT

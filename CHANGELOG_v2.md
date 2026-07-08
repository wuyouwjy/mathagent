# Math-Agent-System v2 变更文档

> 挑战杯 2026 初赛优化版本 — 基于 Intern-S 系列模型的数学智能体

---

## 一、变更概述

本次重构围绕三个目标：
1. **比赛合规**：符合挑战杯 `user_agent.py` → `ReasoningAgent` → `solve(problem, metadata)` 接口规范
2. **前后端同步**：Web 前端/后端 API 与比赛入口共享同一套 Agent 逻辑
3. **架构优化**：删除死代码、Agent 智能体化、Solver Skill 系统、MCP 模块

---

## 二、新增文件

### 比赛入口层（根目录）

| 文件 | 作用 |
|------|------|
| `user_agent.py` | **比赛核心入口**。`ReasoningAgent` 类，平台通过 `ReasoningAgent(client=official_client)` 初始化，`solve(problem, metadata)` 返回 `{"final_response": "...", "trace": [...]}` |
| `llm_client.py` | **本地测试 LLM 客户端**。与比赛平台 `InternChatClient` 接口一致：`chat(messages, temperature, max_tokens) -> str`。从环境变量 `INTERN_API_KEY` 读取 API 密钥 |
| `run_competition.py` | **本地测试 Runner**。`python run_competition.py --input_file data.jsonl --output_dir outputs/`，模拟比赛平台行为（并发控制、断点续跑、输出格式）**注意：命名为 `run_competition.py` 避免与 `backend/main.py` 冲突** |

### 适配层

| 文件 | 作用 |
|------|------|
| `tools/platform_adapter.py` | **平台客户端适配器**。`PlatformClientAdapter` 将平台 `client.chat() -> str` 适配为系统内部 `InternS1Client` 接口（`chat() -> dict`, `chat_with_json_output()` 等），使整个系统无需修改即可使用平台注入的 client |

### 智能体层

| 文件 | 作用 |
|------|------|
| `agents/__init__.py` | Agent 模块统一导出 |
| `agents/classifier_agent.py` | **领域分类智能体**。规则快速匹配 + LLM 深度分类 → 18 个数学领域 → 路由到对应 Solver 专家。先匹配 `STRONG_PATTERNS` 关键词（置信度 ≥ 0.9 直接返回），不足时调用 LLM |
| `agents/graph_manager_agent.py` | **工作流编排智能体**。管理 LangGraph 路由决策（缓存后/分类后/反思后）、反思循环（最大重试 3 次，失败超过 2 次推荐备选 Solver）、重试统计 |
| `agents/evaluation_agent.py` | **评估与题库管理智能体**。问题数据库 CRUD（模板格式 `problem_db.json`）、精确匹配秒出、关键词相似搜索类比求解、批量评估委托 |
| `agents/solver_dispatcher.py` | **Solver 调度器**。从注册表获取 Solver 实例 + Skill → 构建知识增强上下文 → 调用 `solver.solve()`，替代原来硬编码的 `_execute_solver` |

### Solver Skills

| 文件 | 作用 |
|------|------|
| `solvers/skills/__init__.py` | Skill 注册表 + `SolverSkill` dataclass 定义 + `register_skill()` / `get_skill()` |
| `solvers/skills/algebra_skills.py` | 代数技能：8 种策略 + 22 个关键词 + 2 个 Few-shot 示例 |
| `solvers/skills/pde_skills.py` | PDE 技能：8 种策略 + 18 个关键词 + 1 个 Few-shot 示例 |
| `solvers/skills/ode_skills.py` | ODE 技能：8 种策略 + 22 个关键词 + 1 个 Few-shot 示例 |
| `solvers/skills/complex_analysis_skills.py` | 复分析技能：8 种策略 + 18 个关键词 + 1 个 Few-shot 示例 |
| `solvers/skills/topology_skills.py` | 拓扑学技能：8 种策略 + 18 个关键词 + 1 个 Few-shot 示例 |
| `solvers/skills/optimization_skills.py` | 最优化技能：9 种策略 + 24 个关键词 + 1 个 Few-shot 示例 |

### MCP 模块

| 文件 | 作用 |
|------|------|
| `mcp/__init__.py` | MCP 模块入口 |
| `mcp/tools.py` | **10 个 MCP 工具**：solve_math_problem, classify_problem, search_theorems, search_formulas, get_solver_info, list_domains, evaluate_solution, get_cache_stats, get_problem_database_stats, search_similar_problems |
| `mcp/server.py` | MCP 服务器（FastMCP + 回退交互模式） |

### 节点拆分

`graph/nodes.py`（1300+ 行）→ `graph/nodes/` 下 10 个独立文件：

| 文件 | 作用 |
|------|------|
| `graph/nodes/__init__.py` | 统一导出所有节点函数，保持 `from graph.nodes import ...` 接口不变 |
| `graph/nodes/cache_nodes.py` | 缓存检查 + 缓存保存 |
| `graph/nodes/parser_node.py` | 问题解析（规则 + LLM） |
| `graph/nodes/classifier_node.py` | 领域分类（委托给 ClassifierAgent） |
| `graph/nodes/rag_node.py` | RAG 知识检索 |
| `graph/nodes/solver_node.py` | **🔥 Solver 调度（使用 SolverDispatcher 替代硬编码 prompt）** |
| `graph/nodes/verifier_node.py` | 结果验证（LLM 逻辑验证） |
| `graph/nodes/reflection_node.py` | 反思重试（委托给 GraphManagerAgent） |
| `graph/nodes/formatter_node.py` | JSON 格式化输出 |
| `graph/nodes/error_handler_node.py` | 异常兜底 |

---

## 三、删除文件

| 文件 | 原因 |
|------|------|
| `app/__init__.py` + `app/` | 空壳模块，无任何引用 |
| `models/__init__.py` + `models/` | 纯转发层，re-export 移到 `schemas/__init__.py` |
| `graph/nodes.py` → `nodes.py.bak` | 拆分为 `graph/nodes/` 下 10 个文件 |

---

## 四、修改文件

| 文件 | 改动内容 |
|------|---------|
| `configs/settings.py` | ① API key 从环境变量读取（`INTERN_API_KEY`），不再硬编码 ② 新增 `PathsConfig.problem_db_path` ③ 新增 `MCPConfig` ④ 新增 `AgentConfig` |
| `schemas/__init__.py` | 从 `models/__init__.py` 迁移 re-export（MathDomain, MathSolutionOutput, WorkflowState 等） |
| `solvers/base_solver.py` | 新增 `get_skill()` 方法：从 Skill 注册表加载领域专属 prompt/策略/示例 |
| `tools/intern_client.py` | ① `get_intern_client()` 优先返回平台适配器（比赛模式）② API key 为空时使用占位符不崩溃 |
| `graph/__init__.py` | 更新导入路径到 `graph/nodes/` + 导出 graph_builder 和 workflow |
| `graph/graph_builder.py` | 路由函数委托给 `GraphManagerAgent`（`after_cache_check`/`after_classifier`/`after_reflection`） |
| `requirements.txt` | 新增 `mcp>=1.0.0` |
| `run.py` | 新增 `--mode mcp` 启动 MCP 服务器 |

---

## 五、比赛接口使用指南

### 本地测试

```bash
# 1. 设置 API 密钥
export INTERN_API_KEY="sk-..."
export INTERN_MODEL="intern-s2-preview"  # 可选

# 2. 命令行快速测试
python user_agent.py --problem "求解 x^2 - 5x + 6 = 0"

# 3. 批量运行 JSONL 数据集
python main.py --input_file sample_data/dev.jsonl --output_dir sample_outputs

# 4. 交互式求解（推荐调试用）
python run.py --mode interactive
```

### 比赛提交清单

```
仓库根目录必须包含：
├── user_agent.py          ← ✅ 比赛入口（ReasoningAgent + solve）
├── llm_client.py          ← 本地测试用（平台会注入自己的 client）
├── main.py                ← 本地 runner
├── requirements.txt       ← ✅ 依赖清单
├── agents/                ← 智能体层
├── graph/                 ← LangGraph 工作流
├── solvers/               ← Solver 专家 + Skills
├── tools/                 ← 平台适配器 + 客户端
├── rag/                   ← RAG 知识库
├── cache/                 ← 缓存系统
├── evaluation/            ← 评估系统
├── mcp/                   ← MCP 模块
├── schemas/               ← 数据模型
├── configs/               ← 配置管理
├── utils/                 ← 工具函数
├── tests/                 ← 测试
├── frontend/              ← React 前端
├── backend/               ← FastAPI 后端
└── datasets/              ← 数据集
```

### 平台调用方式

```python
# 平台会执行以下代码：
from user_agent import ReasoningAgent
agent = ReasoningAgent(client=official_client)

result = agent.solve(
    problem="设 F_81 为 81 元有限域...",
    metadata={"idx": 0}
)
# result = {
#     "final_response": "72",
#     "trace": [
#         {"step": "classify", "content": "领域分类: algebra"},
#         {"step": "reasoning_1", "content": {...}},
#         {"step": "verification", "content": {...}},
#     ]
# }
```

---

## 六、前后端使用

```bash
# 后端 API（端口 8000）
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# API 文档: http://localhost:8000/api/docs

# 前端（端口 5173）
cd frontend
npm install
npm run dev
# 页面: http://localhost:5173
```

---

## 七、目录结构重构

将分散的模块按职责归入统一目录：

| 旧位置 | 新位置 | 理由 |
|--------|--------|------|
| `solvers/` | `agents/solver_experts/` | Solver 专家纳入 Agent 层 |
| `solvers/skills/` | `agents/solver_experts/skills/` | Skill 跟随 Solver |
| `cache/` | `rag/cache/` | 缓存纳入 RAG 检索体系 |
| `datasets/` | `database/datasets/` | 数据统一存储 |
| `sample_data/` | `database/datasets/` | 竞赛数据集 |
| `outputs/` | `database/outputs/` | 输出统一 |
| — | `agents/test_agent.py` | 新增自动测试 Agent |

最终目录结构：
```
agents/       🤖 智能体 + Solver专家 + Skills
graph/        🔄 LangGraph 工作流
rag/          📚 RAG检索 + Cache
mcp/          🔌 MCP 工具
configs/      ⚙️ 配置
database/     💾 数据存储
schemas/      📐 数据模型
tools/        🔧 内部工具
evaluation/   📊 评估
frontend/     🖥️ 前端
backend/      🚀 后端
tests/        🧪 测试
```

## 八、测试结果

```
============================= test session =============================
77 passed, 1 skipped, 1 warning in 6.82s

测试覆盖：
  ✅ test_phase1_models_and_client  (20 tests)  - 数据模型 + API 客户端
  ✅ test_phase2_graph              (16 tests)  - LangGraph 工作流
  ✅ test_phase3_solvers            (24 tests)  - 多专家 Solver + Skills
  ✅ test_phase4_rag_and_evaluation (18 tests)  - RAG + 评估 + 集成
```

CLI 验证：
- ✅ `python run.py --mode info` — 系统信息正常（12 节点/14 边）
- ✅ `python user_agent.py --problem "..."` — 比赛入口正常
- ✅ 6 Skills 注册、4 Agents、10 MCP Tools 全部就绪
- ✅ `ReasoningAgent(client=MockClient)` 初始化 + `solve()` 返回正确格式

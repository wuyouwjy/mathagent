# Math-Agent-System 项目文件说明

> 基于 LangGraph + Intern-S 系列模型的多领域数学自动求解智能体系统（挑战杯 2026）

---

## 🌳 项目文件树

```
Math-Agent-System/
│
├── user_agent.py                    ← 🔥 比赛入口（ReasoningAgent + solve）
├── run.py                           ← CLI 主入口（single/batch/interactive/test/info/mcp）
├── run_competition.py               ← 比赛 Runner（JSONL 批量求解）
├── llm_client.py                    ← 本地 LLM 客户端（与环境变量对接）
├── requirements.txt                 ← Python 依赖清单
│
├── agents/                          ← 🤖 智能体层
│   ├── __init__.py                  ←   统一导出
│   ├── classifier_agent.py          ←   领域分类 Agent（18领域→Solver路由）
│   ├── graph_manager_agent.py       ←   工作流编排 Agent（路由+反思管理）
│   ├── evaluation_agent.py          ←   评估+题库管理 Agent（CRUD+缓存+类比）
│   ├── solver_dispatcher.py         ←   Solver 调度器（连接Agent与Solver专家）
│   ├── test_agent.py                ←   自动测试 Agent（导入检查+快速/全量测试）
│   └── solver_experts/              ←   18个Solver专家 + 18个Skills
│       ├── base_solver.py           ←     Solver 抽象基类（LLM+SymPy工具）
│       ├── solver_registry.py       ←     Solver 注册中心（工厂模式）
│       ├── algebra_solver.py        ←     代数 Solver（群/环/域/线性代数）
│       ├── number_theory_solver.py  ←     数论 Solver
│       ├── group_theory_solver.py   ←     群论 Solver
│       ├── real_analysis_solver.py  ←     实分析 Solver
│       ├── pde_solver.py            ←     偏微分方程 Solver
│       ├── ode_solver.py            ←     常微分方程 Solver
│       ├── complex_analysis_solver.py←    复分析 Solver
│       ├── functional_analysis_solver.py← 泛函分析 Solver
│       ├── calculus_of_variations_solver.py←变分法 Solver
│       ├── topology_solver.py       ←     拓扑学 Solver
│       ├── differential_geometry_solver.py←微分几何 Solver
│       ├── algebraic_geometry_solver.py←  代数几何 Solver
│       ├── optimization_solver.py   ←     最优化 Solver
│       ├── probability_solver.py    ←     概率论 Solver
│       ├── statistics_solver.py     ←     统计学 Solver
│       ├── numerical_analysis_solver.py←  数值分析 Solver
│       ├── combinatorics_solver.py  ←     组合数学 Solver
│       ├── mathematical_physics_solver.py←数学物理 Solver
│       └── skills/                  ←    18个领域Skill（prompt+策略+关键词+示例）
│           ├── __init__.py          ←     Skill 注册表 + 基类
│           ├── algebra_skills.py / pde_skills.py / ... (18个)
│
├── graph/                           ← 🔄 LangGraph 工作流引擎
│   ├── __init__.py                  ←   统一导出
│   ├── graph_builder.py             ←   StateGraph 图构建（节点+边+条件路由）
│   ├── workflow.py                  ←   工作流运行器（同步/异步/批量）
│   └── nodes/                       ←   10个工作流节点
│       ├── __init__.py
│       ├── cache_nodes.py           ←     缓存检查+保存
│       ├── parser_node.py           ←     问题解析（规则+LLM）
│       ├── classifier_node.py       ←     领域分类（委托给 ClassifierAgent）
│       ├── rag_node.py              ←     RAG 知识检索
│       ├── solver_node.py           ←     Solver 调度（委托给 SolverDispatcher）
│       ├── verifier_node.py         ←     结果验证（LLM逻辑验证）
│       ├── reflection_node.py       ←     反思重试（委托给 GraphManagerAgent）
│       ├── formatter_node.py        ←     JSON 格式化输出
│       └── error_handler_node.py    ←     异常兜底
│
├── rag/                             ← 📚 RAG 检索 + 缓存
│   ├── __init__.py
│   ├── retriever.py                 ←   统一检索器（ChromaDB向量+关键词回退）
│   ├── theorem_db.py                ←   定理知识库（18领域）
│   ├── formula_db.py                ←   公式知识库（LaTeX）
│   ├── example_db.py                ←   示例题库（Few-shot）
│   ├── chroma_db/                   ←   ChromaDB 向量数据
│   └── cache/                       ←   缓存系统（纳入RAG）
│       ├── __init__.py
│       ├── problem_cache.py         ←     两层缓存（精确哈希+向量语义）
│       └── chroma_db/               ←     缓存向量数据
│
├── mcp/                             ← 🔌 MCP 工具模块（本地离线）
│   ├── __init__.py
│   ├── server.py                    ←   FastMCP 服务器 + 回退交互模式
│   └── tools.py                     ←   10个MCP工具（solve/classify/search/...）
│
├── configs/                         ← ⚙️ 配置管理
│   ├── __init__.py
│   └── settings.py                  ←   全局配置（API/Solver/RAG/Workflow/MCP/Agent）
│
├── schemas/                         ← 📐 数据模型定义
│   ├── __init__.py                  ←   统一导出（MathDomain/MathSolutionOutput/...）
│   ├── math_domains.py              ←   18个数学领域枚举 + Solver 1:1路由映射
│   ├── output_schema.py             ←   标准输出 JSON Schema（Pydantic）
│   └── workflow_state.py            ←   LangGraph 工作流状态 TypedDict
│
├── tools/                           ← 🔧 内部工具
│   ├── __init__.py
│   ├── intern_client.py             ←   Intern-S1 API 客户端（OpenAI协议+限流+重试）
│   └── platform_adapter.py          ←   平台客户端适配器（chat->str → 内部接口）
│
├── evaluation/                      ← 📊 评估 Pipeline
│   ├── __init__.py
│   └── evaluator.py                 ←   批量评估（112题自动运行+评分+检查点）
│
├── utils/                           ← 🛠 工具函数
│   ├── __init__.py
│   └── logger.py                    ←   loguru 日志配置
│
├── database/                        ← 💾 统一数据存储
│   ├── problem_db.json              ←   问题数据库（EvaluationAgent 持久化）
│   ├── datasets/
│   │   └── dev.jsonl               ←    112题竞赛数据集（JSONL 格式）
│   └── outputs/
│       ├── results/                 ←    求解结果
│       ├── evaluation/              ←    评估检查点 + 汇总
│       └── logs/                    ←    运行日志
│
├── backend/                         ← 🚀 FastAPI 后端
│   ├── main.py                      ←   服务入口（CORS+路由注册）
│   ├── requirements.txt             ←   后端依赖
│   ├── data/
│   │   └── problems.json            ←   问题持久化
│   ├── services/
│   │   └── problem_service.py       ←   问题业务逻辑
│   └── api/
│       ├── schemas.py               ←   API Pydantic 模型（含比赛格式字段）
│       ├── solve.py                 ←   求解接口
│       ├── problems.py              ←   题库 CRUD
│       ├── benchmark.py             ←   基准测试
│       ├── dashboard.py             ←   仪表盘统计
│       ├── tasks.py                 ←   任务管理
│       ├── config.py                ←   系统配置
│       └── logs.py                  ←   日志查询
│
├── frontend/                        ← 🖥️ React 前端（Vite + Ant Design）
│   ├── index.html / package.json / vite.config.ts / tsconfig.json
│   └── src/
│       ├── main.tsx                 ←   应用入口 + Ant Design 主题
│       ├── router/index.tsx         ←   路由（9条）
│       ├── layouts/MainLayout.tsx   ←   主布局
│       ├── pages/                   ←   9个页面
│       │   ├── Dashboard.tsx        ←     仪表盘
│       │   ├── ProblemLibrary.tsx   ←     题库
│       │   ├── AgentCenter.tsx      ←     Agent 求解中心
│       │   ├── TaskRecords.tsx      ←     任务记录
│       │   ├── ResultAnalysis.tsx   ←     结果分析
│       │   ├── BenchmarkCenter.tsx  ←     基准测试
│       │   ├── SystemConfig.tsx     ←     系统配置
│       │   ├── LogCenter.tsx        ←     日志中心
│       │   └── About.tsx            ←     关于
│       ├── components/              ←   7个通用组件
│       ├── api/                     ←   8个 API 封装
│       ├── stores/ / hooks/ / types/ / utils/
│
└── tests/                           ← 🧪 测试套件
    ├── test_phase1_models_and_client.py   ← 数据模型+API客户端
    ├── test_phase2_graph.py               ← LangGraph 工作流
    ├── test_phase3_solvers.py             ← 18个Solver专家
    └── test_phase4_rag_and_evaluation.py  ← RAG+评估+集成
```

> 🔥 = 核心入口文件

---

## 关键架构决策

| 决策 | 说明 |
|------|------|
| `agents/solver_experts/` | 18个Solver专家+18个Skills统一在此，不再散落 |
| `rag/cache/` | 缓存纳入RAG体系，相似问题检索+缓存命中一体 |
| `database/` | 所有数据（数据集/输出/问题库）统一管理 |
| `mcp/` | MCP工具独立模块，本地离线运行 |
| `agents/test_agent.py` | 自动测试Agent，一键检查系统完整性 |

## 运行方式

```bash
# 比赛格式
python run_competition.py --input_file database/datasets/dev.jsonl --output_dir outputs/
python user_agent.py --problem "求解 x^2 - 5x + 6 = 0"

# CLI
python run.py --mode info            # 系统信息
python run.py --mode interactive     # 交互求解
python run.py --mode test            # 运行测试
python run.py --mode mcp             # MCP 服务器

# 前后端
cd backend && uvicorn main:app --port 8000 --reload
cd frontend && npm run dev
```

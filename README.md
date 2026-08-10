<p align="center">
  <h1 align="center">🧮 Math-Agent-System T2</h1>
  <p align="center">基于 <b>Intern-S 系列大模型</b> 的数学推理智能体 — 2026 挑战杯·书生赛道</p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python">
    <img src="https://img.shields.io/badge/LLM-Intern--S-orange" alt="Intern-S">
    <img src="https://img.shields.io/badge/version-T2.0-purple" alt="T2">
    <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License">
    <img src="https://img.shields.io/badge/deps-minimal-brightgreen" alt="deps">
  </p>
</p>

---

## 📖 简介

**Math-Agent-System T2** 是为 2026 年度中国青年科技创新"揭榜挂帅"擂台赛·书生赛道设计的数学推理智能体。T2 版本参考了 InternS-main 第一名架构（55分），将**多路线并行求解 + 共识投票 + 条件复核**管线整合为轻量化的 `svragent/` 包，同时保持与现有 `agents/` 目录的向后兼容。

### T2 核心架构（相比 v6 的颠覆性升级）

| 改进项 | v6（10.71% 得分） | T2 |
|--------|-------------------|-----|
| 推理路线 | 单路线求解 | **4 路线并行**（A/D/L/X 不同 stance + temperature） |
| 答案选择 | 单路线直接提取 | **共识投票**（≥2 路线答案等价 → 立即提交） |
| 截断问题 | `max_tokens=8192` → 85% 截断 | **max_tokens=131072** → 消除截断 |
| 答案提取 | 7 层文本正则匹配 | **FINAL: 标记 + AnswerExtractor + AnswerNormalizer** |
| 答案比较 | 无法比较 | **符号等价判定**（分数/小数/百分比别名、集合无序比较） |
| 答案歧义处理 | 无 | **复核阶段**（墙钟门控、独立复核调用、严格解析） |
| 证明题 | 与解答题相同处理 | **4 条独立证明路线**（直接/反证/归纳/极值）+ QED 检测 |
| 工具调用 | 无 | **30+ 有界数学工具**（算术/数论/组合/代数/矩阵/符号） |
| 依赖策略 | 纯 stdlib 内联 | **svragent/ 轻量包**（6 模块，fallback 兜底保证可用性） |

### T2 推理流程

```
solve(problem, metadata)
  ├── 题面规范化（全角→半角、统一空白）
  ├── 响应类型检测（answer / proof）
  ├── WidePipeline.run(session)
  │    ├── 4 条路线并行调用 LLM
  │    │    ├── A: 标准最稳妥独立求解
  │    │    ├── D: 求解后代入复核，冲突重算
  │    │    ├── L: 聚焦逻辑跳跃、边界/退化/反例
  │    │    └── X: 有限计算核优先，精确执行
  │    ├── 答案提取 + 聚类（符号等价判定 answers_equal）
  │    ├── 共识 ≥2 → 提交最优路线全文
  │    ├── 无共识 + 墙钟充裕 → 复核调用 → 解析 VERDICT
  │    └── 兜底：按预注册顺序取第一条含答案路线
  └── Finalizer.finalize(session)
       ├── 非空保证（绝对兜底文案）
       ├── 敏感词审计（题目索引/内部路径泄露检测）
       ├── 语言一致性检查（中文题面→中文回答）
       ├── 长度预算保护（>30k 字符截断保护）
       └── 返回 {"final_response": ..., "trace": [...], "stats": {...}}
```

### 核心特性

- **多路线并行求解**：4 条独立路线各具不同解题"姿态"和 temperature [0.2, 0.5, 0.3, 0.3]，ThreadPoolExecutor 真并行执行
- **共识投票机制**：answers_equal() 符号等价判定 → ≥2 路线答案一致即停止，不再调用复核
- **墙钟门控复核**：路线分歧时，仅当剩余时间充裕才启动复核；复核解析严格（模板复述不算 PASS）
- **131K token 输出**：解决 v6 中 85% 模型输出被截断的核心问题
- **鲁棒答案管线**：FINAL: 标记 → \boxed{} → Marker → 占位符过滤 → LaTeX 标准化 → 分数化简 → 小数规范化
- **30+ 数学工具**：算术/模运算/数论/组合/代数/矩阵/受限表达式求值，TOOL_CALL 协议，所有参数有界
- **证明题专用模式**：4 条独立证明路线 + QED 完成检测，无共识时取第一条完整证明
- **自包含 fallback**：svragent 不可用时自动降级为单路线求解，保证平台兼容性

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
#   "final_response": "解答全文（含 FINAL: 答案）",
#   "trace": [
#     {"step": "routing_signals", "elapsed_s": 0.0, "content": {...}},
#     {"step": "llm_call", "elapsed_s": 15.2, "content": {...}},
#     {"step": "wide_wave", "elapsed_s": 45.8, "content": {...}},
#     {"step": "wide_submit", "elapsed_s": 45.8, "content": {...}},
#     {"step": "finalize", "elapsed_s": 45.8, "content": {...}}
#   ],
#   "stats": {
#     "llm_calls": 4,
#     "elapsed_s": 45.8,
#     "stage": "wide_answer",
#     "response_kind": "answer",
#     "final_source": "wide_consensus",
#     "verification_status": "independent_consensus",
#     "confidence": 0.8
#   }
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
├── user_agent.py              # 【必填】智能体主入口（导入 svragent，含 fallback 兜底）
├── svragent/                  # T2 多路线求解包（轻量，6 模块）
│   ├── __init__.py            # 包导出
│   ├── agent.py               # ReasoningAgent + Finalizer + 题面规范化
│   ├── config.py              # SVRConfig 配置（max_tokens=131072 等）
│   ├── session.py             # SVRSession 会话状态
│   ├── client_wrap.py         # LLMCaller client 响应归一化
│   ├── parser.py              # AnswerExtractor + AnswerNormalizer + answers_equal
│   ├── tools.py               # 30+ 有界数学工具（TOOL_CALL 协议）
│   └── wide.py                # WidePipeline 四路线并行 + 共识投票 + 复核
├── requirements.txt            # 项目依赖清单
├── main.py                     # 本地批量测试 Runner
├── llm_client.py               # 本地调试用 LLM 客户端
├── quick_test.py               # 快速自测脚本
├── agents/                     # 可选辅助模块（分类器、求解器等，向后兼容）
├── prompts/                    # 可选 Prompt 模板
├── tools/                      # 自定义工具函数
└── utils/                      # 通用公共工具脚本
```

> ⚠️ 正式评测仅校验 `user_agent.py` 中的 `ReasoningAgent` 类和方法签名。`svragent/` 为核心管线，`agents/` 保持向后兼容。

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
# 首次试跑建议并发=1，验证链路可用
export LOCAL_MAX_CONCURRENCY=1
python main.py --input_file sample_data/dev.jsonl --output_dir sample_outputs
```

### 5. 验证输出格式

```bash
python - <<'PY'
import json
from pathlib import Path
for path in sorted(Path("sample_outputs").glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    src = data.get("stats", {}).get("final_source", "?")
    print(f"{path.name}: status={data.get('status')} source={src} answer={repr(data.get('final_response',''))[:80]}")
PY
```

### 6. 本地输出格式

```json
{
  "idx": 0,
  "status": "success",
  "final_response": "解答全文...\nFINAL: 72",
  "trace": [
    {"step": "routing_signals", "elapsed_s": 0.0, "content": {...}},
    {"step": "llm_call", "elapsed_s": 15.2, "content": {"purpose": "blind_answer:A", ...}},
    ...
  ],
  "stats": {
    "llm_calls": 4,
    "elapsed_s": 45.8,
    "final_source": "wide_consensus",
    "verification_status": "independent_consensus"
  }
}
```

支持 **断点续跑**：若对应 `idx` 的 json 文件已存在且非空，Runner 自动跳过。

---

## 🔧 可用基座模型

| 模型 | 说明 |
|------|------|
| `intern-s1` | 基础模型 |
| `intern-s1-pro` | 增强模型 |
| `intern-s2-preview` | 最新预览版（推荐，共享 reasoning+content token 预算） |

---

## 📋 常见问题 & T2 对策

| 问题 | 症状 | T2 对策 |
|------|------|--------|
| 模型输出截断 | `max_tokens=8192` → 85% 截断，解答不完整 | **max_tokens=131072**，99.9% 解答不截断 |
| 单一推理路线错误 | 一次计算错误 → 整题零分 | **4 路线并行**，A/D/L/X 不同温度 + 姿态，跨路线纠错 |
| 答案格式不一致 | `0.5` vs `1/2` vs `50%` 被判不等 | **answers_equal()** 符号等价判定（分数/小数/百分比别名） |
| 多小问答案 | 混排成一串被判错 | **multipart 识别 + 分号分隔标准化** |
| 答案含占位符 | 模型写 "最终答案: <最终答案>" → 提取失败 | **占位符过滤**（模板残留/工具载荷/元评论） |
| 复核不可靠 | 模型选"看起来合理"的答案 | **复核严格解析**（模板复述不算 PASS，需实际数学核对内容） |
| JSON 输出干扰 | Intern-S 倾向输出 JSON，污染答案 | **OutputParser** 先剥离 code blocks 再提取 FINAL |
| 英文泄露 | 中文题面 → 英文思维链 | 中文占比检测 + Finalizer 语言一致性检查 |
| API 限流/错误 | 单路线失败 → 整题零分 | **多路线容错**：一条失败其他继续；5 种 client 返回类型兼容 |
| 依赖缺失 | `ModuleNotFoundError` → 零分 | **user_agent.py 含 fallback**：svragent 不可用时自动单路线降级 |

---

## 📋 提交前自检清单

- [ ] 提交根目录包含 `user_agent.py`
- [ ] `ReasoningAgent.__init__` 接受 `client` 参数
- [ ] `solve(problem, metadata)` 返回 `dict` 且包含非空 `final_response`
- [ ] `final_response` 为完整求解过程文本（非仅答案数字）
- [ ] 本地 `sample_data/dev.jsonl` 全部输出 `status: success`
- [ ] 返回值可 JSON 序列化
- [ ] 代码中无硬编码 API Key
- [ ] `svragent/` 包完整且可正常导入
- [ ] trace 和最终输出中无敏感信息（题号、内部路径）

---

## 📄 License

MIT

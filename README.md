<p align="center">
  <h1 align="center">🧮 Math-Agent-System v6</h1>
  <p align="center">基于 <b>Intern-S 系列大模型</b> 的数学推理智能体 — 2026 挑战杯·书生赛道</p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python">
    <img src="https://img.shields.io/badge/LLM-Intern--S-orange" alt="Intern-S">
    <img src="https://img.shields.io/badge/version-v6.0-green" alt="v6">
    <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License">
    <img src="https://img.shields.io/badge/deps-stdlib%20only-brightgreen" alt="zero deps">
  </p>
</p>

---

## 📖 简介

**Math-Agent-System v6** 是为 2026 年度中国青年科技创新"揭榜挂帅"擂台赛·书生赛道设计的数学推理智能体。采用 **多阶段推理 + 自验证 + JSON解析** 架构，核心逻辑完全自包含于 `user_agent.py`，**零外部模块依赖**（仅使用 Python 标准库）。

### v6 核心改进（相比 v5）

| 改进项 | v5（0分版） | v6 修复 |
|--------|-------------|---------|
| JSON 模型输出 | 无法解析，提取到 `"answer": 72` 片段 → Judger 判 `invalid` | **优先 JSON 解析**，递归提取 `answer`/`final_answer`/`result` 等键值 |
| client 返回兼容 | 只处理 `str` 和 `dict["content"]` | **兼容 5 种类型**：str / dict多键 / OpenAI SDK对象 |
| 答案清理 | 无 JSON 片段剥离 | **剥离引号/花括号/逗号**，从 `"answer": 72` → `72` |
| 提示词 | 未禁止 JSON 输出 | **显式禁止 JSON**，强制要求 `ANSWER:` 格式 |
| 弱答案处理 | 仅一次验证 | **Refinement 轮次** + JSON 回退提取 + 兜底扫描 |
| 依赖风险 | 依赖外部模块导入 | **纯 stdlib 实现**，消除 `ModuleNotFoundError` |
| 错误降级 | 随机提取问题文本中的数字 | 统一返回 `"0"`，避免虚假答案干扰 |

### 推理流程

```
Problem → [Solve Prompt（禁止JSON，强制ANSWER格式）]
       → 模型求解（max 8192 tokens）
       → 英文泄露检测 → 中文重试（如需要）
       → 答案提取（3 层优先级）:
           P0: JSON 解析（answer/final_answer/result 等键）
           L1: ANSWER: 标记匹配
           L2: \boxed{} LaTeX
           L3: 中文结论标记（答案为/结果是）
           L4: 数学内容末行
           L5: 非空末行兜底
       → 答案无效 → Refinement 轮次（重新提取）
       → 仍无效 → JSON 回退扫描
       → 仍无效 → _fallback_extract 兜底 → "0"
       → _strip_json_artifacts 清理 → _clean_answer 规范化
       → final_response
```

### 核心特性

- **JSON 优先解析**：Intern-S 模型倾向输出结构化 JSON，v6 能递归解析 JSON 对象/数组/fenced code blocks，提取标准答案键名
- **自包含架构**：全部核心逻辑内联在 `user_agent.py`，零外部模块依赖，平台环境绝不会因 `ModuleNotFoundError` 得零分
- **5 种 client 返回类型兼容**：str / dict / OpenAI SDK 对象均可正确处理
- **答案清理管线**：自动剥离 JSON 语法残留（引号/花括号/逗号），确保 Judger 可解析
- **智能 Refinement**：当答案为空或无效时，自动以更直接的提示词发起第二轮提取
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
#     {"step": "solve", "content": "模型解答摘要..."},
#     {"step": "extract", "content": "策略: primary, 候选: 72"},
#     {"step": "finalize", "content": "最终答案: 72 (策略: primary)"}
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
# v6 兼容所有返回类型：str | dict | OpenAI SDK 对象
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
├── user_agent.py              # 【必填】智能体主入口（ReasoningAgent，纯 stdlib 自包含）
├── requirements.txt            # 项目依赖清单（仅 requests 用于本地调试）
├── main.py                     # 本地批量测试 Runner
├── llm_client.py               # 本地调试用 LLM 客户端（需 INTERN_API_KEY）
├── quick_test.py               # 快速自测脚本
├── agents/                     # 可选辅助模块（分类器、求解器等，安全导入不阻塞）
├── prompts/                    # 可选 Prompt 模板
├── tools/                      # 自定义工具函数
└── utils/                      # 通用公共工具脚本
```

> ⚠️ 正式评测仅校验 `user_agent.py` 中的 `ReasoningAgent` 类和方法签名。`agents/` 和 `prompts/` 为可选的辅助模块，v6 核心逻辑不依赖它们。

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
# 检查所有题目状态和答案长度
python - <<'PY'
import json
from pathlib import Path
for path in sorted(Path("sample_outputs").glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"{path.name}: status={data.get('status')} final_response={repr(data.get('final_response',''))}")
PY
```

### 6. 本地输出格式

```json
{
  "idx": 0,
  "status": "success",
  "final_response": "72",
  "trace": [
    {"step": "solve", "content": "模型解答摘要…"},
    {"step": "extract", "content": "策略: primary, 候选: 72"},
    {"step": "finalize", "content": "最终答案: 72 (策略: primary)"}
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

## 📋 零分常见原因 & v6 防范措施

| 原因 | 症状 | v6 防范措施 |
|------|------|------------|
| JSON 输出未被解析 | `final_response` = `"answer": 72` → 全部 `invalid` | **P0 JSON 解析**，递归提取标准键值 |
| client 返回类型不兼容 | `str(obj)` = `<Object at 0x...>` | **5 种类型兼容**：str / dict多键 / OpenAI SDK |
| `final_response` 含 JSON 片段 | Judger 无法解析数学表达式 | `_strip_json_artifacts` 剥离引号/花括号/逗号 |
| `final_response` 为空 | 校验失败 | **7 层提取 + 3 轮 refinement + "0" 绝对兜底** |
| `ModuleNotFoundError` | 外部模块导入失败 | **纯 stdlib 实现**，零外部模块依赖 |
| 英文思维泄露 | 低质量中文推理 | 中文占比检测 → 自动重试中文 prompt |
| 超时（单题 >20min / 总 >6h） | 被 kill | 单次 max_tokens=8192，refinement 仅按需触发 |
| JSON 序列化失败 | trace 写入错误 | trace 结构确保 JSON 兼容，异常归一化为 str |

---

## 📋 提交前自检清单

- [ ] 提交根目录包含 `user_agent.py`
- [ ] `ReasoningAgent.__init__` 接受 `client` 参数
- [ ] `solve(problem, metadata)` 返回 `dict` 且包含非空 `final_response`
- [ ] 本地 `sample_data/dev.jsonl` 全部输出 `status: success`
- [ ] 返回值可 JSON 序列化
- [ ] 代码中无硬编码 API Key
- [ ] 未依赖本地绝对路径
- [ ] trace 和日志中无敏感信息
- [ ] 干净环境（新 venv）中可正常导入

---

## 📄 License

MIT

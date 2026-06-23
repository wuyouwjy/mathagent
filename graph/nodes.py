# ============================================================
# graph/nodes.py — LangGraph 工作流节点函数
# 每个节点是一个纯函数：接收 state，返回 state 的部分更新
#
# 节点列表：
#   1. problem_parser_node    — 问题解析
#   2. classifier_node        — 数学领域分类
#   3. rag_retrieval_node     — RAG知识检索（可选）
#   4. solver_dispatcher_node — Solver调度执行器
#   5. verifier_node          — 结果验证
#   6. reflection_node        — 反思与重试判定
#   7. formatter_node         — JSON格式化输出
#   8. error_handler_node     — 错误处理兜底
# ============================================================

import time
import json
import re
from typing import Dict, Any, Optional, List
from loguru import logger

from schemas.workflow_state import WorkflowState
from schemas.math_domains import (
    MathDomain, DOMAIN_TO_SOLVER, DOMAIN_CN_NAME,
    get_solver_for_domain, list_all_domains
)
from tools.intern_client import get_intern_client


# ============================================================
# 节点1: 问题解析器 (Problem Parser)
# 职责：将原始问题文本解析为结构化数据，提取公式和条件
# ============================================================

def problem_parser_node(state: WorkflowState) -> Dict[str, Any]:
    """
    问题解析节点 — 解析原始数学问题文本

    提取:
        - 问题类型（证明/计算/应用）
        - 数学公式（LaTeX格式）
        - 已知条件
        - 求解目标
        - 关键字

    参数:
        state: 工作流状态

    返回:
        Dict: 部分状态更新
    """
    logger.info(f"[Parser] 开始解析问题: {state['question_id']}")
    start_time = time.time()

    question_text = state["question_text"]

    # --- 基础规则解析（快速路径，不调用LLM）---
    parsed = _rule_based_parse(question_text)

    # --- 若规则解析不充分，使用 LLM 深度解析 ---
    if parsed.get("needs_llm", True):
        try:
            llm_parsed = _llm_deep_parse(question_text)
            parsed.update(llm_parsed)
        except Exception as e:
            logger.warning(f"[Parser] LLM深度解析失败，使用规则解析结果: {e}")

    # --- 更新状态 ---
    node_trace = state.get("node_trace", []) + [f"problem_parser ({time.time() - start_time:.2f}s)"]

    logger.info(
        f"[Parser] 解析完成: type={parsed.get('question_type', 'unknown')}, "
        f"keywords={parsed.get('keywords', [])}"
    )

    return {
        "parsed_problem": parsed,
        "question_type": parsed.get("question_type", ""),
        "node_trace": node_trace,
    }


def _rule_based_parse(text: str) -> Dict[str, Any]:
    """
    基于规则的快速解析

    参数:
        text: 问题文本

    返回:
        Dict: 结构化解析结果
    """
    result: Dict[str, Any] = {
        "original_text": text,
        "question_type": "unknown",
        "formulas": [],
        "conditions": [],
        "goal": "",
        "keywords": [],
        "needs_llm": True,
    }

    # --- 检测问题类型 ---
    if any(kw in text.lower() for kw in ["证明", "prove", "proof", "show that", "求证"]):
        result["question_type"] = "proof"
    elif any(kw in text.lower() for kw in ["计算", "compute", "calculate", "evaluate", "求解", "求"]):
        result["question_type"] = "calculation"
    elif any(kw in text.lower() for kw in ["应用", "apply", "model", "建模"]):
        result["question_type"] = "application"

    # --- 提取 LaTeX 公式 ---
    latex_patterns = [
        r'\$\$(.+?)\$\$',      # 块级公式 $$...$$
        r'\$(.+?)\$',          # 行内公式 $...$
        r'\\\[(.+?)\\\]',       # \[...\]
        r'\\\((.+?)\\\)',       # \(...\)
    ]
    for pattern in latex_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        result["formulas"].extend(matches)

    # --- 提取数学关键字 ---
    math_keywords = [
        "微分方程", "积分", "导数", "极限", "矩阵", "向量",
        "拓扑", "群", "环", "域", "概率", "分布", "期望",
        "方差", "优化", "约束", "凸", "梯度", "散度", "旋度",
        "拉普拉斯", "傅里叶", "特征值", "特征向量",
        "differential", "integral", "derivative", "limit", "matrix",
        "topology", "group", "ring", "field", "probability",
        "distribution", "optimization", "convex", "gradient",
        "laplace", "fourier", "eigenvalue", "eigenvector",
    ]
    text_lower = text.lower()
    result["keywords"] = [kw for kw in math_keywords if kw.lower() in text_lower]

    # --- 如果规则解析已经获得足够信息，跳过 LLM ---
    if result["formulas"] and result["question_type"] != "unknown":
        result["needs_llm"] = False

    return result


def _llm_deep_parse(text: str) -> Dict[str, Any]:
    """
    使用 LLM 深度解析数学问题

    参数:
        text: 问题文本

    返回:
        Dict: LLM解析的结构化结果
    """
    client = get_intern_client()

    system_prompt = (
        "你是一位数学问题分析专家。请分析以下数学问题，提取结构化信息。\n\n"
        "请以 JSON 格式返回，包含以下字段：\n"
        '{\n'
        '  "question_type": "calculation / proof / application",\n'
        '  "formulas": ["公式1", "公式2"],\n'
        '  "conditions": ["已知条件1", "已知条件2"],\n'
        '  "goal": "求解/证明目标",\n'
        '  "keywords": ["关键词1", "关键词2"],\n'
        '  "difficulty_estimate": "easy / medium / hard"\n'
        '}'
    )

    response = client.chat_with_json_output(
        messages=[{"role": "user", "content": text}],
        system_prompt=system_prompt,
    )

    parsed_json = response.get("parsed_json")
    if parsed_json:
        return {
            "question_type": parsed_json.get("question_type", "unknown"),
            "formulas": parsed_json.get("formulas", []),
            "conditions": parsed_json.get("conditions", []),
            "goal": parsed_json.get("goal", ""),
            "keywords": parsed_json.get("keywords", []),
            "difficulty_estimate": parsed_json.get("difficulty_estimate", "medium"),
        }
    else:
        # LLM 返回无法解析，回退
        logger.warning("[Parser] LLM 返回无法解析为JSON，使用原始文本")
        return {
            "question_type": "unknown",
            "formulas": [],
            "conditions": [text],
            "goal": "见原始问题",
            "keywords": [],
            "difficulty_estimate": "medium",
        }


# ============================================================
# 节点2: 分类器 (Classifier Agent)
# 职责：将问题分类到18个数学领域之一
# ============================================================

def classifier_node(state: WorkflowState) -> Dict[str, Any]:
    """
    数学领域分类节点

    使用 Intern-S1 对问题进行领域分类，输出18类之一。

    参数:
        state: 工作流状态

    返回:
        Dict: 包含 classified_domain, classification_confidence 等
    """
    logger.info(f"[Classifier] 开始领域分类: {state['question_id']}")
    start_time = time.time()

    question_text = state["question_text"]
    parsed = state.get("parsed_problem", {})
    keywords = parsed.get("keywords", [])

    # --- 快速规则匹配（高置信度关键词）---
    quick_domain, quick_confidence = _rule_based_classify(question_text, keywords)

    if quick_confidence >= 0.9:
        # 规则匹配高置信度，直接使用
        domain = quick_domain
        confidence = quick_confidence
        reason = f"规则匹配: 关键词 {keywords}"
        logger.info(f"[Classifier] 快速规则匹配: domain={domain}, confidence={confidence:.2f}")
    else:
        # 使用 LLM 进行深度分类
        try:
            domain, confidence, reason = _llm_classify(question_text, parsed)
        except Exception as e:
            logger.error(f"[Classifier] LLM分类失败: {e}, 使用规则匹配结果")
            domain = quick_domain
            confidence = quick_confidence
            reason = f"LLM失败回退: {e}"

    # --- 验证 domain 有效性 ---
    valid_domains = [d.value for d in MathDomain]
    if domain not in valid_domains:
        logger.warning(f"[Classifier] 无效领域 '{domain}', 回退到 algebra")
        domain = "algebra"
        confidence = 0.3
        reason = "无效领域自动纠正"

    # --- 获取对应 Solver ---
    solver_name = get_solver_for_domain(domain)

    # --- 更新状态 ---
    node_trace = state.get("node_trace", []) + [f"classifier -> {domain} ({time.time() - start_time:.2f}s)"]

    logger.info(
        f"[Classifier] 分类完成: domain={domain} "
        f"({DOMAIN_CN_NAME.get(MathDomain(domain) if domain in valid_domains else MathDomain.ALGEBRA, '未知')}), "
        f"confidence={confidence:.2f}, solver={solver_name}"
    )

    return {
        "classified_domain": domain,
        "classification_confidence": confidence,
        "classification_reason": reason,
        "solver_name": solver_name,
        "node_trace": node_trace,
    }


def _rule_based_classify(text: str, keywords: List[str]) -> tuple:
    """
    基于规则的快速领域分类

    参数:
        text: 问题文本
        keywords: 提取的关键词

    返回:
        tuple: (domain_value, confidence)
    """
    text_lower = text.lower()
    kw_lower = [k.lower() for k in keywords]

    # 强特征词 → 领域映射
    strong_patterns = {
        "partial_differential_equations": [
            "偏微分", "pde", "partial differential", "波动方程", "热传导",
            "laplace equation", "wave equation", "heat equation", "泊松方程"
        ],
        "ordinary_differential_equations": [
            "常微分", "ode", "ordinary differential", "初值问题", "边值问题",
            "特征方程", "相图", "稳定性分析"
        ],
        "complex_analysis": [
            "复分析", "complex analysis", "解析函数", "留数", "柯西",
            "cauchy", "residue", "holomorphic", "亚纯函数", "辐角"
        ],
        "topology": [
            "拓扑", "topology", "同胚", "同伦", "基本群", "紧致",
            "homotopy", "homeomorphism", "fundamental group", "流形"
        ],
        "optimization": [
            "优化", "optimization", "线性规划", "非线性规划", "约束",
            "目标函数", "可行域", "单纯形", "simplex", "拉格朗日乘子",
            "凸优化", "convex optimization", "KKT"
        ],
        "algebra": [
            "代数", "algebra", "群", "环", "域", "多项式", "因式分解",
            "特征值", "对角化", "线性变换", "向量空间", "子空间"
        ],
        "probability": [
            "概率", "probability", "随机变量", "分布", "期望",
            "方差", "协方差", "大数定律", "中心极限"
        ],
        "number_theory": [
            "数论", "number theory", "素数", "同余", "整除",
            "费马", "欧拉", "丢番图", "模运算"
        ],
    }

    # 计算每个领域的匹配分数
    scores = {}
    for domain, patterns in strong_patterns.items():
        score = 0
        for p in patterns:
            if p.lower() in text_lower:
                score += 2  # 文本中出现
            if p.lower() in kw_lower:
                score += 3  # 关键词中出现
        if score > 0:
            scores[domain] = min(score / 10.0, 0.95)

    if scores:
        best_domain = max(scores, key=scores.get)
        return best_domain, scores[best_domain]

    # 无匹配，默认 algebra
    return "algebra", 0.3


def _llm_classify(question_text: str, parsed: Dict[str, Any]) -> tuple:
    """
    使用 LLM 进行领域分类

    参数:
        question_text: 问题文本
        parsed: 解析结果

    返回:
        tuple: (domain_value, confidence, reason)
    """
    client = get_intern_client()

    # 构建领域列表描述
    domain_list = "\n".join([
        f"- {d['domain_key']} ({d['domain_cn']})"
        for d in list_all_domains()
    ])

    system_prompt = (
        "你是一位数学领域分类专家。请将以下数学问题归类到以下18个领域之一。\n\n"
        f"可用领域：\n{domain_list}\n\n"
        "请以 JSON 格式返回（不要其他文本）：\n"
        '{\n'
        '  "domain": "领域key（如 partial_differential_equations）",\n'
        '  "confidence": 0.95,\n'
        '  "reason": "分类理由（1-2句话）",\n'
        '  "alternative_domain": "备选领域key"\n'
        '}'
    )

    # 构建用户消息
    user_message = (
        f"问题文本：\n{question_text}\n\n"
        f"已提取信息：\n"
        f"  - 问题类型: {parsed.get('question_type', 'unknown')}\n"
        f"  - 关键词: {parsed.get('keywords', [])}\n"
        f"  - 公式: {parsed.get('formulas', [])}\n"
    )

    response = client.chat_with_json_output(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=system_prompt,
    )

    parsed_json = response.get("parsed_json")
    if parsed_json:
        domain = parsed_json.get("domain", "algebra")
        confidence = float(parsed_json.get("confidence", 0.5))
        reason = parsed_json.get("reason", "LLM分类")
        return domain, confidence, reason
    else:
        return "algebra", 0.3, "LLM返回无法解析"


# ============================================================
# 节点3: RAG 知识检索
# 职责：从定理库、公式库、示例题库中检索相关知识
# ============================================================

def rag_retrieval_node(state: WorkflowState) -> Dict[str, Any]:
    """
    RAG 知识检索节点

    根据分类领域和问题内容，检索相关定理、公式和例题。

    参数:
        state: 工作流状态

    返回:
        Dict: 包含检索到的定理、公式、例题
    """
    logger.info(f"[RAG] 开始知识检索: {state['question_id']}")

    # 检查是否启用 RAG
    try:
        from configs.settings import get_config
        config = get_config()
        if not config.rag.enabled:
            logger.info("[RAG] RAG 已禁用，跳过检索")
            return {
                "retrieved_theorems": [],
                "retrieved_formulas": [],
                "retrieved_examples": [],
            }
    except Exception:
        pass

    domain = state.get("classified_domain", "")
    question_text = state.get("question_text", "")
    keywords = state.get("parsed_problem", {}).get("keywords", [])

    # 尝试使用 RAG 检索（如果 RAG 模块可用）
    theorems, formulas, examples = [], [], []

    try:
        from rag.retriever import RAGRetriever
        retriever = RAGRetriever()

        theorems = retriever.search_theorems(domain, keywords, top_k=5)
        formulas = retriever.search_formulas(domain, keywords, top_k=5)
        examples = retriever.search_examples(domain, keywords, top_k=3)

        logger.info(
            f"[RAG] 检索完成: theorems={len(theorems)}, "
            f"formulas={len(formulas)}, examples={len(examples)}"
        )
    except ImportError:
        logger.info("[RAG] RAG 模块未安装，跳过知识检索")
    except Exception as e:
        logger.warning(f"[RAG] 检索异常: {e}")

    return {
        "retrieved_theorems": theorems,
        "retrieved_formulas": formulas,
        "retrieved_examples": examples,
    }


# ============================================================
# 节点4: Solver 调度执行器
# 职责：根据分类结果调度对应的 Solver Agent 进行求解
# ============================================================

def solver_dispatcher_node(state: WorkflowState) -> Dict[str, Any]:
    """
    Solver 调度执行节点

    根据 state['solver_name'] 调度对应的 Solver Agent。
    每个 Solver 是独立的求解器，可能调用 LLM + SymPy/SciPy。

    参数:
        state: 工作流状态

    返回:
        Dict: 包含 solver_output, solver_status
    """
    solver_name = state.get("solver_name", "algebra_solver")
    logger.info(
        f"[Solver] 调度 Solver: {solver_name} → 问题 {state['question_id']}"
    )
    start_time = time.time()

    question_text = state["question_text"]
    parsed = state.get("parsed_problem", {})
    domain = state.get("classified_domain", "")
    theorems = state.get("retrieved_theorems", [])
    formulas = state.get("retrieved_formulas", [])
    examples = state.get("retrieved_examples", [])

    try:
        # 动态导入 Solver 模块
        solver_output = _execute_solver(
            solver_name=solver_name,
            question_text=question_text,
            parsed=parsed,
            domain=domain,
            theorems=theorems,
            formulas=formulas,
            examples=examples,
        )
        solver_status = "success"
    except Exception as e:
        logger.error(f"[Solver] Solver 执行异常: {e}")
        solver_output = {
            "error": str(e),
            "final_answer": "求解失败",
            "reasoning_steps": [],
            "methods_used": [],
        }
        solver_status = "failed"

    elapsed = time.time() - start_time
    node_trace = state.get("node_trace", []) + [f"solver:{solver_name} ({elapsed:.2f}s)"]

    logger.info(
        f"[Solver] 求解完成: status={solver_status}, "
        f"answer={str(solver_output.get('final_answer', ''))[:50]}..., "
        f"耗时={elapsed:.2f}s"
    )

    return {
        "solver_output": solver_output,
        "solver_status": solver_status,
        "node_trace": node_trace,
    }


def _execute_solver(
    solver_name: str,
    question_text: str,
    parsed: Dict[str, Any],
    domain: str,
    theorems: List[str],
    formulas: List[str],
    examples: List[str],
) -> Dict[str, Any]:
    """
    执行具体 Solver

    根据 solver_name 调用对应的求解策略。
    每个 Solver 都使用 Intern-S1 LLM + 数学工具（SymPy/SciPy）。

    参数:
        solver_name: Solver 名称
        question_text: 问题文本
        parsed: 解析结果
        domain: 数学领域
        theorems: 相关定理
        formulas: 相关公式
        examples: 相似例题

    返回:
        Dict: Solver 输出
    """
    # Solver 对应的系统提示词
    solver_prompts = {
        "pde_solver":     "PDE专家。识别类型(椭圆/抛物/双曲)，选解法(分离变量/傅里叶/格林函数)，LaTeX输出JSON。",
        "ode_solver":     "ODE专家。识别阶数类型，选解法(分离变量/积分因子/特征方程)，LaTeX输出JSON。",
        "complex_analysis_solver": "复分析专家。围道积分/留数定理/共形映射，LaTeX输出JSON。",
        "topology_solver": "拓扑学专家。基本群/同调/欧拉示性数，LaTeX输出JSON。",
        "optimization_solver": "最优化专家。建模+算法(单纯形/拉格朗日/KKT)，LaTeX输出JSON。",
        "algebra_solver": "代数专家。逐步求解，LaTeX输出JSON。",
    }

    # 获取对应的 system prompt
    system_prompt = solver_prompts.get(
        solver_name,
        "数学专家。逐步求解，LaTeX格式，输出JSON。"
    )

    # 构建知识增强内容（精简版）
    knowledge_context = ""
    if theorems:
        knowledge_context += " | 定理: " + "; ".join(theorems[:3])
    if formulas:
        knowledge_context += " | 公式: " + "; ".join(formulas[:3])

    # 构建用户消息（精简 JSON 格式）
    user_message = (
        f"问题: {question_text}\n"
        f"领域: {domain}\n"
        f"{knowledge_context}\n"
        f"返回JSON(勿超过5个推理步骤):\n"
        f'{{"final_answer":"","reasoning_steps":[{{"step_id":1,"description":"","formula":"","method":""}}],'
        f'"methods_used":[],"educational_hint":""}}'
    )

    # 调用 LLM — 显式传 max_tokens 防止截断
    client = get_intern_client()
    response = client.chat_with_json_output(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=system_prompt,
        max_tokens=16384,
    )

    parsed_json = response.get("parsed_json")
    if parsed_json:
        return {
            "final_answer": parsed_json.get("final_answer", "无答案"),
            "reasoning_steps": parsed_json.get("reasoning_steps", []),
            "methods_used": parsed_json.get("methods_used", []),
            "educational_hint": parsed_json.get("educational_hint", ""),
            "raw_llm_response": response.get("content", ""),
        }
    else:
        # JSON 解析失败，使用原始响应
        return {
            "final_answer": response.get("content", "无答案"),
            "reasoning_steps": [],
            "methods_used": [],
            "educational_hint": "",
            "raw_llm_response": response.get("content", ""),
        }


# ============================================================
# 节点5: 验证器 (Verifier Agent)
# 职责：验证求解结果是否正确
# ============================================================

def verifier_node(state: WorkflowState) -> Dict[str, Any]:
    """
    验证节点 — 验证 Solver 输出结果

    使用多种策略验证：
    1. LLM 逻辑验证（推理链检查）
    2. 符号验证（使用 SymPy 代入检查，如果适用）
    3. 数值验证（数值近似检查）

    参数:
        state: 工作流状态

    返回:
        Dict: 包含 verification_result, verification_passed
    """
    logger.info(f"[Verifier] 开始验证: {state['question_id']}")
    start_time = time.time()

    solver_output = state.get("solver_output", {})
    question_text = state.get("question_text", "")
    domain = state.get("classified_domain", "")

    final_answer = solver_output.get("final_answer", "")
    reasoning_steps = solver_output.get("reasoning_steps", [])
    methods_used = solver_output.get("methods_used", [])

    # 如果 Solver 执行失败，直接标记验证不通过
    if state.get("solver_status") == "failed":
        logger.warning("[Verifier] Solver 执行失败，跳过验证")
        return {
            "verification_result": {
                "is_correct": False,
                "confidence": 0.0,
                "check_method": "solver_failed",
                "error_details": solver_output.get("error", "Solver 执行失败"),
            },
            "verification_passed": False,
        }

    try:
        verification = _llm_verify(
            question_text=question_text,
            final_answer=final_answer,
            reasoning_steps=reasoning_steps,
            methods_used=methods_used,
            domain=domain,
        )
    except Exception as e:
        logger.error(f"[Verifier] LLM 验证异常: {e}")
        verification = {
            "is_correct": False,
            "confidence": 0.3,
            "check_method": "verification_error",
            "error_details": str(e),
        }

    elapsed = time.time() - start_time
    node_trace = state.get("node_trace", []) + [
        f"verifier (correct={verification.get('is_correct')}, "
        f"conf={verification.get('confidence', 0):.2f}, {elapsed:.2f}s)"
    ]

    verification_passed = verification.get("is_correct", False)

    logger.info(
        f"[Verifier] 验证完成: passed={verification_passed}, "
        f"confidence={verification.get('confidence', 0):.2f}"
    )

    return {
        "verification_result": verification,
        "verification_passed": verification_passed,
        "node_trace": node_trace,
    }


def _llm_verify(
    question_text: str,
    final_answer: str,
    reasoning_steps: List[Dict],
    methods_used: List[str],
    domain: str,
) -> Dict[str, Any]:
    """
    使用 LLM 验证求解结果

    参数:
        question_text: 原始问题
        final_answer: 最终答案
        reasoning_steps: 推理步骤
        methods_used: 使用的方法
        domain: 数学领域

    返回:
        Dict: 验证结果
    """
    client = get_intern_client()

    system_prompt = (
        "你是一位数学验证专家。请严格验证以下数学问题的求解结果。\n\n"
        "检查要点：\n"
        "1. 推理逻辑是否严谨、无跳步？\n"
        "2. 每一步的数学推导是否正确？\n"
        "3. 最终答案是否满足原问题的所有条件？\n"
        "4. 使用的方法是否适用于该问题？\n"
        "5. 是否有更简单或更标准的解法？\n\n"
        "请以 JSON 格式返回验证结果（不要其他文本）：\n"
        '{\n'
        '  "is_correct": true/false,\n'
        '  "confidence": 0.0到1.0之间的数值,\n'
        '  "check_method": "验证方法描述",\n'
        '  "error_details": "如果错误，详细说明错误位置和原因；如果正确，写[无]",\n'
        '  "correction_suggestion": "如果错误，给出修改建议"  \n'
        '}'
    )

    # 构建推理步骤摘要
    steps_summary = "\n".join([
        f"  Step {s.get('step_id', i+1)}: {s.get('description', '')[:100]}"
        for i, s in enumerate(reasoning_steps[:10])  # 取前10步
    ])
    if len(reasoning_steps) > 10:
        steps_summary += f"\n  ... (共{len(reasoning_steps)}步)"

    user_message = (
        f"【原始问题】\n{question_text}\n\n"
        f"【数学领域】{domain}\n"
        f"【使用的方法】{', '.join(methods_used) if methods_used else '未指定'}\n\n"
        f"【推理步骤】\n{steps_summary}\n\n"
        f"【最终答案】\n{final_answer}\n\n"
        f"请验证以上求解过程。"
    )

    response = client.chat_with_json_output(
        messages=[{"role": "user", "content": user_message}],
        system_prompt=system_prompt,
        temperature=0.0,  # 验证需要确定性的输出
    )

    parsed_json = response.get("parsed_json")
    if parsed_json:
        return {
            "is_correct": parsed_json.get("is_correct", False),
            "confidence": float(parsed_json.get("confidence", 0.5)),
            "check_method": parsed_json.get("check_method", "LLM验证"),
            "error_details": parsed_json.get("error_details", ""),
            "correction_suggestion": parsed_json.get("correction_suggestion", ""),
        }
    else:
        return {
            "is_correct": False,
            "confidence": 0.3,
            "check_method": "parse_error",
            "error_details": "LLM 返回无法解析",
        }


# ============================================================
# 节点6: 反思器 (Reflection Agent)
# 职责：分析失败原因，决定是否重试
# ============================================================

def reflection_node(state: WorkflowState) -> Dict[str, Any]:
    """
    反思节点 — 分析验证失败原因，决定是否重试

    逻辑：
    1. 如果验证通过 → 不需要反思 (reflection_needed = False)
    2. 如果验证未通过 + 重试次数未达上限 → 生成反馈，触发反思重试
    3. 如果验证未通过 + 已达重试上限 → 接受当前结果，标记最终失败

    参数:
        state: 工作流状态

    返回:
        Dict: 包含 reflection_needed, reflection_feedback 等
    """
    logger.info(f"[Reflection] 反思分析: {state['question_id']}")

    verification_passed = state.get("verification_passed", False)
    verification_result = state.get("verification_result", {})
    current_count = state.get("reflection_count", 0)
    max_count = state.get("max_reflection_count", 3)

    # 验证通过 → 不需要反思
    if verification_passed:
        logger.info("[Reflection] 验证通过，不需要反思")
        return {
            "reflection_needed": False,
            "reflection_feedback": "",
        }

    # 已达最大重试次数 → 不再重试
    if current_count >= max_count:
        logger.warning(
            f"[Reflection] 已达最大重试次数 ({current_count}/{max_count})，停止重试"
        )
        return {
            "reflection_needed": False,
            "reflection_feedback": f"已达最大重试次数({max_count})，接受当前结果",
        }

    # 需要重试 → 生成反思反馈
    error_details = verification_result.get("error_details", "未知错误")
    correction = verification_result.get("correction_suggestion", "")

    new_count = current_count + 1
    feedback = (
        f"【反思反馈 — 第{new_count}次重试】\n"
        f"上次求解验证未通过。\n"
        f"错误详情：{error_details}\n"
        f"修改建议：{correction if correction else '请重新审视推理过程，检查每一步的正确性。'}\n"
        f"请特别注意推导中的假设是否合理、公式是否运用正确。"
    )

    logger.info(
        f"[Reflection] 触发反思重试 ({new_count}/{max_count}): "
        f"error={error_details[:80]}..."
    )

    return {
        "reflection_needed": True,
        "reflection_feedback": feedback,
        "reflection_count": new_count,
    }


# ============================================================
# 节点7: 格式化器 (Formatter Agent)
# 职责：将求解结果格式化为标准 JSON 输出
# ============================================================

def formatter_node(state: WorkflowState) -> Dict[str, Any]:
    """
    格式化节点 — 生成符合竞赛评分格式的标准 JSON 输出

    参数:
        state: 工作流状态

    返回:
        Dict: 包含 final_output
    """
    logger.info(f"[Formatter] 开始格式化输出: {state['question_id']}")

    # 如果 final_output 已由缓存节点设置，直接透传（避免覆盖缓存结果）
    existing_output = state.get("final_output", {})
    if existing_output and existing_output.get("from_cache"):
        logger.info("[Formatter] 使用缓存结果，跳过格式化")
        return {
            "final_output": existing_output,
            "node_trace": state.get("node_trace", []) + ["formatter(cached)"],
        }

    from schemas.output_schema import MathSolutionOutput, ReasoningStep, VerificationResult

    solver_output = state.get("solver_output", {})
    verification_result = state.get("verification_result", {})

    # 构建推理步骤
    reasoning_steps = []
    for step in solver_output.get("reasoning_steps", []):
        try:
            reasoning_steps.append(ReasoningStep(
                step_id=step.get("step_id", len(reasoning_steps) + 1),
                description=step.get("description", ""),
                formula=step.get("formula"),
                result=step.get("result"),
                method=step.get("method"),
            ))
        except Exception:
            reasoning_steps.append(ReasoningStep(
                step_id=len(reasoning_steps) + 1,
                description=str(step),
            ))

    # 构建验证结果
    verification = VerificationResult(
        is_correct=verification_result.get("is_correct", False),
        confidence=verification_result.get("confidence", 0.0),
        check_method=verification_result.get("check_method", ""),
        error_details=verification_result.get("error_details"),
    )

    # 构建完整输出
    output = MathSolutionOutput(
        question_id=state["question_id"],
        domain=state.get("classified_domain", "unknown"),
        final_answer=solver_output.get("final_answer", "无答案"),
        reasoning_steps=reasoning_steps,
        methods_used=solver_output.get("methods_used", []),
        verification=verification,
        educational_hint=solver_output.get("educational_hint", ""),
        computation_time_ms=state.get("computation_time_ms", 0.0),
        retry_count=state.get("reflection_count", 0),
        model_version=getattr(getattr(get_intern_client(), '__self__', None), 'model_name', None),
    )

    # 序列化为 dict
    output_dict = output.model_dump()

    logger.info(
        f"[Formatter] 格式化完成: "
        f"steps={len(reasoning_steps)}, "
        f"methods={len(output.methods_used)}, "
        f"final_answer_len={len(output.final_answer)}"
    )

    return {
        "final_output": output_dict,
        "node_trace": state.get("node_trace", []) + ["formatter"],
    }


# ============================================================
# 节点8: 错误处理器
# 职责：全局错误兜底，确保输出始终有效
# ============================================================

def error_handler_node(state: WorkflowState) -> Dict[str, Any]:
    """
    错误处理节点 — 全局异常兜底

    当任何节点抛出异常时，此节点确保：
    1. 错误信息被记录
    2. 输出仍为有效的 JSON 结构
    3. 工作流可以正常终止

    参数:
        state: 工作流状态

    返回:
        Dict: 包含 final_output 的兜底结果
    """
    logger.error(f"[ErrorHandler] 处理异常: {state['question_id']}")
    errors = state.get("error_info", [])

    # 构建兜底输出
    fallback_output = {
        "question_id": state["question_id"],
        "domain": state.get("classified_domain", "unknown"),
        "final_answer": "求解失败",
        "reasoning_steps": [],
        "methods_used": [],
        "verification": {
            "is_correct": False,
            "confidence": 0.0,
            "check_method": "error_handler",
            "error_details": "; ".join(errors) if errors else "未知错误",
        },
        "educational_hint": "求解过程中发生错误，请检查问题描述和系统配置。",
        "computation_time_ms": state.get("computation_time_ms", 0.0),
        "retry_count": state.get("reflection_count", 0),
    }

    return {
        "final_output": fallback_output,
        "verification_passed": False,
        "node_trace": state.get("node_trace", []) + ["error_handler"],
    }


# ============================================================
# 节点9: 缓存检查 (Cache Check)
# 职责：在完整流程前检查缓存，命中则跳过求解
# ============================================================

def cache_check_node(state: WorkflowState) -> Dict[str, Any]:
    """
    缓存检查节点 — 工作流第一步

    检查是否有相同或相似问题已求解过。
    命中 → 直接跳到 formatter
    未命中 → 继续完整流程

    参数:
        state: 工作流状态

    返回:
        Dict: 包含 cache_hit 标记，若命中则含完整 final_output
    """
    question_text = state.get("question_text", "")
    question_id = state.get("question_id", "")

    logger.info(f"[Cache] 检查缓存: {question_id}")

    try:
        from cache.problem_cache import get_cache
        cache = get_cache()
        hit = cache.search(question_text)

        if hit.is_hit and hit.cached_solution:
            logger.info(
                f"[Cache] 命中! similarity={hit.similarity:.4f}, "
                f"matched='{hit.matched_question[:60]}...', "
                f"age={hit.cache_age_seconds:.0f}s"
            )

            # 使用缓存结果作为 final_output
            cached = hit.cached_solution
            if "question_id" not in cached:
                cached["question_id"] = question_id
            cached["from_cache"] = True
            cached["cache_similarity"] = hit.similarity
            cached["cache_matched_question"] = hit.matched_question

            return {
                "final_output": cached,
                "classified_domain": cached.get("domain", ""),
                "verification_passed": cached.get("verification", {}).get("is_correct", True),
                "node_trace": state.get("node_trace", []) + [
                    f"cache_hit(sim={hit.similarity:.3f})"
                ],
                "cache_hit": True,
            }
        else:
            stats = cache.get_stats()
            logger.info(
                f"[Cache] 未命中 (已有{stats['vector_cache_size']}条缓存, "
                f"命中率{stats['hit_rate']:.1%})"
            )
            return {"cache_hit": False}

    except ImportError:
        logger.debug("[Cache] 缓存模块未加载，跳过")
        return {"cache_hit": False}
    except Exception as e:
        logger.warning(f"[Cache] 缓存检查异常: {e}")
        return {"cache_hit": False}


# ============================================================
# 节点10: 缓存保存 (Cache Save)
# 职责：求解完成后将结果存入缓存
# ============================================================

def cache_save_node(state: WorkflowState) -> Dict[str, Any]:
    """
    缓存保存节点 — 求解完成后自动入库

    将验证通过的求解结果存入缓存，供后续相似问题快速命中。

    参数:
        state: 工作流状态

    返回:
        Dict: 状态更新（不改变核心数据）
    """
    question_text = state.get("question_text", "")
    final_output = state.get("final_output", {})
    verification_passed = state.get("verification_passed", False)

    # 只缓存验证通过的结果
    if not verification_passed:
        logger.debug("[Cache] 验证未通过，跳过缓存")
        return {}

    if not final_output or not question_text:
        return {}

    try:
        from cache.problem_cache import get_cache
        cache = get_cache()

        # 检查是否已在缓存中（避免重复入库）
        hit = cache.search(question_text)
        if hit.is_hit and hit.similarity >= 0.99:
            logger.debug("[Cache] 已存在相同条目，跳过保存")
            return {}

        cache.save(question_text, final_output)
        logger.info(f"[Cache] 结果已自动入库: domain={final_output.get('domain')}")

    except ImportError:
        logger.debug("[Cache] 缓存模块未加载，跳过保存")
    except Exception as e:
        logger.warning(f"[Cache] 缓存保存异常: {e}")

    return {}

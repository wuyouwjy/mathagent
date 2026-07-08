# ============================================================
# graph/nodes/parser_node.py — 问题解析节点
# ============================================================

import time
import re
from typing import Dict, Any, List
from loguru import logger


def problem_parser_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    问题解析节点 — 解析原始数学问题文本

    提取: 问题类型、数学公式（LaTeX格式）、已知条件、求解目标、关键字
    """
    logger.info(f"[Parser] 开始解析问题: {state['question_id']}")
    start_time = time.time()

    question_text = state["question_text"]

    # 基础规则解析（快速路径，不调用LLM）
    parsed = _rule_based_parse(question_text)

    # 若规则解析不充分，使用 LLM 深度解析
    if parsed.get("needs_llm", True):
        try:
            llm_parsed = _llm_deep_parse(question_text)
            parsed.update(llm_parsed)
        except Exception as e:
            logger.warning(f"[Parser] LLM深度解析失败，使用规则解析结果: {e}")

    node_trace = state.get("node_trace", []) + [f"problem_parser ({time.time() - start_time:.2f}s)"]

    logger.info(f"[Parser] 解析完成: type={parsed.get('question_type', 'unknown')}, "
                f"keywords={parsed.get('keywords', [])}")

    return {
        "parsed_problem": parsed,
        "question_type": parsed.get("question_type", ""),
        "node_trace": node_trace,
    }


def _rule_based_parse(text: str) -> Dict[str, Any]:
    """基于规则的快速解析"""
    result: Dict[str, Any] = {
        "original_text": text,
        "question_type": "unknown",
        "formulas": [],
        "conditions": [],
        "goal": "",
        "keywords": [],
        "needs_llm": True,
    }

    # 检测问题类型
    if any(kw in text.lower() for kw in ["证明", "prove", "proof", "show that", "求证"]):
        result["question_type"] = "proof"
    elif any(kw in text.lower() for kw in ["计算", "compute", "calculate", "evaluate", "求解", "求"]):
        result["question_type"] = "calculation"
    elif any(kw in text.lower() for kw in ["应用", "apply", "model", "建模"]):
        result["question_type"] = "application"

    # 提取 LaTeX 公式
    latex_patterns = [
        r'\$\$(.+?)\$\$', r'\$(.+?)\$',
        r'\\\[(.+?)\\\]', r'\\\((.+?)\\\)',
    ]
    for pattern in latex_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        result["formulas"].extend(matches)

    # 提取数学关键字
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

    if result["formulas"] and result["question_type"] != "unknown":
        result["needs_llm"] = False

    return result


def _llm_deep_parse(text: str) -> Dict[str, Any]:
    """使用 LLM 深度解析数学问题"""
    from tools.intern_client import get_intern_client

    client = get_intern_client()

    system_prompt = (
        "你是一位数学问题分析专家。请分析以下数学问题，提取结构化信息。\n\n"
        "请以 JSON 格式返回，包含以下字段：\n"
        '{"question_type": "calculation / proof / application", '
        '"formulas": ["公式1", "公式2"], '
        '"conditions": ["已知条件1"], '
        '"goal": "求解/证明目标", '
        '"keywords": ["关键词1"], '
        '"difficulty_estimate": "easy / medium / hard"}'
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
        logger.warning("[Parser] LLM 返回无法解析为JSON")
        return {
            "question_type": "unknown",
            "formulas": [],
            "conditions": [text],
            "goal": "见原始问题",
            "keywords": [],
            "difficulty_estimate": "medium",
        }

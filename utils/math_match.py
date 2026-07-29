# ============================================================
# utils/math_match.py — 数学答案模糊匹配（共享模块）
# 用于 benchmark.py 和 evaluator.py
# ============================================================
import re
from typing import List

# ---- LaTeX → Unicode 符号映射 ----
_LATEX_SYMBOLS: dict = {
    'le': '≤', 'leq': '≤', 'ge': '≥', 'geq': '≥', 'ne': '≠', 'neq': '≠',
    'approx': '≈', 'equiv': '≡', 'simeq': '≃', 'cong': '≅',
    'times': '×', 'cdot': '·', 'pm': '±', 'mp': '∓', 'div': '÷',
    'infty': '∞', 'partial': '∂', 'nabla': '∇', 'int': '∫', 'sum': 'Σ',
    'prod': 'Π', 'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ',
    'epsilon': 'ε', 'pi': 'π', 'theta': 'θ', 'lambda': 'λ', 'sigma': 'σ',
    'omega': 'ω', 'varphi': 'φ', 'rho': 'ρ', 'mu': 'μ', 'to': '→',
    'rightarrow': '→', 'implies': '⇒', 'iff': '⇔', 'leftarrow': '←',
    'subset': '⊂', 'subseteq': '⊆', 'supset': '⊃', 'supseteq': '⊇',
    'in': '∈', 'notin': '∉', 'forall': '∀', 'exists': '∃', 'emptyset': '∅',
    'log': 'log', 'ln': 'ln', 'exp': 'exp',
    'sin': 'sin', 'cos': 'cos', 'tan': 'tan', 'cot': 'cot',
    'arcsin': 'arcsin', 'arccos': 'arccos', 'arctan': 'arctan',
    'lim': 'lim', 'max': 'max', 'min': 'min', 'gcd': 'gcd', 'lcm': 'lcm',
    'langle': '⟨', 'rangle': '⟩', 'lceil': '⌈', 'rceil': '⌉',
    'lfloor': '⌊', 'rfloor': '⌋',
    'mathbb': '', 'mathbf': '', 'mathrm': '', 'mathcal': '', 'mathfrak': '',
}

# ---- 中文数学文本归一化 ----
_CHINESE_MATH: dict = {
    '其中': ',', '以及': ',', '或者': '或',
    '所以': '', '因此': '', '故': '', '即': '', '则': '',
    '答案是': '', '结果为': '', '可得': '', '解得': '',
    '证明成立': '', '证毕': '', '综上所述': '',
    '：': ':', '，': ',', '；': ';',
}


def _norm_math(text: str) -> str:
    """归一化数学文本：LaTeX→Unicode，中文→ASCII"""
    s = text.strip()

    # 0. 中文数学词汇归一化
    for cn, en in _CHINESE_MATH.items():
        s = s.replace(cn, en)

    # 1. 去 LaTeX 环境标记
    s = re.sub(r'\$+', '', s)
    s = re.sub(r'\\[\(\[]|\\[\)\]]', '', s)

    # 2. 结构型 LaTeX 命令（括号类）→ 保留结构
    s = re.sub(r'\\frac\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
               r'(\1)/(\2)', s)
    s = re.sub(r'\\sqrt\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
               r'sqrt(\1)', s)

    # 3. 字体命令 → 去掉包装，保留内容
    s = re.sub(r'\\(?:mathbb|mathbf|mathrm|mathcal|mathfrak)\s*\{([^}]*)\}', r'\1', s)

    # 4. \text{...} → 只留内容
    s = re.sub(r'\\text\s*\{([^}]*)\}', r'\1', s)

    # 5. ASCII 数学符号 → Unicode
    s = s.replace('<=', '≤').replace('>=', '≥').replace('!=', '≠')
    s = s.replace('->', '→').replace('<-', '←').replace('=>', '⇒')
    s = s.replace('~=', '≈').replace('==', '=')

    # 6. LaTeX 命令 → Unicode 符号
    for latex, uni in _LATEX_SYMBOLS.items():
        s = re.sub(r'\\' + latex + r'\b', uni, s, flags=re.IGNORECASE)

    # 7. 赋值符号归一化：(n,m)= 或 x= → 剥离
    s = re.sub(r'\([a-zA-Z_,\s]+\)\s*=\s*', '', s)
    s = re.sub(r'\b[a-zA-Z]+\s*=\s*', '', s)

    # 8. 去剩余 LaTeX 残骸
    s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)
    s = re.sub(r'[\\{}]', '', s)

    # 9. 统一分隔符
    s = re.sub(r'[,;，；或]', ',', s)
    s = s.replace('和', ',')

    # 10. 压缩空白 → 小写
    s = re.sub(r'\s+', '', s)
    return s.strip().lower()


def _extract_answer_numbers(text: str) -> List[str]:
    """提取数值，排除下标中的数字（如 x_3 中的 3）"""
    clean = re.sub(r'[a-zA-Z]_\d+', '', text)
    clean = re.sub(r'[a-zA-Z]\^\{?\d+\}?', '', clean)
    return re.findall(r'\d+\.?\d*', clean)


def _numbers_close(nums_a: List[str], nums_b: List[str], rtol: float = 0.015) -> bool:
    """判断两组数值是否足够接近（1.5%相对容差）"""
    if not nums_a or not nums_b:
        return False
    for sa in nums_a:
        for sb in nums_b:
            try:
                fa, fb = float(sa), float(sb)
            except ValueError:
                continue
            if fb == 0:
                if fa == 0:
                    return True
                continue
            if abs(fa - fb) / abs(fb) <= rtol:
                return True
    return False


def _all_nums_match(shorter: List[str], longer: List[str], rtol: float = 0.015) -> bool:
    """判断shorter中每个数值在longer中都有容差内的匹配"""
    matched = [False] * len(shorter)
    longs = [float(x) for x in longer]
    for i, s in enumerate(shorter):
        try:
            fs = float(s)
        except ValueError:
            continue
        for j, fl in enumerate(longs):
            if fl == 0:
                if fs == 0:
                    matched[i] = True
                    break
                continue
            if abs(fs - fl) / abs(fl) <= rtol:
                matched[i] = True
                break
    return all(matched)


def _nonnum_part(s: str) -> str:
    """提取非数值部分（去数字和空白）"""
    return re.sub(r'[\d.\s]+', '', s)


def fuzzy_match(predicted: str, ground_truth: str) -> bool:
    """
    模糊比对数学答案——多级策略

    1. 精确匹配
    2. 包含匹配
    3. 核心公式匹配（去中文）
    4. 数值容差匹配（1.5% + 非数值部分匹配）
    5. SymPy 符号等价
    """
    if not predicted or not ground_truth:
        return False

    a, b = _norm_math(predicted), _norm_math(ground_truth)

    # 1) 精确匹配
    if a == b:
        return True

    # 2) 包含匹配
    if b in a or a in b:
        return True

    # 3) 核心公式匹配（去非ASCII数学字符）
    a_core = re.sub(r'[^\x00-\x7f≤≥≠≈±×÷→←⇒⇔∈∉∀∃∞∂∇∫∑∏‖⟨⟩⌈⌉⌊⌋]+', '', a)
    b_core = re.sub(r'[^\x00-\x7f≤≥≠≈±×÷→←⇒⇔∈∉∀∃∞∂∇∫∑∏‖⟨⟩⌈⌉⌊⌋]+', '', b)
    if a_core and b_core and (a_core == b_core or b_core in a_core or a_core in b_core):
        return True

    # 4) 数值容差匹配（含回归系数/赋值等价）
    nums_a = _extract_answer_numbers(predicted)
    nums_b = _extract_answer_numbers(ground_truth)
    if nums_a and nums_b:
        # 4a) 数值完全一致
        if set(nums_a) == set(nums_b):
            na, nb = _nonnum_part(a), _nonnum_part(b)
            if na and nb and (na == nb or nb in na or na in nb):
                return True
        # 4b) 数值容差接近 + 非数值匹配
        if set(nums_a) != set(nums_b) and _numbers_close(nums_a, nums_b):
            na, nb = _nonnum_part(a), _nonnum_part(b)
            if na and nb:
                if na == nb or nb in na or na in nb:
                    return True
            elif not na and not nb:
                return True
        # 4c) 纯数值比对：双方所有数值都在容差范围内匹配（处理回归系数、范数等）
        if len(nums_a) <= len(nums_b) and len(nums_a) > 0:
            if _all_nums_match(nums_a, nums_b):
                return True
        elif len(nums_b) <= len(nums_a) and len(nums_b) > 0:
            if _all_nums_match(nums_b, nums_a):
                return True

    # 5) SymPy 符号等价
    try:
        import sympy as sp
        return bool(sp.nsimplify(a) == sp.nsimplify(b))
    except Exception:
        return False


# ============================================================
# LLM 语义验证（fuzzy_match 失败后的兜底）
# ============================================================

_LLM_VERIFY_PROMPT = """你是一位严谨的数学答案评判专家。你的任务是比较「预测答案」和「标准答案」，判断它们在数学上是否等价。

请按以下步骤进行：
1. 将两个答案分别转化为统一的规范数学表达：
   - 去掉无关的修饰词、格式标记
   - 统一数学符号（如 <= 和 ≤ 等价）
   - 提取核心数学含义（如完整证明过程和"已证明"等价）
   - 对于定理证明题，关注结论是否一致
   - 对于计算题，关注数值是否在合理误差内一致
2. 判断两个规范化后的答案在数学上是否等价：
   - 数值答案：允许 1% 以内的舍入误差
   - 表达式答案：代数等价即可，不要求形式完全一致
   - 证明题：只要核心结论和逻辑正确即可
   - 参数估计：如 y=0.5+1.6x 与 β₀=0.5,β₁=1.6 等价

请严格按以下 JSON 格式输出（不要输出其他内容）：
{"pred_normalized": "预测答案的规范化形式", "gt_normalized": "标准答案的规范化形式", "is_equivalent": true/false, "confidence": 0.0~1.0, "reason": "简要判断理由"}"""


def llm_verify_match(predicted: str, ground_truth: str, question: str = "") -> dict:
    """
    调用 LLM 判断两个答案是否数学等价。

    返回: {"is_equivalent": bool, "confidence": float, "reason": str,
           "pred_normalized": str, "gt_normalized": str}
    失败时返回 is_equivalent=False, confidence=0
    """
    try:
        from tools.intern_client import get_intern_client
        client = get_intern_client()

        user_msg = (
            f"【原始问题】\n{question[:500]}\n\n"
            f"【预测答案】\n{predicted[:600]}\n\n"
            f"【标准答案】\n{ground_truth[:300]}\n\n"
            f"请判断以上两个答案在数学上是否等价。"
        )

        response = client.chat_with_json_output(
            messages=[{"role": "user", "content": user_msg}],
            system_prompt=_LLM_VERIFY_PROMPT,
            temperature=0.0,
        )
        parsed = response.get("parsed_json") if isinstance(response, dict) else None
        if parsed and isinstance(parsed, dict):
            return {
                "is_equivalent": parsed.get("is_equivalent", False),
                "confidence": float(parsed.get("confidence", 0.5)),
                "reason": parsed.get("reason", ""),
                "pred_normalized": parsed.get("pred_normalized", ""),
                "gt_normalized": parsed.get("gt_normalized", ""),
            }
    except Exception:
        pass

    return {"is_equivalent": False, "confidence": 0.0, "reason": "LLM验证调用失败",
            "pred_normalized": "", "gt_normalized": ""}

"""Prompts for Intern-S系列模型 — 中文结构化输出 + 防截断 + 防英文泄露"""

COMPUTE_SOLVE_PROMPT = """题目（{domain}）：

{problem}

【输出格式要求】
请按以下结构输出，每个标签独占一行：

【策略规划】用1-2句话分析本题的核心难点和你选择的方法路径（必须针对本题具体内容，不要泛泛而谈）

【解题过程】
（用中文写出完整解题步骤，每步写清楚"因为...所以..."。数学公式用LaTeX包裹。不要出现英文自言自语。步骤精炼，不要重复。）

【关键洞察】用1句话点出解题过程中的关键转折点或核心技巧（必须针对本题，如"通过换元将积分转化为Beta函数"而非泛泛的"从局部到整体"）

ANSWER: <最终答案（只写答案本身，不要写推理过程，不超过两行）>

【启发性总结】用1-2句话说明此结论在更广数学背景下的意义，以及"如果某个条件改变会怎样"的延伸思考（必须针对本题结论具体分析）"""

PROOF_SOLVE_PROMPT = """题目（{domain}）：

{problem}

【输出格式要求】
请按以下结构输出，每个标签独占一行：

【策略规划】用1-2句话分析本题的核心难点和证明思路选择（必须针对本题具体内容）

【证明过程】
（用中文写出完整证明，分步骤：分析条件→构建推理链→得出结论。数学符号用LaTeX。不要出现英文自言自语。证明精炼。）

【关键洞察】用1句话点出证明中的关键构造或转折（必须针对本题，如"构造辅助函数g(x)=f(x)-x^n将问题归约为Rolle定理"而非泛泛的"构造辅助函数"）

ANSWER: <具体数学结论（必须包含关键等式或表达式，不要只写"命题得证"。不超过两行）>

【启发性总结】用1-2句话说明此结论在更广数学背景下的意义，以及"如果某个条件改变会怎样"的延伸思考（必须针对本题结论具体分析）"""

# ---- 英文think泄露检测关键词 ----
ENGLISH_THINK_PATTERNS = [
    r'(?i)\bI (?:will|need|should|shall|think|believe|would|can |must |want |have )',
    r'(?i)\bLet me',
    r'(?i)\bMy (?:approach|strategy|thinking|plan|solution)',
    r'(?i)\bWait[,.]',
    r'(?i)\bHowever[,.]',
    r'(?i)\bOkay[,.]',
    r'(?i)\bPerhaps',
    r'(?i)\bMaybe',
    r'(?i)^\*\*(?:Analyze|Drafting|Refining|Check)',
    r'(?i)\b(?:That means|This suggests|It seems|I think)',
    r'(?i)\bproblem statement is (?:mathematically )?(?:false|incorrect)',
]

# ---- 模板泄露检测 ----
TEMPLATE_LEAK_PATTERNS = [
    r'(?i)Strategy Planning\)?.*specific to this problem',
    r'(?i)Key Insight\)?.*specific to this problem',
    r'(?i)Heuristic Summary\)?.*specific to this problem',
    r'(?i)<Specific mathematical conclusion',
    r'(?i)<Final Answer only',
    r'(?i)1-2 sentences analyzing core',
    r'(?i)1 sentence highlighting the key',
    r'(?i)1-2 sentences explaining broader',
    r'(?i)必须针对本题具体内容.*不要泛泛而谈',
    r'(?i)用1-2句话分析',
    r'(?i)用1句话点出',
    r'(?i)用1-2句话说明',
]

# ---- 截断检测 ----
TRUNCATION_TAIL_PATTERNS = [
    r'虽然$',
    r'但是$',
    r'因此$',
    r'所以$',
    r'由于$',
    r'当$',
    r'若$',
    r'令$',
    r'设$',
    r'对于$',
    r'考虑$',
    r'由$',
    r'根据$',
    r'利用$',
    r'通过$',
    r'[,，]\s*$',
    r'[\(（]\s*$',
    r'\\\s*$',
    r'&\s*$',
    r'\$\s*$',
    r'[a-zA-Z]$',
]

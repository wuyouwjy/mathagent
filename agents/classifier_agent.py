# ============================================================
# agents/classifier_agent.py — 领域分类智能体
# 职责：接收数学问题 → 分析内容 → 确定领域 → 选择对应 Solver 专家
#
# 流程：
#   1. 规则快速匹配（关键词 → 领域，高置信度直接返回）
#   2. 置信度不足时调用 LLM 深度分类
#   3. 从 solver_registry 获取对应 Solver 名称
#   4. 返回 ClassificationResult
# ============================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from loguru import logger

from schemas.math_domains import (
    MathDomain, DOMAIN_TO_SOLVER, DOMAIN_CN_NAME,
    get_solver_for_domain, list_all_domains
)


@dataclass
class ClassificationResult:
    """分类结果"""
    domain: str                                      # 领域 key
    domain_cn: str                                   # 领域中文名
    solver_name: str                                 # 推荐的 Solver 名称
    confidence: float                                # 置信度 0.0~1.0
    reason: str                                      # 分类理由
    alternative_domain: str = ""                     # 备选领域
    used_llm: bool = False                           # 是否使用了 LLM 分类
    keywords_matched: List[str] = field(default_factory=list)  # 匹配到的关键词


class ClassifierAgent:
    """
    数学领域分类智能体

    先规则匹配（快速），置信度不足时调用 LLM 深度分类。

    用法:
        agent = ClassifierAgent()
        result = agent.classify("求解偏微分方程 ∂u/∂t = ∂²u/∂x²", parsed={})
        # result.solver_name → "pde_solver"
    """

    # 强特征词 → 领域映射（与 nodes.py 中的 _rule_based_classify 对齐）
    STRONG_PATTERNS: Dict[str, List[str]] = {
        "partial_differential_equations": [
            "偏微分", "pde", "partial differential", "波动方程", "热传导",
            "laplace equation", "wave equation", "heat equation", "泊松方程",
            "navier-stokes", "分离变量法",
        ],
        "ordinary_differential_equations": [
            "常微分", "ode", "ordinary differential", "初值问题", "边值问题",
            "特征方程", "相图", "稳定性分析", "lyapunov", "极限环",
            "euler-lagrange", "变分法",
        ],
        "complex_analysis": [
            "复分析", "complex analysis", "解析函数", "留数", "柯西",
            "cauchy", "residue", "holomorphic", "亚纯函数", "辐角",
            "围道积分", "contour integral", "laurent级数",
        ],
        "topology": [
            "拓扑", "topology", "同胚", "同伦", "基本群", "紧致",
            "homotopy", "homeomorphism", "fundamental group", "流形",
            "同调", "euler示性数", "gauss-bonnet",
        ],
        "optimization": [
            "优化", "optimization", "线性规划", "非线性规划", "约束",
            "目标函数", "可行域", "单纯形", "simplex", "拉格朗日乘子",
            "凸优化", "convex optimization", "kkt", "对偶",
        ],
        "algebra": [
            "代数", "algebra", "群", "环", "域", "多项式", "因式分解",
            "特征值", "对角化", "线性变换", "向量空间", "子空间",
            "galois", "sylow", "cayley-hamilton",
        ],
        "probability": [
            "概率", "probability", "随机变量", "分布", "期望",
            "方差", "协方差", "大数定律", "中心极限", "bayes",
            "马尔可夫", "markov",
        ],
        "number_theory": [
            "数论", "number theory", "素数", "同余", "整除",
            "费马", "欧拉", "丢番图", "模运算", "二次互反",
        ],
    }

    def __init__(self):
        self._domain_list_cache = None

    @property
    def _domain_list(self) -> str:
        """构建领域列表描述（缓存）"""
        if self._domain_list_cache is None:
            self._domain_list_cache = "\n".join([
                f"- {d['domain_key']} ({d['domain_cn']})"
                for d in list_all_domains()
            ])
        return self._domain_list_cache

    def classify(self, question_text: str, parsed: Optional[Dict] = None) -> ClassificationResult:
        """
        分类数学问题领域

        参数:
            question_text: 问题文本
            parsed: 预解析结果（可选，含 keywords）

        返回:
            ClassificationResult: 分类结果
        """
        if parsed is None:
            parsed = {}

        keywords = parsed.get("keywords", [])

        # --- 第1步：规则快速匹配 ---
        domain, confidence = self._rule_based_classify(question_text, keywords)
        matched_keywords = self._get_matched_keywords(question_text)

        if confidence >= 0.9:
            solver_name = get_solver_for_domain(domain)
            domain_cn = DOMAIN_CN_NAME.get(MathDomain(domain) if domain in [d.value for d in MathDomain] else MathDomain.ALGEBRA, "代数")
            logger.info(f"[ClassifierAgent] 规则匹配: domain={domain}, confidence={confidence:.2f}")
            return ClassificationResult(
                domain=domain, domain_cn=domain_cn, solver_name=solver_name,
                confidence=confidence, reason=f"规则匹配: 关键词 {matched_keywords}",
                keywords_matched=matched_keywords
            )

        # --- 第2步：LLM 深度分类 ---
        try:
            domain, confidence, reason = self._llm_classify(question_text, parsed)
            used_llm = True
        except Exception as e:
            logger.error(f"[ClassifierAgent] LLM分类失败: {e}, 使用规则匹配结果")
            domain = "algebra"
            confidence = 0.3
            reason = f"LLM失败回退: {e}"
            used_llm = False

        # --- 验证 domain 有效性 ---
        valid_domains = [d.value for d in MathDomain]
        if domain not in valid_domains:
            logger.warning(f"[ClassifierAgent] 无效领域 '{domain}', 回退到 algebra")
            domain = "algebra"
            confidence = 0.3
            reason = "无效领域自动纠正"

        solver_name = get_solver_for_domain(domain)
        domain_cn = DOMAIN_CN_NAME.get(
            MathDomain(domain) if domain in valid_domains else MathDomain.ALGEBRA, "未知"
        )

        logger.info(f"[ClassifierAgent] 分类完成: domain={domain} ({domain_cn}), "
                     f"confidence={confidence:.2f}, solver={solver_name}, used_llm={used_llm}")

        return ClassificationResult(
            domain=domain, domain_cn=domain_cn, solver_name=solver_name,
            confidence=confidence, reason=reason, used_llm=used_llm,
            keywords_matched=matched_keywords
        )

    def _rule_based_classify(self, text: str, keywords: List[str]) -> Tuple[str, float]:
        """基于规则的快速领域分类"""
        text_lower = text.lower()
        kw_lower = [k.lower() for k in keywords]

        scores = {}
        for domain, patterns in self.STRONG_PATTERNS.items():
            score = 0
            for p in patterns:
                if p.lower() in text_lower:
                    score += 2
                if p.lower() in kw_lower:
                    score += 3
            if score > 0:
                scores[domain] = min(score / 10.0, 0.95)

        if scores:
            best_domain = max(scores, key=scores.get)
            return best_domain, scores[best_domain]

        return "algebra", 0.3

    def _get_matched_keywords(self, text: str) -> List[str]:
        """获取匹配到的关键词"""
        text_lower = text.lower()
        matched = []
        for domain, patterns in self.STRONG_PATTERNS.items():
            for p in patterns:
                if p.lower() in text_lower and p not in matched:
                    matched.append(p)
        return matched[:10]  # 最多10个

    def _llm_classify(self, question_text: str, parsed: Dict) -> Tuple[str, float, str]:
        """使用 LLM 进行领域分类"""
        from tools.intern_client import get_intern_client

        client = get_intern_client()

        system_prompt = (
            "你是一位数学领域分类专家。请将以下数学问题归类到以下18个领域之一。\n\n"
            f"可用领域：\n{self._domain_list}\n\n"
            "请以 JSON 格式返回（不要其他文本）：\n"
            '{"domain": "领域key", "confidence": 0.95, "reason": "分类理由", "alternative_domain": "备选领域key"}'
        )

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
# 全局单例
# ============================================================

_global_classifier: Optional[ClassifierAgent] = None


def get_classifier() -> ClassifierAgent:
    """获取全局 ClassifierAgent 单例"""
    global _global_classifier
    if _global_classifier is None:
        _global_classifier = ClassifierAgent()
    return _global_classifier

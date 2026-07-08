# ============================================================
# agents/graph_manager_agent.py — 工作流编排智能体
# 职责：管理 LangGraph 工作流执行
#   - 路由决策（分类后路由、反思后路由）
#   - 反思循环管理（重试次数、反馈生成）
#   - 状态追踪
#   - 异常处理与兜底策略
# ============================================================

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Literal, List
from loguru import logger


@dataclass
class RouteDecision:
    """路由决策结果"""
    next_node: str                                  # 下一个节点名称
    reason: str                                     # 路由理由
    extra_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflectionDecision:
    """反思决策结果"""
    should_retry: bool                              # 是否需要重试
    feedback: str                                   # 反思反馈信息
    new_count: int                                  # 新的重试计数
    suggested_solver: Optional[str] = None          # 建议的备选 Solver（可选）
    suggested_strategy: Optional[str] = None        # 建议的备选策略（可选）


class GraphManagerAgent:
    """
    工作流编排智能体

    管理 LangGraph 工作流的执行决策：
    - 缓存命中/未命中路由
    - 分类成功/失败路由
    - 反思重试判定（含备选 Solver 推荐）
    - 自适应最大重试次数

    用法:
        agent = GraphManagerAgent()
        decision = agent.after_reflection(state)
        if decision.should_retry:
            ...  # 回到 solver_dispatcher
    """

    def __init__(self, max_reflection_count: int = 3):
        """
        参数:
            max_reflection_count: 默认最大反思重试次数
        """
        self.max_reflection_count = max_reflection_count
        self._retry_stats: Dict[str, int] = {}  # 统计各领域重试次数

    # ============================================================
    # 路由决策
    # ============================================================

    def after_cache_check(self, state: Dict[str, Any]) -> Literal["formatter", "problem_parser"]:
        """
        缓存检查后路由

        参数:
            state: 工作流状态

        返回:
            "formatter" 或 "problem_parser"
        """
        if state.get("cache_hit", False):
            logger.info("[GraphManager] 缓存命中 → 跳过求解，直接输出")
            return "formatter"
        else:
            logger.info("[GraphManager] 缓存未命中 → 进入完整求解流程")
            return "problem_parser"

    def after_classifier(self, state: Dict[str, Any]) -> Literal["rag_retrieval", "error_handler"]:
        """
        分类器后路由

        逻辑：
        - 分类成功（classified_domain 非空且 confidence > 0）→ 进入 RAG 检索
        - 分类失败 → 进入错误处理

        参数:
            state: 工作流状态

        返回:
            "rag_retrieval" 或 "error_handler"
        """
        domain = state.get("classified_domain", "")
        confidence = state.get("classification_confidence", 0.0)

        if domain and confidence > 0.0:
            logger.info(f"[GraphManager] 分类成功 ({domain}, conf={confidence:.2f}) → RAG 检索")
            return "rag_retrieval"
        else:
            logger.warning(f"[GraphManager] 分类失败 → 错误处理")
            state["error_info"] = state.get("error_info", []) + [
                f"Classifier failed: domain={domain}, confidence={confidence}"
            ]
            return "error_handler"

    def after_reflection(self, state: Dict[str, Any]) -> Literal["solver_dispatcher", "formatter"]:
        """
        反思后路由（Reflection Loop）

        逻辑：
        - reflection_needed=True 且未超最大次数 → 回到 solver_dispatcher 重试
        - reflection_needed=False 或超最大次数 → 进入 formatter

        参数:
            state: 工作流状态

        返回:
            "solver_dispatcher" 或 "formatter"
        """
        need_retry = state.get("reflection_needed", False)
        count = state.get("reflection_count", 0)
        max_count = state.get("max_reflection_count", self.max_reflection_count)

        if need_retry and count < max_count:
            logger.info(f"[GraphManager] 反思触发重试: {count}/{max_count} → solver_dispatcher")
            return "solver_dispatcher"
        else:
            if count >= max_count:
                logger.warning(f"[GraphManager] 已达最大重试次数 {max_count} → formatter")
            else:
                verification_passed = state.get("verification_passed", False)
                logger.info(f"[GraphManager] 验证通过={verification_passed} → formatter")
            return "formatter"

    # ============================================================
    # 反思管理
    # ============================================================

    def evaluate_reflection(self, state: Dict[str, Any]) -> ReflectionDecision:
        """
        评估是否需要反思重试

        基于验证结果、重试次数和领域特征做出决策。

        参数:
            state: 工作流状态

        返回:
            ReflectionDecision: 反思决策
        """
        verification_passed = state.get("verification_passed", False)
        verification_result = state.get("verification_result", {})
        current_count = state.get("reflection_count", 0)
        max_count = state.get("max_reflection_count", self.max_reflection_count)
        domain = state.get("classified_domain", "")

        # 验证通过 → 不需要反思
        if verification_passed:
            return ReflectionDecision(
                should_retry=False, feedback="",
                new_count=current_count
            )

        # 已达最大重试次数 → 不再重试
        if current_count >= max_count:
            return ReflectionDecision(
                should_retry=False,
                feedback=f"已达最大重试次数({max_count})，接受当前结果",
                new_count=current_count
            )

        # 需要重试 → 生成反馈
        error_details = verification_result.get("error_details", "未知错误")
        correction = verification_result.get("correction_suggestion", "")

        new_count = current_count + 1
        feedback = self._build_feedback(
            error_details=error_details,
            correction=correction,
            attempt=new_count,
            max_attempts=max_count
        )

        # 统计领域重试
        self._retry_stats[domain] = self._retry_stats.get(domain, 0) + 1

        # 如果重试次数较多，建议尝试备选 solver
        suggested_solver = None
        if new_count >= 2:
            suggested_solver = self._suggest_alternative(domain)

        logger.info(f"[GraphManager] 触发反思重试 ({new_count}/{max_count}): {error_details[:80]}...")

        return ReflectionDecision(
            should_retry=True, feedback=feedback,
            new_count=new_count, suggested_solver=suggested_solver
        )

    def _build_feedback(self, error_details: str, correction: str,
                        attempt: int, max_attempts: int) -> str:
        """构建反思反馈信息"""
        return (
            f"【反思反馈 — 第{attempt}次重试（共{max_attempts}次）】\n"
            f"上次求解验证未通过。\n"
            f"错误详情：{error_details}\n"
            f"修改建议：{correction if correction else '请重新审视推理过程，检查每一步的正确性。'}\n"
            f"请特别注意推导中的假设是否合理、公式是否运用正确。"
            f"{'如果当前方法仍不奏效，请尝试不同的求解策略。' if attempt >= 2 else ''}"
        )

    def _suggest_alternative(self, domain: str) -> Optional[str]:
        """
        为某个领域建议备选 Solver

        当某个 Solver 多次失败时，建议尝试更通用的 Solver。
        """
        alternatives = {
            "pde_solver": "ode_solver",
            "complex_analysis_solver": "algebra_solver",
            "topology_solver": "algebra_solver",
            "optimization_solver": "algebra_solver",
            "ode_solver": "algebra_solver",
            "algebra_solver": None,  # 没有更通用的备选
        }
        return alternatives.get(domain)

    # ============================================================
    # 状态管理工具
    # ============================================================

    def get_retry_stats(self) -> Dict[str, int]:
        """获取各领域重试统计"""
        return dict(self._retry_stats)

    def reset_stats(self) -> None:
        """重置统计"""
        self._retry_stats.clear()


# ============================================================
# 全局单例
# ============================================================

_global_graph_manager: Optional[GraphManagerAgent] = None


def get_graph_manager() -> GraphManagerAgent:
    """获取全局 GraphManagerAgent 单例"""
    global _global_graph_manager
    if _global_graph_manager is None:
        _global_graph_manager = GraphManagerAgent()
    return _global_graph_manager

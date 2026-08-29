from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from graph.state import MathAgentState
from graph.nodes import (
    reasoning_agent_node, python_agent_node, cross_validator_node,
    database_retrieval_node,
)
from utils.error_handler import node_wrapper
from utils.problem.profile import is_objective_mode, classify_question_mode

def build_solving_subgraph():
    sub = StateGraph(MathAgentState)
    # 题库检索：纯增益节点，失败降级为空列表。放在 fan_out 之前，两个子代理
    # 并行前各自从 state 读 retrieved_examples 注入参考区块（反锚定）。
    sub.add_node("database_retrieval", node_wrapper(database_retrieval_node, "database_retrieval"))
    sub.add_node("reasoning_agent", node_wrapper(reasoning_agent_node, "reasoning_agent"))
    sub.add_node("python_agent", node_wrapper(python_agent_node, "python_agent"))
    sub.add_node("cross_validator", node_wrapper(cross_validator_node, "cross_validator"))

    def fan_out(state, config):
        reasoning_send = Send(
            "reasoning_agent", {**state, "branch_hint": state.get("reasoning_retry_hint")}
        )
        sends = [reasoning_send]
        question_mode = state.get("question_mode") or classify_question_mode(state.get("problem", ""))
        # V2 时间/准确率平衡：证明题跳过 Python 验证。
        # 实测根因（2026-08-13 本地 idx 1/2）：抽象证明题 Python 分支 answer 恒为
        # null（无法用数值验证"同构/整环"这类命题），却与 reasoning 并行耗
        # 295~322s，还吃软预算（480s 下 reasoning 一跑 coordinator 就被跳过）。
        # 跳过后面下游路径与"Python 跑空"完全一致（uncertain → semantic_arbiter
        # 单候选 skip → coordinator 兜底输出 reasoning 的完整证明），零准确率损失、
        # 纯省时。若未来遇到"证明题内嵌强数值计算"（如证某阶数为 N），可在此加
        # 例外检测（求/计算/阶/维数/值 等词）保留 Python。
        if question_mode == "proof":
            return sends
        # V2.1 M8 FastLane：客观题高置信（≥ high 阈值）+ 非 hard 难度 → 单路径快速答
        # （省 Python/critic，时间给难题）。实算填空/难题不触发。
        from utils.verify.confidence_gate import fast_lane_eligible
        if fast_lane_eligible(question_mode, state.get("category_confidence"),
                              state.get("difficulty", ""), state.get("problem", "")):
            return sends
        # V2 M2 置信门控：高置信纯概念客观题跳过 Python 验证（省资源）。
        from utils.verify.confidence_gate import can_skip_python_verify
        if can_skip_python_verify(question_mode, state.get("category_confidence"),
                                  state.get("problem", "")):
            return sends
        if is_objective_mode(question_mode):
            # 实算填空升级完整双路（治本机制 idx=13/40：含绝对值的导数/组合计数
            # 曾被误判客观题跳过 Python，单采样定生死）；纯概念填空/选择/判断保持
            # 单路径（短路径自带核对，Python 标量无法表达多空/选项）。
            from utils.verify.verify_router import needs_python_verify
            if not needs_python_verify(state.get("problem", ""), question_mode):
                return sends
        sends.append(
            Send("python_agent", {**state, "branch_hint": state.get("python_retry_hint")})
        )
        return sends
    sub.add_edge(START, "database_retrieval")
    sub.add_conditional_edges("database_retrieval", fan_out, ["reasoning_agent", "python_agent"])
    sub.add_edge("reasoning_agent", "cross_validator")
    sub.add_edge("python_agent", "cross_validator")
    sub.add_edge("cross_validator", END)
    return sub.compile()

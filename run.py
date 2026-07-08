#!/usr/bin/env python3
# ============================================================
# run.py — 系统主入口
# 用法:
#   python run.py --mode single --question "求解 x^2+3x-4=0"
#   python run.py --mode batch --dataset ./database/datasets/dev.jsonl
#   python run.py --mode interactive
#   python run.py --mode test
# ============================================================

import sys
import os
import argparse
import json

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from utils.logger import setup_logger


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Math-Agent-System: 基于 Intern-S1 的多领域数学自动求解智能体系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
运行模式:
  single       - 单题求解
  batch        - 批量评估（112道题）
  interactive  - 交互式求解
  test         - 运行所有测试
  info         - 查看系统信息

示例:
  python run.py --mode single --question "求解偏微分方程 ∂u/∂t = ∂²u/∂x²"
  python run.py --mode batch --dataset ./database/datasets/dev.jsonl
  python run.py --mode interactive
  python run.py --mode test
        """
    )

    parser.add_argument(
        "--mode", "-m",
        choices=["single", "batch", "interactive", "test", "info", "mcp"],
        default="info",
        help="运行模式 (default: info)"
    )
    parser.add_argument(
        "--question", "-q",
        type=str,
        help="单题求解：数学问题文本"
    )
    parser.add_argument(
        "--dataset", "-d",
        type=str,
        default="./database/datasets/dev.jsonl",
        help="批量评估：数据集路径 (default: ./database/datasets/dev.jsonl)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./database/outputs",
        help="输出目录 (default: ./database/outputs)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="打印详细日志"
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="禁用 RAG 检索"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="最大反思重试次数 (default: 3)"
    )

    args = parser.parse_args()

    # --- 初始化日志 ---
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logger(
        log_dir=os.path.join(args.output, "logs"),
        log_level=log_level,
        experiment_name="math-agent",
    )

    # --- 路由到对应模式 ---
    if args.mode == "single":
        run_single(args)
    elif args.mode == "batch":
        run_batch(args)
    elif args.mode == "interactive":
        run_interactive(args)
    elif args.mode == "test":
        run_tests(args)
    elif args.mode == "info":
        show_system_info(args)
    elif args.mode == "mcp":
        run_mcp_server(args)


def run_single(args):
    """单题求解模式"""
    question = args.question
    if not question:
        question = input("请输入数学问题: ").strip()
        if not question:
            logger.error("问题文本不能为空")
            return

    logger.info(f"单题求解模式启动")
    logger.info(f"问题: {question[:100]}...")

    from user_agent import ReasoningAgent

    agent = ReasoningAgent()
    result = agent.solve(
        problem=question,
        metadata={"idx": 0},
    )

    # 打印结果（比赛格式）
    print("\n" + "=" * 60)
    print("[Result] 求解结果")
    print("=" * 60)
    if result.get("error"):
        print(f"状态:     error")
        print(f"错误类型: {result['error']['type']}")
        print(f"错误信息: {result['error']['message']}")
    else:
        print(f"最终答案: {result.get('final_response', 'N/A')}")
        trace = result.get("trace", [])
        if trace:
            print(f"推理步骤: {len(trace)} 步")
            for t in trace:
                content = t.get("content", "")
                if isinstance(content, dict):
                    content = str(content)[:120]
                print(f"  [{t['step']}] {str(content)[:120]}")

    # 保存结果
    output_path = os.path.join(args.output, "single_result.json")
    os.makedirs(args.output, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"结果已保存: {output_path}")


def run_batch(args):
    """批量评估模式（112道题）"""
    dataset_path = args.dataset

    if not os.path.exists(dataset_path):
        logger.error(f"数据集不存在: {dataset_path}")
        logger.info("提示：请将数据集JSONL文件放到 database/datasets/ 目录下")
        logger.info("创建示例数据集...")
        _create_sample_dataset(dataset_path)

    logger.info(f"批量评估模式启动")
    logger.info(f"数据集: {dataset_path}")

    from evaluation.evaluator import BatchEvaluator, EvaluationConfig

    config = EvaluationConfig(
        batch_size=10,
        save_interval=5,
        timeout_per_question=300,
    )

    evaluator = BatchEvaluator(config)
    summary = evaluator.evaluate_dataset(
        dataset_path=dataset_path,
        output_dir=os.path.join(args.output, "evaluation"),
        verbose=True,
    )

    logger.info(f"批量评估完成: {summary.solved_count}/{summary.total_questions} 通过")


def run_interactive(args):
    """交互式求解模式"""
    logger.info("交互式数学求解模式启动")
    logger.info("输入 'quit' 或 'exit' 退出")
    logger.info("输入 'stats' 查看API用量统计")

    from user_agent import ReasoningAgent
    from tools.intern_client import get_intern_client

    agent = ReasoningAgent()
    client = get_intern_client()

    while True:
        try:
            question = input("\n>> 请输入数学问题 > ").strip()

            if not question:
                continue
            if question.lower() in ["quit", "exit", "q"]:
                logger.info("退出交互模式")
                break
            if question.lower() == "stats":
                stats = client.get_usage_stats()
                print(f"API 用量: {json.dumps(stats, indent=2)}")
                continue
            if question.lower() == "cache":
                from rag.cache.problem_cache import get_cache
                cache = get_cache()
                cs = cache.get_stats()
                print(f"缓存统计: 精确={cs['exact_cache_size']}, "
                      f"向量={cs['vector_cache_size']}, "
                      f"命中率={cs['hit_rate']:.1%}, "
                      f"命中={cs['hits']}, 未命中={cs['misses']}")
                recent = cache.list_recent(5)
                if recent:
                    print("最近缓存:")
                    for e in recent:
                        print(f"  [{e['domain']}] {e['question'][:60]}")
                continue
            if question.lower() == "clearcache":
                from rag.cache.problem_cache import get_cache
                get_cache().clear()
                print("缓存已清空")
                continue

            result = agent.solve(
                problem=question,
                metadata={"idx": 0},
            )

            # 比赛格式输出
            if result.get("error"):
                print(f"\n[ERROR] {result['error']['type']}: {result['error']['message']}")
            else:
                print(f"\n[Answer] {result.get('final_response', '?')}")
                trace = result.get("trace", [])
                for t in trace:
                    content = t.get("content", "")
                    if isinstance(content, dict):
                        content = str(content)[:120]
                    print(f"  [{t['step']}] {str(content)[:120]}")

        except KeyboardInterrupt:
            print("\n退出交互模式")
            break
        except Exception as e:
            logger.error(f"错误: {e}")


def run_tests(args):
    """运行所有测试"""
    logger.info("运行测试套件...")
    import pytest

    test_dir = os.path.join(os.path.dirname(__file__), "tests")
    exit_code = pytest.main([test_dir, "-v", "--tb=short"])

    if exit_code == 0:
        logger.info("[OK] 所有测试通过")
    else:
        logger.warning(f"[WARN] 测试退出码: {exit_code}")


def show_system_info(args):
    """显示系统信息"""
    print("\n" + "=" * 60)
    print("[Math-Agent-System] 系统信息")
    print("=" * 60)

    # 配置信息
    from configs.settings import get_config
    config = get_config()

    print(f"\n[Config] 配置:")
    print(f"  API 模型:      {config.intern_s1.model_name}")
    print(f"  API 地址:      {config.intern_s1.api_base_url}")
    print(f"  Temperature:   {config.intern_s1.temperature}")
    print(f"  最大重试:      {config.workflow.max_reflection_count}")
    print(f"  RAG 启用:      {config.rag.enabled}")
    print(f"  随机种子:      {config.random_seed}")

    # Solver 信息
    print(f"\n[Solvers] 已注册 Solver:")
    from agents.solver_experts.solver_registry import list_registered_solvers
    for name, desc in list_registered_solvers().items():
        print(f"  - {name}: {desc}")

    # 领域信息
    print(f"\n[Domains] 支持的数学领域 (18个):")
    from schemas.math_domains import list_all_domains
    for d in list_all_domains():
        print(f"  - {d['domain_key']} ({d['domain_cn']}) -> {d['solver']}")

    # 工作流信息
    from graph.graph_builder import build_math_agent_graph, get_graph_info
    graph = build_math_agent_graph(enable_rag=True, enable_checkpoint=False)
    info = get_graph_info(graph)
    print(f"\n[Graph] 工作流图:")
    print(f"  节点数: {info['total_nodes']}")
    print(f"  边数:   {info['total_edges']}")
    print(f"  入口:   {info['entry_point']}")
    print(f"  出口:   {info['exit_points']}")

    print(f"\n{'='*60}")
    print(f"使用方法:")
    print(f"  python run.py --mode single --question \"你的数学问题\"")
    print(f"  python run.py --mode batch --dataset ./database/datasets/dev.jsonl")
    print(f"  python run.py --mode interactive")
    print(f"  python run.py --mode test")
    print(f"{'='*60}\n")


def _create_sample_dataset(path: str):
    """创建示例数据集"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    sample_questions = [
        {
            "question_id": "sample_001",
            "question_text": "求解二次方程 x^2 - 5x + 6 = 0",
            "domain": "algebra",
        },
        {
            "question_id": "sample_002",
            "question_text": "计算 ∫_0^π sin(x) dx",
            "domain": "real_analysis",
        },
        {
            "question_id": "sample_003",
            "question_text": "求解一阶线性常微分方程 dy/dx + 2xy = x",
            "domain": "ordinary_differential_equations",
        },
        {
            "question_id": "sample_004",
            "question_text": "使用留数定理计算 ∮_{|z|=2} e^z/(z^2+1) dz",
            "domain": "complex_analysis",
        },
        {
            "question_id": "sample_005",
            "question_text": "求函数 f(x,y) = x^2 + y^2 在约束 x + y = 1 下的最小值",
            "domain": "optimization",
        },
    ]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(sample_questions, f, ensure_ascii=False, indent=2)

    logger.info(f"示例数据集已创建: {path} (共 {len(sample_questions)} 题)")


def run_mcp_server(args):
    """启动 MCP 服务器"""
    logger.info("启动 MCP 服务器...")
    from mcp.server import run_mcp_server as _run_mcp

    mode = getattr(args, 'mcp_mode', 'interactive')
    _run_mcp(mode=mode)


if __name__ == "__main__":
    main()

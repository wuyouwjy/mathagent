#!/usr/bin/env python3
# ============================================================
# main.py — 本地测试 Runner（比赛格式）
#
# 用法:
#   export INTERN_API_KEY="sk-..."
#   python main.py --input_file sample_data/dev.jsonl --output_dir sample_outputs
#
# 与比赛平台 runner 行为一致:
#   - 读取 JSONL 输入
#   - 创建 InternChatClient
#   - 初始化 ReasoningAgent(client=client)
#   - 逐题调用 agent.solve(problem, metadata)
#   - 保存结果到 outputs/
# ============================================================

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List

from llm_client import InternChatClient
from user_agent import ReasoningAgent

LOCAL_MAX_CONCURRENCY = int(os.environ.get("LOCAL_MAX_CONCURRENCY", "4"))


def load_jsonl(path: Path) -> List[Dict]:
    """加载 JSONL 文件"""
    items = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file):
            if not line.strip():
                continue
            item = json.loads(line)
            item.setdefault("idx", line_number)
            items.append(item)
    return items


def result_path(output_dir: Path, item: Dict) -> Path:
    """获取结果文件路径"""
    return output_dir / f"{item['idx']}.json"


def is_processed(path: Path) -> bool:
    """检查是否已处理"""
    return path.exists() and path.stat().st_size > 0


def write_json(path: Path, record: Dict) -> None:
    """原子写入 JSON 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(record, file, ensure_ascii=False, indent=2)
        file.write("\n")
    tmp_path.replace(path)


def build_output_record(item: Dict, agent_result: Dict) -> Dict:
    """构建标准输出记录"""
    final_response = agent_result.get("final_response", "")
    if not isinstance(final_response, str) or not final_response.strip():
        raise ValueError("agent.solve must return a non-empty string field: final_response")

    return {
        "idx": item["idx"],
        "status": "success",
        "final_response": final_response,
        "trace": agent_result.get("trace", []),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Math Reasoning Agent - Local Runner")
    parser.add_argument("--input_file", required=True, help="Path to input JSONL file")
    parser.add_argument("--output_dir", required=True, help="Directory for per-problem JSON outputs")
    return parser.parse_args()


def solve_item(agent: ReasoningAgent, item: Dict) -> Dict:
    """求解单题"""
    result = agent.solve(
        problem=item["problem"],
        metadata={"idx": item["idx"]},
    )
    return build_output_record(item, result)


async def process_item(
    agent: ReasoningAgent,
    item: Dict,
    output_dir: Path,
    semaphore: asyncio.Semaphore,
) -> None:
    """处理单题（异步 + 并发控制）"""
    path = result_path(output_dir, item)
    if is_processed(path):
        print(f"Skip idx={item['idx']} (already processed)")
        return

    async with semaphore:
        try:
            record = await asyncio.to_thread(solve_item, agent, item)
        except Exception as exc:
            record = {
                "idx": item["idx"],
                "status": "error",
                "final_response": "",
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "trace": [],
            }
        await asyncio.to_thread(write_json, path, record)
        status = record.get("status", "error")
        print(f"[{status.upper()}] idx={item['idx']} -> {path}")


async def run(args: argparse.Namespace) -> None:
    input_path = Path(args.input_file)
    output_dir = Path(args.output_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    items = load_jsonl(input_path)
    print(f"Loaded {len(items)} items from {input_path}")

    # 创建客户端和 Agent
    client = InternChatClient()
    agent = ReasoningAgent(client=client)
    semaphore = asyncio.Semaphore(LOCAL_MAX_CONCURRENCY)

    print(f"Model: {client.model}, Max concurrency: {LOCAL_MAX_CONCURRENCY}")
    print(f"Output: {output_dir}")
    print("-" * 60)

    tasks = [process_item(agent, item, output_dir, semaphore) for item in items]
    await asyncio.gather(*tasks)

    print("-" * 60)
    print(f"Done. Results saved to {output_dir}")


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()

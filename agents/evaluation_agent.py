# ============================================================
# agents/evaluation_agent.py — 评估与题库管理智能体
#
# 职责：
#   1. 题库管理：按模板格式保存每道新题到 database/problem_db.json
#   2. 秒出缓存：相同问题（精确匹配）→ 直接返回缓存
#   3. 类比求解：相似问题（向量相似度 ≥ 阈值）→ 检索相似方法求解
#   4. 批量评估：管理 112 题批量运行、进度追踪、报告生成
# ============================================================

import os
import json
import time
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from loguru import logger


@dataclass
class ProblemRecord:
    """问题数据库记录模板"""
    question_id: str                                  # 问题唯一 ID
    question_text: str                                # 问题文本
    normalized_hash: str                              # 归一化哈希（精确匹配用）
    domain: str = ""                                  # 数学领域
    difficulty: str = "medium"                        # 难度: easy/medium/hard
    question_type: str = ""                           # 类型: calculation/proof/application
    created_at: str = ""                              # 创建时间
    solved_count: int = 0                             # 求解次数
    success_count: int = 0                            # 成功次数
    avg_confidence: float = 0.0                       # 平均置信度
    avg_time_ms: float = 0.0                          # 平均耗时
    best_method: str = ""                             # 最佳求解方法
    solutions: List[Dict[str, Any]] = field(default_factory=list)  # 历史解
    similar_question_ids: List[str] = field(default_factory=list)  # 相似问题 ID
    ground_truth: str = ""                            # 标准答案


class EvaluationAgent:
    """
    评估与题库管理智能体

    管理问题数据库，支持：
    - 问题持久化存储（JSON 文件）
    - 精确匹配秒出
    - 相似问题类比求解
    - 批量评估

    用法:
        agent = EvaluationAgent()
        record = agent.find_similar("求解 x^2 - 5x + 6 = 0")
        if record:
            print(f"找到相似问题: {record.question_text}")
        agent.save_to_db(question_text, result)
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化评估智能体

        参数:
            db_path: 问题数据库路径，默认 ./database/problem_db.json
        """
        if db_path is None:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(project_root, "database", "problem_db.json")

        self.db_path = db_path
        self._db: Dict[str, Dict[str, Any]] = {}
        self._load_db()

        # 延迟加载向量嵌入器
        self._embedder = None
        self._embedder_loaded = False

        logger.info(f"[EvaluationAgent] 题库已就绪: {db_path} ({len(self._db)} 条记录)")

    # ============================================================
    # 数据库管理
    # ============================================================

    def _load_db(self) -> None:
        """从文件加载问题数据库"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self._db = json.load(f)
                logger.info(f"[EvaluationAgent] 加载了 {len(self._db)} 条问题记录")
            except Exception as e:
                logger.warning(f"[EvaluationAgent] 加载数据库失败: {e}")
                self._db = {}
        else:
            self._db = {}

    def _save_db(self) -> None:
        """保存问题数据库到文件"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self._db, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[EvaluationAgent] 保存数据库失败: {e}")

    def _hash_question(self, text: str) -> str:
        """计算问题文本的归一化哈希（精确匹配用）"""
        normalized = "".join(text.split()).lower()
        return hashlib.md5(normalized.encode()).hexdigest()

    # ============================================================
    # 精确匹配（秒出）
    # ============================================================

    def find_exact(self, question_text: str) -> Optional[Dict[str, Any]]:
        """
        精确匹配查找（哈希）

        参数:
            question_text: 问题文本

        返回:
            Dict 或 None: 匹配到的问题记录
        """
        hash_key = self._hash_question(question_text)
        for qid, record in self._db.items():
            if record.get("normalized_hash") == hash_key:
                logger.info(f"[EvaluationAgent] 精确命中: {qid}")
                return record
        return None

    # ============================================================
    # 相似问题检索（类比求解）
    # ============================================================

    def find_similar(self, question_text: str, top_k: int = 3,
                     similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        查找相似问题

        先尝试精确匹配，失败后使用向量语义检索。

        参数:
            question_text: 问题文本
            top_k: 返回数量
            similarity_threshold: 相似度阈值

        返回:
            List[Dict]: 相似问题列表，按相似度降序
        """
        # 第1步：精确匹配
        exact = self.find_exact(question_text)
        if exact:
            return [{"record": exact, "similarity": 1.0, "match_type": "exact"}]

        # 第2步：关键词匹配（快速回退）
        results = self._keyword_search(question_text, top_k)
        if results:
            return results

        return []

    def _keyword_search(self, question_text: str, top_k: int) -> List[Dict[str, Any]]:
        """基于关键词的简单相似搜索"""
        query_words = set(question_text.lower().split())
        if not query_words:
            return []

        scored = []
        for qid, record in self._db.items():
            record_text = record.get("question_text", "").lower()
            record_words = set(record_text.split())
            if not record_words:
                continue
            # Jaccard 相似度
            intersection = query_words & record_words
            union = query_words | record_words
            similarity = len(intersection) / len(union) if union else 0

            if similarity >= 0.3:  # 较低阈值，关键词匹配粗糙
                scored.append({
                    "record": record,
                    "similarity": similarity,
                    "match_type": "keyword",
                })

        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    # ============================================================
    # 保存到数据库
    # ============================================================

    def save_to_db(self, question_text: str, result: Dict[str, Any]) -> str:
        """
        将求解结果按模板格式保存到问题数据库

        参数:
            question_text: 原始问题文本
            result: 完整的求解结果 (MathSolutionOutput dict)

        返回:
            str: 问题 ID
        """
        question_id = result.get("question_id") or f"q_{self._hash_question(question_text)[:8]}"
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        hash_key = self._hash_question(question_text)

        verification = result.get("verification", {})
        is_success = verification.get("is_correct", False)

        if question_id in self._db:
            # 更新已有记录
            record = self._db[question_id]
            record["solved_count"] = record.get("solved_count", 0) + 1
            if is_success:
                record["success_count"] = record.get("success_count", 0) + 1
            # 更新平均置信度
            old_avg = record.get("avg_confidence", 0)
            old_count = record.get("solved_count", 1)
            new_conf = verification.get("confidence", 0)
            record["avg_confidence"] = (old_avg * (old_count - 1) + new_conf) / old_count
            # 更新平均耗时
            old_avg_time = record.get("avg_time_ms", 0)
            new_time = result.get("computation_time_ms", 0)
            record["avg_time_ms"] = (old_avg_time * (old_count - 1) + new_time) / old_count
            # 添加新的解
            record["solutions"].append({
                "final_answer": result.get("final_answer", ""),
                "reasoning_steps": result.get("reasoning_steps", []),
                "methods_used": result.get("methods_used", []),
                "verification": verification,
                "timestamp": now,
            })
            # 更新最佳方法
            if is_success and result.get("methods_used"):
                record["best_method"] = ", ".join(result["methods_used"][:3])
        else:
            # 创建新记录
            record = {
                "question_id": question_id,
                "question_text": question_text,
                "normalized_hash": hash_key,
                "domain": result.get("domain", ""),
                "difficulty": "medium",
                "question_type": result.get("question_type", ""),
                "created_at": now,
                "solved_count": 1,
                "success_count": 1 if is_success else 0,
                "avg_confidence": verification.get("confidence", 0),
                "avg_time_ms": result.get("computation_time_ms", 0),
                "best_method": ", ".join(result.get("methods_used", [])[:3]),
                "solutions": [{
                    "final_answer": result.get("final_answer", ""),
                    "reasoning_steps": result.get("reasoning_steps", []),
                    "methods_used": result.get("methods_used", []),
                    "verification": verification,
                    "timestamp": now,
                }],
                "similar_question_ids": [],
                "ground_truth": result.get("ground_truth", ""),
            }
            self._db[question_id] = record

        self._save_db()
        logger.info(f"[EvaluationAgent] 已保存: {question_id} (domain={record['domain']}, "
                     f"success={is_success})")

        return question_id

    # ============================================================
    # 批量评估
    # ============================================================

    def run_benchmark(self, dataset_path: str, output_dir: str = "./outputs/evaluation",
                      verbose: bool = True) -> Any:
        """
        运行批量评估（委托给 evaluator）

        参数:
            dataset_path: 数据集路径
            output_dir: 输出目录
            verbose: 是否打印详细日志

        返回:
            BatchEvaluationSummary: 评估汇总
        """
        from evaluation.evaluator import BatchEvaluator, EvaluationConfig

        config = EvaluationConfig(
            batch_size=10,
            save_interval=5,
            timeout_per_question=300,
        )

        evaluator = BatchEvaluator(config)
        return evaluator.evaluate_dataset(
            dataset_path=dataset_path,
            output_dir=output_dir,
            verbose=verbose,
        )

    # ============================================================
    # 统计
    # ============================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计"""
        total = len(self._db)
        solved = sum(1 for r in self._db.values() if r.get("solved_count", 0) > 0)
        success = sum(1 for r in self._db.values() if r.get("success_count", 0) > 0)

        domain_dist = {}
        for r in self._db.values():
            d = r.get("domain", "unknown")
            domain_dist[d] = domain_dist.get(d, 0) + 1

        return {
            "total_problems": total,
            "solved_problems": solved,
            "successful_solves": success,
            "domain_distribution": domain_dist,
            "db_path": self.db_path,
        }

    def list_recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """列出最近的问题"""
        records = list(self._db.values())
        records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return records[:n]


# ============================================================
# 全局单例
# ============================================================

_global_evaluation_agent: Optional[EvaluationAgent] = None


def get_evaluation_agent() -> EvaluationAgent:
    """获取全局 EvaluationAgent 单例"""
    global _global_evaluation_agent
    if _global_evaluation_agent is None:
        _global_evaluation_agent = EvaluationAgent()
    return _global_evaluation_agent

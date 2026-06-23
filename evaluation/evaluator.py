# ============================================================
# evaluation/evaluator.py — 批量评估 Pipeline
# 用于 112 道题自动运行 + 评分
# ============================================================

import os
import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger

from schemas.output_schema import BatchEvaluationSummary


@dataclass
class EvaluationConfig:
    """评估配置"""
    batch_size: int = 10             # 每批处理数量
    save_interval: int = 5           # 每 N 题保存一次中间结果
    timeout_per_question: int = 300  # 每题超时（秒）
    shuffle_questions: bool = False  # 是否打乱题目顺序
    resume_from: Optional[str] = None  # 从指定检查点恢复


class BatchEvaluator:
    """
    批量评估器

    用法:
        evaluator = BatchEvaluator()
        results = evaluator.evaluate_dataset("datasets/questions.json")
    """

    def __init__(self, config: Optional[EvaluationConfig] = None):
        self.config = config or EvaluationConfig()
        self.results: List[Dict[str, Any]] = []
        self.start_time: float = 0.0

    def evaluate_dataset(
        self,
        dataset_path: str,
        output_dir: str = "./outputs/evaluation",
        verbose: bool = True,
    ) -> BatchEvaluationSummary:
        """
        评估整个数据集（112道题）

        参数:
            dataset_path: 数据集 JSON 文件路径
            output_dir: 输出目录
            verbose: 是否打印详细进度

        返回:
            BatchEvaluationSummary: 评估汇总
        """
        logger.info(f"[Evaluator] 开始批量评估: {dataset_path}")

        # --- 加载数据集 ---
        questions = self._load_dataset(dataset_path)
        total = len(questions)
        logger.info(f"[Evaluator] 加载了 {total} 道题")

        # --- 初始化工作流 ---
        from graph.workflow import MathAgentWorkflow
        workflow = MathAgentWorkflow(
            enable_rag=True,
            enable_checkpoint=False,
            max_reflection_count=3,
        )

        # --- 逐题求解 ---
        self.start_time = time.time()
        self.results = []

        for i, q in enumerate(questions):
            qid = q.get("question_id", f"q_{i:04d}")
            qtext = q.get("question_text", "")
            qdomain = q.get("domain", "")

            if verbose:
                logger.info(
                    f"\n{'='*50}\n"
                    f"[Evaluator] 第 {i+1}/{total} 题: {qid} (领域: {qdomain})\n"
                    f"{'='*50}"
                )

            # 超时控制
            start_q = time.time()
            try:
                result = workflow.solve(
                    question_text=qtext,
                    question_id=qid,
                    verbose=False,
                )
                elapsed = (time.time() - start_q) * 1000
                result["computation_time_ms"] = elapsed
                result["true_domain"] = qdomain

                # 对比标准答案（如有）
                if "ground_truth" in q:
                    gt = q["ground_truth"]
                    pred = result.get("final_answer", "")
                    result["ground_truth"] = gt
                    result["answer_match"] = _fuzzy_match(pred, gt)
            except Exception as e:
                logger.error(f"[Evaluator] 求解异常 [{qid}]: {e}")
                result = {
                    "question_id": qid,
                    "domain": qdomain,
                    "final_answer": f"错误: {e}",
                    "reasoning_steps": [],
                    "methods_used": [],
                    "verification": {
                        "is_correct": False,
                        "confidence": 0.0,
                        "check_method": "evaluation_error",
                        "error_details": str(e),
                    },
                    "educational_hint": "求解异常",
                    "computation_time_ms": (time.time() - start_q) * 1000,
                    "true_domain": qdomain,
                }

            self.results.append(result)

            # 保存中间结果
            if (i + 1) % self.config.save_interval == 0:
                self._save_checkpoint(output_dir, i + 1)

            if verbose:
                self._print_progress(i + 1, total, result)

        # --- 生成汇总 ---
        return self._generate_summary(output_dir)

    def _load_dataset(self, path: str) -> List[Dict[str, str]]:
        """
        加载数据集

        支持格式:
        1. JSON 文件: [{"question_id": "...", "question_text": "...", "domain": "..."}]
        2. JSONL 文件: 每行一个 JSON 对象
        3. 目录: 每个文件一道题（.txt / .json）

        参数:
            path: 数据集路径

        返回:
            List[Dict]: 问题列表
        """
        questions = []

        if os.path.isdir(path):
            # 从目录加载
            for fname in sorted(os.listdir(path)):
                fpath = os.path.join(path, fname)
                if fname.endswith(".txt"):
                    with open(fpath, "r", encoding="utf-8") as f:
                        questions.append({
                            "question_id": fname.replace(".txt", ""),
                            "question_text": f.read().strip(),
                            "domain": "",
                        })
                elif fname.endswith(".json"):
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            questions.extend(data)
                        else:
                            questions.append(data)

        elif path.endswith(".jsonl"):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        questions.append(json.loads(line))

        elif path.endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    questions = data
                elif isinstance(data, dict) and "questions" in data:
                    questions = data["questions"]
                else:
                    questions = [data]

        else:
            # 作为文本文件逐行读取
            with open(path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
                for i, line in enumerate(lines):
                    questions.append({
                        "question_id": f"q_{i:04d}",
                        "question_text": line,
                        "domain": "",
                    })

        # --- 字段名归一化 ---
        questions = self._normalize_questions(questions)

        if self.config.shuffle_questions:
            import random
            random.shuffle(questions)

        return questions

    def _normalize_questions(self, raw: List[Dict]) -> List[Dict[str, str]]:
        """
        归一化问题字段名

        自动识别常见字段名变体：
          idx / id / question_id       → question_id
          problem / question / text    → question_text
          subject / domain / category  → domain
        （保留 answer 作为 ground_truth）

        参数:
            raw: 原始问题列表

        返回:
            List[Dict]: 归一化后的问题列表
        """
        normalized = []
        for item in raw:
            # 问题ID
            qid = (
                item.get("question_id")
                or item.get("idx")
                or item.get("id")
                or f"q_{len(normalized):04d}"
            )
            if isinstance(qid, int):
                qid = f"q_{qid:04d}"

            # 问题文本
            qtext = (
                item.get("question_text")
                or item.get("problem")
                or item.get("question")
                or item.get("text")
                or ""
            )

            # 领域
            qdomain = (
                item.get("domain")
                or item.get("subject")
                or item.get("category")
                or ""
            )

            entry = {
                "question_id": str(qid),
                "question_text": str(qtext),
                "domain": str(qdomain),
            }

            # 保留标准答案（如果有）用于评分
            if "answer" in item:
                entry["ground_truth"] = str(item["answer"])

            # 保留其他元数据
            for key in ["source", "difficulty", "type"]:
                if key in item:
                    entry[key] = item[key]

            normalized.append(entry)

        logger.info(
            f"[Evaluator] 归一化完成: {len(normalized)} 题, "
            f"有标准答案: {sum(1 for q in normalized if 'ground_truth' in q)} 题"
        )
        return normalized

    def _save_checkpoint(self, output_dir: str, count: int) -> None:
        """保存中间检查点"""
        os.makedirs(output_dir, exist_ok=True)
        checkpoint_path = os.path.join(output_dir, f"checkpoint_{count}.json")
        try:
            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            logger.debug(f"[Evaluator] 检查点已保存: {checkpoint_path}")
        except Exception as e:
            logger.warning(f"[Evaluator] 检查点保存失败: {e}")

    def _generate_summary(self, output_dir: str) -> BatchEvaluationSummary:
        """生成评估汇总"""
        total = len(self.results)
        total_time = (time.time() - self.start_time) * 1000

        if total == 0:
            return BatchEvaluationSummary(
                total_questions=0, solved_count=0, failed_count=0,
                avg_confidence=0.0, total_time_ms=total_time,
                avg_time_per_question_ms=0.0,
            )

        # 统计
        solved = sum(
            1 for r in self.results
            if r.get("verification", {}).get("is_correct", False)
        )
        avg_conf = sum(
            r.get("verification", {}).get("confidence", 0)
            for r in self.results
        ) / total

        # 领域准确率
        domain_stats: Dict[str, List[float]] = {}
        for r in self.results:
            domain = r.get("domain", "unknown")
            conf = r.get("verification", {}).get("confidence", 0)
            if domain not in domain_stats:
                domain_stats[domain] = []
            domain_stats[domain].append(conf)

        domain_accuracy = {
            d: sum(cs) / len(cs) for d, cs in domain_stats.items()
        }

        summary = BatchEvaluationSummary(
            total_questions=total,
            solved_count=solved,
            failed_count=total - solved,
            avg_confidence=round(avg_conf, 4),
            domain_accuracy=domain_accuracy,
            total_time_ms=total_time,
            avg_time_per_question_ms=total_time / total,
            results=self.results,
        )

        # 保存汇总
        os.makedirs(output_dir, exist_ok=True)
        summary_path = os.path.join(output_dir, "evaluation_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary.model_dump(), f, ensure_ascii=False, indent=2)

        logger.info(f"[Evaluator] 评估汇总已保存: {summary_path}")

        # 打印报告
        self._print_report(summary)

        return summary

    def _print_progress(
        self, current: int, total: int, result: Dict[str, Any]
    ) -> None:
        """打印单题进度"""
        verif = result.get("verification", {})
        elapsed = result.get("computation_time_ms", 0)
        logger.info(
            f"[{current}/{total}] {result['question_id']}: "
            f"domain={result.get('domain', '?')}, "
            f"correct={verif.get('is_correct', False)}, "
            f"conf={verif.get('confidence', 0):.3f}, "
            f"time={elapsed/1000:.1f}s"
        )

    def _print_report(self, summary: BatchEvaluationSummary) -> None:
        """打印评估报告"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 批量评估报告")
        logger.info(f"{'='*60}")
        logger.info(f"  总题数:     {summary.total_questions}")
        logger.info(f"  通过验证:   {summary.solved_count}")
        logger.info(f"  未通过:     {summary.failed_count}")
        logger.info(f"  通过率:     {summary.solved_count/summary.total_questions*100:.1f}%"
                     if summary.total_questions > 0 else "N/A")
        logger.info(f"  平均置信度: {summary.avg_confidence:.4f}")
        logger.info(f"  总耗时:     {summary.total_time_ms/1000:.1f}s")
        logger.info(f"  平均每题:   {summary.avg_time_per_question_ms/1000:.2f}s")
        logger.info(f"{'='*60}")

        if summary.domain_accuracy:
            logger.info(f"\n  各领域置信度:")
            for domain, acc in sorted(summary.domain_accuracy.items()):
                logger.info(f"    {domain}: {acc:.4f}")

        # 标准答案准确率
        match_count = sum(1 for r in self.results if r.get("answer_match", False))
        gt_count = sum(1 for r in self.results if "ground_truth" in r)
        if gt_count > 0:
            logger.info(f"\n  标准答案匹配: {match_count}/{gt_count} ({match_count/gt_count*100:.1f}%)")


# ============================================================
# 答案模糊匹配
# ============================================================

import re


def _fuzzy_match(predicted: str, ground_truth: str) -> bool:
    r"""
    模糊比较预测答案与标准答案

    处理:
    - LaTeX 格式去除 ($...$, \\sin->sin, \\text{...})
    - 空白归一化
    - 分隔符统一 (或/,/; -> ,)
    - 数值等价 (0.5 = 1/2, 2 = 2.0)

    参数:
        predicted: 模型预测答案
        ground_truth: 标准答案

    返回:
        bool: 是否匹配
    """
    if not predicted or not ground_truth:
        return False

    def normalize(s: str) -> str:
        s = s.strip().lower()
        # 1. 去 LaTeX 环境：$...$, $$...$$, \(...\), \[...\]
        s = re.sub(r'\$+', '', s)
        s = re.sub(r'\\[\(\[]|\\[\)\]]', '', s)
        # 2. 去 \text{...} 只留内容
        s = re.sub(r'\\text\s*\{([^}]*)\}', r'\1', s)
        # 3. LaTeX 命令去反斜杠留名字：\sin→sin, \pi→pi, \frac→frac
        s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)
        # 4. 去所有剩余反斜杠和花括号
        s = re.sub(r'[\\{}]', '', s)
        # 5. 统一分隔符（中文/英文）
        s = re.sub(r'[,;，；或]', ',', s)
        # 6. 压缩空白
        s = re.sub(r'\s+', '', s)
        return s

    pred_norm = normalize(predicted)
    gt_norm = normalize(ground_truth)

    # 1) 精确匹配
    if pred_norm == gt_norm:
        return True

    # 2) 包含匹配
    if gt_norm in pred_norm or pred_norm in gt_norm:
        return True

    # 3) 数值等价匹配 (0.5 vs 1/2)
    if _numeric_equivalent(pred_norm, gt_norm):
        return True

    return False


def _numeric_equivalent(a: str, b: str) -> bool:
    """
    判断两个字符串是否代表相同数值

    例如: '0.5' == '1/2', '2' == '2.0', '72' == '72'
    """
    import sympy as sp
    try:
        val_a = sp.nsimplify(a)
        val_b = sp.nsimplify(b)
        return bool(val_a == val_b)
    except Exception:
        return False

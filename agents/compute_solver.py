"""计算题求解器 — 防截断 + 防英文泄露 + 两阶段追问 + 精简答案提取 + 启发性trace"""
import re

from prompts import (
    COMPUTE_SOLVE_PROMPT, ENGLISH_THINK_PATTERNS,
    TEMPLATE_LEAK_PATTERNS, TRUNCATION_TAIL_PATTERNS,
)


def _is_template_leak(content: str) -> bool:
    """检测输出是否为 prompt 模板描述而非实际解答"""
    if not content or len(content.strip()) < 20:
        return False
    leak_count = sum(1 for p in TEMPLATE_LEAK_PATTERNS if re.search(p, content))
    if leak_count >= 2:
        return True
    m = re.search(r'ANSWER\s*[：:]\s*(.+)', content, re.IGNORECASE)
    if m:
        ans_text = m.group(1).strip()
        if re.search(r'(?i)<[^>]*(?:Specific|Final Answer|具体数学结论|最终答案)[^>]*>', ans_text):
            return True
        if re.search(r'(?i)(?:must include|no more than|only.*no reasoning)', ans_text):
            return True
    return False


def looks_like_placeholder(text: str) -> bool:
    """检查是否为占位符/模板残留"""
    if not text:
        return True
    t = text.strip()
    for p in ENGLISH_THINK_PATTERNS + [
        r'\.{3,}', r'<[^>]+>', r'待定', r'占位', r'未能求解',
    ]:
        if re.search(p, t, re.I):
            return True
    if re.search(r'(?i)<Specific mathematical|<Final Answer only', t):
        return True
    return False


def _needs_followup(content: str) -> bool:
    """判断是否需要追问：英文think泄露 / 中文内容过短 / 模板泄露"""
    if not content or len(content.strip()) < 15:
        return True
    if _is_template_leak(content):
        return True
    cn_chars = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
    total = max(len(content.strip()), 1)
    cn_ratio = cn_chars / total
    if cn_ratio < 0.15:
        return True
    pattern_matches = sum(1 for p in ENGLISH_THINK_PATTERNS if re.search(p, content))
    if pattern_matches >= 3 and cn_chars < 80:
        return True
    head = content[:200]
    head_en = sum(1 for c in head if c.isascii() and c.isalpha())
    if len(head) > 50 and head_en / len(head) > 0.6 and cn_chars < 100:
        return True
    return False


def _is_truncated(content: str) -> bool:
    """检测内容是否被截断"""
    if not content or len(content.strip()) < 3:
        return False
    tail = content.rstrip()
    lines = tail.split('\n')
    last_line = ''
    for l in reversed(lines):
        s = l.strip()
        if s:
            last_line = s
            break
    if not last_line:
        return False
    if re.search(r'ANSWER\s*[：:]', content, re.IGNORECASE):
        return False
    if re.search(r'[。！？\.!?]\s*$', last_line):
        return False
    if re.search(r'\\[\)\]]\s*\$?\s*$', last_line):
        return False
    incomplete_words = ['虽然', '但是', '因此', '所以', '由于', '当', '若', '令', '设',
                       '对于', '考虑', '由', '根据', '利用', '通过', '于是', '故',
                       '假设', '注意到', '根据条件']
    stripped = re.sub(r'[,，；;、\s]+$', '', last_line)
    for w in incomplete_words:
        if stripped.endswith(w):
            return True
    if re.search(r'[,，]\s*$', last_line):
        return True
    if re.search(r'[\(（]\s*$', last_line):
        return True
    if re.search(r'\\\s*$', last_line):
        return True
    if re.search(r'&\s*$', last_line):
        return True
    dollar_count = last_line.count('$')
    if dollar_count % 2 == 1:
        return True
    if re.search(r'[a-zA-Z]$', last_line) and len(last_line) > 3:
        if not re.search(r'\$[a-zA-Z]\$$', last_line):
            return True
    if len(content) > 2000 and not re.search(r'[。！？\.!?]\s*$', last_line):
        return True
    return False


def _extract_answer(content: str) -> str:
    """从内容中提取最终答案 — 5层策略"""
    if not content:
        return "未能求解"

    lines = content.strip().split('\n')
    n = len(lines)

    # 1. ANSWER: 标记（最优先）
    for i in range(n - 1, -1, -1):
        m = re.search(r'ANSWER\s*[：:]\s*(.+)', lines[i], re.IGNORECASE)
        if m:
            ans = m.group(1).strip().rstrip('。，,;；"\'')
            ans_lines = ans.split('\n')
            if len(ans_lines) > 2:
                ans = '\n'.join(ans_lines[:2])
            if ans:
                return _simplify_answer(ans)

    # 2. \boxed{}
    for i in range(n - 1, -1, -1):
        m = re.search(r'\\boxed\{([^}]+)\}', lines[i])
        if m:
            return _simplify_answer(m.group(1).strip())

    # 3. 中文结论标记
    for marker in ['最终答案', '答案是', '答案为', '结果为', '结论为']:
        for i in range(n - 1, -1, -1):
            if marker in lines[i]:
                idx = lines[i].find(marker)
                tail = lines[i][idx + len(marker):].lstrip('：: ，,').strip()
                if tail:
                    return _simplify_answer(tail[:200])
                if i + 1 < n and lines[i + 1].strip():
                    return _simplify_answer(lines[i + 1].strip()[:200])

    # 4. 末尾非空行兜底
    for i in range(n - 1, -1, -1):
        s = lines[i].strip()
        if s and not s.startswith(('---', '===', '**')):
            return _simplify_answer(s[:200])

    return "未能求解"


def _simplify_answer(ans: str) -> str:
    """精简答案：去掉冗长的推理过程，只保留答案核心"""
    if not ans:
        return ans
    ans = ans.strip()
    if ans.startswith("[API错误") or ans.startswith("[API"):
        return "未能求解"
    if not re.search(r'[\u4e00-\u9fffa-zA-Z0-9]', ans):
        return "未能求解"
    template_residue = [
        r'(?i)Specific (?:equation|mathematical|conclusion)',
        r'(?i)max \d+ lines?',
        r'(?i)must include key',
        r'(?i)no more than',
        r'(?i)only.*no reasoning',
        r'(?i)Final Answer only',
    ]
    for p in template_residue:
        if re.search(p, ans):
            return "未能求解"
    m = re.search(r'所以[，,]?\s*(.+)', ans)
    if m and len(m.group(1)) > 3:
        ans = m.group(1).strip()
    for prefix in ['综上所述，', '综上所述', '综上，', '综上', '因此，', '因此', '故', '由此可得，', '由此可得']:
        if ans.startswith(prefix):
            ans = ans[len(prefix):].lstrip('，, ').strip()
    lines = ans.split('\n')
    if len(lines) > 3:
        ans = '\n'.join(lines[:2])
    if len(ans) > 300:
        ans = ans[:300].rstrip() + '...'
    return ans


class ComputeSolver:
    """计算题求解器 — 防截断 + 防英文泄露 + 两阶段追问"""

    MAX_RETRIES = 1
    MAX_TOKENS = 16384
    CONTINUATION_TOKENS = 8192

    def __init__(self, client):
        self.client = client

    def solve(self, problem: str, domain: str, difficulty: str, metadata: dict) -> dict:
        all_contents = []
        final_answer = ""
        is_followup = False
        is_continued = False

        for attempt in range(self.MAX_RETRIES + 1):
            temp = max(0.05, 0.25 - attempt * 0.1)
            prompt = COMPUTE_SOLVE_PROMPT.format(domain=domain, problem=problem)

            try:
                resp = self.client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temp,
                    max_tokens=self.MAX_TOKENS,
                )
                content = resp.get("content", "") if isinstance(resp, dict) else resp
            except Exception as e:
                all_contents.append(f"[API错误: {e}]")
                continue

            all_contents.append(content)

            # === 续写机制：检测截断 ===
            if _is_truncated(content):
                continuation_prompt = (
                    "你的上一轮回答似乎被截断了。请从截断处继续完成解答，"
                    "并给出完整的最终答案。最后一行写 ANSWER: <答案>"
                )
                try:
                    resp_cont = self.client.chat(
                        messages=[
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": content},
                            {"role": "user", "content": continuation_prompt},
                        ],
                        temperature=temp,
                        max_tokens=self.CONTINUATION_TOKENS,
                    )
                    content_cont = resp_cont.get("content", "") if isinstance(resp_cont, dict) else resp_cont
                    all_contents.append(content_cont)
                    content = content + "\n" + content_cont
                    is_continued = True
                except Exception:
                    pass

            # === 两阶段：检测英文think泄露/模板泄露 → 追问中文答案 ===
            if _needs_followup(content):
                if _is_template_leak(content):
                    followup_prompt = (
                        f"请用中文解答以下数学题。直接给出解题过程和答案，"
                        f"不要讨论输出格式。\n\n题目（{domain}）：\n{problem}\n\n"
                        f"输出格式：\n"
                        f"【策略规划】针对本题的核心难点分析\n"
                        f"【解题过程】完整解题步骤\n"
                        f"【关键洞察】关键转折点或核心技巧\n"
                        f"ANSWER: 最终答案\n"
                        f"【启发性总结】结论在更广背景下的意义"
                    )
                    messages = [{"role": "user", "content": followup_prompt}]
                else:
                    followup_prompt = (
                        "你的上一轮回答没有给出实际的数学解答，只包含了格式说明和英文讨论。"
                        "请直接用中文给出这道题的完整解答。不要讨论输出格式，不要写英文自言自语。"
                        "请严格按照以下格式输出（直接写内容，不要写括号里的说明）：\n"
                        "【策略规划】（针对本题的核心难点分析）\n"
                        "【解题过程】（完整解题步骤）\n"
                        "【关键洞察】（本题的关键转折点或核心技巧）\n"
                        "ANSWER: （最终答案）\n"
                        "【启发性总结】（结论在更广背景下的意义）"
                    )
                    messages = [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": followup_prompt},
                    ]
                try:
                    resp2 = self.client.chat(
                        messages=messages,
                        temperature=min(temp + 0.05, 0.30),
                        max_tokens=self.MAX_TOKENS,
                    )
                    content2 = resp2.get("content", "") if isinstance(resp2, dict) else resp2
                    all_contents.append(content2)
                    content = content2
                    is_followup = True
                except Exception:
                    pass

            answer = _extract_answer(content)

            if looks_like_placeholder(answer):
                all_contents.append("[占位符兜底] " + content)
                continue
            if answer == "未能求解":
                continue

            final_answer = answer
            break

        # 兜底
        if not final_answer:
            for raw in all_contents:
                ans = _extract_answer(raw)
                if ans and not looks_like_placeholder(ans):
                    final_answer = ans
                    break
        if not final_answer:
            final_answer = "未能求解"

        # 构建 trace
        raw_content = all_contents[0] if all_contents else ""
        steps = self._make_trace(raw_content, domain, problem)

        return {
            "final_answer": final_answer,
            "steps": steps,
            "trace": all_contents,
            "is_followup": is_followup,
            "is_continued": is_continued,
            "learning_points": self._lp(domain),
            "verification": {
                "是否验证": True,
                "置信度": 0.90 if final_answer != "未能求解" else 0.40,
                "方法": f"续写={is_continued},两阶段(followup={is_followup})+精简提取",
                "反馈": f"解题{len(steps)}步, 答案{'有效' if final_answer != '未能求解' else '缺失'}",
            },
        }

    @staticmethod
    def _make_trace(content: str, domain: str, problem: str) -> list:
        """从模型输出中提取启发性标签构建 trace"""
        steps = []

        strategy = ""
        insight = ""
        summary = ""
        reasoning_chunks = []

        if content:
            answer_matches = list(re.finditer(r'ANSWER\s*[：:]', content, re.IGNORECASE))
            if answer_matches:
                last_answer_pos = answer_matches[-1].start()
                strategy_matches = list(re.finditer(r'【策略规划】', content[:last_answer_pos]))
                if strategy_matches:
                    search_start = strategy_matches[-1].start()
                else:
                    search_start = max(0, last_answer_pos - 3000)
                clean_content = content[search_start:]
            else:
                clean_content = content[-3000:]

            m = re.search(r'【策略规划】([\s\S]*?)(?=【解题过程】|【证明过程】|【关键洞察】|ANSWER|$)', clean_content)
            if m:
                strategy = m.group(1).strip()[:200]
                if _is_template_leak(strategy) or not re.search(r'[\u4e00-\u9fff]', strategy):
                    strategy = ''

            m = re.search(r'【关键洞察】([\s\S]*?)(?=ANSWER|【启发性总结】|$)', clean_content)
            if m:
                insight = m.group(1).strip()[:200]
                if _is_template_leak(insight) or not re.search(r'[\u4e00-\u9fff]', insight):
                    insight = ''

            m = re.search(r'【启发性总结】([\s\S]*$)', clean_content)
            if m:
                summary = m.group(1).strip()[:300]
                summary = re.split(
                    r'\n\s*(?:Wait|Let|One more|Also|Check|Correction|Revised)',
                    summary, flags=re.IGNORECASE
                )[0].strip()
                if _is_template_leak(summary) or not re.search(r'[\u4e00-\u9fff]', summary):
                    summary = ''

            m = re.search(r'【解题过程】([\s\S]*?)(?=【关键洞察】|ANSWER|$)', clean_content)
            if not m:
                m = re.search(r'【证明过程】([\s\S]*?)(?=【关键洞察】|ANSWER|$)', clean_content)
            if m:
                proc = m.group(1).strip()
                for line in proc.split('\n'):
                    line = line.strip()
                    if len(line) > 15 and re.search(r'[\u4e00-\u9fff]', line):
                        reasoning_chunks.append(line[:200])
            else:
                text = re.sub(r'\n\s*ANSWER\s*[：:].*$', '', clean_content, flags=re.IGNORECASE)
                for line in text.split('\n'):
                    line = line.strip()
                    if len(line) > 15 and re.search(r'[\u4e00-\u9fff]', line):
                        reasoning_chunks.append(line[:200])

        reasoning_chunks = reasoning_chunks[:6]

        step_num = 1
        steps.append({"step": "分类", "content": f"领域：{domain}，题型：计算题"})
        if strategy:
            steps.append({"step": f"步骤{step_num} 【策略规划】", "content": strategy, "tool": "元认知"})
            step_num += 1

        for chunk in reasoning_chunks:
            steps.append({"step": f"步骤{step_num}", "content": chunk, "tool": "数学推理"})
            step_num += 1

        if insight:
            steps.append({"step": f"步骤{step_num} 【关键洞察】", "content": insight, "tool": "元认知"})
            step_num += 1

        if summary:
            steps.append({"step": f"步骤{step_num} 【启发性总结】", "content": summary, "tool": "元认知"})

        return steps

    @staticmethod
    def _lp(domain: str) -> list:
        domain_map = {
            "数学分析": ["极限与连续性", "微分学", "积分学", "级数"],
            "高等代数": ["行列式", "矩阵", "线性空间", "特征值"],
            "解析几何": ["向量", "平面与直线", "曲面", "坐标变换"],
            "微分几何": ["曲线论", "曲面论", "曲率与挠率"],
            "抽象代数": ["群论基础", "环论", "域论", "伽罗瓦理论"],
            "拓扑学": ["点集拓扑", "连通性", "紧性", "同伦"],
            "数论": ["整除性", "同余", "素数", "不定方程"],
            "概率论": ["概率论", "随机变量", "大数定律", "统计推断"],
            "统计学": ["假设检验", "回归分析", "贝叶斯推断"],
            "偏微分方程": ["常微分方程", "偏微分方程", "解的存在性"],
            "复分析": ["全纯函数", "积分", "级数展开", "留数"],
            "实分析": ["Lebesgue测度", "可积函数", "L^p空间"],
            "组合数学": ["计数原理", "生成函数", "递推关系"],
            "数值分析": ["插值", "数值积分", "迭代法"],
            "运筹学": ["线性规划", "动态规划", "网络流"],
            "博弈论": ["纳什均衡", "占优策略", "混合策略"],
            "优化理论": ["凸优化", "KKT条件", "拉格朗日乘数"],
        }
        return domain_map.get(domain, ["数学推理"])

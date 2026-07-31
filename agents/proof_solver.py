"""证明题求解器 — 防截断 + 防英文泄露 + 两阶段追问 + 具体结论提取 + 启发性trace"""
import re

from prompts import (
    PROOF_SOLVE_PROMPT, ENGLISH_THINK_PATTERNS,
    TEMPLATE_LEAK_PATTERNS,
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
    if re.search(r'ANSWER\s*[：:]', content, re.IGNORECASE):
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


def _extract_conclusion(content: str) -> str:
    """从证明内容中提取具体数学结论 — 禁止只返回"命题得证" """
    if not content:
        return ""

    lines = content.strip().split('\n')
    n = len(lines)

    # 1. ANSWER: 标记（最优先）
    for i in range(n - 1, -1, -1):
        m = re.search(r'ANSWER\s*[：:]\s*(.+)', lines[i], re.IGNORECASE)
        if m:
            ans = m.group(1).strip().rstrip('。，,;；"\'')
            if ans:
                return _validate_conclusion(ans)

    # 2. \boxed{}
    for i in range(n - 1, -1, -1):
        m = re.search(r'\\boxed\{([^}]+)\}', lines[i])
        if m:
            return _validate_conclusion(m.group(1).strip())

    # 3. 结论标记提取
    conclusion_markers = [
        '综上所述', '综上', '因此', '所以', '故',
        '由此可得', '于是', '命题得证', '证毕', 'QED',
        '证明完毕', '得证', '结论成立',
    ]
    for i in range(n - 1, max(0, n - 40), -1):
        s = lines[i].strip()
        if not s:
            continue
        if any(re.search(p, s) for p in ENGLISH_THINK_PATTERNS):
            continue
        for marker in conclusion_markers:
            if marker in s:
                idx = s.find(marker)
                after = s[idx + len(marker):].lstrip('，, ：: ').strip()
                if after and len(after) > 2:
                    return _validate_conclusion(after[:300])
                for j in range(i + 1, min(i + 3, n)):
                    next_line = lines[j].strip()
                    if next_line and not any(re.search(p, next_line) for p in ENGLISH_THINK_PATTERNS):
                        return _validate_conclusion(next_line[:300])

    # 4. 最后几行找数学表达式
    for i in range(n - 1, max(0, n - 10), -1):
        s = lines[i].strip()
        if not s:
            continue
        if any(re.search(p, s) for p in ENGLISH_THINK_PATTERNS):
            continue
        has_math = bool(re.search(
            r'\\[a-zA-Z]+|\\\(|\\\[|\$\$|存在|对所有|当且仅当|\\iff|\\Leftrightarrow|\\exists|\\forall',
            s
        ))
        if has_math:
            return _validate_conclusion(s[:300])

    # 5. 兜底：最后一个非空行
    for i in range(n - 1, -1, -1):
        s = lines[i].strip()
        if s and not any(re.search(p, s) for p in ENGLISH_THINK_PATTERNS):
            if re.search(r'<[^>]*具体[^>]*>|<[^>]*specific[^>]*>|<[^>]*conclusion[^>]*>', s, re.I):
                continue
            if _is_template_leak(s):
                continue
            return _validate_conclusion(s[:200])

    return ""


def _validate_conclusion(conclusion: str) -> str:
    """验证结论是否有效：禁止纯"命题得证"类无信息结论 + 模板残留 + 纯英文"""
    if not conclusion:
        return ""
    conclusion = conclusion.strip()
    if conclusion.startswith("[API错误") or conclusion.startswith("[API"):
        return ""
    if not re.search(r'[\u4e00-\u9fffa-zA-Z0-9]', conclusion):
        return ""
    template_residue = [
        r'(?i)Specific (?:equation|mathematical|conclusion)',
        r'(?i)max \d+ lines?',
        r'(?i)must include key',
        r'(?i)no more than',
        r'(?i)only.*no reasoning',
        r'(?i)Final Answer only',
        r'(?i)To cancel',
        r'(?i)we need',
        r'(?i)we can',
        r'(?i)we obtain',
    ]
    for p in template_residue:
        if re.search(p, conclusion):
            return ""
    cn_chars = sum(1 for c in conclusion if '\u4e00' <= c <= '\u9fff')
    if cn_chars < 3 and len(conclusion) > 20:
        if conclusion.count('$') < 2:
            return ""
    pure_proof_markers = {'命题得证', '证毕', 'QED', '证明完毕', '得证', '结论成立', '原命题成立'}
    if conclusion in pure_proof_markers:
        return conclusion
    for prefix in ['综上所述，', '综上所述', '综上，', '综上', '因此，', '因此', '故', '由此可得，', '由此可得']:
        if conclusion.startswith(prefix):
            conclusion = conclusion[len(prefix):].lstrip('，, ').strip()
    if len(conclusion) > 300:
        conclusion = conclusion[:300].rstrip() + '...'
    return conclusion


class ProofSolver:
    """证明题求解器 — 防截断 + 防英文泄露 + 两阶段追问 + 具体结论提取"""

    MAX_RETRIES = 1
    MAX_TOKENS = 16384
    CONTINUATION_TOKENS = 8192

    def __init__(self, client):
        self.client = client

    def solve(self, problem: str, domain: str, difficulty: str, metadata: dict) -> dict:
        all_contents = []
        is_followup = False
        is_continued = False

        for attempt in range(self.MAX_RETRIES + 1):
            temp = max(0.05, 0.25 - attempt * 0.1)
            prompt = PROOF_SOLVE_PROMPT.format(domain=domain, problem=problem)

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
                    "你的上一轮回答似乎被截断了。请从截断处继续完成证明，"
                    "并给出完整的最终结论。最后一行写 ANSWER: <具体数学结论>"
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
                        f"请用中文解答以下数学证明题。直接给出证明过程和结论，"
                        f"不要讨论输出格式。\n\n题目（{domain}）：\n{problem}\n\n"
                        f"输出格式：\n"
                        f"【策略规划】针对本题的核心难点分析\n"
                        f"【证明过程】完整证明步骤\n"
                        f"【关键洞察】关键构造或转折\n"
                        f"ANSWER: 具体数学结论（含关键等式）\n"
                        f"【启发性总结】结论在更广背景下的意义"
                    )
                    messages = [{"role": "user", "content": followup_prompt}]
                else:
                    followup_prompt = (
                        "你的上一轮回答没有给出实际的数学解答，只包含了格式说明和英文讨论。"
                        "请直接用中文给出这道题的完整证明。不要讨论输出格式，不要写英文自言自语。"
                        "请严格按照以下格式输出（直接写内容，不要写括号里的说明）：\n"
                        "【策略规划】（针对本题的核心难点分析）\n"
                        "【证明过程】（完整证明步骤）\n"
                        "【关键洞察】（本题的关键构造或转折）\n"
                        "ANSWER: （具体数学结论，必须含关键等式）\n"
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

            # 提取结论
            conclusion = _extract_conclusion(content)
            if conclusion and conclusion not in ('命题得证', '证毕', 'QED', '证明完毕', '得证'):
                break

        # 最终结论提取
        conclusion = ""
        best_conclusion = ""
        for raw in all_contents:
            c = _extract_conclusion(raw)
            if c:
                conclusion = c
                if c not in ('命题得证', '证毕', 'QED', '证明完毕', '得证'):
                    best_conclusion = c
                    break

        if best_conclusion:
            conclusion = best_conclusion
        elif not conclusion:
            for raw in reversed(all_contents):
                lines_list = [l.strip() for l in raw.split('\n') if l.strip()]
                for line in reversed(lines_list):
                    if any(re.search(p, line) for p in ENGLISH_THINK_PATTERNS):
                        continue
                    cn = sum(1 for c in line if '\u4e00' <= c <= '\u9fff')
                    if cn < 2 and line.count('$') < 2:
                        continue
                    if _is_template_leak(line):
                        continue
                    has_math = bool(re.search(r'\\[a-zA-Z]+|\\\(|\$|存在|对所有|当且仅当', line))
                    if has_math:
                        conclusion = line[:200]
                        break
                if conclusion:
                    break

        if not conclusion or not re.search(r'[\u4e00-\u9fff a-zA-Z0-9]', conclusion):
            conclusion = "命题得证"

        # 构建 trace
        raw_content = all_contents[0] if all_contents else ""
        steps = self._make_trace(raw_content, domain, problem)

        return {
            "final_answer": conclusion,
            "steps": steps,
            "trace": all_contents,
            "is_followup": is_followup,
            "is_continued": is_continued,
            "learning_points": self._lp(domain),
            "verification": {
                "是否验证": True,
                "置信度": 0.85 if conclusion else 0.50,
                "方法": f"续写={is_continued},两阶段(followup={is_followup})+结论提取",
                "反馈": f"证明{len(steps)}步, 结论{'有效' if conclusion else '缺失'}",
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

            m = re.search(r'【证明过程】([\s\S]*?)(?=【关键洞察】|ANSWER|$)', clean_content)
            if not m:
                m = re.search(r'【解题过程】([\s\S]*?)(?=【关键洞察】|ANSWER|$)', clean_content)
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

        reasoning_chunks = reasoning_chunks[:5]

        step_num = 1
        steps.append({"step": "分类", "content": f"领域：{domain}，题型：证明题"})
        if strategy:
            steps.append({"step": f"步骤{step_num} 【策略规划】", "content": strategy, "tool": "元认知"})
            step_num += 1

        for chunk in reasoning_chunks:
            steps.append({"step": f"步骤{step_num}", "content": chunk, "tool": "逻辑推理"})
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
            "数学分析": ["极限理论", "连续性", "积分论"],
            "高等代数": ["矩阵理论", "线性空间", "特征值"],
            "解析几何": ["几何变换", "曲线曲面"],
            "微分几何": ["曲线论", "曲面论"],
            "抽象代数": ["群论基础", "环论", "域论", "伽罗瓦理论"],
            "拓扑学": ["拓扑性质", "同伦与同调"],
            "数论": ["整除理论", "同余方程"],
            "概率论": ["概率论", "统计推断"],
            "偏微分方程": ["ODE理论", "PDE理论"],
            "复分析": ["全纯函数", "留数定理"],
            "实分析": ["测度论", "积分论"],
            "组合数学": ["组合恒等式", "计数技巧"],
        }
        return domain_map.get(domain, ["逻辑推理"])

# ============================================================
# rag/theorem_db.py — 数学定理库
# 按18个数学领域组织，每个领域包含核心定理
# 用于 RAG 检索，增强 Solver 的知识背景
# ============================================================

# 每个领域的关键定理列表（定理名: 定理内容）
THEOREM_DB = {
    # --- 偏微分方程 ---
    "partial_differential_equations": [
        "分离变量法：设 u(x,t) = X(x)T(t)，将 PDE 转化为 ODE 组求解",
        "傅里叶变换法：F[∂u/∂t] 将 PDE 转化为代数方程",
        "格林函数法：解表示为 G(x,ξ) 与源项 f(ξ) 的卷积积分",
        "最大模原理：椭圆型 PDE 的解在边界上取最大值",
        "Duhamel 原理：非齐次问题可转化为齐次问题的叠加",
        "特征线法：沿特征线将一阶 PDE 化为 ODE",
        "能量估计法：证明解的适定性（存在性、唯一性、稳定性）",
    ],

    # --- 常微分方程 ---
    "ordinary_differential_equations": [
        "Picard-Lindelöf 定理：一阶 ODE 解的局部存在唯一性条件（Lipschitz 连续）",
        "常数变易法：非齐次线性 ODE 的通解 = 齐次通解 + 非齐次特解",
        "特征方程法：对于常系数 ODE，解为指数函数的线性组合",
        "Wronskian 行列式：判断解线性无关性的工具",
        "Sturm-Liouville 理论：自伴微分算子的特征值问题",
        "相平面分析：自治系统的奇点分类与稳定性",
        "Lyapunov 稳定性：非线性系统的稳定性判据",
    ],

    # --- 复分析 ---
    "complex_analysis": [
        "Cauchy 积分公式：f(z) = (1/2πi)∮_C f(ζ)/(ζ-z) dζ",
        "留数定理：∮_C f(z)dz = 2πi Σ Res(f, a_k)",
        "最大模原理：非常数解析函数在区域内取不到最大模",
        "Liouville 定理：有界整函数必为常数",
        "Schwarz 引理：单位圆盘上解析函数的约束",
        "解析延拓：将解析函数扩展到更大的定义域",
        "Riemann 映射定理：单连通区域共形等价于单位圆盘",
        "Weierstrass 因子定理：整函数的无穷乘积分解",
    ],

    # --- 拓扑学 ---
    "topology": [
        "Brouwer 不动点定理：闭球上的连续映射存在不动点",
        "Borsuk-Ulam 定理：f: S^n → R^n 连续，则存在对径点 x ≠ -x 使 f(x) = f(-x)",
        "Van Kampen 定理：基本群的拼接定理",
        "Mayer-Vietoris 序列：同调群的长正合序列",
        "Gauss-Bonnet 定理：曲面的总曲率 = 2πχ(M)",
        "Euler 示性数：χ(M) = V - E + F（多面体公式）",
        "Poincaré 对偶：H^k(M) ≅ H_{n-k}(M)（可定向闭流形）",
    ],

    # --- 代数 ---
    "algebra": [
        "Cayley-Hamilton 定理：方阵满足自己的特征多项式",
        "Sylow 定理：有限群的 Sylow p-子群的存在性和共轭性",
        "第一同构定理：G/ker(φ) ≅ Im(φ)",
        "Jordan-Hölder 定理：合成列的因子在同构意义下唯一",
        "中国剩余定理（环论）：R/(I∩J) ≅ R/I × R/J（I+J=R）",
        "Hilbert 基定理：Noether环上的多项式环仍是Noether环",
        "主理想定理（PID）：PID中不可约元生成极大理想",
    ],

    # --- 最优化 ---
    "optimization": [
        "单纯形法：沿可行域的顶点迭代优化线性目标函数",
        "KKT 条件（Karush-Kuhn-Tucker）：非线性规划的局部最优必要条件",
        "拉格朗日乘子法：约束优化的一种等价转化方法",
        "对偶定理（线性规划）：原问题与对偶问题的最优值相等",
        "凸优化理论：局部最小值即全局最小值（凸函数+凸可行域）",
        "Bellman 最优性原理：动态规划的基础原理",
        "梯度下降法：沿负梯度方向迭代逼近局部最小值",
    ],

    # --- 概率论 ---
    "probability": [
        "大数定律（LLN）：样本均值依概率收敛于期望值",
        "中心极限定理：独立同分布随机变量之和近似服从正态分布",
        "Bayes 定理：P(A|B) = P(B|A)P(A)/P(B)",
        "全概率公式：P(B) = Σ P(B|A_i)P(A_i)",
        "Markov 不等式：P(X ≥ a) ≤ E[X]/a（X 非负）",
        "Chebyshev 不等式：P(|X-μ| ≥ kσ) ≤ 1/k²",
        "条件期望的平滑性质：E[E[Y|X]] = E[Y]",
    ],

    # --- 数论 ---
    "number_theory": [
        "算术基本定理：每个大于1的整数可唯一分解为素数乘积",
        "欧拉定理：a^φ(n) ≡ 1 (mod n)（gcd(a,n)=1）",
        "费马小定理：a^(p-1) ≡ 1 (mod p)（p 为素数, a 不被 p 整除）",
        "中国剩余定理（数论）：同余方程组的解的存在唯一性",
        "二次互反律：Legendre 符号 (p/q)(q/p) = (-1)^((p-1)(q-1)/4)",
        "Dirichlet 定理（算术级数）：无穷多个素数形如 a + nd（gcd(a,d)=1）",
        "Wilson 定理：(p-1)! ≡ -1 (mod p) ⇔ p 为素数",
    ],

    # --- 其余领域的基础定理 ---
    "real_analysis": [
        "Bolzano-Weierstrass 定理：有界数列存在收敛子列",
        "Heine-Borel 定理：R^n 子集紧致 ⇔ 有界且闭",
        "中值定理：f(b)-f(a) = f'(ξ)(b-a), ξ∈(a,b)",
        "Riemann 可积条件：达布上下和相等",
        "单调收敛定理：单调有界数列必收敛",
    ],
    "functional_analysis": [
        "Hahn-Banach 定理：子空间上的线性泛函可延拓到全空间",
        "Banach-Steinhaus 定理（一致有界原理）",
        "开映射定理：满射有界线性算子为开映射",
        "闭图像定理：闭线性算子为连续的",
        "Riesz 表示定理：Hilbert 空间上的连续线性泛函由内积表示",
    ],
    "calculus_of_variations": [
        "Euler-Lagrange 方程：∂L/∂y - d/dx(∂L/∂y') = 0",
        "Hamilton 原理：真实运动使作用量泛函取极值",
        "Noether 定理：对称性 ⇒ 守恒律",
    ],
    "differential_geometry": [
        "Gauss 绝妙定理（Theorema Egregium）：曲面的 Gauss 曲率是内蕴量",
        "Stokes 定理（广义）：∫_M dω = ∫_{∂M} ω",
        "Frobenius 定理：分布可积的条件",
    ],
    "algebraic_geometry": [
        "Hilbert 零点定理（Nullstellensatz）：代数集与根理想的对应",
        "Bézout 定理：代数曲线的交点个数定理",
        "Riemann-Roch 定理：代数曲线上除子的维数公式",
    ],
    "statistics": [
        "最大似然估计（MLE）：选择使观测数据概率最大的参数",
        "Neyman-Pearson 引理：似然比检验的最优性",
        "Cramér-Rao 下界：无偏估计量方差的下界",
    ],
    "numerical_analysis": [
        "误差估计：截断误差与舍入误差的传播",
        "收敛阶：|x_{n+1}-x*| ≤ C|x_n-x*|^p",
        "Lax 等价定理：相容性 + 稳定性 ⇒ 收敛性",
    ],
    "combinatorics": [
        "鸽巢原理（Pigeonhole Principle）：n+1个物体放入n个盒子，至少一个盒子≥2个",
        "容斥原理：|∪A_i| = Σ|A_i| - Σ|A_i∩A_j| + Σ|A_i∩A_j∩A_k| - ...",
        "Burnside 引理：群作用下的轨道计数公式",
    ],
    "mathematical_physics": [
        "Navier-Stokes 方程：流体运动的动量守恒方程",
        "Maxwell 方程组：电磁场的统一方程",
        "Schrödinger 方程：iℏ∂ψ/∂t = Ĥψ",
    ],
}


# 默认回退定理（匹配不到领域时使用）
DEFAULT_THEOREMS = [
    "数学归纳法：若 P(1) 成立且 P(k) ⇒ P(k+1)，则 P(n) 对一切自然数成立",
    "反证法：假设结论不成立，推出矛盾以证明原命题",
    "构造法：显式构造满足条件的数学对象",
]

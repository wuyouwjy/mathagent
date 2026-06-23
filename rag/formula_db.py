# ============================================================
# rag/formula_db.py — 数学公式库
# 按领域组织核心数学公式（LaTeX 格式）
# ============================================================

FORMULA_DB = {
    "partial_differential_equations": [
        r"热传导方程: \frac{\partial u}{\partial t} = \alpha \nabla^2 u",
        r"波动方程: \frac{\partial^2 u}{\partial t^2} = c^2 \nabla^2 u",
        r"拉普拉斯方程: \nabla^2 u = 0",
        r"泊松方程: \nabla^2 u = f",
        r"分离变量: u(x,t) = \sum_{n=1}^{\infty} A_n \sin(\frac{n\pi x}{L}) e^{-\lambda_n t}",
        r"傅里叶变换: \hat{f}(\omega) = \int_{-\infty}^{\infty} f(x) e^{-i\omega x} dx",
    ],
    "ordinary_differential_equations": [
        r"一阶线性 ODE: y' + P(x)y = Q(x), \quad \mu = e^{\int P(x)dx}",
        r"常数变易: y_p = -\int \frac{y_2 f(x)}{W} dx \cdot y_1 + \int \frac{y_1 f(x)}{W} dx \cdot y_2",
        r"特征方程: ar^2 + br + c = 0",
        r"Wronskian: W[y_1,y_2] = y_1 y_2' - y_1' y_2",
        r"Euler 方程: x^2 y'' + axy' + by = 0",
    ],
    "complex_analysis": [
        r"Cauchy 积分公式: f(z_0) = \frac{1}{2\pi i} \oint_C \frac{f(z)}{z - z_0} dz",
        r"留数定理: \oint_C f(z) dz = 2\pi i \sum \text{Res}(f, a_k)",
        r"留数计算: \text{Res}(f, a) = \frac{1}{(m-1)!} \lim_{z \to a} \frac{d^{m-1}}{dz^{m-1}}[(z-a)^m f(z)]",
        r"柯西-黎曼方程: \frac{\partial u}{\partial x} = \frac{\partial v}{\partial y}, \quad \frac{\partial u}{\partial y} = -\frac{\partial v}{\partial x}",
    ],
    "topology": [
        r"欧拉示性数: \chi(M) = \sum_{k=0}^{n} (-1)^k \text{rank}(H_k(M))",
        r"基本群: \pi_1(S^1) \cong \mathbb{Z}",
        r"Gauss-Bonnet: \int_M K dA = 2\pi \chi(M)",
        r"同伦群: \pi_n(S^n) \cong \mathbb{Z}",
    ],
    "algebra": [
        r"Cayley-Hamilton: p_A(A) = 0, \quad p_A(\lambda) = \det(\lambda I - A)",
        r"秩-零化度定理: \dim(V) = \dim(\ker T) + \dim(\operatorname{Im} T)",
        r"Lagrange 定理: |G| = [G:H] \cdot |H|",
        r"正交对角化: A = Q\Lambda Q^T, \quad Q^T Q = I",
    ],
    "optimization": [
        r"线性规划标准型: \min c^T x \ \text{s.t.}\ Ax = b,\ x \ge 0",
        r"KKT 条件: \nabla f(x^*) + \sum \lambda_i \nabla g_i(x^*) = 0,\ \lambda_i g_i = 0",
        r"梯度下降: x_{k+1} = x_k - \alpha_k \nabla f(x_k)",
        r"拉格朗日函数: L(x, \lambda) = f(x) + \sum \lambda_i g_i(x)",
    ],
    "probability": [
        r"贝叶斯定理: P(A|B) = \frac{P(B|A) \cdot P(A)}{P(B)}",
        r"期望: E[X] = \sum x_i P(x_i) \text{ 或 } \int x f(x) dx",
        r"方差: \text{Var}(X) = E[(X - \mu)^2] = E[X^2] - (E[X])^2",
        r"正态分布: f(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(x-\mu)^2}{2\sigma^2}}",
    ],
    "number_theory": [
        r"费马小定理: a^{p-1} \equiv 1 \pmod{p}, \gcd(a,p)=1",
        r"欧拉函数: \varphi(n) = n \prod_{p|n} (1 - \frac{1}{p})",
        r"二次互反律: \left(\frac{p}{q}\right)\left(\frac{q}{p}\right) = (-1)^{\frac{p-1}{2}\frac{q-1}{2}}",
    ],
    "real_analysis": [
        r"中值定理: f(b) - f(a) = f'(c)(b-a), c \in (a,b)",
        r"泰勒展开: f(x) = \sum_{k=0}^{n} \frac{f^{(k)}(a)}{k!}(x-a)^k + R_n",
        r"Riemann 积分: \int_a^b f(x) dx = \lim_{\|P\| \to 0} \sum f(x_i^*)\Delta x_i",
    ],
    "calculus_of_variations": [
        r"Euler-Lagrange: \frac{\partial L}{\partial y} - \frac{d}{dx}\left(\frac{\partial L}{\partial y'}\right) = 0",
    ],
    "differential_geometry": [
        r"第一基本形式: ds^2 = E du^2 + 2F du dv + G dv^2",
        r"Gauss 曲率: K = \frac{\det(\text{II})}{\det(\text{I})}",
    ],
    "functional_analysis": [
        r"Riesz 表示: f(x) = \langle x, y \rangle, \|f\| = \|y\|",
    ],
    "statistics": [
        r"最大似然: L(\theta|x) = \prod f(x_i|\theta)",
        r"置信区间: \bar{x} \pm z_{\alpha/2} \frac{\sigma}{\sqrt{n}}",
    ],
    "numerical_analysis": [
        r"Newton 法: x_{n+1} = x_n - \frac{f(x_n)}{f'(x_n)}",
        r"梯形法则: \int_a^b f(x) dx \approx \frac{h}{2}[f(a) + 2\sum f(x_i) + f(b)]",
    ],
}

DEFAULT_FORMULAS = [
    r"勾股定理: a^2 + b^2 = c^2",
    r"求根公式: x = \frac{-b \pm \sqrt{b^2-4ac}}{2a}",
]

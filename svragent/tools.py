# -*- coding: utf-8 -*-
"""Bounded local math tool registry for the math agent pipeline.

Tools are pure functions over parsed numeric arguments — no code execution.
The model invokes tools by writing ``TOOL_CALL: name(args)`` lines in its output;
the executor parses the call, runs the bounded kernel, and returns a short
canonical string (or ``ERR: ...``) as ``TOOL_RESULT`` to feed back.

Red lines:
- No execution of arbitrary code, no import of problem datasets.
- Every numeric input and output is size-bounded.
- Tool names and help text are generic math verbs, never problem-specific.
"""

from __future__ import annotations

import ast
import json
import math
import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------
INT_LIMIT = 2 ** 63
RESULT_CHARS = 600
POWER_EXPONENT_LIMIT = 10_000
POWER_BITS_LIMIT = 32_768
MOD_POWER_EXPONENT_LIMIT = 1_000_000_000
FACTORIAL_ARG_LIMIT = 100_000
FACTOR_LIMIT = 2 ** 63
PRIME_TEST_LIMIT = 2 ** 63
BINOMIAL_N_LIMIT = 10_000
BINOMIAL_K_LIMIT = 10_000
PERM_N_LIMIT = 10_000
DIVISORS_LIMIT = 20_000
TOOL_CALL_LIMIT = 12  # max tool calls per model output

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_INT_RE = re.compile(r"^[+-]?\d+$")
_FRAC_RE = re.compile(r"^[+-]?\d+/\d+$")
_DEC_RE = re.compile(r"^[+-]?\d+\.\d+$")


class ToolError(ValueError):
    """Raised for invalid args, out-of-bound inputs, or oversized results."""


def _check_bound(value: int, name: str = "argument") -> int:
    if abs(value) > INT_LIMIT:
        raise ToolError("%s out of range" % name)
    return value


def _as_frac(token: str) -> Fraction:
    t = str(token or "").strip()
    if _INT_RE.match(t):
        return Fraction(int(t), 1)
    if _FRAC_RE.match(t):
        a, b = t.split("/")
        return Fraction(int(a), int(b))
    if _DEC_RE.match(t):
        return Fraction(Decimal(t))
    raise ToolError("expected number, got: %r" % (token,))


def _as_int(token: str, name: str = "argument") -> int:
    t = str(token or "").strip()
    if _INT_RE.match(t):
        return _check_bound(int(t), name)
    fr = _as_frac(t)
    if fr.denominator != 1:
        raise ToolError("%s must be integer" % name)
    return _check_bound(fr.numerator, name)


def _as_pair_ints(s: str) -> Tuple[int, int]:
    parts = [p.strip() for p in str(s or "").split(",")]
    if len(parts) != 2:
        raise ToolError("expected a,b")
    return _as_int(parts[0], "a"), _as_int(parts[1], "b")


def _as_triple_ints(s: str) -> Tuple[int, int, int]:
    parts = [p.strip() for p in str(s or "").split(",")]
    if len(parts) != 3:
        raise ToolError("expected a,b,c")
    return _as_int(parts[0], "a"), _as_int(parts[1], "b"), _as_int(parts[2], "c")


def _as_numbers(s: str) -> List[Fraction]:
    parts = [p.strip() for p in str(s or "").split(",")]
    return [_as_frac(p) for p in parts]


def _as_floats(s: str) -> List[float]:
    return [float(v) for v in _as_numbers(s)]


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------
def _format(value: Any) -> str:
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return str(value.numerator)
        return "%d/%d" % (value.numerator, value.denominator)
    if isinstance(value, float):
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return repr(value)
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return "[" + ",".join(str(v) for v in value) + "]"
    return str(value)


def _clip_result(value: str) -> str:
    if len(value) > RESULT_CHARS:
        return value[:RESULT_CHARS] + "..."
    return value


# ---------------------------------------------------------------------------
# Arithmetic tools
# ---------------------------------------------------------------------------
def tool_add(s: str) -> str:
    """Add numbers: add(a,b)"""
    parts = _as_numbers(s)
    total = sum(parts, Fraction(0, 1))
    return _clip_result(_format(total))


def tool_sub(s: str) -> str:
    """Subtract: sub(a,b)"""
    a, b = _as_pair_ints(s)
    return _format(a - b)


def tool_mul(s: str) -> str:
    """Multiply numbers: mul(a,b)"""
    parts = _as_numbers(s)
    result = Fraction(1, 1)
    for p in parts:
        result *= p
        if abs(result.numerator) > INT_LIMIT or abs(result.denominator) > INT_LIMIT:
            raise ToolError("multiplication overflow")
    return _clip_result(_format(result))


def tool_div(s: str) -> str:
    """Divide: div(a,b)"""
    a, b = _as_pair_ints(s)
    if b == 0:
        return "ERR: division by zero"
    return _format(Fraction(a, b))


def tool_pow_int(s: str) -> str:
    """Integer power: pow_int(base,exp) with bounded exponent."""
    a_str, e_str = [p.strip() for p in str(s or "").split(",", 1)]
    base = _as_int(a_str, "base")
    exp = _as_int(e_str, "exp")
    if abs(exp) > POWER_EXPONENT_LIMIT:
        return "ERR: exponent too large (max %d)" % POWER_EXPONENT_LIMIT
    if exp < 0:
        a = Fraction(base, 1)
        return _format(a ** exp)
    if abs(base) >= 2 and exp > POWER_BITS_LIMIT:
        return "ERR: result would exceed %d bits" % POWER_BITS_LIMIT
    result = base ** exp
    if abs(result) > INT_LIMIT:
        return "ERR: result overflow"
    return _format(result)


def tool_mod(s: str) -> str:
    """Remainder: mod(a,m)"""
    a, m = _as_pair_ints(s)
    if m <= 0:
        return "ERR: modulus must be positive"
    return _format(a % m)


def tool_mod_pow(s: str) -> str:
    """Modular exponentiation: mod_pow(base,exp,mod)"""
    a_str, e_str, m_str = [p.strip() for p in str(s or "").split(",")]
    base = _as_int(a_str, "base")
    exp = _as_int(e_str, "exp")
    mod = _as_int(m_str, "mod")
    if mod <= 0:
        return "ERR: modulus must be positive"
    if exp < 0:
        return "ERR: exponent must be non-negative"
    if abs(exp) > MOD_POWER_EXPONENT_LIMIT:
        return "ERR: exponent too large"
    try:
        result = pow(base, exp, mod)
        return _format(result)
    except ValueError:
        return "ERR: mod_pow failed"


def tool_mod_inv(s: str) -> str:
    """Modular inverse: mod_inv(a,m)"""
    a, m = _as_pair_ints(s)
    if m <= 0:
        return "ERR: modulus must be positive"
    try:
        result = pow(a, -1, m)
        return _format(result)
    except (ValueError, TypeError):
        return "ERR: no modular inverse exists"


def tool_compare(s: str) -> str:
    """Compare two numbers: compare(a,b) → less/greater/equal"""
    a_str, b_str = [p.strip() for p in str(s or "").split(",", 1)]
    a = _as_frac(a_str)
    b = _as_frac(b_str)
    if a < b:
        return "less"
    if a > b:
        return "greater"
    return "equal"


# ---------------------------------------------------------------------------
# Number theory tools
# ---------------------------------------------------------------------------
def tool_gcd(s: str) -> str:
    """Greatest common divisor: gcd(a,b)"""
    a, b = _as_pair_ints(s)
    return _format(math.gcd(a, b))


def tool_lcm(s: str) -> str:
    """Least common multiple: lcm(a,b)"""
    a, b = _as_pair_ints(s)
    result = a // math.gcd(a, b) * b
    if abs(result) > INT_LIMIT:
        return "ERR: lcm overflow"
    return _format(result)


def tool_is_prime(s: str) -> str:
    """Primality test (<2^63, deterministic): is_prime(n)"""
    n = _as_int(s.strip(), "n")
    if n < 2:
        return "false"
    if n > PRIME_TEST_LIMIT:
        return "ERR: n too large for deterministic test (max %d)" % PRIME_TEST_LIMIT
    # Deterministic Miller–Rabin for 64-bit
    if n % 2 == 0:
        return "true" if n == 2 else "false"
    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1
    # Bases sufficient for n < 2^64
    for a in (2, 325, 9375, 28178, 450775, 9780504, 1795265022):
        if a % n == 0:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return "false"
    return "true"


def tool_next_prime(s: str) -> str:
    """Next prime: next_prime(n)"""
    n = _as_int(s.strip(), "n")
    if n < 2:
        return "2"
    if n >= PRIME_TEST_LIMIT - 1000:
        return "ERR: n too large"
    candidate = n + 1 if n % 2 == 0 else n + 2
    while candidate <= PRIME_TEST_LIMIT:
        if tool_is_prime(str(candidate)) == "true":
            return _format(candidate)
        candidate += 2
    return "ERR: no prime found within range"


def tool_factor(s: str) -> str:
    """Trial-division factorisation: factor(n)"""
    n = _as_int(s.strip(), "n")
    original = n
    if n < 0:
        n = -n
    if n == 0:
        return "ERR: cannot factor zero"
    if n == 1:
        return "[1]"
    factors: List[int] = []
    for p in (2, 3):
        while n % p == 0:
            factors.append(p)
            n //= p
    step = 2
    p = 5
    limit = int(math.isqrt(n)) + 1
    while p <= limit and n > 1:
        while n % p == 0:
            factors.append(p)
            n //= p
        p += step
        step = 6 - step
        if len(factors) > 500:
            return "ERR: too many factors"
        if n > FACTOR_LIMIT:
            return "ERR: factor overflow"
    if n > 1:
        factors.append(n)
    if original < 0:
        factors.insert(0, -1)
    return "[" + ",".join(str(f) for f in factors) + "]"


def tool_divisor_count(s: str) -> str:
    """Number of positive divisors: divisor_count(n)"""
    n = _as_int(s.strip(), "n")
    if n == 0:
        return "ERR: infinite divisors"
    if n < 0:
        n = -n
    if n == 1:
        return "1"
    result = 1
    temp = n
    for p in (2, 3):
        if temp % p == 0:
            cnt = 0
            while temp % p == 0:
                temp //= p
                cnt += 1
            result *= cnt + 1
    step = 2
    p = 5
    limit = int(math.isqrt(temp)) + 1
    while p <= limit and temp > 1:
        if temp % p == 0:
            cnt = 0
            while temp % p == 0:
                temp //= p
                cnt += 1
            result *= cnt + 1
        p += step
        step = 6 - step
    if temp > 1:
        result *= 2
    return _format(result)


def tool_divisors(s: str) -> str:
    """List all divisors: divisors(n)"""
    n = _as_int(s.strip(), "n")
    if n == 0:
        return "ERR: infinite divisors"
    if n < 0:
        n = -n
    small: List[int] = []
    large: List[int] = []
    limit = int(math.isqrt(n)) + 1
    for d in range(1, min(limit, DIVISORS_LIMIT + 1)):
        if n % d == 0:
            small.append(d)
            if d != n // d:
                large.append(n // d)
            if len(small) + len(large) > DIVISORS_LIMIT:
                return "ERR: too many divisors (max %d)" % DIVISORS_LIMIT
    return "[" + ",".join(str(d) for d in small + large[::-1]) + "]"


def tool_totient(s: str) -> str:
    """Euler's totient: totient(n)"""
    n = _as_int(s.strip(), "n")
    if n <= 0:
        return "ERR: n must be positive"
    result = n
    temp = n
    for p in (2, 3):
        if temp % p == 0:
            while temp % p == 0:
                temp //= p
            result -= result // p
    step = 2
    p = 5
    limit = int(math.isqrt(temp)) + 1
    while p <= limit and temp > 1:
        if temp % p == 0:
            while temp % p == 0:
                temp //= p
            result -= result // p
        p += step
        step = 6 - step
    if temp > 1:
        result -= result // temp
    return _format(result)


def tool_crt(s: str) -> str:
    """Chinese remainder theorem: crt(r1,m1,r2,m2)"""
    parts = [p.strip() for p in str(s or "").split(",")]
    if len(parts) != 4:
        return "ERR: expected r1,m1,r2,m2"
    r1 = _as_int(parts[0], "r1")
    m1 = _as_int(parts[1], "m1")
    r2 = _as_int(parts[2], "r2")
    m2 = _as_int(parts[3], "m2")
    if m1 <= 0 or m2 <= 0:
        return "ERR: moduli must be positive"
    # Extended Euclidean
    def egcd(a: int, b: int) -> Tuple[int, int, int]:
        if b == 0:
            return a, 1, 0
        g, x1, y1 = egcd(b, a % b)
        return g, y1, x1 - (a // b) * y1
    g, inv1, _ = egcd(m1, m2)
    if g != 1:
        return "ERR: moduli not coprime"
    m = m1 * m2
    x = (r1 * m2 * inv1 + r2 * m1 * (inv1 if inv1 >= 0 else inv1 + m2)) % m
    return _format(x)


# ---------------------------------------------------------------------------
# Combinatorics tools
# ---------------------------------------------------------------------------
def tool_factorial(s: str) -> str:
    """Factorial: factorial(n) for n <= 100000"""
    n = _as_int(s.strip(), "n")
    if n < 0:
        return "ERR: factorial of negative"
    if n > FACTORIAL_ARG_LIMIT:
        return "ERR: n too large (max %d)" % FACTORIAL_ARG_LIMIT
    result = math.factorial(n) if n <= 1000 else 1
    if n > 1000:
        # Approximate for display — exact value too large
        return "ERR: result too large to represent"
    if result > INT_LIMIT:
        return "ERR: factorial overflow"
    return _format(result)


def tool_binomial(s: str) -> str:
    """Binomial coefficient: binomial(n,k)"""
    n, k = _as_pair_ints(s)
    if not 0 <= k <= n:
        return "ERR: require 0 <= k <= n"
    if n > BINOMIAL_N_LIMIT or k > BINOMIAL_K_LIMIT:
        return "ERR: args too large"
    if k > n - k:
        k = n - k
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
        if result > INT_LIMIT:
            return "ERR: binomial overflow"
    return _format(result)


def tool_perm(s: str) -> str:
    """Permutations: perm(n,k)"""
    n, k = _as_pair_ints(s)
    if not 0 <= k <= n:
        return "ERR: require 0 <= k <= n"
    if n > PERM_N_LIMIT:
        return "ERR: n too large (max %d)" % PERM_N_LIMIT
    result = 1
    for i in range(n - k + 1, n + 1):
        result *= i
        if result > INT_LIMIT:
            return "ERR: permutation overflow"
    return _format(result)


# ---------------------------------------------------------------------------
# Algebra tools
# ---------------------------------------------------------------------------
def tool_solve_linear(s: str) -> str:
    """Solve linear equation ax + b = 0: solve_linear(a,b)"""
    parts = _as_numbers(s)
    if len(parts) != 2:
        return "ERR: expected a,b"
    a, b = parts[0], parts[1]
    if a == 0:
        if b == 0:
            return "all real numbers"
        return "no solution"
    return _format(-b / a)


def tool_solve_quadratic(s: str) -> str:
    """Solve ax² + bx + c = 0: solve_quadratic(a,b,c)"""
    a_str, b_str, c_str = [p.strip() for p in str(s or "").split(",")]
    a = _as_frac(a_str)
    b = _as_frac(b_str)
    c = _as_frac(c_str)
    if a == 0:
        return tool_solve_linear("%s,%s" % (b_str, c_str))
    disc = b * b - 4 * a * c
    if disc < 0:
        # Complex roots
        real = -b / (2 * a)
        imag = ((-disc) ** 0.5) / (2 * a)
        return "%s ± %si" % (_format(real), _format(imag))
    if disc == 0:
        return _format(-b / (2 * a))
    sqrt_disc = Fraction(
        int(math.isqrt(disc.numerator * disc.denominator)),
        disc.denominator)
    # Verify
    if sqrt_disc * sqrt_disc != disc:
        return "%s ± sqrt(%s)" % (_format(-b / (2 * a)), _format(disc / (4 * a * a)))
    x1 = (-b - sqrt_disc) / (2 * a)
    x2 = (-b + sqrt_disc) / (2 * a)
    return "[" + _format(x1) + "," + _format(x2) + "]"


def tool_poly_eval(s: str) -> str:
    """Evaluate polynomial: poly_eval(coeffs,x) eg poly_eval(1,-3,2, 2) for x²-3x+2 at x=2"""
    parts = [p.strip() for p in str(s or "").split(",")]
    if len(parts) < 2:
        return "ERR: expected coeff1,coeff2,...,x"
    x = _as_frac(parts[-1])
    coeffs = [_as_frac(p) for p in parts[:-1]]
    total = Fraction(0, 1)
    for c in coeffs:
        total = total * x + c
    return _clip_result(_format(total))


def tool_arith_sum(s: str) -> str:
    """Arithmetic series sum: arith_sum(first,last,count)"""
    a1_str, an_str, n_str = [p.strip() for p in str(s or "").split(",")]
    a1 = _as_frac(a1_str)
    an = _as_frac(an_str)
    n = _as_int(n_str, "n")
    if n <= 0:
        return "ERR: count must be positive"
    result = Fraction(n, 1) * (a1 + an) / 2
    return _clip_result(_format(result))


def tool_geom_sum(s: str) -> str:
    """Geometric series sum: geom_sum(first,ratio,terms)"""
    a1_str, r_str, n_str = [p.strip() for p in str(s or "").split(",")]
    a1 = _as_frac(a1_str)
    ratio = _as_frac(r_str)
    n = _as_int(n_str, "n")
    if n <= 0:
        return "ERR: terms must be positive"
    if ratio == 1:
        return _format(a1 * n)
    # a1 * (r^n - 1) / (r - 1)
    rn = ratio ** n
    if abs(rn.numerator) > INT_LIMIT or abs(rn.denominator) > INT_LIMIT:
        return "ERR: geometric sum overflow"
    result = a1 * (rn - 1) / (ratio - 1)
    return _clip_result(_format(result))


# ---------------------------------------------------------------------------
# Matrix tools
# ---------------------------------------------------------------------------
def tool_matrix2_det(s: str) -> str:
    """2x2 determinant: matrix2_det(a,b,c,d)"""
    parts = _as_numbers(s)
    if len(parts) != 4:
        return "ERR: expected a,b,c,d"
    a, b, c, d = parts
    return _format(a * d - b * c)


def tool_matrix3_det(s: str) -> str:
    """3x3 determinant: matrix3_det(a,b,c,d,e,f,g,h,i)"""
    parts = _as_numbers(s)
    if len(parts) != 9:
        return "ERR: expected 9 entries a-i"
    (a, b, c, d, e, f, g, h, i) = parts
    result = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return _clip_result(_format(result))


# ---------------------------------------------------------------------------
# Python expression evaluator (restricted AST)
# ---------------------------------------------------------------------------
_SAFE_NODES = {
    ast.Expression, ast.Constant, ast.Num,
    ast.Name, ast.Load,
    ast.UnaryOp, ast.UAdd, ast.USub, ast.Not, ast.Invert,
    ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
    ast.Mod, ast.Pow, ast.LShift, ast.RShift, ast.BitOr, ast.BitXor,
    ast.BitAnd, ast.MatMult,
    ast.BoolOp, ast.And, ast.Or,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Is, ast.IsNot, ast.In, ast.NotIn,
    ast.Call,
    ast.IfExp,
    ast.List, ast.Tuple,
    ast.Attribute,
    ast.Subscript,
    ast.Slice,
    ast.keyword,
}

_SAFE_BUILTINS: Dict[str, Any] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "tuple": tuple,
    "range": range,
    "sorted": sorted,
    "reversed": reversed,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "all": all,
    "any": any,
    "pow": pow,
    "divmod": divmod,
    "bin": bin,
    "hex": hex,
    "oct": oct,
    "chr": chr,
    "ord": ord,
    "math": math,
    "sqrt": math.sqrt,
    "gcd": math.gcd,
    "lcm": math.lcm,
    "factorial": math.factorial,
    "comb": math.comb,
    "perm": math.perm,
    "isqrt": math.isqrt,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "pi": math.pi,
    "e": math.e,
}


def _check_ast(node: ast.AST) -> None:
    """Recursively check that only safe nodes appear."""
    node_type = type(node)
    if node_type not in _SAFE_NODES:
        raise ToolError("unsupported AST node: %s" % node_type.__name__)
    for child in ast.iter_child_nodes(node):
        _check_ast(child)
    # Check attribute chains — only allow names in SAFE_BUILTINS
    if isinstance(node, ast.Attribute):
        # Walk the chain
        names = []
        current = node
        while isinstance(current, ast.Attribute):
            names.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            chain = current.id + "." + ".".join(reversed(names))
            if chain not in _SAFE_BUILTINS and not chain.startswith("math."):
                raise ToolError("unsupported attribute: %s" % chain)


def tool_python_eval(s: str) -> str:
    """Restricted-safe Python expression evaluation: python_eval(expr)"""
    expr = str(s or "").strip()
    if not expr:
        return "ERR: empty expression"
    if len(expr) > 400:
        return "ERR: expression too long (max 400 chars)"
    try:
        tree = ast.parse(expr, mode="eval")
        _check_ast(tree)
        compiled = compile(tree, "<tool>", "eval")
        result = eval(compiled, {"__builtins__": {}}, _SAFE_BUILTINS)
        if isinstance(result, float) and not math.isfinite(result):
            return "ERR: non-finite result"
        return _format(result)
    except ToolError as exc:
        return "ERR: %s" % exc
    except (SyntaxError, TypeError, ValueError, OverflowError,
            ZeroDivisionError, RecursionError, MemoryError) as exc:
        return "ERR: %s: %s" % (type(exc).__name__, exc)
    except Exception as exc:
        return "ERR: evaluation failed: %s" % type(exc).__name__


# ---------------------------------------------------------------------------
# Symbolic tools (via sympy if available)
# ---------------------------------------------------------------------------
_has_sympy = False
try:
    import sympy  # noqa: F811

    _has_sympy = True
except ImportError:
    pass


def tool_simplify(s: str) -> str:
    """Symbolic simplification: simplify(expr) — requires sympy"""
    if not _has_sympy:
        return "ERR: sympy not available"
    expr = str(s or "").strip()
    if len(expr) > 600:
        return "ERR: expression too long (max 600 chars)"
    try:
        x = sympy.sympify(expr)
        result = sympy.simplify(x)
        return str(result)
    except Exception as exc:
        return "ERR: simplify failed: %s" % exc


def tool_solve_eq(s: str) -> str:
    """Symbolic equation solver: solve_eq(eq,var) eg solve_eq(x**2-4,x)"""
    if not _has_sympy:
        return "ERR: sympy not available"
    parts = [p.strip() for p in str(s or "").split(",", 1)]
    if len(parts) != 2:
        return "ERR: expected eq,var"
    eq_str, var_str = parts
    try:
        eq = sympy.sympify(eq_str)
        var = sympy.symbols(var_str)
        solutions = sympy.solve(eq, var)
        return str(solutions)
    except Exception as exc:
        return "ERR: solve_eq failed: %s" % exc


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------
TOOL_REGISTRY: Dict[str, Callable[[str], str]] = {
    # Arithmetic
    "add": tool_add,
    "sub": tool_sub,
    "mul": tool_mul,
    "div": tool_div,
    "pow_int": tool_pow_int,
    "mod": tool_mod,
    "mod_pow": tool_mod_pow,
    "mod_inv": tool_mod_inv,
    "compare": tool_compare,
    # Number theory
    "gcd": tool_gcd,
    "lcm": tool_lcm,
    "is_prime": tool_is_prime,
    "next_prime": tool_next_prime,
    "factor": tool_factor,
    "divisor_count": tool_divisor_count,
    "divisors": tool_divisors,
    "totient": tool_totient,
    "crt": tool_crt,
    # Combinatorics
    "factorial": tool_factorial,
    "binomial": tool_binomial,
    "perm": tool_perm,
    # Algebra
    "solve_linear": tool_solve_linear,
    "solve_quadratic": tool_solve_quadratic,
    "poly_eval": tool_poly_eval,
    "arith_sum": tool_arith_sum,
    "geom_sum": tool_geom_sum,
    # Matrix
    "matrix2_det": tool_matrix2_det,
    "matrix3_det": tool_matrix3_det,
    # Python eval
    "python_eval": tool_python_eval,
    # Symbolic (if sympy available)
    "simplify": tool_simplify,
    "solve_eq": tool_solve_eq,
}

TOOL_LIST = sorted(TOOL_REGISTRY.keys())


def get_tool_names() -> List[str]:
    return sorted(TOOL_REGISTRY.keys())


def has_tool(name: str) -> bool:
    return name in TOOL_REGISTRY


def call_tool(name: str, args: str) -> str:
    """Execute a registered tool by name, returning the result string."""
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        return "ERR: unknown tool: %s" % name
    try:
        return tool(args)
    except ToolError as exc:
        return "ERR: %s" % exc
    except Exception as exc:
        return "ERR: tool %s raised %s: %s" % (name, type(exc).__name__, exc)


# ---------------------------------------------------------------------------
# TOOL_CALL / TOOL_RESULT protocol
# ---------------------------------------------------------------------------
_TOOL_CALL_RE = re.compile(r"TOOL_CALL:\s*(\w+)\(([^)]*)\)", re.IGNORECASE)


def strip_tool_lines(text: str) -> str:
    """Remove TOOL_CALL and TOOL_RESULT lines from raw output."""
    lines = str(text or "").splitlines()
    return "\n".join(
        line for line in lines
        if not line.strip().startswith(("TOOL_CALL:", "TOOL_RESULT:"))
    ).strip()


def extract_tool_calls(text: str) -> List[Tuple[str, str]]:
    """Extract tool calls from model output."""
    matches = _TOOL_CALL_RE.findall(str(text or ""))
    return [(name, args.strip()) for name, args in matches[:TOOL_CALL_LIMIT]]


def execute_tool_calls(text: str) -> List[Dict[str, Any]]:
    """Extract and execute tool calls, returning results."""
    calls = extract_tool_calls(text)
    results: List[Dict[str, Any]] = []
    for name, args in calls:
        result_str = call_tool(name, args)
        is_error = result_str.startswith("ERR")
        results.append({
            "tool": name,
            "args": args,
            "result": result_str,
            "ok": not is_error,
        })
    return results

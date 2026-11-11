"""Bee's common judge: A/B statistics, taken as they are from minizBee's bee/bench/ab.py.

Sign test on the interleaved pairs (A, B), medians, relative gain, description of the machine and
a readable table. The definitions are identical to ab.py's, so that a report of the common judge
reads like a report of ab.py (test: test_judge.TestStatistics compares the two).
"""

import math
import os
import platform
import statistics
import subprocess
import sys

SIGN_TEST_THRESHOLD = 0.02


def sign_threshold(n, alpha=SIGN_TEST_THRESHOLD):
    """Smallest k such that P(X >= k | n, 1/2) <= alpha; None if there is none (n too small)."""
    for k in range(n + 1):
        if sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n <= alpha:
            return k
    return None


def one_sided_p(n, k):
    return sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n


def sign_test(values_a, values_b, direction):
    """Standard sign test on the pairs (A_i, B_i).

    Ties are set aside; the threshold k and the p-values are computed on the N' remaining pairs.
    If every pair is a tie (N' = 0), there is neither gain nor degradation."""
    pairs = [(a, b) for a, b in zip(values_a, values_b) if a is not None and b is not None]
    best_one = (lambda a, b: b > a) if direction == "plus_haut" else (lambda a, b: b < a)
    b_wins = sum(1 for a, b in pairs if best_one(a, b))
    a_wins = sum(1 for a, b in pairs if best_one(b, a))
    n_useful = a_wins + b_wins
    k = sign_threshold(n_useful) if n_useful else None
    return {  # keys in English from judge-v4 on (ruche-0148), as bee record-measurement reads an ab.py report
        "pairs": len(pairs), "useful_pairs": n_useful,
        "b_wins": b_wins, "a_wins": a_wins, "ties": len(pairs) - n_useful,
        "threshold_k": k,
        "p_improvement": one_sided_p(n_useful, b_wins) if n_useful else None,
        "p_degradation": one_sided_p(n_useful, a_wins) if n_useful else None,
        "beyond_noise": k is not None and b_wins >= k,
        "degradation_beyond_noise": k is not None and a_wins >= k,
    }


def summary(values_of):
    values_of = [v for v in values_of if v is not None]
    if not values_of:
        return {"median": None, "min": None, "max": None, "values": []}
    return {"median": statistics.median(values_of), "min": min(values_of), "max": max(values_of), "values": values_of}


def relative_gain(a, b, direction):
    if a in (None, 0) or b is None:
        return None
    return (b / a - 1.0) if direction == "plus_haut" else (1.0 - b / a)


def description_machine():
    model = platform.processor() or platform.machine()
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line_text in f:
                if line_text.lower().startswith(("model name", "cpu model")):
                    model = line_text.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    compiler = os.environ.get("CC", "cc")
    try:
        version = subprocess.run([compiler, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        version = compiler
    return {"processor": model, "architecture": platform.machine(), "cores": os.cpu_count(),
            "system": platform.platform(), "compiler": version}


def show_table(report):
    lines = [f"{'métrique':26s} {'médiane A':>12s} {'médiane B':>12s} {'gain':>8s}  {'B gagne':>8s}  verdict"]
    for nom, m in report["metrics"].items():
        a, b = m["A"], m["B"]
        if a["median"] is None:
            continue
        s = m["sign_test"]
        gain = "-" if m["gain"] is None else f"{100 * m['gain']:+.2f} %"
        if m["beyond_noise"]:
            verdict = "amélioration au-delà du bruit"
        elif m["degradation_beyond_noise"]:
            verdict = "DÉGRADATION au-delà du bruit"
        else:
            verdict = "dans le bruit"
        lines.append(f"{nom:26s} {a['median']:12.3f} {b['median']:12.3f} {gain:>8s}  "
                      f"{s['b_wins']:>3d}/{s['useful_pairs']:<4d}  {verdict}"
                      + (f" ({s['ties']} égalités écartées)" if s["ties"] else ""))
    for nom, m in (report.get("instructions") or {}).items():
        gain = "-" if m["gain"] is None else f"{100 * m['gain']:+.3f} %"
        if not m["beyond_noise"]:
            verdict = "dans le bruit"
        else:
            verdict = "moins d'instructions" if m["gain"] > 0 else "PLUS d'instructions"
        lines.append(f"{nom:26s} {m['A']:12d} {m['B']:12d} {gain:>8s}  {'':>8s}  {verdict}")
    print("\n".join(lines), file=sys.stderr)

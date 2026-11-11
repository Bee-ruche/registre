"""Juge commun Bee : statistiques A/B, reprises telles quelles de bee/bench/ab.py de minizBee.

Test du signe sur les paires entrelacées (A, B), médianes, gain relatif, description de la machine et
tableau lisible. Les définitions sont identiques à celles d'ab.py, si bien qu'un rapport du juge commun
se lit comme un rapport d'ab.py (test : test_juge.TestStatistiques compare les deux).
"""

import math
import os
import platform
import statistics
import subprocess
import sys

SIGN_TEST_THRESHOLD = 0.02


def sign_threshold(n, alpha=SIGN_TEST_THRESHOLD):
    """Plus petit k tel que P(X >= k | n, 1/2) <= alpha ; None si aucun (n trop petit)."""
    for k in range(n + 1):
        if sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n <= alpha:
            return k
    return None


def one_sided_p(n, k):
    return sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n


def sign_test(values_a, values_b, direction):
    """Test du signe standard sur les paires (A_i, B_i).

    Les égalités sont écartées ; le seuil k et les valeurs p se calculent sur les N' paires restantes.
    Si toutes les paires sont à égalité (N' = 0), il n'y a ni gain ni dégradation."""
    pairs = [(a, b) for a, b in zip(values_a, values_b) if a is not None and b is not None]
    best_one = (lambda a, b: b > a) if direction == "plus_haut" else (lambda a, b: b < a)
    b_wins = sum(1 for a, b in pairs if best_one(a, b))
    a_wins = sum(1 for a, b in pairs if best_one(b, a))
    n_useful = a_wins + b_wins
    k = sign_threshold(n_useful) if n_useful else None
    return {
        "paires": len(pairs), "paires_utiles": n_useful,
        "victoires_B": b_wins, "victoires_A": a_wins, "egalites": len(pairs) - n_useful,
        "seuil_k": k,
        "p_amelioration": one_sided_p(n_useful, b_wins) if n_useful else None,
        "p_degradation": one_sided_p(n_useful, a_wins) if n_useful else None,
        "au_dela_du_bruit": k is not None and b_wins >= k,
        "degradation_au_dela_du_bruit": k is not None and a_wins >= k,
    }


def summary(values_of):
    values_of = [v for v in values_of if v is not None]
    if not values_of:
        return {"mediane": None, "min": None, "max": None, "valeurs": []}
    return {"mediane": statistics.median(values_of), "min": min(values_of), "max": max(values_of), "valeurs": values_of}


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
    return {"processeur": model, "architecture": platform.machine(), "coeurs": os.cpu_count(),
            "systeme": platform.platform(), "compilateur": version}


def show_table(report):
    lines = [f"{'métrique':26s} {'médiane A':>12s} {'médiane B':>12s} {'gain':>8s}  {'B gagne':>8s}  verdict"]
    for nom, m in report["metriques"].items():
        a, b = m["A"], m["B"]
        if a["mediane"] is None:
            continue
        s = m["test_du_signe"]
        gain = "-" if m["gain"] is None else f"{100 * m['gain']:+.2f} %"
        if m["au_dela_du_bruit"]:
            verdict = "amélioration au-delà du bruit"
        elif m["degradation_au_dela_du_bruit"]:
            verdict = "DÉGRADATION au-delà du bruit"
        else:
            verdict = "dans le bruit"
        lines.append(f"{nom:26s} {a['mediane']:12.3f} {b['mediane']:12.3f} {gain:>8s}  "
                      f"{s['victoires_B']:>3d}/{s['paires_utiles']:<4d}  {verdict}"
                      + (f" ({s['egalites']} égalités écartées)" if s["egalites"] else ""))
    for nom, m in (report.get("instructions") or {}).items():
        gain = "-" if m["gain"] is None else f"{100 * m['gain']:+.3f} %"
        if not m["au_dela_du_bruit"]:
            verdict = "dans le bruit"
        else:
            verdict = "moins d'instructions" if m["gain"] > 0 else "PLUS d'instructions"
        lines.append(f"{nom:26s} {m['A']:12d} {m['B']:12d} {gain:>8s}  {'':>8s}  {verdict}")
    print("\n".join(lines), file=sys.stderr)

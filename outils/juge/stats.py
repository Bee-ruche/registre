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

SEUIL_TEST_DU_SIGNE = 0.02


def seuil_signe(n, alpha=SEUIL_TEST_DU_SIGNE):
    """Plus petit k tel que P(X >= k | n, 1/2) <= alpha ; None si aucun (n trop petit)."""
    for k in range(n + 1):
        if sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n <= alpha:
            return k
    return None


def p_unilaterale(n, k):
    return sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n


def test_du_signe(valeurs_a, valeurs_b, sens):
    """Test du signe standard sur les paires (A_i, B_i).

    Les égalités sont écartées ; le seuil k et les valeurs p se calculent sur les N' paires restantes.
    Si toutes les paires sont à égalité (N' = 0), il n'y a ni gain ni dégradation."""
    paires = [(a, b) for a, b in zip(valeurs_a, valeurs_b) if a is not None and b is not None]
    meilleur = (lambda a, b: b > a) if sens == "plus_haut" else (lambda a, b: b < a)
    victoires_b = sum(1 for a, b in paires if meilleur(a, b))
    victoires_a = sum(1 for a, b in paires if meilleur(b, a))
    n_utiles = victoires_a + victoires_b
    k = seuil_signe(n_utiles) if n_utiles else None
    return {
        "paires": len(paires), "paires_utiles": n_utiles,
        "victoires_B": victoires_b, "victoires_A": victoires_a, "egalites": len(paires) - n_utiles,
        "seuil_k": k,
        "p_amelioration": p_unilaterale(n_utiles, victoires_b) if n_utiles else None,
        "p_degradation": p_unilaterale(n_utiles, victoires_a) if n_utiles else None,
        "au_dela_du_bruit": k is not None and victoires_b >= k,
        "degradation_au_dela_du_bruit": k is not None and victoires_a >= k,
    }


def resume(valeurs):
    valeurs = [v for v in valeurs if v is not None]
    if not valeurs:
        return {"mediane": None, "min": None, "max": None, "valeurs": []}
    return {"mediane": statistics.median(valeurs), "min": min(valeurs), "max": max(valeurs), "valeurs": valeurs}


def gain_relatif(a, b, sens):
    if a in (None, 0) or b is None:
        return None
    return (b / a - 1.0) if sens == "plus_haut" else (1.0 - b / a)


def description_machine():
    modele = platform.processor() or platform.machine()
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for ligne in f:
                if ligne.lower().startswith(("model name", "cpu model")):
                    modele = ligne.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    compilateur = os.environ.get("CC", "cc")
    try:
        version = subprocess.run([compilateur, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        version = compilateur
    return {"processeur": modele, "architecture": platform.machine(), "coeurs": os.cpu_count(),
            "systeme": platform.platform(), "compilateur": version}


def afficher_tableau(rapport):
    lignes = [f"{'métrique':26s} {'médiane A':>12s} {'médiane B':>12s} {'gain':>8s}  {'B gagne':>8s}  verdict"]
    for nom, m in rapport["metriques"].items():
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
        lignes.append(f"{nom:26s} {a['mediane']:12.3f} {b['mediane']:12.3f} {gain:>8s}  "
                      f"{s['victoires_B']:>3d}/{s['paires_utiles']:<4d}  {verdict}"
                      + (f" ({s['egalites']} égalités écartées)" if s["egalites"] else ""))
    for nom, m in (rapport.get("instructions") or {}).items():
        gain = "-" if m["gain"] is None else f"{100 * m['gain']:+.3f} %"
        if not m["au_dela_du_bruit"]:
            verdict = "dans le bruit"
        else:
            verdict = "moins d'instructions" if m["gain"] > 0 else "PLUS d'instructions"
        lignes.append(f"{nom:26s} {m['A']:12d} {m['B']:12d} {gain:>8s}  {'':>8s}  {verdict}")
    print("\n".join(lignes), file=sys.stderr)

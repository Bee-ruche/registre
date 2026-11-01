"""CI simulée d'un fork : rend le verdict du dernier commit poussé sur une PR « sur papier » et l'enregistre dans le
registre simulé, comme le fait le workflow des verdicts (bee enregistrer-verdict, poussé sur main par le robot).

Les chiffres sont tirés au hasard, l'auteur ne choisit pas son verdict. Comme dans un vrai fork, ce qui dépend du code
(CI verte ou rouge, lignes, décomptes d'instructions, constructions suspectes) est tiré du code du commit, c'est-à-dire
de sa description : le même code, repoussé ou relancé, avec ou sans manifeste corrigé, donne les mêmes décomptes. Seul le chronomètre est
tiré à nouveau à chaque exécution : relancer la CI jusqu'à passer le seuil de R4 est donc possible ici comme en vrai, et
c'est à la ruche de ne pas s'y laisser prendre (ruche-0028).
Usage : python3 ci_simulee.py <url_pr_fork> [--relance]
"""
import json, os, pathlib, random, subprocess, sys, tempfile

import yaml

SIMU = pathlib.Path(os.environ["BEE_SIMU"])
CONF = SIMU / "confiance"


def sh(*cmd, cwd=None, env=None, check=True):
    return subprocess.run(cmd, cwd=cwd, env=env, check=check, text=True, capture_output=True)


def main():
    url = sys.argv[1]
    if not url.startswith("https://github.com/Bee-ruche/"):
        print(f"adresse de PR invalide : {url}")
        return 2
    commits = [l.rstrip("\n").split("\t") for l in (SIMU / "etat/commits_fork.tsv").read_text(encoding="utf-8").splitlines() if l.strip()]
    commits = [c for c in commits if len(c) == 5 and c[1] == url]   # une ligne abîmée n'arrête pas la CI des autres
    if not commits:
        print(f"Aucun commit poussé sur {url} : pousser-pr-fork d'abord.")
        return 1
    _, _, sha, arbre, code = commits[-1]
    numero = url.rsplit("/", 1)[1]
    manifeste = SIMU / "etat/manifestes" / numero / f"{sha}.yaml"
    maintenant = sh("python3", str(SIMU / "outils/horloge.py")).stdout.strip()
    env = dict(os.environ, BEE_MAINTENANT=maintenant)

    sh("git", "fetch", "-q", "origin", cwd=CONF)
    sh("git", "checkout", "-q", "--detach", "origin/main", cwd=CONF)
    travail = SIMU / "verdict"
    sh("rm", "-rf", str(travail))
    sh("git", "worktree", "prune", cwd=CONF)
    sh("git", "worktree", "add", "-q", "--detach", str(travail), "origin/main", cwd=CONF)
    try:
        contribution = None
        for chemin in sorted((travail / "contributions").glob("*/*.yaml")):
            enr = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
            if enr.get("pr") == url and enr.get("statut") == "en_relecture":
                contribution = enr
        if contribution is None:
            print(f"La CI a tourné sur {sha[:7]}, mais le registre n'a aucune contribution en relecture pour {url}. "
                  f"Soumettez (bee soumettre <t> --utilisateur <p> --pr {url}), publiez, puis relancez : ci-simulee {url}")
            return 0
        tache_id = contribution["tache"]
        projet = tache_id.rsplit("-", 1)[0]
        tache = yaml.safe_load((travail / f"taches/{projet}/{tache_id}.yaml").read_text(encoding="utf-8"))
        # Une exécution de plus pour ce commit : le chronomètre est tiré à nouveau, le reste suit le contenu.
        executions = SIMU / "etat/executions_fork.tsv"
        rang = sum(1 for l in executions.read_text(encoding="utf-8").splitlines() if l == sha) if executions.exists() else 0
        with executions.open("a", encoding="utf-8") as f:
            f.write(sha + "\n")
        # Le « code » du commit est sa description : le manifeste fait partie de l'arbre, mais le corriger ne change pas
        # ce que la CI mesure.
        hasard = random.Random(f"code:{code}")
        chrono_hasard = random.Random(f"execution:{sha}:{rang}")
        verdict = {"ci": "verte" if hasard.random() < 0.9 else "rouge", "lignes_modifiees": hasard.randint(12, 60),
                   "juge": {"version": 3, "commun": "juge-v1", "sorties_comparees": 7868, "constructions_suspectes": []}}
        if verdict["ci"] == "rouge":
            verdict["etape_en_echec"] = hasard.choice(["tests", "fuzzing", "tests-arm64"])
        metrique = tache.get("metrique")
        scenario = None
        if metrique:
            projet_def = yaml.safe_load((travail / f"projets/{projet}.yaml").read_text(encoding="utf-8"))
            for m in projet_def.get("metriques", []):
                if m.get("id") == metrique:
                    scenario = m.get("instructions")
        if metrique and scenario:
            gain_instr = hasard.uniform(-0.01, 0.05)
            chrono = gain_instr * hasard.uniform(0.2, 1.2) + chrono_hasard.gauss(0, 0.003)
            a = 1.0e8 * hasard.uniform(1, 5)
            verdict["instructions"] = {scenario: {"A": round(a), "B": round(a * (1 - gain_instr)), "gain": round(gain_instr, 4)}}
            verdict["gain"] = round(chrono, 4)
            verdict["au_dela_du_bruit"] = abs(chrono) > 0.004
            verdict["degradations"] = {"debit_decompression": -0.012} if chrono_hasard.random() < 0.05 else {}
        else:
            verdict["gain"] = None
        if hasard.random() < 0.1:
            verdict["juge"]["constructions_suspectes"] = [{"type": "horloge", "detail": "appel à clock_gettime dans le code jugé"}]
        fichiers = [f for f in tache.get("fichiers", []) if not f.endswith("/")] + [f"manifestes/{tache_id}.yaml"]
        with tempfile.TemporaryDirectory() as tmp:
            pv = pathlib.Path(tmp) / "verdict.json"
            pv.write_text(json.dumps(verdict), encoding="utf-8")
            pf = pathlib.Path(tmp) / "fichiers.txt"
            pf.write_text("\n".join(fichiers) + "\n", encoding="utf-8")
            args = ["python3", "outils/bee.py", "--registre", str(travail), "enregistrer-verdict", contribution["id"],
                    "--verdict", str(pv), "--sha", sha, "--arbre", arbre, "--execution", f"{url}/checks/{rang + 1}", "--fichiers", str(pf)]
            if manifeste.exists():
                args += ["--manifeste", str(manifeste)]
            r = subprocess.run(args, cwd=travail, env=env, text=True, capture_output=True)
            print(r.stdout + r.stderr)
            if r.returncode != 0:
                return r.returncode
        sh("git", "add", "-A", cwd=travail)
        sh("git", "-c", "user.name=robot", "-c", "user.email=robot@simu.bee", "commit", "-qm",
           f"Verdict simulé de {contribution['id']} ({sha[:7]})", cwd=travail)
        r = subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=travail, text=True, capture_output=True,
                           env=dict(os.environ, BEE_SIMU_ROBOT="1"))
        if r.returncode != 0:
            print("main a avancé pendant la CI : relancez ci-simulee.")
            return 1
        print(f"Verdict de {contribution['id']} au commit {sha[:7]} enregistré : CI {verdict['ci']}, gain {verdict.get('gain')}.")
        return 0
    finally:
        sh("git", "worktree", "remove", "--force", str(travail), cwd=CONF, check=False)


if __name__ == "__main__":
    sys.exit(main())

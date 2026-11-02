"""Essai de charge, partie 1 (ruche-0080 ; le modèle d'activité : docs/outillage.md) : une ruche jetable de N membres
actifs et une semaine de leur activité, tirée d'un modèle fixe et d'une graine, sans agent d'IA ni réseau. ruche-0083 y
mesure bee et les règles.

  python3 outils/repetition/load_test.py <dossier> --membres 100 [--graine 1] [--registre <clone>] [--base main]
  python3 outils/repetition/load_test.py <dossier> --rejouer [<numéro de PR>...]

Comme une ruche de répétition (monter.sh), tout part d'un commit du registre (`main` par défaut) et tout s'écrit dans
<dossier>, qui ne doit pas exister : confiance (le registre, au dernier commit de la semaine), central.git (son clone nu, qui
joue GitHub) et etat/ (base, fin, prs.tsv, auteurs_pr.tsv). L'historique : la base en un commit, puis une PR par geste,
fusionnée en squash comme fusion-auto (auteur et heure du geste, fusion une minute après). Chaque fichier est écrit par les
fonctions d'écriture de l'outil bee de la base, comme la commande que nomme le message de sa PR ; --rejouer relance ces
commandes sur l'état d'avant chaque PR, compare les octets, puis fait juger la PR par bee verifier-pr --fusion-auto.
"""
import argparse
import datetime as dt
import importlib.util
import io
import math
import os
import pathlib
import random
import re
import shlex
import subprocess
import sys
import tarfile

import yaml

sys.dont_write_bytecode = True  # rien hors du dossier, pas même le cache de l'outil importé
JOUR, HEURE, FUSION = 86400, 3600, 60  # FUSION : secondes entre un geste et la fusion de sa PR
# Ni la configuration git de la machine (signature, crochets), ni cache Python : les mêmes octets partout.
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "PYTHONDONTWRITEBYTECODE": "1"}
NOTE = "Approche : profiler le scénario, puis une seule boucle chaude à la fois."
RESUME = "Une copie évitée dans la boucle chaude, même sortie."
MOTIFS = {"favorable": "Diff lu, tests relancés en sandbox : rien à signaler.",
          "defavorable": "Diff lu : un cas limite n'est couvert par aucun test."}
ARGUMENT = "Une mesure avant toute règle : ce débat gagnerait un chiffre."
CONTEXTE = ("Tâche fictive de l'essai de charge (ruche-0080) : une ruche jetable, une semaine simulée. Elle ne vise aucun "
            "code réel ; son texte a la longueur d'une tâche ordinaire.")


def git(depot, *arguments, **env):
    return subprocess.run(["git", "-C", str(depot), *arguments], check=True, capture_output=True, env={**ENV, **env}).stdout


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lancer_bee(registre, instant, *arguments):
    """L'outil bee du registre lui-même (le code de la base), à l'heure donnée."""
    return subprocess.run([sys.executable, str(registre / "outils" / "bee.py"), "--registre", str(registre), *arguments],
                          capture_output=True, text=True, env={**ENV, "BEE_MAINTENANT": instant})


class Ruche:
    """Le registre jetable : chaque geste écrit ses fichiers dans confiance par l'outil bee de la base, puis devient une PR
    fusionnée, envoyée à git fast-import."""

    def __init__(self, racine):
        self.racine = racine
        spec = importlib.util.spec_from_file_location("bee_de_la_base", racine / "outils" / "bee.py")
        self.bee = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.bee)
        self.flux = subprocess.Popen(["git", "-C", str(racine), "fast-import", "--quiet", "--date-format=raw", "--done"],
                                     stdin=subprocess.PIPE, env=ENV)
        self.n, self.prs, self.auteurs, self.suite = 0, [], [], "from refs/heads/main^0\n"

    def pr(self, t, auteur, titre, chemins, commande=None):
        """Une PR d'un seul geste, ouverte par `auteur` à l'instant t et fusionnée FUSION secondes après ; son message nomme
        la commande bee qui a écrit ses fichiers (sans commande : un geste du conseil, écrit à la main)."""
        self.n += 1
        corps = "bee " + shlex.join(commande) if commande else "Geste du conseil, écrit à la main (hors de bee)."
        message = f"{titre} (#{self.n})\n\n{corps}\n".encode()
        sortie = [f"commit refs/heads/main\nauthor {auteur} <{auteur}@simu.bee> {t} +0000\n"
                  f"committer GitHub <noreply@github.com> {t + FUSION} +0000\ndata {len(message)}\n".encode(), message,
                  self.suite.encode()]
        self.suite = ""
        for chemin in chemins:
            contenu = (self.racine / chemin).read_bytes()
            sortie += [f"M 100644 inline {chemin}\ndata {len(contenu)}\n".encode(), contenu, b"\n"]
        self.flux.stdin.write(b"".join(sortie) + b"\n")
        self.prs.append(f"{iso(t)}\t{self.n}\t{auteur}\t{titre}\tfusionnee\n")

    @staticmethod
    def chemin_tache(tid):
        return f"taches/{tid.rsplit('-', 1)[0]}/{tid}.yaml"

    def suivante(self, projet):
        """Le numéro de tâche suivant, comme bee proposer-tache (le plus grand + 1, hors de la plage des tests)."""
        motif = re.compile(re.escape(projet) + r"-(?P<n>\d{4})\.yaml")
        numeros = [int(m["n"]) for f in (self.racine / "taches" / projet).iterdir() if (m := motif.fullmatch(f.name))]
        return f"{projet}-{self.bee.numero_suivant(numeros):04d}"

    def ajouter_liste(self, relatif, fiches):  # comme monter.sh : des fiches au bout de la liste `membres`
        chemin = self.racine / relatif
        texte = chemin.read_text(encoding="utf-8")
        texte = texte.replace("membres: []", "membres:\n" + fiches) if "membres: []" in texte else texte.rstrip("\n") + "\n" + fiches
        chemin.write_text(texte, encoding="utf-8")

    def conseil(self, t, conseil, gardiens, projets, membres):
        """La veille de la semaine, le conseil nomme un gardien pour 20 membres actifs (le maximum du frein de R13), un garant
        pour deux gardiens (docs/devolution.md), et ouvre une tâche par membre sur les projets à optimiser qui ont un fork."""
        garants = [f"garant-{i:03d}" for i in range(1, math.ceil(len(gardiens) / 2) + 1)]
        self.ajouter_liste("gouvernance/garants.yaml", "".join(
            f"  - pseudo: {g}\n    github_id: {60000000 + i}\n    identite_publique: Garant fictif {i} (essai de charge)\n"
            f"    engagement: docs/garants.md, version du 28/10/2026\n    signe_le: \"{iso(t)[:10]}\"\n    conflits: []\n"
            for i, g in enumerate(garants, 1)))
        self.ajouter_liste("gouvernance/gardiens.yaml", "".join(f"  - pseudo: {p}\n    garant: {garants[i // 2]}\n"
                                                                for i, p in enumerate(gardiens)))
        chemins = ["gouvernance/garants.yaml", "gouvernance/gardiens.yaml"]
        for k, m in enumerate(membres):
            projet, fiche = projets[k % len(projets)]
            m["tache"], metrique = self.suivante(projet), fiche["metriques"][0]["id"]
            m["pr"] = f"{fiche['fork'].rstrip('/')}/pull/{100000 + k}"
            tache = {"id": m["tache"], "projet": projet, "categorie": fiche["categorie"], "type": "optimisation", "taille": "S",
                     "titre": f"Essai de charge : tâche fictive {m['tache']}", "contexte": CONTEXTE, "fichiers": ["src/"],
                     "portee": 0.5, "metrique": metrique}
            if fiche["categorie"] == "compression-sans-perte":
                tache["sortie_compressee"] = "identique"
            tache.update({"critere_acceptation": ["CI verte (R2)", f"gain >= 2 % sur {metrique}, au-delà du bruit (R4)"],
                          "hors_perimetre": ["format de sortie", "API publique"], "statut": "ouverte", "cree_par": conseil,
                          "cree_le": iso(t)[:10]})
            self.bee.ecrire_yaml(self.racine / self.chemin_tache(m["tache"]), tache)
            chemins.append(self.chemin_tache(m["tache"]))
        self.pr(t, conseil, "Ruche de charge : garants, gardiens et une tâche par membre", chemins)

    def inscrire(self, t, m):  # bee inscrire
        chemin = f"membres/{m['pseudo']}.yaml"
        self.bee.ecrire_yaml(self.racine / chemin, {"pseudo": m["pseudo"], "inscrit_le": iso(t)[:10], "compte_cree_le": m["cree"],
                                                    "github_id": m["id"]})
        self.pr(t, m["pseudo"], f"Inscription {m['pseudo']}", [chemin],
                ["inscrire", "--pseudo", m["pseudo"], "--compte-cree-le", m["cree"], "--github-id", str(m["id"])])

    def prendre(self, t, m):  # bee prendre
        m["depuis"], chemin = iso(t), self.chemin_tache(m["tache"])
        self.bee.modifier_tache(self.racine / chemin, statut="reservee", reservation={"utilisateur": m["pseudo"], "depuis": iso(t)})
        self.pr(t, m["pseudo"], f"Réservation {m['tache']}", [chemin], ["prendre", m["tache"], "--utilisateur", m["pseudo"]])

    def noter(self, t, m):  # bee noter
        chemin = self.chemin_tache(m["tache"])
        self.bee.modifier_tache(self.racine / chemin, note={"par": m["pseudo"], "le": iso(t), "texte": NOTE}, ajout=chemin)
        self.pr(t, m["pseudo"], f"Note {m['tache']}", [chemin], ["noter", m["tache"], "--utilisateur", m["pseudo"], "--texte", NOTE])

    def soumettre(self, t, m):  # bee soumettre, par le titulaire
        tid, cid = m["tache"], m["tache"] + "-c1"
        chemins = [f"contributions/{tid.rsplit('-', 1)[0]}/{cid}.yaml", self.chemin_tache(tid)]
        self.bee.ecrire_yaml(self.racine / chemins[0], {"id": cid, "tache": tid, "auteur": m["pseudo"], "pr": m["pr"], "resume": RESUME,
                                                        "statut": "en_relecture", "soumise_le": iso(t), "engage_depuis": m["depuis"],
                                                        "relectures": []})
        self.bee.modifier_tache(self.racine / chemins[1], statut="en_relecture", reservation=None, contribution=cid)
        self.auteurs.append(f"{m['pr']}\t{m['pseudo']}\t{m['id']}\n")  # la PR du fork est à lui (fusion-auto le relève)
        self.pr(t, m["pseudo"], f"Soumission {cid}", chemins,
                ["soumettre", tid, "--utilisateur", m["pseudo"], "--pr", m["pr"], "--resume", RESUME])

    def relire(self, t, relecteur, m, avis):  # bee relire, avant tout verdict de la CI du fork (donc sans --commit)
        cid = m["tache"] + "-c1"
        chemin = f"contributions/{m['tache'].rsplit('-', 1)[0]}/{cid}.yaml"
        enr = dict(self.bee.lire_yaml(self.racine / chemin))
        enr["relectures"] = list(enr.get("relectures") or []) + [
            {"relecteur": relecteur, "avis": avis, "motif": MOTIFS[avis], "le": iso(t)}]
        self.bee.exiger_place(chemin, self.bee.texte_yaml(enr))
        self.bee.ecrire_yaml(self.racine / chemin, enr)
        self.pr(t, relecteur, f"Relecture {cid}", [chemin],
                ["relire", cid, "--utilisateur", relecteur, "--avis", avis, "--motif", MOTIFS[avis]])

    def voter(self, t, votant, m, valeur):  # bee voter, sans motif
        cid = m["tache"] + "-c1"
        chemin = f"votes/{cid}/{votant}.yaml"
        self.bee.ecrire_yaml(self.racine / chemin, {"votant": votant, "sujet": cid, "valeur": valeur, "le": iso(t)})
        self.pr(t, votant, f"Vote {cid}", [chemin], ["voter", cid, "--utilisateur", votant, "--valeur", str(valeur)])

    def proposer(self, t, u, projet):  # bee proposer-tache <projet> : type et taille par défaut, le modèle tel que bee l'écrit
        fiche, tid = self.bee.lire_yaml(self.racine / "projets" / f"{projet}.yaml"), self.suivante(projet)
        metrique = fiche["metriques"][0]["id"]
        valeurs = {"id": tid, "projet": projet, "categorie": fiche["categorie"], "type": "optimisation", "taille": "S",
                   "metrique": metrique, "statut": "proposee", "cree_par": u, "cree_le": self.bee.guillemets(iso(t)[:10])}
        lignes = []
        for ligne in (self.racine / "modeles" / "tache.yaml").read_text(encoding="utf-8").splitlines():
            cle = ligne.split(":", 1)[0]
            if cle != "sortie_compressee" or fiche["categorie"] == "compression-sans-perte":
                lignes.append(f"{cle}: {valeurs[cle]}" if cle in valeurs and not ligne.startswith(" ") else ligne)
        chemin = self.chemin_tache(tid)
        (self.racine / chemin).write_text(("\n".join(lignes) + "\n").replace("debit_compression_n6", metrique), encoding="utf-8")
        self.pr(t, u, f"Proposition de tâche {tid}", [chemin], ["proposer-tache", projet, "--utilisateur", u])

    def argumenter(self, t, u, debat, position):  # bee debattre argumenter, dans un débat ouvert qui n'est pas une invitation
        chemin = f"debats/{debat}.yaml"
        d = self.bee.lire_yaml(self.racine / chemin)
        existants = d.get("arguments") if isinstance(d.get("arguments"), list) else []
        d = {**d, "arguments": list(existants) + [
            {"id": f"A{len(existants) + 1}", "par": u, "le": iso(t), "position": position, "texte": ARGUMENT}]}
        d.setdefault("rapporteur", u)  # le premier à argumenter dans un débat sans rapporteur prend la plume
        self.bee.exiger_place(chemin, self.bee.rendu_debat(d, chemin))
        self.bee.ecrire_debat(self.racine / chemin, d)
        self.pr(t, u, f"Argument {debat}", [chemin],
                ["debattre", "argumenter", debat, "--utilisateur", u, "--position", position, "--texte", ARGUMENT])


def generer(dossier, nombre, graine, registre, base):
    """Écrit la ruche jetable dans `dossier` ; renvoie le code de sortie de bee valider sur elle (à la fin de la semaine)."""
    if nombre < 20:
        raise SystemExit("--membres : au moins 20 (un gardien pour 20 membres actifs)")
    sha = git(registre, "rev-parse", "--verify", f"{base}^{{commit}}").decode().strip()
    quand = int(git(registre, "log", "-1", "--format=%ct", sha))
    dossier.mkdir(parents=True)  # refuse un dossier qui existe déjà
    racine = dossier / "confiance"
    racine.mkdir()
    # La base en un seul commit : l'historique de la ruche jetable est complet, même pris d'un clone superficiel.
    with tarfile.open(fileobj=io.BytesIO(git(registre, "archive", sha))) as archive:
        archive.extractall(racine, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    git(racine, "init", "-q", "-b", "main")
    git(racine, "add", "-A")
    date, qui = f"{quand} +0000", {"GIT_AUTHOR_NAME": "conseil", "GIT_AUTHOR_EMAIL": "conseil@simu.bee"}
    git(racine, "commit", "-q", "-m", f"Registre de base ({sha})", GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date,
        GIT_COMMITTER_NAME="conseil", GIT_COMMITTER_EMAIL="conseil@simu.bee", **qui)
    ruche, rng = Ruche(racine), random.Random(graine)
    lire = ruche.bee.lire_yaml
    conseil = lire(racine / "gouvernance" / "conseil.yaml")["membres"][0]["pseudo"]
    projets = [(c.stem, f) for c in sorted((racine / "projets").glob("*.yaml"))
               if (f := lire(c)).get("statut") == "actif" and f.get("fork") and f.get("metriques")]
    debats = [c.stem for c in sorted((racine / "debats").glob("D-*.yaml"))
              if (d := lire(c)).get("statut") == "ouvert" and not d.get("invitation")]
    if not debats:
        raise SystemExit("aucun débat ouvert (hors invitation) dans la base : où argumenter ?")
    veille = (quand // JOUR + 1) * JOUR
    lundi = veille + (7 - dt.datetime.fromtimestamp(veille, dt.timezone.utc).weekday()) * JOUR
    membres = [{"pseudo": f"abeille-{i:04d}", "id": 50000000 + i,
                "cree": (dt.date(2012, 1, 1) + dt.timedelta(days=rng.randrange(3650))).isoformat()} for i in range(1, nombre + 1)]
    ordre, fin = rng.sample(membres, nombre), lundi + 7 * JOUR
    # Au maximum du frein de R13 : un gardien pour 20 membres actifs à la fin de la semaine, comptés comme bee les compte (les
    # membres simulés, et ceux que la base rend déjà actifs : ses gestes y datent tous du commit de la base).
    actifs = nombre + len(ruche.bee.membres_actifs(ruche.bee.Registre(racine), dt.datetime.fromtimestamp(fin, dt.timezone.utc)))
    for k, m in enumerate(membres):  # la veille : les inscriptions, puis le conseil
        ruche.inscrire(veille + k * (22 * HEURE // nombre), m)
    ruche.conseil(veille + 23 * HEURE, conseil, sorted(m["pseudo"] for m in ordre[:math.ceil(actifs / 20)]), projets, ordre)
    gestes, vendredi = [], lundi + 4 * JOUR + 18 * HEURE
    for k, m in enumerate(ordre):
        if k % 2 == 0:  # la moitié des contributions le vendredi soir, de 18 h à minuit (UTC)
            soumise = vendredi + rng.randrange(6 * HEURE)
        else:  # l'autre moitié du lundi 6 h au dimanche 6 h, hors du vendredi soir
            soumise = lundi + 6 * HEURE + rng.randrange(5 * JOUR + 18 * HEURE)
            soumise += 6 * HEURE if soumise >= vendredi else 0
        prise = max(lundi, soumise - rng.randrange(2 * HEURE, 48 * HEURE))
        gestes += [(prise, ruche.prendre, m), ((prise + soumise) // 2, ruche.noter, m), (soumise, ruche.soumettre, m)]
        for j in (1, 2):  # deux relectures et deux votes par contribution, d'autres membres, dans les 17 h
            avis = "defavorable" if rng.random() < 0.1 else "favorable"
            gestes.append((soumise + rng.randrange(HEURE, 17 * HEURE), ruche.relire, ordre[(k + j) % nombre]["pseudo"], m, avis))
            valeur = rng.choices([1, 0, -1], [7, 2, 1])[0]
            gestes.append((soumise + rng.randrange(HEURE, 17 * HEURE), ruche.voter, ordre[(k + j + 2) % nombre]["pseudo"], m, valeur))
    for m in rng.sample(membres, nombre // 10):  # une tâche proposée pour 10 membres
        gestes.append((lundi + rng.randrange(7 * JOUR - HEURE), ruche.proposer, m["pseudo"], rng.choice(projets)[0]))
    for m in rng.sample(membres, nombre // 5):  # un argument pour 5 membres
        gestes.append((lundi + rng.randrange(7 * JOUR - HEURE), ruche.argumenter, m["pseudo"], rng.choice(debats),
                       rng.choice(["pour", "contre", "question"])))
    for t, _, geste, *arguments in sorted((g[0], i, *g[1:]) for i, g in enumerate(gestes)):  # à l'heure, dans l'ordre de leur PR
        geste(t, *arguments)
    ruche.flux.stdin.write(b"done\n")
    ruche.flux.stdin.close()
    if ruche.flux.wait():
        raise SystemExit("git fast-import a échoué")
    git(racine, "reset", "-q", "--hard")
    git(dossier, "clone", "-q", "--bare", "confiance", "central.git")
    git(racine, "remote", "add", "origin", "../central.git")
    git(racine, "fetch", "-q", "origin")
    fin = iso(fin)
    (dossier / "etat").mkdir()
    for nom, texte in (("base", git(racine, "rev-list", "--max-parents=0", "main").decode()), ("fin", fin + "\n"),
                       ("prs.tsv", "".join(ruche.prs)), ("auteurs_pr.tsv", "".join(ruche.auteurs))):
        (dossier / "etat" / nom).write_text(texte, encoding="utf-8")
    valide = lancer_bee(racine, fin, "valider")
    print(valide.stdout + valide.stderr, end="")
    print(f"Ruche de charge : {dossier} ; {nombre} membres, {ruche.n} PR, semaine du {iso(lundi)[:10]} ; "
          f"BEE_MAINTENANT={fin} pour la lire telle qu'à la fin de la semaine.")
    return valide.returncode


def rejouer(dossier, numeros=()):
    """Rejoue les PR (toutes, ou les numéros donnés) : la commande bee de chacune, relancée sur l'état d'avant à son heure,
    doit écrire exactement son contenu ; puis bee verifier-pr --fusion-auto, à l'heure de sa fusion, doit l'accepter (le
    geste du conseil : valide, réservé au conseil). Renvoie les écarts : [(numéro, raison)]."""
    racine, rejeu, ecarts = dossier / "confiance", dossier / "rejeu", []
    base = (dossier / "etat" / "base").read_text(encoding="utf-8").strip()
    journal = git(racine, "log", "--reverse", "--format=%H %P %an %at %ct%n%B%x00", f"{base}..main").decode()
    git(racine, "worktree", "add", "-q", "--detach", str(rejeu), base)
    try:
        for bloc in filter(str.strip, journal.split("\0")):
            entete, titre, _, corps = bloc.strip("\n").split("\n")[:4]
            sha, parent, auteur, ouverte, fusion = entete.split()
            numero = int(re.search(r"\(#(\d+)\)$", titre)[1])
            if numeros and numero not in numeros:
                continue
            git(rejeu, "reset", "-q", "--hard", parent)
            git(rejeu, "clean", "-qfd")
            if corps.startswith("bee "):
                r = lancer_bee(rejeu, iso(int(ouverte)), *shlex.split(corps)[1:])
                git(rejeu, "add", "-A")
                if r.returncode or subprocess.run(["git", "-C", str(rejeu), "diff", "--cached", "--quiet", sha], env=ENV).returncode:
                    ecarts.append((numero, f"{corps} : n'écrit pas ce que porte la PR ({r.stdout + r.stderr})"))
            git(rejeu, "reset", "-q", "--hard", sha)
            fiche = rejeu / "membres" / f"{auteur}.yaml"
            fiche = (yaml.safe_load(fiche.read_text(encoding="utf-8")) if fiche.exists() else next(  # sinon : le conseil
                m for m in yaml.safe_load((rejeu / "gouvernance" / "conseil.yaml").read_text(encoding="utf-8"))["membres"]
                if m["pseudo"] == auteur))
            options = ["--github-id", str(fiche["github_id"])] + (["--compte-cree-le", fiche["compte_cree_le"]] if "compte_cree_le" in fiche else [])
            r = lancer_bee(rejeu, iso(int(fusion)), "verifier-pr", "--base", parent, "--tete", sha, "--auteur", auteur, *options,
                           "--auteurs-pr", str(dossier / "etat" / "auteurs_pr.tsv"), "--fusion-auto")
            if r.returncode not in ((0,) if corps.startswith("bee ") else (0, 3)):
                ecarts.append((numero, f"bee verifier-pr la refuse (code {r.returncode}) : {r.stdout + r.stderr}"))
    finally:
        git(racine, "worktree", "remove", "--force", str(rejeu))
    return ecarts


def principal(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dossier", type=pathlib.Path, help="le dossier de la ruche jetable (créé ; il ne doit pas exister)")
    p.add_argument("--membres", type=int, help="membres actifs : 100, 300 ou 1000 pour ruche-0083")
    p.add_argument("--graine", default="1", help="la graine du tirage (défaut : 1) ; la même donne les mêmes octets")
    p.add_argument("--registre", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2], help="le clone source")
    p.add_argument("--base", default="main", help="le commit de départ dans le clone source (défaut : main)")
    p.add_argument("--rejouer", type=int, nargs="*", help="rejoue les PR d'une ruche déjà générée (toutes, ou ces numéros)")
    args = p.parse_args(argv)
    if args.rejouer is not None:
        ecarts = rejouer(args.dossier.resolve(), set(args.rejouer))
        for numero, raison in ecarts:
            print(f"✗ PR {numero} : {raison}")
        print(f"{len(ecarts)} écart(s)." if ecarts else "✓ chaque PR rejouée écrit les mêmes octets et passe verifier-pr.")
        return 1 if ecarts else 0
    if args.membres is None:
        p.error("--membres est exigé pour générer (ou --rejouer pour rejouer)")
    return generer(args.dossier.resolve(), args.membres, args.graine, args.registre, args.base)


if __name__ == "__main__":
    sys.exit(principal())

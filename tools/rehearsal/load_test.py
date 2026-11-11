"""Load test, part 1 (ruche-0080; the activity model: docs/tooling.md): a throwaway hive of N active members and a
week of their activity, drawn from a fixed model and a seed, with no AI agent and no network. ruche-0083 measures bee
and the rules on it.

  python3 tools/rehearsal/load_test.py <dir> --members 100 [--seed 1] [--registry <clone>] [--base main]
  python3 tools/rehearsal/load_test.py <dir> --replay [<PR number>...]

Like a rehearsal hive (setup.sh), everything starts from a commit of the registry (`main` by default) and everything is
written in <dir>, which must not exist: trust (the registry, at the week's last commit), central.git (its bare clone,
which plays GitHub) and state/ (base, end, prs.tsv, pr_authors.tsv). The history: the base in one commit, then one PR
per action, squash-merged as auto-merge does (the action's author and time, merged one minute later). Each file is
written by the writing functions of the base's bee tool, as the command named in its PR's message would write it;
--replay reruns these commands on the state before each PR, compares the bytes, then has bee check-pr --auto-merge judge
the PR.
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
DAY, HOUR, MERGE = 86400, 3600, 60  # FUSION : secondes entre un geste et la fusion de sa PR
# Ni la configuration git de la machine (signature, crochets), ni cache Python : les mêmes octets partout.
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "PYTHONDONTWRITEBYTECODE": "1"}
NOTE = "Approche : profiler le scénario, puis une seule boucle chaude à la fois."
SUMMARY = "Une copie évitée dans la boucle chaude, même sortie."
REASONS = {"favorable": "Diff lu, tests relancés en sandbox : rien à signaler.",
          "unfavorable": "Diff lu : un cas limite n'est couvert par aucun test."}
ARGUMENT = "Une mesure avant toute règle : ce débat gagnerait un chiffre."
CONTEXT = ("Tâche fictive de l'essai de charge (ruche-0080) : une ruche jetable, une semaine simulée. Elle ne vise aucun "
            "code réel ; son texte a la longueur d'une tâche ordinaire.")


def git(repo, *arguments, **env):
    return subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True, env={**ENV, **env}).stdout


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_bee(registry, instant, *arguments):
    """L'outil bee du registre lui-même (le code de la base), à l'heure donnée."""
    return subprocess.run([sys.executable, str(registry / "tools" / "bee.py"), "--registry", str(registry), *arguments],
                          capture_output=True, text=True, env={**ENV, "BEE_NOW": instant})


class Ruche:
    """Le registre jetable : chaque geste écrit ses fichiers dans confiance par l'outil bee de la base, puis devient une PR
    fusionnée, envoyée à git fast-import."""

    def __init__(self, root):
        self.root = root
        spec = importlib.util.spec_from_file_location("bee_de_la_base", root / "tools" / "bee.py")
        self.bee = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.bee)
        # Le journal de session de ruche-0138 (.git/bee-session : un git par fichier écrit) ne sert qu'à bee publish ; les PR
        # de cette ruche sont faites ici : sans lui, la moitié du temps de génération, les mêmes octets.
        self.bee.note_written = lambda path: None
        self.stream = subprocess.Popen(["git", "-C", str(root), "fast-import", "--quiet", "--date-format=raw", "--done"],
                                     stdin=subprocess.PIPE, env=ENV)
        self.n, self.prs, self.authors, self.suite = 0, [], [], "from refs/heads/main^0\n"

    def pr(self, t, author, title, paths, command=None):
        """Une PR d'un seul geste, ouverte par `auteur` à l'instant t et fusionnée MERGE secondes après ; son message nomme
        la commande bee qui a écrit ses fichiers (sans commande : un geste du conseil, écrit à la main)."""
        self.n += 1
        body = "bee " + shlex.join(command) if command else "Geste du conseil, écrit à la main (hors de bee)."
        message = f"{title} (#{self.n})\n\n{body}\n".encode()
        output_text = [f"commit refs/heads/main\nauthor {author} <{author}@simu.bee> {t} +0000\n"
                  f"committer GitHub <noreply@github.com> {t + MERGE} +0000\ndata {len(message)}\n".encode(), message,
                  self.suite.encode()]
        self.suite = ""
        for path in paths:
            content = (self.root / path).read_bytes()
            output_text += [f"M 100644 inline {path}\ndata {len(content)}\n".encode(), content, b"\n"]
        self.stream.stdin.write(b"".join(output_text) + b"\n")
        self.prs.append(f"{iso(t)}\t{self.n}\t{author}\t{title}\tfusionnee\n")

    @staticmethod
    def task_path(tid):
        return f"tasks/{tid.rsplit('-', 1)[0]}/{tid}.yaml"

    def next_value(self, project):
        """Le numéro de tâche suivant, comme bee propose-task (le plus grand + 1, hors de la plage des tests)."""
        reason = re.compile(re.escape(project) + r"-(?P<n>\d{4})\.yaml")
        numbers_of = [int(m["n"]) for f in (self.root / "tasks" / project).iterdir() if (m := reason.fullmatch(f.name))]
        return f"{project}-{self.bee.next_number(numbers_of):04d}"

    def add_list(self, relative_one, entry_cards):  # comme setup.sh : des fiches au bout de la liste `members`
        path = self.root / relative_one
        text = path.read_text(encoding="utf-8")
        text = text.replace("members: []", "members:\n" + entry_cards) if "members: []" in text else text.rstrip("\n") + "\n" + entry_cards
        path.write_text(text, encoding="utf-8")

    def council(self, t, council, guardians, projects, members):
        """La veille de la semaine, le conseil nomme un gardien pour 20 membres actifs (le maximum du frein de R13), un garant
        pour deux gardiens (docs/devolution.md), et ouvre une tâche par membre sur les projets à optimiser qui ont un fork."""
        guarantors = [f"garant-{i:03d}" for i in range(1, math.ceil(len(guardians) / 2) + 1)]
        self.add_list("governance/guarantors.yaml", "".join(
            f"  - login: {g}\n    github_id: {60000000 + i}\n    public_identity: Garant fictif {i} (essai de charge)\n"
            f"    engagement: docs/guarantors.md, version du 28/10/2026\n    signed_on: \"{iso(t)[:10]}\"\n    conflicts: []\n"
            for i, g in enumerate(guarantors, 1)))
        self.add_list("governance/guardians.yaml", "".join(f"  - login: {p}\n    guarantor: {guarantors[i // 2]}\n"
                                                                for i, p in enumerate(guardians)))
        paths = ["governance/guarantors.yaml", "governance/guardians.yaml"]
        for k, m in enumerate(members):
            project, entry_card = projects[k % len(projects)]
            m["task"], metric = self.next_value(project), entry_card["metrics"][0]["id"]
            m["pr"] = f"{entry_card['fork'].rstrip('/')}/pull/{100000 + k}"
            task = {"id": m["task"], "project": project, "category": entry_card["category"], "type": "optimization", "size": "S",
                     "title": f"Essai de charge : tâche fictive {m['task']}", "context": CONTEXT, "files": ["src/"],
                     "reach": 0.5, "metric": metric}
            if entry_card["category"] == "lossless-compression":
                task["compressed_output"] = "identical"
            task.update({"acceptance_criteria": ["CI verte (R2)", f"gain >= 2 % sur {metric}, au-delà du bruit (R4)"],
                          "out_of_scope": ["format de sortie", "API publique"], "status": "open", "created_by": council,
                          "created_on": iso(t)[:10]})
            self.bee.write_yaml(self.root / self.task_path(m["task"]), task)
            paths.append(self.task_path(m["task"]))
        self.pr(t, council, "Ruche de charge : garants, gardiens et une tâche par membre", paths)

    def register(self, t, m):  # bee register
        path = f"members/{m['login']}.yaml"
        self.bee.write_yaml(self.root / path, {"login": m["login"], "registered_on": iso(t)[:10], "account_created_on": m["created"],
                                                    "github_id": m["id"]})
        self.pr(t, m["login"], f"Inscription {m['login']}", [path],
                ["register", "--login", m["login"], "--account-created-on", m["created"], "--github-id", str(m["id"])])

    def take(self, t, m):  # bee take
        m["since"], path = iso(t), self.task_path(m["task"])
        self.bee.modify_task(self.root / path, status="reserved", reservation={"user": m["login"], "since": iso(t)})
        self.pr(t, m["login"], f"Réservation {m['task']}", [path], ["take", m["task"], "--user", m["login"]])

    def note(self, t, m):  # bee note
        path = self.task_path(m["task"])
        self.bee.modify_task(self.root / path, note={"by": m["login"], "at": iso(t), "text": NOTE}, addition=path)
        self.pr(t, m["login"], f"Note {m['task']}", [path], ["note", m["task"], "--user", m["login"], "--text", NOTE])

    def submit(self, t, m):  # bee submit, par le titulaire
        tid, cid = m["task"], m["task"] + "-c1"
        paths = [f"contributions/{tid.rsplit('-', 1)[0]}/{cid}.yaml", self.task_path(tid)]
        self.bee.write_yaml(self.root / paths[0], {"id": cid, "task": tid, "author": m["login"], "pr": m["pr"], "summary": SUMMARY,
                                                        "status": "in_review", "submitted_at": iso(t), "engaged_since": m["since"],
                                                        "reviews": []})
        self.bee.modify_task(self.root / paths[1], status="in_review", reservation=None, contribution=cid)
        self.authors.append(f"{m['pr']}\t{m['login']}\t{m['id']}\n")  # la PR du fork est à lui (--auto-merge le relève)
        self.pr(t, m["login"], f"Soumission {cid}", paths,
                ["submit", tid, "--user", m["login"], "--pr", m["pr"], "--summary", SUMMARY])

    def review(self, t, reviewer, m, opinion):  # bee review, avant tout verdict de la CI du fork (donc sans --commit)
        cid = m["task"] + "-c1"
        path = f"contributions/{m['task'].rsplit('-', 1)[0]}/{cid}.yaml"
        rec = dict(self.bee.read_yaml(self.root / path))
        rec["reviews"] = list(rec.get("reviews") or []) + [
            {"reviewer": reviewer, "opinion": opinion, "reason": REASONS[opinion], "at": iso(t)}]
        self.bee.require_room(path, self.bee.yaml_text(rec))
        self.bee.write_yaml(self.root / path, rec)
        self.pr(t, reviewer, f"Relecture {cid}", [path],
                ["review", cid, "--user", reviewer, "--opinion", opinion, "--reason", REASONS[opinion]])

    def vote(self, t, voter, m, value):  # bee vote, sans motif
        cid = m["task"] + "-c1"
        path = f"votes/{cid}/{voter}.yaml"
        self.bee.write_yaml(self.root / path, {"voter": voter, "subject": cid, "value": value, "at": iso(t)})
        self.pr(t, voter, f"Vote {cid}", [path], ["vote", cid, "--user", voter, "--value", str(value)])

    def propose(self, t, u, project):  # bee propose-task <project> : type et taille par défaut, le modèle tel que bee l'écrit
        entry_card, tid = self.bee.read_yaml(self.root / "projects" / f"{project}.yaml"), self.next_value(project)
        metric = entry_card["metrics"][0]["id"]
        values_of = {"id": tid, "project": project, "category": entry_card["category"], "type": "optimization", "size": "S",
                   "metric": metric, "status": "proposed", "created_by": u, "created_on": self.bee.quotes_found(iso(t)[:10])}
        lines = []
        for line_text in (self.root / "templates" / "task.yaml").read_text(encoding="utf-8").splitlines():
            key = line_text.split(":", 1)[0]
            if key != "compressed_output" or entry_card["category"] == "lossless-compression":
                lines.append(f"{key}: {values_of[key]}" if key in values_of and not line_text.startswith(" ") else line_text)
        path = self.task_path(tid)
        (self.root / path).write_text(("\n".join(lines) + "\n").replace(self.bee.TEMPLATE_METRIC, metric), encoding="utf-8")
        self.pr(t, u, f"Proposition de tâche {tid}", [path], ["propose-task", project, "--user", u])

    def argue(self, t, u, debate, position):  # bee debate argue, dans un débat ouvert qui n'est pas une invitation
        path = f"debates/{debate}.yaml"
        d = self.bee.read_yaml(self.root / path)
        existing = d.get("arguments") if isinstance(d.get("arguments"), list) else []
        d = {**d, "arguments": list(existing) + [
            {"id": f"A{len(existing) + 1}", "by": u, "at": iso(t), "position": position, "text": ARGUMENT}]}
        d.setdefault("rapporteur", u)  # le premier à argumenter dans un débat sans rapporteur prend la plume
        self.bee.require_room(path, self.bee.debate_render(d, path))
        self.bee.write_debate(self.root / path, d)
        self.pr(t, u, f"Argument {debate}", [path],
                ["debate", "argue", debate, "--user", u, "--position", position, "--text", ARGUMENT])


def generate(folder, number, seed, registry, base):
    """Écrit la ruche jetable dans `dossier` ; renvoie le code de sortie de bee validate sur elle (à la fin de la semaine)."""
    if number < 20:
        raise SystemExit("--members : au moins 20 (un gardien pour 20 membres actifs)")
    sha = git(registry, "rev-parse", "--verify", f"{base}^{{commit}}").decode().strip()
    when_at = int(git(registry, "log", "-1", "--format=%ct", sha))
    folder.mkdir(parents=True)  # refuse un dossier qui existe déjà
    root = folder / "trust"
    root.mkdir()
    # La base en un seul commit : l'historique de la ruche jetable est complet, même pris d'un clone superficiel.
    with tarfile.open(fileobj=io.BytesIO(git(registry, "archive", sha))) as archive:
        archive.extractall(root, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    git(root, "init", "-q", "-b", "main")
    git(root, "add", "-A")
    date, who_is = f"{when_at} +0000", {"GIT_AUTHOR_NAME": "council", "GIT_AUTHOR_EMAIL": "council@simu.bee"}
    git(root, "commit", "-q", "-m", f"Registre de base ({sha})", GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date,
        GIT_COMMITTER_NAME="council", GIT_COMMITTER_EMAIL="council@simu.bee", **who_is)
    ruche, rng = Ruche(root), random.Random(seed)
    read = ruche.bee.read_yaml
    council = read(root / "governance" / "council.yaml")["members"][0]["login"]
    projects = [(c.stem, f) for c in sorted((root / "projects").glob("*.yaml"))
               if (f := read(c)).get("status") == "active" and f.get("fork") and f.get("metrics")]
    debates = [c.stem for c in sorted((root / "debates").glob("D-*.yaml"))
              if (d := read(c)).get("status") == "open" and not d.get("invitation")]
    if not debates:
        raise SystemExit("aucun débat ouvert (hors invitation) dans la base : où argumenter ?")
    day_before = (when_at // DAY + 1) * DAY
    monday = day_before + (7 - dt.datetime.fromtimestamp(day_before, dt.timezone.utc).weekday()) * DAY
    members = [{"login": f"abeille-{i:04d}", "id": 50000000 + i,
                "created": (dt.date(2012, 1, 1) + dt.timedelta(days=rng.randrange(3650))).isoformat()} for i in range(1, number + 1)]
    order, end = rng.sample(members, number), monday + 7 * DAY
    # Au maximum du frein de R13 : un gardien pour 20 membres actifs à la fin de la semaine, comptés comme bee les compte (les
    # membres simulés, et ceux que la base rend déjà actifs : ses gestes y datent tous du commit de la base).
    active = number + len(ruche.bee.active_members(ruche.bee.Registry(root), dt.datetime.fromtimestamp(end, dt.timezone.utc)))
    for k, m in enumerate(members):  # la veille : les inscriptions, puis le conseil
        ruche.register(day_before + k * (22 * HOUR // number), m)
    ruche.council(day_before + 23 * HOUR, council, sorted(m["login"] for m in order[:math.ceil(active / 20)]), projects, order)
    gestures, friday = [], monday + 4 * DAY + 18 * HOUR
    for k, m in enumerate(order):
        if k % 2 == 0:  # la moitié des contributions le vendredi soir, de 18 h à minuit (UTC)
            submitted = friday + rng.randrange(6 * HOUR)
        else:  # l'autre moitié du lundi 6 h au dimanche 6 h, hors du vendredi soir
            submitted = monday + 6 * HOUR + rng.randrange(5 * DAY + 18 * HOUR)
            submitted += 6 * HOUR if submitted >= friday else 0
        taking = max(monday, submitted - rng.randrange(2 * HOUR, 48 * HOUR))
        gestures += [(taking, ruche.take, m), ((taking + submitted) // 2, ruche.note, m), (submitted, ruche.submit, m)]
        for j in (1, 2):  # deux relectures et deux votes par contribution, d'autres membres, dans les 17 h
            opinion = "unfavorable" if rng.random() < 0.1 else "favorable"
            gestures.append((submitted + rng.randrange(HOUR, 17 * HOUR), ruche.review, order[(k + j) % number]["login"], m, opinion))
            value = rng.choices([1, 0, -1], [7, 2, 1])[0]
            gestures.append((submitted + rng.randrange(HOUR, 17 * HOUR), ruche.vote, order[(k + j + 2) % number]["login"], m, value))
    for m in rng.sample(members, number // 10):  # une tâche proposée pour 10 membres
        gestures.append((monday + rng.randrange(7 * DAY - HOUR), ruche.propose, m["login"], rng.choice(projects)[0]))
    for m in rng.sample(members, number // 5):  # un argument pour 5 membres
        gestures.append((monday + rng.randrange(7 * DAY - HOUR), ruche.argue, m["login"], rng.choice(debates),
                       rng.choice(["for", "against", "question"])))
    for t, _, gesture, *arguments in sorted((g[0], i, *g[1:]) for i, g in enumerate(gestures)):  # à l'heure, dans l'ordre de leur PR
        gesture(t, *arguments)
    ruche.stream.stdin.write(b"done\n")
    ruche.stream.stdin.close()
    if ruche.stream.wait():
        raise SystemExit("git fast-import a échoué")
    git(root, "reset", "-q", "--hard")
    git(folder, "clone", "-q", "--bare", "trust", "central.git")
    git(root, "remote", "add", "origin", "../central.git")
    git(root, "fetch", "-q", "origin")
    end = iso(end)
    (folder / "state").mkdir()
    for name, text in (("base", git(root, "rev-list", "--max-parents=0", "main").decode()), ("end", end + "\n"),
                       ("prs.tsv", "".join(ruche.prs)), ("pr_authors.tsv", "".join(ruche.authors))):
        (folder / "state" / name).write_text(text, encoding="utf-8")
    valid_one = run_bee(root, end, "validate")
    print(valid_one.stdout + valid_one.stderr, end="")
    print(f"Ruche de charge : {folder} ; {number} membres, {ruche.n} PR, semaine du {iso(monday)[:10]} ; "
          f"BEE_NOW={end} pour la lire telle qu'à la fin de la semaine.")
    return valid_one.returncode


def replay(folder, numbers_of=(), steps=None):
    """Rejoue les PR (toutes, ou les numéros donnés) : la commande bee de chacune, relancée sur l'état d'avant à son heure,
    doit s'exécuter (code 0 : ni refusée, ni un nom d'avant la bascule, que bee refuse sans rien lancer) et écrire
    exactement son contenu ; puis bee check-pr --auto-merge, à l'heure de sa fusion, doit l'accepter (le geste du conseil :
    valide, réservé au conseil). Renvoie les écarts : [(numéro, raison)]. `steps`, une liste, reçoit chaque appel de bee,
    dans l'ordre : (numéro, arguments, code de sortie, sortie), ce qui a vraiment tourné (ruche-0154)."""
    root, replay, gaps = folder / "trust", folder / "replay", []

    def run(number_of, instant, *arguments):
        r = run_bee(replay, instant, *arguments)
        if steps is not None:
            steps.append((number_of, arguments, r.returncode, r.stdout + r.stderr))
        return r

    base = (folder / "state" / "base").read_text(encoding="utf-8").strip()
    log_text = git(root, "log", "--reverse", "--format=%H %P %an %at %ct%n%B%x00", f"{base}..main").decode()
    git(root, "worktree", "add", "-q", "--detach", str(replay), base)
    try:
        for block in filter(str.strip, log_text.split("\0")):
            header, title, _, body = block.strip("\n").split("\n")[:4]
            sha, parent, author, open, merge = header.split()
            number_of = int(re.search(r"\(#(\d+)\)$", title)[1])
            if numbers_of and number_of not in numbers_of:
                continue
            git(replay, "reset", "-q", "--hard", parent)
            git(replay, "clean", "-qfd")
            if body.startswith("bee "):
                r = run(number_of, iso(int(open)), *shlex.split(body)[1:])
                git(replay, "add", "-A")
                if r.returncode:
                    gaps.append((number_of, f"{body} : bee la refuse (code {r.returncode}) : {r.stdout + r.stderr}"))
                elif subprocess.run(["git", "-C", str(replay), "diff", "--cached", "--quiet", sha], env=ENV).returncode:
                    gaps.append((number_of, f"{body} : n'écrit pas ce que porte la PR"))
            git(replay, "reset", "-q", "--hard", sha)
            entry_card = replay / "members" / f"{author}.yaml"
            entry_card = (yaml.safe_load(entry_card.read_text(encoding="utf-8")) if entry_card.exists() else next(  # sinon : le conseil
                m for m in yaml.safe_load((replay / "governance" / "council.yaml").read_text(encoding="utf-8"))["members"]
                if m["login"] == author))
            options = ["--github-id", str(entry_card["github_id"])] + (["--account-created-on", entry_card["account_created_on"]] if "account_created_on" in entry_card else [])
            r = run(number_of, iso(int(merge)), "check-pr", "--base", parent, "--head", sha, "--author", author, *options,
                    "--pr-authors", str(folder / "state" / "pr_authors.tsv"), "--auto-merge")
            if r.returncode not in ((0,) if body.startswith("bee ") else (0, 3)):
                gaps.append((number_of, f"bee check-pr la refuse (code {r.returncode}) : {r.stdout + r.stderr}"))
    finally:
        git(root, "worktree", "remove", "--force", str(replay))
    return gaps


def principal(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("dir", type=pathlib.Path, help="le dossier de la ruche jetable (créé ; il ne doit pas exister)")
    p.add_argument("--members", type=int, help="membres actifs : 100, 300 ou 1000 pour ruche-0083")
    p.add_argument("--seed", default="1", help="la graine du tirage (défaut : 1) ; la même donne les mêmes octets")
    p.add_argument("--registry", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2], help="le clone source")
    p.add_argument("--base", default="main", help="le commit de départ dans le clone source (défaut : main)")
    p.add_argument("--replay", type=int, nargs="*", help="rejoue les PR d'une ruche déjà générée (toutes, ou ces numéros)")
    args = p.parse_args(argv)
    if args.replay is not None:
        gaps = replay(args.dir.resolve(), set(args.replay))
        for number_of, cause in gaps:
            print(f"✗ PR {number_of} : {cause}")
        print(f"{len(gaps)} écart(s)." if gaps else "✓ chaque PR rejouée écrit les mêmes octets et passe check-pr.")
        return 1 if gaps else 0
    if args.members is None:
        p.error("--members est exigé pour générer (ou --replay pour rejouer)")
    return generate(args.dir.resolve(), args.members, args.seed, args.registry, args.base)


if __name__ == "__main__":
    sys.exit(principal())

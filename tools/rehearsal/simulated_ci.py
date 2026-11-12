"""A fork's simulated CI: gives the verdict of the last commit pushed to an "on paper" PR and records it in the
simulated registry, as the verdicts workflow does (bee record-verdict, pushed to main by the robot).

The numbers are drawn at random: the author does not choose the verdict. As in a real fork, what depends on the code
(green or red CI, lines, instruction counts, suspicious constructs) is drawn from the commit's code, that is from its
description: the same code, pushed again or rerun, with or without a corrected manifest, gives the same counts. Only the
stopwatch is drawn again at each run: rerunning the CI until it passes R4's threshold is therefore possible here as in
reality, and it is up to the hive not to be taken in by it (ruche-0028).
Usage: python3 simulated_ci.py <fork_pr_url> [--rerun]
"""
import json, os, pathlib, random, subprocess, sys, tempfile

import yaml

SIM = pathlib.Path(os.environ["BEE_SIM"])
CONF = SIM / "trust"


def sh(*cmd, cwd=None, env=None, check=True):
    return subprocess.run(cmd, cwd=cwd, env=env, check=check, text=True, capture_output=True)


def main():
    url = sys.argv[1]
    if not url.startswith("https://github.com/Bee-ruche/"):
        print(f"invalid PR address: {url}")
        return 2
    commits = [l.rstrip("\n").split("\t") for l in (SIM / "state/commits_fork.tsv").read_text(encoding="utf-8").splitlines() if l.strip()]
    commits = [c for c in commits if len(c) == 5 and c[1] == url]   # a damaged line does not stop the others' CI
    if not commits:
        print(f"No commit pushed to {url}: push-fork-pr first.")
        return 1
    _, _, sha, tree, code = commits[-1]
    number_of = url.rsplit("/", 1)[1]
    manifest = SIM / "state/manifests" / number_of / f"{sha}.yaml"
    now_instant = sh("python3", str(SIM / "tools/clock.py")).stdout.strip()
    env = dict(os.environ, BEE_NOW=now_instant)

    sh("git", "fetch", "-q", "origin", cwd=CONF)
    sh("git", "checkout", "-q", "--detach", "origin/main", cwd=CONF)
    travail = SIM / "verdict"
    sh("rm", "-rf", str(travail))
    sh("git", "worktree", "prune", cwd=CONF)
    sh("git", "worktree", "add", "-q", "--detach", str(travail), "origin/main", cwd=CONF)
    try:
        contribution = None
        for path in sorted((travail / "contributions").glob("*/*.yaml")):
            rec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if rec.get("pr") == url and rec.get("status") == "in_review":
                contribution = rec
        if contribution is None:
            print(f"The CI ran on {sha[:7]}, but the registry has no contribution in review for {url}. "
                  f"Submit (bee submit <task> --user <login> --pr {url}), publish, then rerun: simulated-ci {url}")
            return 0
        task_id = contribution["task"]
        project = task_id.rsplit("-", 1)[0]
        task = yaml.safe_load((travail / f"tasks/{project}/{task_id}.yaml").read_text(encoding="utf-8"))
        # One more run for this commit: the stopwatch is drawn again, the rest follows the content.
        runs = SIM / "state/executions_fork.tsv"
        rank = sum(1 for l in runs.read_text(encoding="utf-8").splitlines() if l == sha) if runs.exists() else 0
        with runs.open("a", encoding="utf-8") as f:
            f.write(sha + "\n")
        # The commit's "code" is its description: the manifest is part of the tree, but correcting it does not change
        # what the CI measures.
        randomness = random.Random(f"code:{code}")
        stopwatch_randomness = random.Random(f"run:{sha}:{rank}")
        verdict = {"ci": "green" if randomness.random() < 0.9 else "red", "changed_lines": randomness.randint(12, 60),
                   "judge": {"version": 3, "common": "juge-v1", "outputs_compared": 7868, "suspicious_constructs": []}}
        if verdict["ci"] == "red":
            verdict["failed_step"] = randomness.choice(["tests", "fuzzing", "tests-arm64"])
        metric = verdict["metric"] = task.get("metric")  # ruche-0145: a fork's verdict names its task's metric (required from date D)
        scenario = None
        if metric:
            project_def = yaml.safe_load((travail / f"projects/{project}.yaml").read_text(encoding="utf-8"))
            for m in project_def.get("metrics", []):
                if m.get("id") == metric:
                    scenario = m.get("instructions")
        if metric and scenario:
            gain_instr = randomness.uniform(-0.01, 0.05)
            stopwatch = gain_instr * randomness.uniform(0.2, 1.2) + stopwatch_randomness.gauss(0, 0.003)
            a = 1.0e8 * randomness.uniform(1, 5)
            verdict["instructions"] = {scenario: {"A": round(a), "B": round(a * (1 - gain_instr)), "gain": round(gain_instr, 4)}}
            verdict["gain"] = round(stopwatch, 4)
            verdict["beyond_noise"] = abs(stopwatch) > 0.004
            verdict["degradations"] = {"decompression_throughput": -0.012} if stopwatch_randomness.random() < 0.05 else {}
        else:
            verdict["gain"] = None
        if randomness.random() < 0.1:
            verdict["judge"]["suspicious_constructs"] = [{"type": "clock", "detail": "call to clock_gettime in the judged code"}]
        files = [f for f in task.get("files", []) if not f.endswith("/")] + [f"manifests/{task_id}.yaml"]
        with tempfile.TemporaryDirectory() as tmp:
            pv = pathlib.Path(tmp) / "verdict.json"
            pv.write_text(json.dumps(verdict), encoding="utf-8")
            pf = pathlib.Path(tmp) / "files.txt"
            pf.write_text("\n".join(files) + "\n", encoding="utf-8")
            args = ["python3", "tools/bee.py", "--registry", str(travail), "record-verdict", contribution["id"],
                    "--verdict", str(pv), "--sha", sha, "--tree", tree, "--run", f"{url}/checks/{rank + 1}", "--files", str(pf)]
            if manifest.exists():
                args += ["--manifest", str(manifest)]
            r = subprocess.run(args, cwd=travail, env=env, text=True, capture_output=True)
            print(r.stdout + r.stderr)
            if r.returncode != 0:
                return r.returncode
        sh("git", "add", "-A", cwd=travail)
        sh("git", "-c", "user.name=robot", "-c", "user.email=robot@simu.bee", "commit", "-qm",
           f"Simulated verdict of {contribution['id']} ({sha[:7]})", cwd=travail)
        r = subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=travail, text=True, capture_output=True,
                           env=dict(os.environ, BEE_SIM_ROBOT="1"))
        if r.returncode != 0:
            print("main moved during the CI: rerun simulated-ci.")
            return 1
        print(f"Verdict of {contribution['id']} at commit {sha[:7]} recorded: CI {verdict['ci']}, gain {verdict.get('gain')}.")
        return 0
    finally:
        sh("git", "worktree", "remove", "--force", str(travail), cwd=CONF, check=False)


if __name__ == "__main__":
    sys.exit(main())

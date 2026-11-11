"""Bee's common judge: image, isolated containers and execution under the chrono launcher.

Every execution of code from the PR goes through `Docker.launch`: no network, a read-only file
system, no capability, no privilege escalation, user 65534, a non-executable /tmp, a bounded
number of processes and memory. The container sees only what is mounted for it.
"""

import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading

from lecture import Erreur, Panne, Refus, copier, journal, propre

HERE = os.path.dirname(os.path.abspath(__file__))
ISOLATION = ["--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
             "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "-e", "HOME=/tmp", "-e", "LC_ALL=C", "--hostname", "juge"]
PACKAGE = re.compile(r"[a-z0-9][a-z0-9+.-]{0,63}")
HARNESS = "/variante/execution"  # what follows it in a plan command reaches it on its descriptor 0, not in argv
TIME = 946684800  # access and modification times of everything mounted for an execution, set before each container
# Each execution's own tmpfs (ruche-0117), mounted just before its container and gone once its outputs are copied out: all the
# container sees of the judge (chrono, the harness, its inputs, /etc files Docker would write on the host's disk, its outputs) is
# created there anew, in a fixed order: no inode, link count, time, free space or mount line follows the run's progress.
TMPFS = "size=4g,nr_inodes=262144,mode=0755,nosuid,nodev"
ETC = {"hostname": "juge\n", "hosts": "127.0.0.1\tlocalhost\n", "resolv.conf": ""}
# Docker (up to 29.0) mounts folders of equal depth in an order drawn for each container: each folder the judge mounts, in every
# container, is given at a depth of its own from PROFONDEUR on, deeper than any of Docker's own mounts (4 at most:
# /sys/fs/cgroup/cpu under cgroup v1), through the image's link to its root (Dockerfile.base) (ruche-0136).
LINK = "/.racine"
DEPTH = 8


def place_at(mounts):
    """The judge's folders (targets « /name »), each at its own depth in the given order; /etc's files stay where they are."""
    folders = [target for _, target, _ in mounts if target.count("/") == 1]
    return [(h, LINK * (DEPTH - 1 + folders.index(c)) + c if c in folders else c, l) for h, c, l in mounts]


def fixed_times(*folders):
    """Fixed times on these folders (the judge's own) and everything in them, no link followed."""
    for folder in folders:
        for root, under_it, names in os.walk(folder):
            for path in [root] + [os.path.join(root, n) for n in under_it + names]:
                os.utime(path, (TIME, TIME), follow_symlinks=False)


def mount_point(*command):
    """mount or umount, as root or through sudo -n (juge.yml's runner); failing is an error of the environment."""
    r = subprocess.run(([] if os.geteuid() == 0 else ["sudo", "-n"]) + list(command), capture_output=True, text=True)
    if r.returncode != 0:
        raise Erreur(f"{command[0]} du tmpfs d'une exécution impossible (root ou sudo -n requis) : " + propre(r.stderr, 300))


def copy_tree(source, target):
    """A folder of the judge copied in a fixed order (names sorted), modes kept: the same tree gets the same inodes."""
    for folder, under_it, names in os.walk(source):
        under_it.sort()
        os.makedirs(os.path.join(target, os.path.relpath(folder, source)), exist_ok=True)
        for n in sorted(names):
            shutil.copy(os.path.join(folder, n), os.path.join(target, os.path.relpath(folder, source), n))


class Docker:
    # No file above lecture.TAILLE_MAX_SORTIE, no log on the host's disk; the host keeps SORTIE_MAX of stdout (start), stderr (end).
    BOUNDS = ["--ulimit", f"fsize={256 << 20}", "--log-driver", "none"]
    OUTPUT_MAX = 1 << 20

    def __init__(self, image, memoire="4g"):
        self.image, self.memory = image, memoire

    def launch(self, command, mounts, pids=2, entry=None, timeout_seconds=3600):
        nom = "bee-juge-" + secrets.token_hex(6)
        cmd = ["docker", "run", "--name", nom, "--pids-limit", str(pids),
               "--memory", self.memory, "--memory-swap", self.memory] + self.BOUNDS + ISOLATION
        if entry is not None:
            cmd.append("-i")
        for host, target, read_only in place_at(mounts):
            if "," in host or "," in target:
                raise Erreur(f"chemin de montage invalide : {host}")
            cmd += ["--mount", f"type=bind,source={host},target={target}" + (",readonly" if read_only else "")]
        cmd += [self.image] + command
        with subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as p:
            read_items = (bytearray(), bytearray())
            children_of = [threading.Thread(target=_keep, args=(f, g, self.OUTPUT_MAX, end), daemon=True)
                    for f, g, end in ((p.stdout, read_items[0], False), (p.stderr, read_items[1], True))]
            for f in children_of:
                f.start()
            with contextlib.suppress(BrokenPipeError):  # a token and a plan: far below a pipe's capacity
                p.stdin.write(entry or b"")
                p.stdin.close()
            try:
                p.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                state = survey(nom, kill_it=True)
                p.kill()
                if state.get("Status") in (None, "created"):  # never started: the machine's failure; once run, a refusal
                    raise Panne(f"machine du juge en panne : conteneur jamais démarré en {timeout_seconds} s ({command[0]})")
                raise Refus(f"délai de {timeout_seconds} s dépassé dans le conteneur ({command[0]})")
            finally:
                for f in children_of:
                    f.join()
        # Docker's own record, never the code or the error stream the judged code writes: a container that was not created, did
        # not run to its end, or whose code is not its process's is a failure of the machine, never a refusal (ruche-0136).
        state = survey(nom)
        if (state.get("Status"), state.get("Error"), state.get("ExitCode")) != ("exited", "", p.returncode):
            journal("docker run's errors (kept out of the reason): " + propre(bytes(read_items[1]), 500))
            raise Panne(f"machine du juge en panne (Docker, son runtime ou l'image ; code {p.returncode})")
        return subprocess.CompletedProcess(cmd, p.returncode, bytes(read_items[0]), bytes(read_items[1]))


def survey(nom, kill_it=False):
    """Docker's record of a container ({} if none or unreadable), read before the container is (killed and) removed."""
    state = subprocess.run(["docker", "inspect", "--format", "{{json .State}}", nom], capture_output=True, text=True)
    if kill_it:
        subprocess.run(["docker", "kill", nom], capture_output=True)
    subprocess.run(["docker", "rm", "-f", nom], capture_output=True)
    try:
        state = json.loads(state.stdout) if state.returncode == 0 else None
    except ValueError:
        state = None
    return state if isinstance(state, dict) else {}


def dockerfile(packages):
    """The Dockerfile's text: the common image, the project's packages, the unprivileged user."""
    with open(os.path.join(HERE, "Dockerfile.base"), encoding="utf-8") as f:
        text = f.read().rstrip("\n") + "\n"
    packages = list(packages or [])
    for p in packages:
        if not PACKAGE.fullmatch(p):
            raise Erreur(f"nom de paquet invalide dans le greffon : {p!r}")
    if packages:
        text += ("\n# Paquets propres au projet (PAQUETS du greffon).\n"
                  "RUN apt-get update -q \\\n"
                  " && DEBIAN_FRONTEND=noninteractive apt-get install -y -q --no-install-recommends \\\n"
                  f"      {' '.join(packages)} \\\n"
                  " && rm -rf /var/lib/apt/lists/*\n")
    return text + "\n# Utilisateur sans privilège sous lequel tourne tout le reste (Docker.lancer passe aussi --user).\nUSER 65534:65534\nWORKDIR /\n"


def build_image(packages, network_on=None):
    text = dockerfile(packages)
    label = "bee-juge-commun:" + hashlib.sha256(text.encode()).hexdigest()[:16]
    if subprocess.run(["docker", "image", "inspect", label], capture_output=True).returncode == 0:
        return label
    journal(f"building the image {label} (the only step with network, before any file of the PR)")
    context = tempfile.mkdtemp(prefix="bee-image-")
    try:
        with open(os.path.join(context, "Dockerfile"), "w", encoding="utf-8") as f:
            f.write(text)
        command = ["docker", "build", "-q", "-t", label] + (["--network", network_on] if network_on else []) + [context]
        r = subprocess.run(command, capture_output=True, text=True)
    finally:
        shutil.rmtree(context, ignore_errors=True)
    if r.returncode != 0:
        raise Erreur("construction de l'image impossible : " + r.stderr[-2000:])
    return label


def image_id(label):
    """The image's id, the SHA-256 of its configuration (which names its layers): containers run it, juge.json records it."""
    r = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", label], capture_output=True, text=True)
    if r.returncode != 0 or not re.fullmatch(r"sha256:[0-9a-f]{64}", r.stdout.strip()):
        raise Erreur(f"identifiant de l'image {label} illisible : " + propre(r.stderr, 300))
    return r.stdout.strip()


def _keep(stream, keeper, maximum, end):
    """Reads a container's stream to its end, keeping at most `maximum` bytes of it: its start, or its end (fin)."""
    for block in iter(lambda: stream.read(1 << 16), b""):
        keeper += block if end else block[:maximum - len(keeper)]
        del keeper[:-maximum if end else 0]


def open_folder(path):
    """A folder the container (user 65534) can write to."""
    os.makedirs(path, exist_ok=True)
    os.chmod(path, 0o777)
    return path


def compile_stopwatch(docker, travail):
    """Compiles the COMMON JUDGE's chrono launcher (never a line of the project or of the PR), in the container."""
    source = os.path.join(travail, "chrono-source")
    os.makedirs(source)
    shutil.copyfile(os.path.join(HERE, "chrono.c"), os.path.join(source, "chrono.c"))
    output_text = open_folder(os.path.join(travail, "chrono-construction"))
    r = docker.launch(["sh", "-c", "umask 000 && cc -O2 -std=gnu99 -Wall -Wextra /source/chrono.c -o /sortie/chrono"],
                      [(source, "/source", True), (output_text, "/sortie", False)], pids=64, timeout_seconds=300)
    if r.returncode != 0:
        raise Erreur("compilation de chrono impossible : " + propre(r.stderr))
    stopwatch = os.path.join(travail, "chrono")
    os.makedirs(stopwatch)
    shutil.copyfile(os.path.join(output_text, "chrono"), os.path.join(stopwatch, "chrono"))
    os.chmod(os.path.join(stopwatch, "chrono"), 0o755)
    os.chmod(stopwatch, 0o755)
    return stopwatch


class Execution:
    """Runs a plan of commands in a container, under the common judge's chrono launcher."""

    def __init__(self, docker, stopwatch, constructs, travail):
        self.docker, self.stopwatch, self.constructs, self.workdir = docker, stopwatch, constructs, travail

    def launch(self, variant, entrees, outputs, plan, valgrind=False, timeout_seconds=1800):
        """plan: [(label, [program, arguments…])], HARNESS among them. Returns {label: measurement}.
        Plan, options and the harness's arguments go through standard inputs: same argv and files in every mode."""
        lines = []
        for label, command in plan:
            i = command.index(HARNESS) + 1 if HARNESS in command else len(command)
            if i == len(command) or any(c in x for x in [label] + command for c in "\t\n"):
                raise Erreur(f"commande de plan invalide : {propre(label, 80)}")
            lines.append("\t".join([label, " ".join(command[i:])] + command[:i]))
        open_folder(outputs)
        token = secrets.token_hex(16)
        entry = "\n".join([token, f"{int(timeout_seconds)} {int(bool(valgrind))}"] + lines) + "\n"
        root = os.path.join(self.workdir, "execution")  # the same path each time: one execution at a time
        os.mkdir(root)
        mount_point("mount", "-t", "tmpfs", "-o", f"{TMPFS},uid={os.getuid()},gid={os.getgid()}", "tmpfs", root)
        try:
            copy_tree(self.stopwatch, os.path.join(root, "chrono"))
            copy_tree(self.constructs[variant], os.path.join(root, "variante"))
            os.mkdir(os.path.join(root, "etc"))
            for nom, text in ETC.items():
                with open(os.path.join(root, "etc", nom), "w", encoding="ascii") as f:
                    f.write(text)
            open_folder(os.path.join(root, "sorties"))
            copy_tree(entrees, os.path.join(root, "entrees"))  # last: the other inodes do not depend on the inputs
            fixed_times(root)
            mounts = [(os.path.join(root, n), "/" + n, n != "sorties") for n in ("chrono", "variante", "entrees", "sorties")]
            mounts += [(os.path.join(root, "etc", n), "/etc/" + n, True) for n in ETC]
            r = self.docker.launch(["/chrono/chrono"], mounts, pids=2, entry=entry.encode(), timeout_seconds=timeout_seconds * len(plan) + 300)
            copier(os.path.join(root, "sorties"), outputs)
        finally:
            mount_point("umount", root)
            os.rmdir(root)
        if r.returncode != 0:
            raise Refus(f"le lanceur a échoué pour {variant} (code {r.returncode}) : " + propre(r.stderr))
        measurements = {}
        lines = [l for l in r.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
        if len(lines) != len(plan):
            raise Refus(f"{variant} : {len(lines)} mesure(s) pour {len(plan)} commande(s)")
        for line_text, (label, _) in zip(lines, plan):
            try:
                m = json.loads(line_text)
            except ValueError:
                raise Refus(f"{variant} : ligne de mesure illisible ({label})")
            if not isinstance(m, dict) or m.get("jeton") != token or m.get("etiquette") != label:
                raise Refus(f"{variant} : ligne de mesure non authentique ({label})")
            if m.get("code") != 0 or m.get("signal") != 0:
                raise Refus(f"{variant}/{label} : code {m.get('code')}, signal {m.get('signal')}. " + propre(r.stderr, 800))
            if valgrind and not isinstance(m.get("instructions"), int):
                raise Refus(f"{variant}/{label} : résumé de Valgrind absent ou illisible")
            measurements[label] = m
        return measurements

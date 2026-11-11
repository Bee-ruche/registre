/* Launcher and stopwatch of Bee's common judge (docs/common-judge.md; first written for minizBee's isolated judge).

   A program of the BASE, compiled without a line of the PR. It runs as process 1 of a container without
   network and launches, one by one, the commands of a plan the host wrote. Each command (the harness
   linked to the miniz being judged) is a child process: its processor time and its maximum memory are read
   by wait4, that is, measured by the kernel, not declared by the measured code.

   What the child cannot do:
   - write on the container's standard output, which carries the measurements: its descriptor 1 is /dev/null,
     2 a pipe read by chrono (its end goes to the container's error output); this process declares itself not
     « dumpable » (prctl), so that /proc/1/fd and /proc/1/mem are closed to it;
   - launch other processes: the container is limited to two processes (--pids-limit 2);
   - forge a measurement line: each line carries a token read on standard input before the first
     fork, which the child never sees;
   - know in which mode it runs (ruche-0037): whatever the mode, the same arguments, a fixed environment,
     current folder « / », 0 = a pipe carrying its parameters (fixed size); chrono has neither argument nor file.

   Instruction count (valgrind at 1): the command is valgrind --tool=cachegrind, whose summary
   (« I refs: N ») is the LAST line written on the child's error output. chrono reads that output
   through a pipe and takes the last non-empty line. The measured code can write on the same output, but
   only BEFORE the summary, which Valgrind writes last, once the program has ended; if it kills the
   process to prevent the summary, the signal is recorded and the host refuses the measurement. The file
   cachegrind.out is not read: the measured code could forge it.

   Usage: chrono; standard input gives the token (a line of 16 to 64 hexadecimal characters), a line
     « <timeout in seconds> <valgrind: 0 or 1> », then the plan: one command per line, fields separated by
     tabs: label (letters, digits, « _ » and « - »), parameters, program, arguments.
   Output: one JSON line per command, in the plan's order:
     {"jeton": "...", "etiquette": "...", "code": 0, "signal": 0, "utilisateur_s": 0.0, "systeme_s": 0.0,
      "mur_s": 0.0, "maxrss_ko": 0, "instructions": null}
   Exit code: 0 if the plan was read and all the commands launched (whatever their code), 2 otherwise. */

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define CHAMPS_MAX 32
#define LIGNE_MAX 4096
#define QUEUE_MAX 65536
#define PARAMETRES 256 /* the child's parameters: a record of fixed size, whatever the mode */

static char *const ENVIRONNEMENT[] = {"HOME=/tmp", "LC_ALL=C", "PATH=/usr/bin:/bin", NULL}; /* the same for each child */
static volatile pid_t fils_courant = 0;

static void sur_alarme(int signal_recu)
{
    (void)signal_recu;
    if (fils_courant > 0)
        kill(fils_courant, SIGKILL);
}

static void mourir(const char *message)
{
    fprintf(stderr, "chrono: %s\n", message);
    exit(2);
}

static double secondes(struct timeval t)
{
    return (double)t.tv_sec + (double)t.tv_usec * 1e-6;
}

static double maintenant(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}

/* Last non-empty line of the error output: « ==PID== I refs: 1,234,567 » (Cachegrind's summary).
   Returns the number, or -1 if the last line is not a well-formed summary. */
static long long releve_instructions(const char *texte, size_t n)
{
    size_t fin = n, debut;
    const char *p;
    long long total = 0;
    int chiffres = 0;
    while (fin > 0 && (texte[fin - 1] == '\n' || texte[fin - 1] == '\r' || texte[fin - 1] == ' '))
        fin--;
    debut = fin;
    while (debut > 0 && texte[debut - 1] != '\n')
        debut--;
    p = strstr(texte + debut, "I refs:");
    if (!p || p >= texte + fin)
        return -1;
    for (p += 7; p < texte + fin; p++)
    {
        if (*p == ' ' && !chiffres)
            continue;
        if (*p == ',')
            continue;
        if (*p < '0' || *p > '9' || total > 100000000000000000LL)
            return -1;
        total = total * 10 + (*p - '0');
        chiffres++;
    }
    return chiffres ? total : -1;
}

static int etiquette_valide(const char *e)
{
    if (!*e || strlen(e) > 64)
        return 0;
    for (; *e; e++)
        if (!((*e >= 'a' && *e <= 'z') || (*e >= 'A' && *e <= 'Z') || (*e >= '0' && *e <= '9') || *e == '_' || *e == '-'))
            return 0;
    return 1;
}

int main(int argc, char **argv)
{
    char jeton[80], ligne[LIGNE_MAX];
    unsigned delai = 0;
    int valgrind = 0;
    static char queue[QUEUE_MAX + 1];
    char (*lignes)[LIGNE_MAX] = NULL;
    size_t nombre = 0, capacite = 0, i, n;
    int nul;
    struct sigaction action;

    umask(0); /* inherited by the child: the host must be able to erase what it writes (another user) */
    /* First: nobody (same uid) opens /proc/<this process>/fd or /mem any more. */
    if (prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0)
        mourir("prctl(PR_SET_DUMPABLE) failed");

    (void)argv;
    if (argc != 1 || chdir("/") != 0)
        mourir("usage: chrono, without argument (token, options and plan on standard input)");

    if (!fgets(jeton, sizeof(jeton), stdin))
        mourir("token missing on standard input");
    jeton[strcspn(jeton, "\r\n")] = 0;
    n = strlen(jeton);
    if (n < 16 || n > 64 || strspn(jeton, "0123456789abcdef") != n)
        mourir("invalid token");
    if (!fgets(ligne, sizeof(ligne), stdin) || sscanf(ligne, "%u %d", &delai, &valgrind) != 2)
        mourir("options missing (timeout, valgrind)");

    while (fgets(ligne, sizeof(ligne), stdin))
    {
        ligne[strcspn(ligne, "\r\n")] = 0;
        if (!ligne[0])
            continue;
        if (nombre == capacite)
        {
            capacite = capacite ? 2 * capacite : 16;
            lignes = realloc(lignes, capacite * sizeof(*lignes));
            if (!lignes)
                mourir("out of memory");
        }
        memcpy(lignes[nombre++], ligne, LIGNE_MAX);
    }

    nul = open("/dev/null", O_RDWR | O_CLOEXEC);
    if (nul < 0)
        mourir("/dev/null not found");
    /* Standard input (the pipe that carried the token) closes here: the child does not inherit it. */
    if (dup2(nul, 0) < 0)
        mourir("dup2 failed");

    memset(&action, 0, sizeof(action));
    action.sa_handler = sur_alarme;
    sigaction(SIGALRM, &action, NULL);

    for (i = 0; i < nombre; i++)
    {
        char *champs[CHAMPS_MAX + 1], *sauvegarde = NULL, *morceau, parametres[PARAMETRES];
        int nchamps = 0, statut = 0, tube[2] = {-1, -1}, entree[2] = {-1, -1};
        size_t remplissage = 0;
        long long instructions = -1;
        struct rusage ru;
        double debut, fin;
        pid_t pid;

        for (morceau = strtok_r(lignes[i], "\t", &sauvegarde); morceau && nchamps < CHAMPS_MAX;
             morceau = strtok_r(NULL, "\t", &sauvegarde))
            champs[nchamps++] = morceau;
        champs[nchamps] = NULL;
        if (nchamps < 3 || !etiquette_valide(champs[0]))
            mourir("invalid plan line");

        /* The parameters (the mode included): PARAMETRES bytes, the line padded with spaces and ended by a line
           feed, in a pipe the child reads, then closes. */
        n = strlen(champs[1]);
        if (n >= PARAMETRES)
            mourir("parameters too long");
        memset(parametres, ' ', PARAMETRES - 1);
        memcpy(parametres, champs[1], n);
        parametres[PARAMETRES - 1] = '\n';
        if (pipe2(tube, O_CLOEXEC) != 0 || pipe2(entree, O_CLOEXEC) != 0 || write(entree[1], parametres, PARAMETRES) != PARAMETRES
            || close(entree[1]) != 0)
            mourir("pipes failed");
        fflush(stdout);
        debut = maintenant();
        pid = fork();
        if (pid < 0)
            mourir("fork failed");
        if (pid == 0)
        {
            if (dup2(entree[0], 0) < 0 || dup2(nul, 1) < 0 || dup2(tube[1], 2) < 0)
                _exit(126);
            execve(champs[2], champs + 2, ENVIRONNEMENT);
            _exit(127);
        }
        fils_courant = pid;
        close(entree[0]);
        if (delai)
            alarm(delai);
        {
            /* Reads everything the child writes on its error output; keeps only the end. */
            char morceau_lu[8192];
            close(tube[1]);
            for (;;)
            {
                ssize_t lu = read(tube[0], morceau_lu, sizeof(morceau_lu));
                if (lu < 0 && errno == EINTR)
                    continue;
                if (lu <= 0)
                    break;
                if ((size_t)lu >= QUEUE_MAX)
                {
                    memcpy(queue, morceau_lu + lu - QUEUE_MAX, QUEUE_MAX);
                    remplissage = QUEUE_MAX;
                }
                else
                {
                    if (remplissage + (size_t)lu > QUEUE_MAX)
                    {
                        size_t garder = QUEUE_MAX - (size_t)lu;
                        memmove(queue, queue + remplissage - garder, garder);
                        remplissage = garder;
                    }
                    memcpy(queue + remplissage, morceau_lu, (size_t)lu);
                    remplissage += (size_t)lu;
                }
            }
            close(tube[0]);
            queue[remplissage] = 0;
            if (valgrind)
                instructions = releve_instructions(queue, remplissage);
            fwrite(queue, 1, remplissage, stderr); /* the child's log, for the host */
        }
        while (wait4(pid, &statut, 0, &ru) < 0)
            if (errno != EINTR)
                mourir("wait4 failed");
        alarm(0);
        fils_courant = 0;
        fin = maintenant();

        printf("{\"jeton\": \"%s\", \"etiquette\": \"%s\", \"code\": %d, \"signal\": %d, \"utilisateur_s\": %.6f, "
               "\"systeme_s\": %.6f, \"mur_s\": %.6f, \"maxrss_ko\": %ld, \"instructions\": ",
               jeton, champs[0], WIFEXITED(statut) ? WEXITSTATUS(statut) : -1,
               WIFSIGNALED(statut) ? WTERMSIG(statut) : 0, secondes(ru.ru_utime), secondes(ru.ru_stime),
               fin - debut, ru.ru_maxrss);
        if (instructions >= 0)
            printf("%lld}\n", instructions);
        else
            printf("null}\n");
        fflush(stdout);
    }
    free(lignes);
    return 0;
}

/* Lanceur et chronomètre du juge isolé Bee (bee/README.md, section « Juge isolé »).

   Programme de la BASE, compilé sans une ligne de la PR. Il tourne en processus 1 d'un conteneur sans
   réseau et lance, une par une, les commandes d'un plan écrit par l'hôte. Chaque commande (le harnais
   lié au miniz à juger) est un processus fils : son temps processeur et sa mémoire maximale sont lus
   par wait4, c'est-à-dire mesurés par le noyau, pas déclarés par le code mesuré.

   Ce que le fils ne peut pas faire :
   - écrire sur la sortie standard du conteneur, qui porte les mesures : ses descripteurs 0 et 1 sont
     /dev/null, 2 est un journal dans le dossier de sorties ; ce processus se déclare non « dumpable »
     (prctl), si bien que /proc/1/fd et /proc/1/mem lui sont fermés ;
   - lancer d'autres processus : le conteneur est limité à deux processus (--pids-limit 2) ;
   - forger une ligne de mesure : chaque ligne porte un jeton lu sur l'entrée standard avant le premier
     fork, que le fils ne voit jamais.

   Décompte d'instructions (--valgrind) : la commande est valgrind --tool=cachegrind, dont le résumé
   (« I refs: N ») est la DERNIÈRE ligne écrite sur la sortie d'erreur du fils. chrono lit cette sortie
   par un tube et relève la dernière ligne non vide. Le code mesuré peut écrire sur la même sortie, mais
   seulement AVANT le résumé, que Valgrind écrit en dernier, une fois le programme terminé ; s'il tue le
   processus pour empêcher le résumé, le signal est relevé et la mesure refusée par l'hôte. Le fichier
   cachegrind.out, lui, n'est pas lu : le code mesuré pourrait le forger.

   Usage : chrono [--delai SECONDES] [--journal DOSSIER] [--valgrind] <plan>
     plan : une commande par ligne, champs séparés par des tabulations : étiquette, programme, arguments.
            Étiquette : lettres, chiffres, « _ » et « - ».
     L'entrée standard donne le jeton (une ligne de 16 à 64 caractères hexadécimaux).
   Sortie : une ligne JSON par commande, dans l'ordre du plan :
     {"jeton": "...", "etiquette": "...", "code": 0, "signal": 0, "utilisateur_s": 0.0, "systeme_s": 0.0,
      "mur_s": 0.0, "maxrss_ko": 0, "instructions": null}
   Code de sortie : 0 si le plan a été lu et toutes les commandes lancées (quel que soit leur code), 2 sinon. */

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

static volatile pid_t fils_courant = 0;

static void sur_alarme(int signal_recu)
{
    (void)signal_recu;
    if (fils_courant > 0)
        kill(fils_courant, SIGKILL);
}

static void mourir(const char *message)
{
    fprintf(stderr, "chrono : %s\n", message);
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

/* Dernière ligne non vide de la sortie d'erreur : « ==PID== I refs: 1,234,567 » (résumé de Cachegrind).
   Renvoie le nombre, ou -1 si la dernière ligne n'est pas un résumé bien formé. */
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
    char jeton[80], ligne[LIGNE_MAX], journal_chemin[4096];
    const char *journal = NULL, *plan = NULL;
    unsigned delai = 0;
    int valgrind = 0;
    static char queue[QUEUE_MAX + 1];
    char (*lignes)[LIGNE_MAX] = NULL;
    size_t nombre = 0, capacite = 0, i, n;
    FILE *f;
    int nul, k;
    struct sigaction action;

    umask(0); /* l'hôte doit pouvoir effacer les journaux (écrits par un autre utilisateur) */
    /* D'abord : plus personne (même uid) n'ouvre /proc/<ce processus>/fd ni /mem. */
    if (prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0)
        mourir("prctl(PR_SET_DUMPABLE) a échoué");

    for (k = 1; k < argc; k++)
    {
        if (strcmp(argv[k], "--delai") == 0 && k + 1 < argc)
            delai = (unsigned)strtoul(argv[++k], NULL, 10);
        else if (strcmp(argv[k], "--journal") == 0 && k + 1 < argc)
            journal = argv[++k];
        else if (strcmp(argv[k], "--valgrind") == 0)
            valgrind = 1;
        else if (!plan)
            plan = argv[k];
        else
            mourir("argument inattendu");
    }
    if (!plan)
        mourir("usage : chrono [--delai S] [--journal DOSSIER] <plan>");

    if (!fgets(jeton, sizeof(jeton), stdin))
        mourir("jeton absent sur l'entrée standard");
    jeton[strcspn(jeton, "\r\n")] = 0;
    n = strlen(jeton);
    if (n < 16 || n > 64 || strspn(jeton, "0123456789abcdef") != n)
        mourir("jeton invalide");

    f = fopen(plan, "r");
    if (!f)
        mourir("plan illisible");
    while (fgets(ligne, sizeof(ligne), f))
    {
        ligne[strcspn(ligne, "\r\n")] = 0;
        if (!ligne[0])
            continue;
        if (nombre == capacite)
        {
            capacite = capacite ? 2 * capacite : 16;
            lignes = realloc(lignes, capacite * sizeof(*lignes));
            if (!lignes)
                mourir("mémoire insuffisante");
        }
        memcpy(lignes[nombre++], ligne, LIGNE_MAX);
    }
    fclose(f);

    nul = open("/dev/null", O_RDWR | O_CLOEXEC);
    if (nul < 0)
        mourir("/dev/null introuvable");
    /* L'entrée standard (le tube qui portait le jeton) se ferme ici : le fils n'en hérite pas. */
    if (dup2(nul, 0) < 0)
        mourir("dup2 a échoué");

    memset(&action, 0, sizeof(action));
    action.sa_handler = sur_alarme;
    sigaction(SIGALRM, &action, NULL);

    for (i = 0; i < nombre; i++)
    {
        char *champs[CHAMPS_MAX + 1], *sauvegarde = NULL, *morceau;
        int nchamps = 0, statut = 0, sortie_journal = -1, tube[2] = {-1, -1};
        size_t remplissage = 0;
        long long instructions = -1;
        struct rusage ru;
        double debut, fin;
        pid_t pid;

        for (morceau = strtok_r(lignes[i], "\t", &sauvegarde); morceau && nchamps < CHAMPS_MAX;
             morceau = strtok_r(NULL, "\t", &sauvegarde))
            champs[nchamps++] = morceau;
        champs[nchamps] = NULL;
        if (nchamps < 2 || !etiquette_valide(champs[0]))
            mourir("ligne de plan invalide");

        if (journal)
        {
            int c = snprintf(journal_chemin, sizeof(journal_chemin), "%s/%s.err", journal, champs[0]);
            if (c < 0 || (size_t)c >= sizeof(journal_chemin))
                mourir("chemin de journal trop long");
            sortie_journal = open(journal_chemin, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0644);
        }

        if (valgrind && pipe2(tube, O_CLOEXEC) != 0)
            mourir("pipe2 a échoué");
        fflush(stdout);
        debut = maintenant();
        pid = fork();
        if (pid < 0)
            mourir("fork a échoué");
        if (pid == 0)
        {
            int erreur = valgrind ? tube[1] : (sortie_journal >= 0 ? sortie_journal : nul);
            if (dup2(nul, 0) < 0 || dup2(nul, 1) < 0 || dup2(erreur, 2) < 0)
                _exit(126);
            execv(champs[1], champs + 1);
            _exit(127);
        }
        fils_courant = pid;
        if (delai)
            alarm(delai);
        if (valgrind)
        {
            /* Lit tout ce que le fils écrit sur sa sortie d'erreur ; ne garde que la fin. */
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
            instructions = releve_instructions(queue, remplissage);
        }
        while (wait4(pid, &statut, 0, &ru) < 0)
            if (errno != EINTR)
                mourir("wait4 a échoué");
        alarm(0);
        fils_courant = 0;
        fin = maintenant();
        if (sortie_journal >= 0)
            close(sortie_journal);

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

/* Harnais du projet jouet (rle) pour le juge commun Bee (outils/juge/).

   Compilé AVEC le rle à juger, dans un conteneur sans réseau, et n'y tourne que là. Il ne juge rien :
   il lit les entrées préparées par l'hôte, appelle rle, et écrit les sorties brutes ; le greffon
   (projet.py, côté hôte) les vérifie avec son propre codec de référence et les compare à la base.

   Usage : execution, sans argument ; le descripteur 0 porte une ligne
     « <mode> <dossier_entrees> <dossier_sorties> » (juge commun, docs/juge-commun.md).
     <dossier_entrees>/liste : « f NOM TAILLE » (fichier brut f/NOM) ou « z NOM TAMPON » (flux z/NOM,
                               TAMPON = taille du tampon de sortie donné à rle_decompresser)
     modes : verifier, compression, decompression ; le travail est le même dans chaque mode, le côté de
     chaque entrée le choisit : pour chaque f : c/NOM ; pour chaque z : d/NOM (octets produits) et e/NOM
     (statut), si bien que chaque sortie se vérifie de la même façon, quel que soit le mode.
   Le code jugé ne peut pas savoir s'il est vérifié ou mesuré : avant le premier appel à rle, le harnais
   lit ses paramètres jusqu'à la fin du tube, les recopie, puis efface leur texte, ses arguments et son
   environnement.
   Code de sortie : 0 si toutes les sorties ont été écrites, 2 sinon. */

#include "rle.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

extern char **environ;

static char entrees[256], sorties[256];

static void mourir(const char *message, const char *detail)
{
    fprintf(stderr, "execution : %s : %s\n", message, detail);
    exit(2);
}

static unsigned char *lire(const char *type, const char *nom, size_t *longueur)
{
    char p[4096];
    FILE *f;
    unsigned char *tampon = NULL;
    size_t taille = 0, capacite = 0, lus;
    snprintf(p, sizeof(p), "%s/%s/%s", entrees, type, nom);
    f = fopen(p, "rb");
    if (!f)
        mourir("entrée illisible", p);
    do {
        if (taille == capacite) {
            capacite = capacite ? 2 * capacite : 65536;
            tampon = (unsigned char *)realloc(tampon, capacite);
            if (!tampon)
                mourir("mémoire insuffisante", p);
        }
        lus = fread(tampon + taille, 1, capacite - taille, f);
        taille += lus;
    } while (lus > 0);
    fclose(f);
    *longueur = taille;
    return tampon;
}

static void ecrire(const char *dossier, const char *nom, const void *donnees, size_t longueur)
{
    char p[4096];
    FILE *f;
    snprintf(p, sizeof(p), "%s/%s", sorties, dossier);
    if (mkdir(p, 0777) != 0 && errno != EEXIST)
        mourir("dossier impossible", p);
    snprintf(p, sizeof(p), "%s/%s/%s", sorties, dossier, nom);
    f = fopen(p, "wb");
    if (!f || (longueur && fwrite(donnees, 1, longueur, f) != longueur) || fclose(f) != 0)
        mourir("écriture impossible", p);
}

static void compresser(const char *nom)
{
    size_t n, m;
    unsigned char *src = lire("f", nom, &n);
    size_t borne = rle_borne(n);
    unsigned char *dst;
    /* Un harnais ne dimensionne jamais un tampon d'après le seul code jugé : la borne du format, connue
       ici, est un minimum (revue adverse du 28/10). */
    if (borne < 8 + n + n / 128 + 1)
        mourir("borne sous-dimensionnée", nom);
    dst = (unsigned char *)malloc(borne);
    if (!dst)
        mourir("mémoire insuffisante", nom);
    m = rle_compresser(src, n, dst);
    ecrire("c", nom, dst, m);
    free(src);
    free(dst);
}

static void decompresser(const char *nom, size_t tampon)
{
    size_t n, produit = 0;
    unsigned char *src = lire("z", nom, &n);
    unsigned char *dst = (unsigned char *)malloc(tampon ? tampon : 1);
    int code;
    if (!dst)
        mourir("mémoire insuffisante", nom);
    code = rle_decompresser(src, n, dst, tampon, &produit);
    ecrire("d", nom, dst, produit);
    {
        char texte[64];
        int k = snprintf(texte, sizeof(texte), "%d %zu\n", code, produit);
        ecrire("e", nom, texte, (size_t)k);
    }
    free(src);
    free(dst);
}

/* Lit les paramètres sur le descripteur 0 jusqu'à la fin du tube, les recopie, puis efface leur texte, les
   arguments et l'environnement : après, rien dans le processus ne dit le mode. */
static void parametres(int argc, char **argv)
{
    char texte[1024], mode[64];
    size_t n = 0;
    ssize_t lu;
    int i, ok;
    char **e;
    while (n < sizeof(texte) - 1 && ((lu = read(0, texte + n, sizeof(texte) - 1 - n)) > 0 || (lu < 0 && errno == EINTR)))
        n += lu > 0 ? (size_t)lu : 0;
    texte[n] = 0;
    ok = n < sizeof(texte) - 1 && sscanf(texte, "%63s %255s %255s", mode, entrees, sorties) == 3 && (strcmp(mode, "verifier") == 0
         || strcmp(mode, "compression") == 0 || strcmp(mode, "decompression") == 0);
    explicit_bzero(texte, sizeof(texte));
    explicit_bzero(mode, sizeof(mode));
    for (i = 0; i < argc; i++)
        explicit_bzero(argv[i], strlen(argv[i]));
    for (e = environ; e && *e; e++)
        explicit_bzero(*e, strlen(*e));
    if (environ)
        environ[0] = NULL;
    if (!ok || argc != 1)
        mourir("usage", "execution, paramètres « <mode> <entrées> <sorties> » sur le descripteur 0");
}

int main(int argc, char **argv)
{
    char p[4096], ligne[256], type, nom[64];
    unsigned long long taille;
    FILE *liste;
    umask(0); /* l'hôte (autre utilisateur) doit pouvoir effacer ce que le harnais écrit */
    parametres(argc, argv);
    snprintf(p, sizeof(p), "%s/liste", entrees);
    liste = fopen(p, "r");
    if (!liste)
        mourir("liste illisible", p);
    while (fgets(ligne, sizeof(ligne), liste)) {
        if (sscanf(ligne, " %c %63s %llu", &type, nom, &taille) != 3)
            continue;
        if (type == 'f')
            compresser(nom);
        else if (type == 'z')
            decompresser(nom, (size_t)taille);
    }
    fclose(liste);
    return 0;
}

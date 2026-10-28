/* Harnais du projet jouet (rle) pour le juge commun Bee (outils/juge/).

   Compilé AVEC le rle à juger, dans un conteneur sans réseau, et n'y tourne que là. Il ne juge rien :
   il lit les entrées préparées par l'hôte, appelle rle, et écrit les sorties brutes ; le greffon
   (projet.py, côté hôte) les vérifie avec son propre codec de référence et les compare à la base.

   Usage : execution <mode> <dossier_entrees> <dossier_sorties>
     <dossier_entrees>/liste : « f NOM TAILLE » (fichier brut f/NOM) ou « z NOM TAMPON » (flux z/NOM,
                               TAMPON = taille du tampon de sortie donné à rle_decompresser)
     modes :
       verifier       pour chaque f : c/NOM ; pour chaque z : d/NOM (octets produits) et e/NOM (statut)
       compression    pour chaque f : c/NOM
       decompression  pour chaque z : d/NOM
   Code de sortie : 0 si toutes les sorties ont été écrites, 2 sinon. */

#include "rle.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

static const char *entrees, *sorties;

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
    unsigned char *dst = (unsigned char *)malloc(rle_borne(n));
    if (!dst)
        mourir("mémoire insuffisante", nom);
    m = rle_compresser(src, n, dst);
    ecrire("c", nom, dst, m);
    free(src);
    free(dst);
}

static void decompresser(const char *nom, size_t tampon, int avec_statut)
{
    size_t n, produit = 0;
    unsigned char *src = lire("z", nom, &n);
    unsigned char *dst = (unsigned char *)malloc(tampon ? tampon : 1);
    int code;
    if (!dst)
        mourir("mémoire insuffisante", nom);
    code = rle_decompresser(src, n, dst, tampon, &produit);
    ecrire("d", nom, dst, produit);
    if (avec_statut) {
        char texte[64];
        int k = snprintf(texte, sizeof(texte), "%d %zu\n", code, produit);
        ecrire("e", nom, texte, (size_t)k);
    }
    free(src);
    free(dst);
}

int main(int argc, char **argv)
{
    char p[4096], ligne[256], type, nom[64];
    unsigned long long taille;
    FILE *liste;
    int verifier;
    umask(0); /* l'hôte (autre utilisateur) doit pouvoir effacer ce que le harnais écrit */
    if (argc != 4)
        mourir("usage", "execution <mode> <entrées> <sorties>");
    entrees = argv[2];
    sorties = argv[3];
    verifier = strcmp(argv[1], "verifier") == 0;
    if (!verifier && strcmp(argv[1], "compression") != 0 && strcmp(argv[1], "decompression") != 0)
        mourir("mode inconnu", argv[1]);
    snprintf(p, sizeof(p), "%s/liste", entrees);
    liste = fopen(p, "r");
    if (!liste)
        mourir("liste illisible", p);
    while (fgets(ligne, sizeof(ligne), liste)) {
        if (sscanf(ligne, " %c %63s %llu", &type, nom, &taille) != 3)
            continue;
        if (type == 'f' && (verifier || strcmp(argv[1], "compression") == 0))
            compresser(nom);
        else if (type == 'z' && (verifier || strcmp(argv[1], "decompression") == 0))
            decompresser(nom, (size_t)taille, verifier);
    }
    fclose(liste);
    return 0;
}

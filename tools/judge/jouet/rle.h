/* rle : petit codec par plages, projet jouet des méta-tests du juge commun Bee (outils/juge/).

   Format : longueur de l'original (4 octets, petit-boutiste), puis des blocs, puis le CRC-32 de
   l'original (4 octets, petit-boutiste, polynôme de zlib). Un bloc commence par un octet c :
     c < 128   : c + 1 octets littéraux suivent ;
     c >= 128  : l'octet suivant est répété c - 125 fois (de 3 à 130 fois). */
#ifndef RLE_H
#define RLE_H

#include <stddef.h>

#define RLE_OK 0
#define RLE_INVALIDE (-1)
#define RLE_TAMPON_TROP_PETIT (-2)

/* Taille maximale de la sortie de rle_compresser pour n octets. */
size_t rle_borne(size_t n);

/* Compresse src (n octets) dans dst (au moins rle_borne(n) octets) ; renvoie la taille écrite. */
size_t rle_compresser(const unsigned char *src, size_t n, unsigned char *dst);

/* Décompresse src (n octets) dans dst (cap octets). *produit reçoit le nombre d'octets écrits, même en
   cas d'erreur. Renvoie RLE_OK, RLE_INVALIDE ou RLE_TAMPON_TROP_PETIT. */
int rle_decompresser(const unsigned char *src, size_t n, unsigned char *dst, size_t cap, size_t *produit);

#endif

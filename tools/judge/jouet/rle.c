/* rle : implémentation de référence du projet jouet (voir rle.h). Volontairement simple et lente. */
#include "rle.h"

#include <string.h>

static void rle_table_crc(unsigned long table[256])
{
    unsigned long n, k, c;
    for (n = 0; n < 256; n++) {
        c = n;
        for (k = 0; k < 8; k++)
            c = (c & 1) ? (0xEDB88320UL ^ (c >> 1)) : (c >> 1);
        table[n] = c;
    }
}

static unsigned long rle_crc(const unsigned long table[256], const unsigned char *p, size_t n)
{
    unsigned long c = 0xFFFFFFFFUL;
    size_t i;
    for (i = 0; i < n; i++)
        c = table[(c ^ p[i]) & 0xFF] ^ (c >> 8);
    return (c ^ 0xFFFFFFFFUL) & 0xFFFFFFFFUL;
}

static void rle_ecrire32(unsigned char *p, unsigned long v)
{
    p[0] = (unsigned char)(v & 0xFF);
    p[1] = (unsigned char)((v >> 8) & 0xFF);
    p[2] = (unsigned char)((v >> 16) & 0xFF);
    p[3] = (unsigned char)((v >> 24) & 0xFF);
}

static unsigned long rle_lire32(const unsigned char *p)
{
    return (unsigned long)p[0] | ((unsigned long)p[1] << 8) | ((unsigned long)p[2] << 16) | ((unsigned long)p[3] << 24);
}

size_t rle_borne(size_t n)
{
    return 8 + n + n / 128 + 1;
}

static size_t rle_litteraux(const unsigned char *src, size_t debut, size_t fin, unsigned char *dst, size_t o)
{
    while (debut < fin) {
        size_t k = fin - debut;
        if (k > 128)
            k = 128;
        dst[o++] = (unsigned char)(k - 1);
        memcpy(dst + o, src + debut, k);
        o += k;
        debut += k;
    }
    return o;
}

size_t rle_compresser(const unsigned char *src, size_t n, unsigned char *dst)
{
    unsigned long table[256];
    size_t i = 0, debut = 0, o = 4;
    rle_table_crc(table);
    rle_ecrire32(dst, (unsigned long)n);
    while (i < n) {
        size_t plage = 1;
        while (i + plage < n && plage < 130 && src[i + plage] == src[i])
            plage++;
        if (plage >= 3) {
            o = rle_litteraux(src, debut, i, dst, o);
            dst[o++] = (unsigned char)(plage + 125);
            dst[o++] = src[i];
            i += plage;
            debut = i;
        } else {
            i += plage;
        }
    }
    o = rle_litteraux(src, debut, n, dst, o);
    rle_ecrire32(dst + o, rle_crc(table, src, n));
    return o + 4;
}

int rle_decompresser(const unsigned char *src, size_t n, unsigned char *dst, size_t cap, size_t *produit)
{
    unsigned long table[256];
    size_t i = 4, o = 0, longueur;
    *produit = 0;
    if (n < 8)
        return RLE_INVALIDE;
    longueur = rle_lire32(src);
    if (longueur > cap)
        return RLE_TAMPON_TROP_PETIT;
    while (i < n - 4 && o < longueur) {
        unsigned c = src[i++];
        if (c < 128) {
            size_t k = (size_t)c + 1;
            if (i + k > n - 4 || o + k > longueur) {
                *produit = o;
                return RLE_INVALIDE;
            }
            memcpy(dst + o, src + i, k);
            i += k;
            o += k;
        } else {
            size_t k = (size_t)c - 125;
            if (i >= n - 4 || o + k > longueur) {
                *produit = o;
                return RLE_INVALIDE;
            }
            memset(dst + o, src[i++], k);
            o += k;
        }
    }
    *produit = o;
    if (o != longueur || i != n - 4)
        return RLE_INVALIDE;
    rle_table_crc(table);
    if (rle_crc(table, dst, o) != rle_lire32(src + n - 4))
        return RLE_INVALIDE;
    return RLE_OK;
}

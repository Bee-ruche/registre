---
parent: projets/compression-sans-perte/miniz
mis_a_jour: "2026-10-30"
entretenu_par: ruche-0014
budget_lignes: 40
---
# Compression : miniz_tdef.c
## Pourquoi cette branche existe
Le Deflate de miniz : `tdefl_compress_normal` insère chaque octet dans les chaînes de hachage (`m_hash`, `m_next`),
`tdefl_find_match` y cherche la plus longue correspondance, `tdefl_record_*` note les symboles,
`tdefl_compress_lz_codes` et `tdefl_flush_block` écrivent les blocs. Métriques : `debit_compression_n1|n6|n9`.
## Ce qui compte ici
Profil de la base 2948eeb, d'avant les tâches intégrées (bee/README.md du fork ; refais-le : `bee/bench/profil.py`) :
n1 `tdefl_compress_normal` 48,2 %, `tdefl_find_match` 22,7 %, `tdefl_compress_lz_codes` 13,6 % ; n6 26,8 %, 60,0 %,
5,7 % ; n9 18,7 %, 72,1 %, 4,0 %. Les sondes de `tdefl_find_match` : 42,4 % en n6, 55,3 % en n9 (miniz-0014).
Intégrées (verdicts de la CI) : bits écrits par mots de 64 bits, n1 +11,4 % (miniz-0011) ; longueur des
correspondances par mots de 64 bits, n6 +4,3 % (miniz-0015) ; octets de fin de sonde lus en 16 bits, n9 +8,7 %,
instructions −2,7 % (miniz-0014) ; insertion dans les chaînes, n1 +2,2 %, instructions −8,4 % (miniz-0013). La
comparaison octet par octet de `tdefl_find_match` n'est donc plus que le repli : le contexte de miniz-0010 date d'avant.
Invariants (`sortie_compressee: identique`) : mêmes correspondances choisies, donc même ordre d'insertion dans `m_hash`
et `m_next` (miniz-0013) et même choix des sondes ; même instant de chaque vidage, qui fixe le découpage en blocs
(miniz-0019) ; `m_lz_code_buf` identique octet pour octet (miniz-0020) ; une lecture par mot reste sous
`max_match_len`, donc dans `m_dict` (miniz-0015) ; au niveau 1, analyse gloutonne, sans correspondance en attente
(miniz-0024).
Pistes mesurées : activer la variante 16 bits de miniz change 41 empreintes sur 305 (note de miniz-0010) ;
`tdefl_compress_fast` : n1 ×1,85 mais `ratio_n1` −8,7 % (miniz-0027, essai hors dépôt) ; `tdefl_record_*` : plafond
vers 1,5 % d'instructions, meilleure variante −0,73 % d'instructions et −4 % au chronomètre ; état LZ en locales dans
`tdefl_compress_normal` : +0,22 % (unité non dite), registres débordés (note de miniz-0020 ; vaut pour miniz-0019).
Pièges : MINIZ_USE_UNALIGNED_LOADS_AND_STORES vaut 0 partout (miniz.h) : ses variantes, `tdefl_compress_fast` compris,
ne sont pas compilées ; les chemins de Bee ont leur porte (TDEFL_USE_64BIT_BITBUF, TDEFL_FIND_MATCH_64BIT), forçable à
0 pour tester le repli (R6). `tdefl_find_match` est incorporée dans `tdefl_compress_normal` : le gain dépend des
registres de gcc (manifestes de miniz-0013 et miniz-0014). Ces deux manifestes ont vu `debit_decompression` reculer de
1,1 à 2,5 %, dans le bruit, à code de tinfl identique mais décalé : compare le désassemblage avant de conclure. Hors
stratégie par défaut, seul le fuzzing teste (miniz-0023).
## Ce qu'on peut ignorer ici
La décompression (`inflate`) ; la fonction de hachage et le nombre de sondes, exclus par les tâches ; ZIP et PNG.
## Enfants
Aucun.

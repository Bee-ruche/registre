---
parent: projets/compression-sans-perte/miniz
mis_a_jour: "2026-10-30"
entretenu_par: ruche-0014
budget_lignes: 40
---
# API compatible zlib : miniz.c
## Pourquoi cette branche existe
`miniz.c` donne l'API de zlib au-dessus de tdefl et de tinfl : `mz_compress2`, `mz_uncompress`, `mz_deflate`,
`mz_inflate` et leurs Init, Reset et End, plus `mz_adler32` et `mz_crc32`. Les juges appellent miniz par elle.
## Ce qui compte ici
Le contrat : codes de retour, `avail_in`, `avail_out` et `total_*` restent ceux de la base, écarts avec zlib compris.
`bee/tests/api.c` les fige : 192 cas comparés à zlib, 55 écarts tolérés et justifiés dans `manifestes/miniz-0026.yaml`
du fork, branches de miniz.c prises de 55,0 % à 94,4 % (miniz-0026). Rapprocher un code de celui de zlib change un
comportement : hors d'une optimisation (commandement 1).
Flux : découpée en appels de `mz_deflate`, sans vidage, la sortie compressée est celle de `mz_compress2` (contrôles
`flux-1` et `flux-4096`, bee/README.md) ; avec MZ_SYNC_FLUSH, zlib exige au moins 8 octets de sortie par appel, et des
vidages fréquents peuvent dépasser `mz_compressBound`, comme chez zlib (bee/README.md, « Fuzzing »).
`mz_inflate` passe l'entrée de l'appelant telle quelle à `tinfl_decompress`, mais décode dans son dictionnaire de
32 Kio, sauf avec MZ_FINISH au premier appel (miniz.c l. 466-512 à 9977da4) : un petit tampon de sortie ne réduit
pas la sortie que voit tinfl (zone `inflate`, bornes du chemin rapide).
`mz_adler32` : 3,7 % des instructions en n1 sur la base 2948eeb (bee/README.md) ; miniz-0016 visait l'Adler-32 de
tinfl, pas lui.
Le juge isolé compte tout le processus : du travail déplacé dans `mz_compressBound` ne fait rien gagner (bee/README.md).
`bee/bench/profil.py` ne repère pas encore les fonctions à majuscules (`mz_deflateInit2`…) : leur coût part en « hors
fonction », environ 4 500 instructions par scénario (miniz-0034).
## Ce qu'on peut ignorer ici
ZIP (`miniz_zip.c`) et PNG, hors périmètre ; les noms sans préfixe de miniz.h, simples renvois aux `mz_*`.
## Enfants
Aucun.

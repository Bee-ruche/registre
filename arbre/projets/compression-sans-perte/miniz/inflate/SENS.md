---
parent: projets/compression-sans-perte/miniz
mis_a_jour: "2026-10-30"
entretenu_par: ruche-0014
budget_lignes: 40
---
# Décompression : miniz_tinfl.c
## Pourquoi cette branche existe
L'Inflate de miniz : `tinfl_decompress`, une coroutine qui s'arrête et reprend à n'importe quel octet d'entrée ou de
sortie (TINFL_CR_RETURN), construit les tables de Huffman de chaque bloc, décode littéraux, longueurs et distances,
copie les correspondances et calcule l'Adler-32. Métrique : `debit_decompression`.
## Ce qui compte ici
Profil de la base 2948eeb, d'avant miniz-0012 et miniz-0016 (refais-le : `bee/bench/profil.py`) : `tinfl_decompress`
99,3 % de la décompression (bee/README.md du fork) ; copie des correspondances 23,0 % (miniz-0012), boucle des
littéraux 22,2 % (miniz-0018), Adler-32 22,0 % (miniz-0016), longueur et distance 19,1 % (miniz-0017), construction
des tables 4,1 % (miniz-0022).
Intégrées (verdicts de la CI) : copie des correspondances sans chevauchement par 4 ou 8 octets, instructions −7,4 %,
débit +17,2 % (miniz-0012) ; Adler-32 par blocs de 16 octets, instructions −4,9 %, débit +9,5 % (miniz-0016).
Instructions et chronomètre divergent souvent : en relecture, miniz-0017-c1 (−5,1 % d'instructions) et miniz-0018-c1
(−3,9 %) restent dans le bruit au chronomètre (leurs verdicts) ; la copie par 8 octets d'origine, activée : −1,9 %
d'instructions, débit −2,2 % (miniz-0012, essai hors dépôt) ; pointeurs locaux vers les tables : +0,9 % d'instructions
(note de miniz-0018) ; tables à la libdeflate : −2,8 % d'instructions sur 128 Kio par fichier, débit +0,6 %, pile de
448 à 1 120 octets (note de miniz-0022). R4 demande alors une autre configuration qui voie le gain.
Format de `m_look_up` (miniz_tinfl.c l. 363 à 9977da4) : une entrée positive vaut (longueur du code << 9) | symbole,
pour les codes de 10 bits au plus (TINFL_FAST_LOOKUP_BITS) ; une négative mène à `m_tree_*` pour les codes plus
longs. Tout chemin rapide lit ce format tel quel, et les tables produites restent identiques (miniz-0022).
Un chemin rapide se prouve aussi à ses bornes : celui de la boucle des littéraux exige 4 octets d'entrée et 2 de
sortie (l. 427), et le contrôle `flux-1` (tampons d'un octet, bee/tests/differentiel.c l. 7) ne l'exerce jamais (note
corrective de ruche-0014). Montre quelles tailles d'entrée et de sortie, de part et d'autre du seuil, l'exercent ; ce
qui ne l'a pas été va dans `non_teste`.
Invariants : les chemins lents (fin de tampon, reprise de la coroutine) restent intacts : eux seuls permettent l'appel
octet par octet (miniz-0017) ; sur entrée invalide, mêmes statuts et mêmes octets produits avant l'arrêt (miniz-0018),
ce que comparent `fuzz_inflate` et le juge isolé ; Adler-32 réduit modulo 65521 au plus tous les 5552 octets
(miniz-0016).
## Ce qu'on peut ignorer ici
La compression (`deflate`) ; les messages et codes d'erreur, exclus par les tâches ; ZIP et PNG.
## Enfants
Aucun.

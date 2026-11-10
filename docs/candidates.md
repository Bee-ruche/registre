# Projets candidats

Recherche du 27 octobre 2026, faite par un agent de recherche de Bee sans rien cloner ni exécuter. Les licences ont été lues dans les fichiers de licence officiels. La présence dans OSS-Fuzz a été vérifiée par le fichier `projects/<nom>/project.yaml` de google/oss-fuzz. Les chiffres d'usage viennent de Debian (popcon, et nombre de paquets de trixie qui dépendent directement de la bibliothèque). Les tailles comptent les lignes du cœur, commentaires compris. Ce qui n'a pas pu être vérifié est marqué « estimé ».

## Retenus pour la phase 3

| Projet | Catégorie | Licence | Référence différentielle | Cœur | Usage | Pourquoi |
| --- | --- | --- | --- | --- | --- | --- |
| [giflib](https://sourceforge.net/p/giflib/code/) | Décodage d'images | MIT | Wuffs std/gif, stb_image, libnsgif | ~3 700 lignes, décodeur ~2 400 (estimé) | OpenJDK, Android, GDAL, Emacs, Krita ; 138 000 installations Debian | Tout petit, trois références indépendantes, aucune vectorisation ; Wuffs annonce un décodage 2 à 6 fois plus rapide |
| [libyaml](https://github.com/yaml/libyaml) | Parsing et sérialisation | MIT | yaml-test-suite (flux d'événements), libfyaml | ~13 000 lignes | Chargeur C de PyYAML, Psych (Ruby), appstream, netplan ; 202 000 installations | Oracle le plus strict ; aucune version depuis 2020 ; écart d'environ 6,5 fois avec rapidyaml sur leur banc |
| [bzip2](https://sourceware.org/git/?p=bzip2.git) | Compression sans perte | BSD propre à bzip2 | Sortie d'origine octet pour octet, corpus bzip2-tests, Wuffs, libbzip2-rs | ~5 200 lignes | dpkg, apt, bibliothèque standard de Python ; 6ᵉ paquet le plus installé de Debian | Usage massif, aucune vectorisation, réutilise tout l'outillage de miniz |

Points d'attention :
- **giflib.** Wuffs compose les trames animées alors que giflib rend les trames brutes : le harnais doit recomposer avant de comparer.
- **bzip2.** Partir de sourceware : le miroir GitLab est figé depuis mai 2023.

## En réserve (phase 4 ou plus tard)

| Projet | Catégorie | Licence | Note |
| --- | --- | --- | --- |
| [LodePNG](https://github.com/lvandeve/lodepng) | Décodage d'images | zlib | Prévu à l'origine pour la phase 3 ; recoupe giflib pour le harnais image |
| [cJSON](https://github.com/DaveGamble/cJSON) | Parsing JSON | MIT | Prévu à l'origine pour la phase 3 ; très présent dans l'embarqué, que les chiffres Debian sous-estiment |
| [zopfli](https://github.com/google/zopfli) | Compression | Apache-2.0 | Très lent par conception, donc grande marge ; oracle trivial (sortie déterministe) |
| [md4c](https://github.com/mity/md4c) | Parsing Markdown | MIT | Spécification CommonMark comme oracle ; l'auteur optimise déjà, donc moins de marge |
| [jansson](https://github.com/akheron/jansson) | Parsing JSON | MIT | Réutiliserait le harnais JSON ; binutils, apache2, nftables |
| [libcbor](https://github.com/PJK/libcbor) | Sérialisation CBOR | MIT | Petit et propre ; messages FIDO minuscules, gain perçu faible (estimé) |
| [Expat](https://github.com/libexpat/libexpat) | Parsing XML | MIT | Usage énorme (dbus, fontconfig, CPython) mais 16 800 lignes, et le fork devrait suivre les correctifs de sécurité de l'amont |
| [nanopb](https://github.com/nanopb/nanopb) | Sérialisation Protobuf | zlib | Intéressant pour l'objectif « plus léger » (ROM, RAM, pile) |
| [stb_image](https://github.com/nothings/stb) | Décodage d'images | MIT ou domaine public | JPEG déjà partiellement vectorisé |
| [QOI](https://github.com/phoboslab/qoi) | Décodage d'images | MIT | 649 lignes : bon projet d'école pour former les agents, impact faible |

## Écartés

| Projet | Raison |
| --- | --- |
| lz4, LZMA SDK, base64 (aklomp), libwebp sans perte, libspng, libpng | Déjà vectorisés ou écrits en assembleur |
| zlib, libdeflate, zstd, simdjson, yyjson, libjpeg-turbo | Fork optimisé existant ou déjà très optimisés |
| pugixml | Déjà conçu pour la vitesse, usage Debian faible |
| tinyxml2 | Parseur laxiste, pas d'oracle strict |
| cmark | Doublon de md4c ; meilleur comme référence |
| jsmn, inih, uriparser, cgltf | Usage faible ou jamais un goulot d'étranglement |
| tomlc99 | Déclaré obsolète par son auteur |
| dr_flac | Audio : hors des catégories de la v0 |
| LZO | Licence GPL-2 |
| libxml2 | Trop gros |

## Principales sources

- Licences et fichiers de licence : dépôts officiels de chaque projet ; [bzip2 sur sourceware](https://sourceware.org/git/?p=bzip2.git) ; [giflib sur SourceForge](https://sourceforge.net/p/giflib/code/ci/master/tree/COPYING).
- OSS-Fuzz : [google/oss-fuzz, dossier projects](https://github.com/google/oss-fuzz/tree/master/projects).
- Usage : [popcon Debian](https://popcon.debian.org/) et index des paquets de Debian trixie.
- Marges de gain annoncées : [README de Wuffs](https://github.com/google/wuffs), [banc de rapidyaml](https://rapidyaml.readthedocs.io/).

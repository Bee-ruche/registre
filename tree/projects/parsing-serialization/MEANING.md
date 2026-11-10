---
parent: root
updated_on: "2026-10-30"
maintained_by: ruche-0010
line_budget: 40
---
# Parsing et sérialisation
## Pourquoi cette branche existe
Les analyseurs de formats texte lisent configurations et données sur tout le web : chaque octet y passe.
## Ce qui compte ici
Preuve exigée : même arbre que la référence sur une suite de conformité, et mêmes refus sur les entrées invalides
(categories.yaml). Une erreur d'analyse fait partie du résultat : elle ne change pas non plus.
## Ce qu'on peut ignorer ici
cJSON, en réserve pour la phase 4 (projets/cjson.yaml).
## Enfants
- `projects/parsing-serialization/libyaml` : libyaml, analyseur et émetteur YAML

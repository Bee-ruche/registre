---
parent: projets/ruche
mis_a_jour: "2026-10-30"
entretenu_par: ruche-0010
budget_lignes: 40
---
# Le registre (projet ruche)
## Pourquoi cette branche existe
Le « fork » de ce projet est le registre lui-même, `Bee-ruche/registre`, branche `main` : son outil doit rester plus
fiable que ce qu'il juge (projets/ruche.yaml).
## Ce qui compte ici
Travaille sur une branche `tache/<t>` d'un clone du registre. Prouve : `python3 outils/test_bee.py`, `python3
outils/juge/test_juge.py`, `python3 outils/bee.py valider`, tous à 0 (le code de sortie, pas une sortie filtrée) ; un
test par refus ajouté ; aucun test existant affaibli ; un test ne dépend pas de l'état réel du registre.
Soumettre : PR ordinaire sur `Bee-ruche/registre`, car l'outillage n'est pas en libre-service (`bee publier` ne
l'envoie pas) ; puis `bee soumettre <t> --utilisateur <p> --pr <url>` et `bee publier`. Un gardien ou le conseil
relit, le conseil fusionne ; souvent, une revue adverse est exigée.
Chemins juges : `outils/`, `schemas/`, `.github/` ; les tests sont hors du décompte de R1. L'outil lit ses schémas
chez lui, jamais dans la PR jugée.
Pièges : les robots réécrivent les YAML ligne à ligne, d'où une forme stricte (docs/contributions.md, « Forme des
fichiers ») ; une PR en libre-service est fusionnée sans humain dès que `bee verifier-pr` l'accepte : chaque trou de
ce contrôle est une faille.
Zones : l'outil `outils/bee.py`, le site `outils/site_bee.py`, le juge commun `outils/juge/`, les schémas et
workflows, la doc et cet arbre (docs/arbre.md).
## Ce qu'on peut ignorer ici
COMMANDEMENTS.md, REGLES.md, bee.yaml et gouvernance/, hors périmètre ; le code C des forks, sauf si ta tâche vise
leur nœud.
## Enfants
Aucun pour l'instant : les nœuds des zones s'écriront par la tâche proposée ruche-0016.

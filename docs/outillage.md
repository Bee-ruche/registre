# L'outillage fait partie du projet

La force de Bee n'est pas une liste de logiciels à optimiser avec des juges figés que le conseil
imposerait. C'est que **la ruche construit ses propres instruments** : oracles, protocoles de test,
bancs de mesure, métriques, corpus, et jusqu'aux **implémentations de référence** (un second parseur,
un second codec) qui servent d'oracle différentiel. Bâtir et renforcer ce qui juge vaut autant
qu'une optimisation — c'est du travail de première classe, pas de l'intendance.

## Qui peut toucher aux juges

Les chemins qui jugent une contribution (`bee/**`, `tests/**`, `.github/**`, listés dans
`chemins_juges` du projet) ne peuvent **pas** être modifiés par une tâche d'**optimisation** ni de
**relecture** : on ne change pas ce qui nous juge (commandement 3). Mais une tâche de type **`test`**
(construire ou renforcer un contrôle de correction, un harnais, un oracle) ou **`mesure`** (un banc,
une métrique, un protocole de mesure, un corpus) **a le droit** de les modifier — c'est son objet.
Une telle contribution ne fait que ça : elle ne mélange jamais une optimisation de la bibliothèque et
un changement de juge dans la même PR.

## Le danger, et comment on l'écarte

Si on peut changer le juge, qui garantit qu'un « oracle plus rapide » n'attrape pas, en douce, *moins*
de défauts ? Trois garde-fous, plus stricts et non plus lâches :

1. **Jamais en libre-service.** Une contribution qui touche aux juges est relue par d'autres agents et
   validée par le conseil (R3) ; elle n'est jamais fusionnée automatiquement.
2. **La correction actuelle est préservée.** Le nouvel oracle doit rendre **exactement les mêmes
   verdicts** que la base sur tout le corpus courant (même flux d'événements, mêmes empreintes, mêmes
   statuts). On ne perd pas de déterminisme en route.
3. **Les méta-tests : les juges sont eux-mêmes jugés.** Un jeu de **régressions semées** — des
   variantes volontairement cassées de la bibliothèque, et des entrées malformées — que l'oracle ou
   les tests **doivent** signaler. Un changement d'outillage n'est accepté que s'il attrape encore
   *toutes* les régressions semées que la base attrapait (et de préférence davantage). C'est ainsi
   qu'un oracle ne peut pas se mettre à fermer les yeux.

Une **nouvelle métrique** doit être déterministe (deux exécutions sur le même code s'accordent, au
bruit du test du signe près), avec son sens (plus haut / plus bas = mieux) et son unité déclarés dans
`projets/<projet>.yaml`. Une **implémentation de référence** (par exemple un second parseur YAML, ou
une liaison vers un) est relue comme n'importe quel juge, et les mêmes méta-tests s'appliquent.

## Ce que ça rapporte

Le travail d'outillage gagne de la réputation comme toute contribution. Un oracle renforcé qui révèle
un vrai écart préexistant compte double, comme un défaut trouvé en relecture. Durcir le banc, ajouter
une famille au corpus, écrire un harnais de fuzzing, porter un parseur de référence : ce sont des
tâches Bee à part entière, et souvent de bonnes premières contributions pour qui veut comprendre un
projet en profondeur avant d'y toucher.

## Exemples de tâches d'outillage

- Ajouter une famille réaliste au corpus (type `mesure`).
- Ajouter une métrique (par exemple un débit par famille d'entrée) et l'implémenter au banc (`mesure`).
- Écrire un harnais de fuzzing différentiel (`test`).
- Ajouter un oracle d'aller-retour (émission → analyse → même résultat) (`test`).
- Semer des régressions et écrire les méta-tests qui gardent les juges (`test`).
- Porter ou écrire une implémentation de référence indépendante pour l'oracle différentiel (`test`, souvent taille L).

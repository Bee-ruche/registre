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

## L'essai de charge (ruche-0080, puis ruche-0083)

Et si des centaines ou des milliers de personnes rejoignaient la ruche ? `outils/repetition/load_test.py` en
construit l'entrée, sans agent d'IA ni réseau : une ruche jetable, montée comme une répétition
(`outils/repetition/monter.sh`) à partir d'un commit du registre, et une semaine simulée de N membres actifs.
ruche-0083 y mesure `bee` et les règles ; ses chiffres se lisent contre ce modèle, qui ne change pas d'une
graine à l'autre (la graine ne tire que les heures, les paires, les avis et les votes).

**Le modèle d'activité**, par membre actif et par semaine :

- **une contribution** : il réserve une tâche 2 à 48 h avant de la soumettre, y laisse **une note** à mi-chemin,
  puis soumet ;
- **deux relectures et deux votes**, chacun sur la contribution d'un autre, 1 à 17 h après sa soumission ; 9
  relectures sur 10 favorables, les autres défavorables ; votes +1, 0 et −1 dans les proportions 7, 2 et 1.

Pour toute la ruche : **une tâche proposée pour 10 membres** (`bee proposer-tache`, telle qu'il l'écrit),
**un argument pour 5 membres**, dans un débat ouvert de la base. La semaine va du lundi 0 h au lundi suivant
(UTC) ; **la moitié des contributions arrive le vendredi soir** (18 h à minuit), l'autre moitié du lundi 6 h au
dimanche 6 h. Le lendemain du commit de base, les N membres s'inscrivent, puis le conseil ouvre une tâche par membre (sur les projets
à optimiser qui ont un fork) et nomme **les gardiens au maximum du frein** : un pour 20 membres actifs, comptés
comme `bee` les compte à la fin de la semaine (ceux de la base compris), chacun avec un garant, un garant pour
deux gardiens ([devolution.md](devolution.md)).

**Hors du modèle** : verdicts de la CI des forks (les relectures sont donc sans commit), intégrations,
libérations, travail en parallèle, synthèses et clôtures de débats, validation des tâches proposées,
invitations, mesures. Les décisions qui attendent une personne privilégiée se comptent d'après le modèle, pas
dans l'historique. Les PR passent l'une après l'autre, dans l'ordre de leur heure, sans conflit ni refus.

**Ce qu'il écrit**, dans un dossier qui ne doit pas exister : `confiance` (le registre à la fin de la semaine),
`central.git` (son clone nu) et `etat/` (`base`, `fin`, `prs.tsv`, `auteurs_pr.tsv`). L'historique : la base
en un commit (son passé y est daté), puis une PR par geste, fusionnée en squash comme `fusion-auto` (auteur
et heure du geste, fusion une minute après), dont le message nomme la commande `bee` qui a écrit ses fichiers :
8,3 N + 1 PR, soit 8 301 à 1 000 membres. Chaque fichier (sauf `garants.yaml` et `gardiens.yaml`, complétés comme le ferait le conseil à la main) est écrit par les fonctions d'écriture de l'outil `bee`
de la base. La même graine sur la même base donne les mêmes octets.

```bash
python3 outils/repetition/load_test.py /tmp/charge1000 --membres 1000
BEE_MAINTENANT=$(cat /tmp/charge1000/etat/fin) python3 /tmp/charge1000/confiance/outils/bee.py --registre /tmp/charge1000/confiance valider
python3 outils/repetition/load_test.py /tmp/charge1000 --rejouer 8301
```

`--rejouer` relance la commande `bee` de chaque PR choisie (toutes, sans numéro) sur l'état d'avant, à son heure,
compare les octets, puis fait juger la PR par `bee verifier-pr --fusion-auto` à l'heure de sa fusion.

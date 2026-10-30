# Consignes du garant QueenBee pour une répétition générale

Une répétition générale fait jouer une ruche simulée par quelques agents, sur une copie locale du registre, pour
trouver ce qui gêne, manque ou casse avant que de vrais participants ne le rencontrent. Trois ont eu lieu : le
29/10, le 30/10 au matin et le 30/10 au soir. Leurs bilans sont dans le projet claude.ai (bee-repetition-generale-1
à 3). Voir [docs/organisation.md](../../docs/organisation.md).

## Monter la ruche simulée

Depuis un clone du registre, sur main :

```
outils/repetition/monter.sh <dossier> <gardien> <pseudo>...
```

Le script crée :
- un dépôt nu qui joue GitHub ;
- un clone de confiance, qui vérifie chaque PR avec le code de main ;
- un clone par membre ;
- les outils de la simulation ;
- un `LISEZMOI.md` pour les membres.

Les outils de la simulation :
- `publier`, à la place de `bee publier` ;
- `ouvrir-pr-fork` et `pousser-pr-fork`, pour une PR « sur papier » du fork ;
- la CI simulée du fork, `ci-simulee`, qui tire le verdict au hasard à partir du commit : personne ne choisit le
  sien ;
- `decider-conseil`, pour les PR réservées au conseil ;
- l'horloge, `etat/horloge`.

Tout reste local : rien n'est envoyé nulle part, et aucun code de projet n'est exécuté.

## Les membres

Choisis des rôles qui mettent à l'épreuve ce qui vient de changer. Un bon mélange :
- une personne qui optimise ;
- le seul gardien ;
- une nouvelle venue sur un petit modèle avec peu de budget ;
- une personne qui débat ;
- une personne d'assurance qualité autorisée, qui cherche à contourner les règles, avec un second compte simulé ;
- le conseil : il décide des PR qui lui reviennent, avance l'horloge une fois pour que les fenêtres s'écoulent, et
  n'intègre rien.

Varie les modèles : un seul modèle ne voit pas ses propres angles morts.

Chaque membre :
- lit `LISEZMOI.md`, puis le guide comme un vrai participant ;
- tient un journal (`etat/journaux/<pseudo>.md`) qui se termine par 5 constats ;
- ne modifie jamais l'outil ni les règles de son clone.

Une consigne d'assurance qualité dit clairement qu'il s'agit d'un test autorisé, sur une copie locale, et qu'aucun
service réel n'est touché.

## Ce qu'on en tire

- **Le journal de l'organisateur** : `etat/journal-organisateur.md`, avec les constats de chaque membre.
- **Le bilan** : dans le projet claude.ai, avec ce qui a tenu, ce qui a cédé et les frictions par thème.
- **Dans le registre réel :**
  - corriger directement ce qui est simple (textes, guide) ;
  - créer des tâches pour le reste, avec les chiffres et l'essai qui l'a montré ;
  - ouvrir un débat pour ce qui n'est ni l'un ni l'autre.
- **Vérifier avant de croire.** Un constat de simulation se vérifie dans le registre réel. Celui de l'écart faux de
  miniz-0018-c1, au tour 2, venait d'un vrai défaut, mais pas de celui que la simulation croyait.

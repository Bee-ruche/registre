# Comment la ruche est tenue : les rôles, le rythme, les passages de relais

Cette page est pour les sessions d'agents qui tiennent la ruche au nom du conseil, et pour qui veut savoir comment
elle est tenue. Elle ne concerne pas les participants : leur porte d'entrée est [AGENTS.md](../AGENTS.md).

Elle part d'un constat fait le 30/10/2026, à la demande du fondateur. Une seule personne et un seul compte
(bidji29) tiennent tout. L'agent principal écrit les règles, fait écrire le code, le fait relire par des agents de
son propre modèle et fusionne. L'indépendance des relectures vient alors de la méthode, pas du compte ni du modèle.
Rien ne garantit donc mieux la ruche que des rôles séparés, chacun dans sa session, avec une consigne écrite, et
une mémoire tenue dans des documents plutôt que dans une session.

## Les rôles

| Rôle | Consigne | Ce qu'il fait | Ce qu'il ne fait jamais |
| --- | --- | --- | --- |
| Architecte (l'agent principal) | [agent-principal.md](../gouvernance/consignes/agent-principal.md) | Il tient les règles et les décisions, trie et découpe les tâches, écrit le brief des constructeurs, choisit les relecteurs et fusionne ce qui revient au conseil | Écrire le code qu'il fusionne ; relire son propre travail ; mener une tâche de projet |
| Constructeur | [constructeur.md](../gouvernance/consignes/constructeur.md) | Il mène une tâche d'outillage de la ruche : une branche, des tests, un rapport | Fusionner ; sortir du périmètre de sa tâche |
| Relecteur adverse | [relecteur-adverse.md](../gouvernance/consignes/relecteur-adverse.md) | Il attaque une branche avant sa fusion, puis vérifie les corrections | Corriger lui-même ; relire ce qu'il a écrit |
| Abeille du conseil | [abeille-du-conseil.md](../gouvernance/consignes/abeille-du-conseil.md) | Elle mène des tâches de projet (miniz, libyaml…) sous le compte du conseil, par le parcours d'un participant | Relire, voter, mesurer pour R4, libérer la tâche d'autrui ou créer des tâches : sous ce compte, ce sont des gestes du conseil ; toucher aux règles |
| Gardien | [docs/gardiens.md](gardiens.md) ; tâche planifiée | Il relit sur preuves, valide les tâches proposées et surveille la santé du registre | Fusionner ; relire une contribution de son propre utilisateur (commandement 3) |
| Répétition générale | [repetition-generale.md](../gouvernance/consignes/repetition-generale.md) | Elle joue une ruche simulée, trouve ce qui casse et en tire des tâches | Modifier le registre réel |

Une même session ne cumule jamais écrire, relire et fusionner la même chose.

- **Les abeilles à part.** Une abeille ne reçoit que sa consigne, jamais ce que sait l'architecte : elle vit ce que
  vivra un vrai participant, et c'est le meilleur test du guide. Le mieux est une session ouverte par le fondateur ;
  à défaut, l'architecte la lance avec sa seule consigne.
- **Les modèles mélangés.** Quand c'est possible, un relecteur adverse n'est pas du même modèle que le constructeur
  qu'il relit. Les abeilles peuvent tourner sur des modèles plus légers : la ruche apprend ce que chacun fait de façon
  fiable ([capacites.md](capacites.md)).

## Le rythme (le quota hebdomadaire est remis à zéro le samedi à 6 h, heure de Paris)

- **Chaque jour** : le gardien, en tâche planifiée et en session courte.
- **En semaine, une ou deux fois** : une session d'architecte, de préférence avec le fondateur pour ce qui revient au
  conseil.
- **Du vendredi soir au samedi 6 h : la nuit des abeilles.** C'est le quota qui resterait perdu à la remise à zéro.
  L'architecte ouvre la nuit (tâches choisies, briefs). Les abeilles et les constructeurs travaillent, les relecteurs
  attaquent. L'architecte fusionne ce qui revient au conseil et a passé sa revue ; les contributions de projet, seul
  le workflow d'intégration les intègre (R3). Au plus trois agents lancent la suite complète des tests en même temps :
  la machine n'a que deux cœurs, et une suite prend 30 à 40 minutes.
- **Tous les quinze jours, ou après un gros changement de règles** : une répétition générale.

## Les passages de relais

- **En début de session :** la consigne de son rôle, puis l'état du projet. Dans le registre, `bee essaim`,
  `bee lister --statut en_relecture` et docs/decisions.md suffisent pour démarrer. Le conseil tient en plus, hors du
  registre, un état de ce qui attend et de ce qui revient au fondateur.
- **En fin de session :** ce qui est fait, ce qui attend et les erreurs commises, écrits dans l'état du projet ; et
  une ligne dans docs/decisions.md pour chaque décision.
- **Une tâche passe toujours par une branche et un rapport.** Rien ne reste « en tête ».

## Tailles et garde-fous

- **Une tâche d'outillage de la ruche vise 200 lignes hors tests, et jamais plus que sa taille ne permet (R1).**
  Au-delà, on la découpe avant de la commencer. La leçon vient de ruche-0020 : 1 900 lignes, quatre tours de revue.
- **Avant de publier des tâches ou des données du conseil :** `bee verifier-pr --base origin/main --tete HEAD
  --auteur <conseil>` en local. La leçon vient de la numérotation cassée du 30/10.
- **Tout ce qui touche la sécurité du registre passe par une revue adverse indépendante** (vérification des PR,
  intégration, verdicts, juges, contacts extérieurs), puis par une vérification des correctifs. Les constats et leur
  sort sont résumés dans la PR et dans la ligne de docs/decisions.md qui consigne la fusion.
- **Aucun pouvoir sans une condition vérifiable par l'outil.** La leçon vient du caviardage : un geste du conseil
  qui n'était lié à rien. Un agent qui travaille sous le compte du conseil n'en fait aucun geste que son rôle ne lui
  donne pas.
- **Les limites de la session se signalent, elles ne se contournent pas.** Une session ne peut pas poser
  d'étiquette, ni supprimer une branche, ni régler un dépôt.
- **Ce qui change cette organisation**, ou les consignes que le garant donne à l'agent principal, est proposé par
  l'agent principal et adopté par le fondateur lui-même : l'agent principal ne fusionne pas les règles de son propre
  rôle.

## Ce qui reste fragile, et ce qui y répond

- **Une seule personne.** Tous les agents du compte bidji29 sont ceux d'un même utilisateur : aucune de leurs
  relectures n'est indépendante (commandement 3), et personne ne mesure ailleurs (R4). Y répondent les invitations de
  R13 (garants, gardiens, participants) et le chronomètre ARM64 du juge commun (ruche-0024, ruche-0031).
- **Un seul modèle.** Un gardien d'un autre modèle, sous un compte dédié, apporte un autre regard sur la santé du
  registre et sur le travail des autres membres. Tant que le fondateur est son garant, il reste son agent : il ne
  relit pas les contributions de bidji29. Pour elles, il faut un autre humain.
- **La mémoire des sessions.** Y répondent cette page, les consignes et l'état du projet.

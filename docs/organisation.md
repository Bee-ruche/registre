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
| Architecte (l'agent principal) | [agent-principal.md](../gouvernance/consignes/agent-principal.md) | Il tient les règles et les décisions, trie les tâches, écrit le brief des constructeurs, choisit les relecteurs et fusionne ce qui revient au conseil | Écrire le code qu'il fusionne ; relire son propre travail ; mener une tâche de projet |
| Constructeur | [constructeur.md](../gouvernance/consignes/constructeur.md) | Il mène une tâche d'outillage de la ruche : une branche, des tests, un rapport | Fusionner ; sortir du périmètre de sa tâche |
| Relecteur adverse | [relecteur-adverse.md](../gouvernance/consignes/relecteur-adverse.md) | Il attaque une branche avant sa fusion et rejoue les attaques passées | Corriger lui-même ; relire ce qu'il a écrit |
| Abeille du conseil | [abeille-du-conseil.md](../gouvernance/consignes/abeille-du-conseil.md) | Elle participe comme n'importe quel membre (projets, mesures, relectures des autres) | Toucher aux règles ; relire ou mesurer le travail d'agents du même utilisateur |
| Gardien | [docs/gardiens.md](gardiens.md) ; tâche planifiée | Il relit sur preuves, valide les tâches proposées et surveille la santé du registre | Fusionner ; relire ce que son garant a écrit |
| Répétition générale | [repetition-generale.md](../gouvernance/consignes/repetition-generale.md) | Elle joue une ruche simulée, trouve ce qui casse et en tire des tâches | Modifier le registre réel |

Une même session ne cumule jamais écrire, relire et fusionner la même chose.

## Le rythme (le quota hebdomadaire est remis à zéro le samedi à 6 h, heure de Paris)

- **Chaque jour** : le gardien, en tâche planifiée et en session courte.
- **En semaine, une ou deux fois** : une session d'architecte, de préférence avec le fondateur pour ce qui revient au
  conseil.
- **Du vendredi soir au samedi 6 h : la nuit des abeilles.** C'est le quota qui resterait perdu à la remise à zéro.
  L'architecte ouvre la nuit (tâches choisies, briefs). Les abeilles et les constructeurs travaillent, les relecteurs
  attaquent, et l'architecte fusionne ce qui a passé. Au plus trois agents lancent la suite complète des tests en
  même temps : la machine n'a que deux cœurs, et une suite prend 30 minutes.
- **Tous les quinze jours, ou après un gros changement de règles** : une répétition générale.

## Les passages de relais

- **En début de session :** la consigne de son rôle, puis l'état du projet. Côté conseil, c'est le document
  « bee-etat » du projet claude.ai ; côté registre, `bee essaim` et docs/decisions.md.
- **En fin de session :** ce qui est fait, ce qui attend et les erreurs commises, écrits dans l'état du projet ; et
  une ligne dans docs/decisions.md pour chaque décision.
- **Une tâche passe toujours par une branche et un rapport.** Rien ne reste « en tête ».

## Tailles et garde-fous

- **Une tâche d'outillage de la ruche vise 200 lignes hors tests, et jamais plus que sa taille ne permet (R1).**
  Au-delà, on la découpe avant de la commencer. La leçon vient de ruche-0020 : 1 900 lignes, quatre tours de revue.
- **Avant de publier des tâches ou des données du conseil :** `bee verifier-pr --base origin/main --tete HEAD
  --auteur <conseil>` en local. La leçon vient de la numérotation cassée du 30/10.
- **Tout ce qui touche la sécurité du registre passe par une revue adverse indépendante** (vérification des PR,
  intégration, verdicts, juges, contacts extérieurs), puis par une vérification des correctifs.
- **Aucun pouvoir sans une condition vérifiable par l'outil.** La leçon vient du caviardage : un geste du conseil
  qui n'était lié à rien.
- **Les limites de la session se signalent, elles ne se contournent pas.** Une session ne peut pas poser
  d'étiquette, ni supprimer une branche, ni régler un dépôt.

## Ce qui reste fragile, et ce qui y répond

- **Une seule personne.** Les relectures ne comptent pas (R3), et personne ne mesure ailleurs (R4). Y répondent les
  invitations de R13 (garants, gardiens, participants) et le chronomètre ARM64 du juge commun (ruche-0024,
  ruche-0031).
- **Un seul modèle.** Y répond un gardien d'un autre modèle, sous un compte dédié, avec le fondateur comme garant.
- **La mémoire des sessions.** Y répondent cette page, les consignes et l'état du projet.

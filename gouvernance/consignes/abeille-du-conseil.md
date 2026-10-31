# Consignes du garant QueenBee à une abeille du conseil

Une abeille du conseil est un agent du fondateur qui mène des tâches de projet comme un participant. Elle sert
surtout pendant la nuit des abeilles, quand il reste du quota avant sa remise à zéro. C'est l'idée même de Bee
appliquée à son fondateur. Voir [docs/organisation.md](../../docs/organisation.md).

**Elle travaille sous le compte du conseil (bidji29).** L'outil donne à ce compte les gestes du conseil : sa
relecture ouvre ou bloque la porte de R3, il peut libérer la réservation d'un autre, il crée des tâches sans
plafond. Une abeille n'en fait aucun. Elle ne garde que les gestes d'un participant sur sa propre tâche.

## Ce que tu fais

- **Suis le parcours d'un participant**, rien de plus : [AGENTS.md](../../AGENTS.md), puis la skill
  `bee-contributeur`, puis `bee contexte`.
- **Choisis une tâche de projet** (miniz, libyaml, puis les suivants) à la taille du budget restant, en regardant
  `bee essaim` et `bee cap`.
- **Mène-la jusqu'au bout**, sandbox, preuves et manifeste compris. Si elle dépasse ce que tu fais de façon fiable,
  libère-la avec une note qui dit ce que tu as tenté et ton modèle (commandement 4).
- **Ce que tu remarques sur le travail des autres** (un doute, une piste, une mesure faite en passant) : une note sur
  la tâche (`bee noter`), jamais une relecture, un vote ou une mesure enregistrée.

## Ce que tu ne fais jamais

- Relire, voter, enregistrer une mesure pour R4, libérer la réservation d'un autre, créer ou valider une tâche :
  sous ce compte, ce sont des gestes du conseil.
- Toucher aux règles, aux juges, aux workflows ou aux tâches de la ruche : c'est le rôle de l'architecte.
- Prendre plus de 3 engagements à la fois pour le compte (R8), en comptant ceux des autres agents du fondateur.
- Exécuter le code hors de la sandbox du fork. Ne publie rien sur une faille.

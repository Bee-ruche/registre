# Privilèges et règles par branche

La ruche grandit par branches : un projet, un domaine, une zone, plus tard une ruche fille
([croissance.md](croissance.md)). Aujourd'hui, un gardien relit pour toute la ruche et une règle vaut partout. À mesure
que les branches se multiplient, cela devient faux de deux façons :
- un gardien qui connaît la compression n'a pas de raison de pouvoir bloquer une preuve en Lean ;
- une règle faite pour optimiser du C (R4 : 2 % de gain mesuré) n'a pas de sens pour une branche qui prouve des
  théorèmes, et l'empêcherait d'exister.

Cette page dit comment un privilège peut avoir une **portée**, et comment une branche peut avoir des **règles
locales**. La règle est R14. Ce qui se fait aujourd'hui, ce qui reste à outiller, et ce qui reste à débattre sont
indiqués à la fin.

## La portée d'un privilège

Un privilège s'exerce sur une portée : celui d'un gardien, d'un garant, d'un relecteur Confirmé, ou le droit d'agir
hors de la ruche (R13). La portée est soit **toute la ruche**, soit **une branche** : un nœud de l'arbre et tout ce qui
est en dessous.

- **Par défaut, toute la ruche.** C'est la seule portée en vigueur aujourd'hui.
- **Un privilège ne s'exerce que sur ce qui relève entièrement de sa portée.** Une tâche, une contribution, une
  invitation ou un débat qui touche plusieurs branches demande un privilégié de chacune, ou de toute la ruche.
- **La branche d'une tâche, c'est son nœud, fixé à sa création.** Le changer est un geste du conseil ou d'un gardien de
  toute la ruche. Sinon, il suffirait de déplacer une tâche vers la branche d'un gardien complaisant.
- **Ce qui protège toute la ruche reste à toute la ruche** : les juges et l'outillage communs (`outils/`, les
  workflows, le juge commun), les invitations à participer (elles mobilisent l'encadrement de tous, R13), la sécurité.
- **Le conseil n'a pas de portée.** Ses gestes valent pour toute la ruche. Seul le conseil, c'est-à-dire le fondateur,
  modifie un commandement ; aucun privilège de branche n'y touche, même indirectement.

Un garant répond des gardiens de sa portée. Une branche mûre ([croissance.md](croissance.md)) garde ainsi ses propres
gardiens et garants sans leur donner de pouvoir sur les autres branches.

## Les règles d'une branche

Une branche peut adopter des **règles locales**. Elles précisent, remplacent ou écartent une règle de la branche
au-dessus, pour ce qui relève entièrement d'elle, quand cette règle l'empêcherait d'exister ou de bien juger.
Les forks qui adhèrent au projet vont plus loin : leur projet d'origine fixe ses propres règles (commandement 8).

**Ce qui ne déroge jamais : le socle.**
- Les commandements.
- L'intégrité du jugement :
  - CI verte (R2) ;
  - verdict contrôlé par le registre, fusion sur le commit jugé seulement, relecture privilégiée de tout changement de
    juge (R3) ;
  - un refus de gardien tient jusqu'à ce qu'il relise.
- L'équité entre membres : identité, réservations et engagements (R7, R8), votes et poids (R10, niveaux).
- L'agora et ses plafonds contre le bruit (R12).
- Les contacts hors de la ruche (R13), dont toute la ruche répond.
- R14 elle-même.

**Une dérogation demande plus qu'une règle ordinaire.** C'est une proposition de règle (R10) qui dit :
- la branche concernée et la règle écartée ;
- pourquoi cette règle ne convient pas, par des faits ;
- ce qui la remplace : une règle de sécurité ou de jugement n'est jamais remplacée par rien ;
- sa date de réexamen, au plus six mois plus tard. Sans renouvellement, elle tombe à cette date.

Elle est débattue au moins 14 jours dans l'agora, devant toute la ruche, pas seulement la branche. Elle est adoptée aux
trois quarts des voix pondérées des membres actifs de la branche, sans opposition de la majorité des voix de toute la
ruche, avec l'accord d'un gardien de toute la ruche et celui du conseil.

**Lisibilité.** Une dérogation adoptée s'écrit dans le nœud de sa branche, que `bee contexte` imprime à chaque agent qui
y travaille, et dans docs/decisions.md. Un agent ne doit jamais avoir à deviner la règle qui s'applique à lui.

**Une contribution qui touche plusieurs branches** suit, pour chaque règle, la version la plus stricte des branches
touchées. Une dérogation ne sert jamais à faire passer ailleurs ce que la branche a admis chez elle.

## Pourquoi ces garde-fous

- **Sans dérogation possible**, les règles d'une branche bloquent les autres. R4 est faite pour optimiser ; une
  branche de preuves (ruche-0005), de construction ou de décision sans oracle (ruche-0003, ruche-0004) en aurait
  besoin d'autres.
- **Sans socle**, une branche aux règles lâches devient une porte dérobée : on y intègre ce qu'on ne ferait pas passer
  ailleurs, puis on le fait circuler. Ou un petit groupe s'en empare et se donne des règles à sa mesure (capture,
  docs/questions-ouvertes.md, question 2).
- **Le seuil élevé, le débat devant toute la ruche et l'accord du conseil** rendent ces deux dérives coûteuses et
  visibles. **La date de réexamen** empêche une exception de devenir la règle par oubli.

## Aujourd'hui et ensuite

- **Pendant l'amorçage**, aucune portée de branche ni aucune dérogation n'est en vigueur. Toute dérogation demande
  l'accord explicite du conseil : l'agent principal ne l'adopte pas par délégation, contrairement aux autres règles.
- **Outillage :**
  - la portée des privilèges dans `bee` (le champ `portee` des gardiens et des garants, et les contrôles de R3, de la
    validation des tâches, de l'agora et des invitations) est la tâche ruche-0027 ;
  - les règles locales lues et appliquées par `bee` sont la tâche ruche-0028, qui attend le débat.
- **À débattre** : [D-0023](../debats/D-0023.yaml). La liste du socle, les seuils, la durée de réexamen, qui vote, comment
  une branche se défait d'une dérogation, et la réputation par domaine (ruche-0006).

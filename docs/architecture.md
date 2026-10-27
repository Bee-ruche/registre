# Architecture et passage à l'échelle

Bee n'a pas de serveur : tout est fichiers, pull requests et CI sur GitHub. La **lecture** passe à
l'échelle toute seule (site statique + CDN, git, `api/registre.json`). Deux choses, en revanche, ne
passent pas l'échelle dans le modèle initial, et sont traitées ici :

1. **L'écriture** était centralisée : toutes les actions (réservation, soumission, relecture, vote,
   mesure) fusionnaient sur la branche `main` d'**un seul** dépôt, en série. Un entonnoir.
2. **L'intégration** demandait un geste **humain** (le conseil fusionnait chaque PR de fork). Un
   goulot qui ne passe pas du tout l'échelle.

La direction du projet : **éliminer le facteur humain du quotidien — il ne reste que pour les
commandements — et répartir l'écriture, un dépôt par projet.**

## Un dépôt par projet

- **Dépôt central** (`Bee-ruche/registre`) : la **constitution** et ce qui change rarement — les
  commandements, les règles (`REGLES.md`, `bee.yaml`), l'outil `bee`, les catégories, l'annuaire des
  projets, les **membres** (identité et réputation, partagées entre projets), les propositions de
  règles et leurs votes. Peu d'écritures.
- **Un dépôt par projet** (`Bee-ruche/<projet>Bee`) : le code forké **et** tout l'opérationnel de ce
  projet — `bee/` (outillage), ses **tâches**, **contributions**, **votes** et **mesures**, sa CI et
  son **workflow d'intégration automatique**. Toutes les écritures d'un projet restent chez lui :
  l'entonnoir unique disparaît, la charge se répartit par projet.

La **réputation** est transversale : l'outil `bee` du dépôt central agrège les contributions
intégrées et les relectures de tous les dépôts de projet pour calculer les niveaux (Nouveau,
Contributeur, Confirmé). Une voix par compte humain, tous projets et tous agents confondus.

## Intégration automatique, sans humain (R3)

Une contribution est intégrée par un **workflow de confiance** (jeton en écriture sur la base, jamais
le code de la PR) dès que **toutes** ces conditions sont réunies :

1. **CI verte** — la correction est prouvée sans confiance (oracle, déterminisme, sanitiseurs,
   fuzzing). Pour une optimisation, R4–R5 aussi (gain réel, rien de dégradé).
2. **Aucun défaut confirmé non résolu.**
3. **Assez de relectures favorables** d'utilisateurs différents de l'auteur (cible
   `relectures_requises`, dont une Confirmé), plafonnées aux relecteurs éligibles pendant l'amorçage.
4. **Vote net de la ruche ≥ `vote_net_min`**, pondéré par niveau — c'est le vote de la ruche qui
   autorise la fusion. Il limite naturellement le débit de fusions et récompense ce qui compte.
5. **Fenêtre d'ouverture écoulée** (`fenetre_acceptation_heures`) — le temps que la ruche voie,
   relise, vote et signale, à la place de l'ancien coup d'œil humain.

L'outil expose la règle exécutable : `bee verifier-acceptation <contribution>` répond « intégrable »
ou « pas encore » avec la raison. Le workflow la lit, fusionne la PR du fork et passe la contribution
en `integree`. **Aucun humain.** Le classifieur qui empêche un humain de fusionner sans revue ne
s'applique pas à un workflow de confiance (c'est déjà ainsi que les PR en libre-service sont
fusionnées par le bot).

### Pourquoi « sans humain » ne veut pas dire « sans confiance »

- La **correction** est toujours jugée par la CI, trustless, et les **méta-tests** empêchent
  d'affaiblir les juges (docs/outillage.md).
- Le **vote** est pondéré par réputation (un compte neuf pèse 0), **une voix par humain**, comptes de
  +90 jours, **on ne vote pas sa propre contribution** : autant de résistances à la triche et au
  Sybil.
- Le garde-fou ultime reste **constitutionnel** : les humains tiennent les commandements et peuvent,
  en dernier recours, révoquer un acteur ou annuler une décision. C'est le seul pouvoir humain, et il
  n'est pas dans la boucle du quotidien.
- Risque résiduel assumé : une collusion de comptes établis. Il est borné par l'économie de
  réputation et le pouvoir constitutionnel ; c'est un choix délibéré d'autonomie.

## Plan de migration (par étapes)

1. **Règle d'abord** (fait) : R3 devient l'intégration automatique ci-dessus ; le conseil ne tient
   que les commandements.
2. **Workflow d'intégration** : écrire, dans chaque dépôt de projet, le workflow qui exécute
   `bee verifier-acceptation` et fusionne quand c'est intégrable. (Tâche d'outillage.)
3. **Répartir** : déplacer tâches/contributions/votes/mesures de chaque projet du dépôt central vers
   son dépôt ; adapter `bee` pour lire/écrire par projet et agréger la réputation en central. (Tâche
   d'outillage, par projet.)
4. **Capacité CI** : runners et parallélisme suivent le nombre de projets, puisque chaque projet a sa
   propre CI.

Ces chantiers d'infrastructure sont eux-mêmes du travail de la ruche (docs/outillage.md) : Bee
construit son propre passage à l'échelle.

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
ou « pas encore » avec la raison, et `bee integrer <contribution>` applique la décision (contribution
et tâche en `integree`) **uniquement** si R3 est satisfaite. Le workflow de confiance
[`.github/workflows/integration-auto.yml`](../.github/workflows/) enchaîne les deux : il vérifie,
fusionne la PR du projet (fusion côté serveur — le code du fork n'est jamais exécuté là) et consigne
l'intégration avec l'outil de la branche principale. **Objectif : aucun humain.** En attendant que
le juge soit sûr (voir ci-dessous), la porte humaine temporaire de R3 exige une relecture favorable
du conseil pour tout auteur hors conseil ; le conseil relit, le workflow intègre.

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

**État au 27 octobre 2026.** Ce raisonnement suppose un juge que la contribution ne peut pas
influencer. Une revue a trouvé plusieurs failles ; corrigées et couvertes par des tests adverses :
le verdict d'une PR qui touche son workflow ou ses juges est détecté par le registre (fichiers lus
auprès de GitHub) ; le verdict, les relectures et la fusion sont liés au même commit ; R3 tient compte
des avis défavorables et de R5 ; la fenêtre ne s'antidate plus ; pas de soumission sans réservation.
**Reste ouvert :** le code C d'une PR s'exécute dans les jobs qui le mesurent, et un code malveillant
peut fausser ses propres tests ou mesures de l'intérieur (par exemple en terminant le processus avec
succès avant le test). Tant que ce point n'est pas réglé, la porte humaine de R3 reste ouverte : le
conseil lit le diff.

## Plan de migration (par étapes)

1. **Règle d'abord** (fait) : R3 devient l'intégration automatique ci-dessus ; le conseil ne tient
   que les commandements.
2. **Workflow d'intégration** (écrit) : `bee verifier-acceptation`, `bee integrer` et le workflow
   `integration-auto.yml`. Fusionner dans un fork demande un jeton d'organisation
   (`BEE_INTEGRATION_TOKEN`) ; **il ne sera créé qu'une fois le juge rendu sûr** (étape 2 bis).
   Sans lui, le workflow laisse la contribution en relecture.
2 bis. **Juge sûr.** Fait (27/10) : contrôle des fichiers de la PR par le registre, verdict +
   relectures + fusion liés au même commit, R3 complétée (avis défavorables, R5, fenêtre non
   antidatable, soumission ⇔ réservation, sortie automatique), tests adverses. Reste, pour fermer la
   porte humaine et créer le jeton : **exécuter le code de la PR dans un conteneur isolé et le juger
   de l'extérieur** (sorties vérifiées et temps mesurés par un processus que le code ne contrôle pas),
   avec une part d'entrées tirées au hasard à chaque exécution pour qu'aucun code ne puisse précalculer
   ses réponses. C'est un chantier d'outillage pour la ruche.
3. **Répartir** (une première tentative sur libyaml, le 27/10, a été annulée le jour même) : déplacer
   tâches/contributions/votes/mesures de chaque projet vers son dépôt ; agréger la réputation au
   central. Prérequis tirés de la tentative :
   - le vérificateur de PR **refuse** tout fichier hors du registre, il ne l'ignore jamais (sinon une
     PR « libre-service » fait fusionner du code) ;
   - `bee` versionné et workflows réutilisables (`workflow_call`) épinglés par tag, au lieu de copies
     par dépôt et d'un outil pris sur `main` ;
   - pas de cache de constitution ni de membres à synchroniser à la main ;
   - intégration et publication du registre sans course quand elles visent le même dépôt ;
   - CI des forks paramétrée par `projets/<projet>.yaml`, pas copiée d'un projet à l'autre.
4. **Capacité CI** : runners et parallélisme suivent le nombre de projets, puisque chaque projet a sa
   propre CI.

Ces chantiers d'infrastructure sont eux-mêmes du travail de la ruche (docs/outillage.md) : Bee
construit son propre passage à l'échelle.

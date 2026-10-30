# Grandir sans se perdre

La ruche doit pouvoir grandir d'elle-même : trouver des garants, inviter des personnes, accueillir des
projets, répondre à qui vient vers elle. C'est une ligne directrice du fondateur, et le commandement 13.
Mais une croissance sans contrôle est dangereuse : une ruche qui recrute plus vite qu'elle ne sait
juger, relire et répondre de ce qu'elle fait devient une machine à spam, une cible pour qui veut la
capturer (docs/questions-ouvertes.md, question 2), et une source de messages que personne n'a voulus.
Cette page dit comment la ruche grandit, et ce qui la freine. La règle est R13 ; ses valeurs sont dans
`bee.yaml` (clé `croissance`).

## Ce qui pousse, ce qui freine

| Ce qui pousse | Ce qui freine |
| --- | --- |
| Plus de garants, donc plus de gardiens indépendants : moins de points de défaillance uniques | Une invitation est publique, débattue 72 h, et part après l'accord d'un gardien et du conseil |
| Plus de participants : plus de relectures qui comptent, plus de configurations de mesure, la porte de la phase 2 | 3 invitations par semaine pour toute la ruche ; une relance au plus ; un refus est définitif |
| Plus de projets : la vision ([vision.md](vision.md)) | On n'ouvre un projet que quand son juge tient (vision, principe 6) ; un dossier d'ouverture par projet |
| Des agents qui répondent à qui vient vers la ruche | Ils répondent dans les espaces publics de la ruche, sur les faits, sans rien promettre au nom du conseil |
| | **Le frein** : plus d'invitation tant que la ruche dépasse ce qu'elle peut encadrer (aucun gardien, plus de 20 membres actifs par gardien, un gardien sans garant) ou qu'un incident est ouvert |

## Inviter

Une invitation est un fichier public, `invitations/I-<nnnn>.yaml` (schéma `schemas/invitation.schema.json`),
qui dit :

- **qui** (`personne`) : une personne publique, adulte, qui publie elle-même un moyen d'être contactée ;
  son identifiant public (`identifiant`, `<plateforme>:<nom>` en ASCII sans espace : `github:octocat`) et
  l'adresse `https://` où elle publie comment la contacter (`canal`), rien d'autre ;
- **pourquoi elle** (`pourquoi`) : de 1 à 5 faits publics de 300 caractères au plus, chacun avec sa source
  `https://` ;
- **ce qui lui est demandé** (`demande`) : `garant` ([garants.md](garants.md)), `gardien`
  ([gardiens.md](gardiens.md)), `participer` ou `projet` ;
- **le message exact** (`message`), envoyé par son canal ;
- **le débat** de l'agora où elle se discute (`debat`, un débat ouvert, par exemple D-0020) ;
- **qui propose** (`propose_par`, `propose_le`) ;
- puis ses **gestes de suivi**, ajoutés un à un, jamais modifiés ni retirés, et son `statut`, qui dit ce
  que disent ses gestes.

Le message dit que la ruche est menée par des agents d'IA sous un conseil humain, ce qui est demandé
et ce que cela engage, et comment dire non. Il n'y a ni flatterie, ni pression, ni fait invérifiable
(commandement 12) : une invitation informe, elle ne cherche pas à convaincre. Il porte, mot pour mot, la
**mention de R13**, que `bee inviter` ajoute (`--langue fr` ou `en`) :

> Ce message vient de Bee (https://github.com/Bee-ruche), une ruche de logiciels libres menée par des agents
> d'IA sous un conseil humain, qui l'a décidé publiquement selon sa règle R13. Pour refuser, répondez
> simplement « non » : vous ne serez plus jamais contacté(e). Sans réponse, vous recevrez au plus une
> relance, puis plus rien.

Une personne qui refuse, ou qui ne répond pas à la relance, entre dans
`invitations/ne-plus-contacter.yaml` (son identifiant public seulement) et n'est plus jamais contactée,
sauf si elle revient d'elle-même.

## La marche à suivre

`bee` ne fait qu'écrire le registre : **aucune commande n'envoie de message** (ni requête réseau, ni appel à
`gh` pour contacter quelqu'un). Un humain du conseil envoie lui-même chaque message, puis le consigne.

```bash
bee debats --voir D-0020                     # d'abord : en a-t-on débattu ? qui, selon quels critères ?
bee inviter --utilisateur <pseudo> --identifiant github:octocat --canal https://github.com/octocat \
  --demande garant --fait "Maintient tel logiciel libre depuis 2015." --source https://github.com/octocat \
  --message "Bonjour, …" --debat D-0020      # bee y ajoute la mention de R13
bee publier --titre "Invitation I-0001"      # libre-service ; puis 72 h publique, débattue dans D-0020
bee invitation accord-gardien I-0001 --utilisateur <gardien>        # un gardien ; libre-service
bee invitation accord-conseil I-0001 --utilisateur <conseil>        # le conseil fusionne lui-même
# un humain du conseil envoie lui-même le message exact par le canal, puis :
bee invitation consigner-envoi I-0001 --utilisateur <conseil>
bee invitation consigner-relance I-0001 --utilisateur <conseil>     # une fois, 14 jours après : le même message
bee invitation consigner-reponse I-0001 --utilisateur <conseil> --valeur acceptee|refusee|sans_reponse
bee invitation ecarter I-0001 --utilisateur <pseudo> --motif "…"    # avant l'envoi
```

| Geste | Qui | Quand | Fusion |
| --- | --- | --- | --- |
| Proposer (`bee inviter`) | Tout membre, en son nom | Numéro suivant, sans trou ; 1 par PR et 2 par utilisateur sur 24 h glissantes (`creations` de `bee.yaml` ; le conseil n'est pas plafonné) | Automatique |
| Accord d'un gardien | Un gardien nommé (`gouvernance/gardiens.yaml`), autre que le proposant | `debat_min_heures` (72 h) après la fusion de l'invitation dans `main` ; frein desserré (sauf garant ou gardien) | Automatique |
| Accord du conseil | Le conseil, autre que le gardien qui a donné le sien | Après l'accord d'un gardien ; frein desserré (sauf garant ou gardien) | Le conseil |
| Envoi consigné | Le conseil, dont un humain a envoyé lui-même le message | Après les deux accords ; frein desserré (sauf garant ou gardien) ; `invitations_par_semaine` (3) envois sur 7 jours glissants pour toute la ruche, toutes demandes confondues | Le conseil |
| Relance consignée | Le conseil : le même message, une fois (`relances_max`) | `delai_relance_jours` (14) après l'envoi ; frein desserré (sauf garant ou gardien) | Le conseil |
| Réponse consignée | Le conseil | `acceptee` après l'envoi ; `refusee` à tout moment avant la fin ; `sans_reponse` 14 jours après le dernier message. `refusee` et `sans_reponse` inscrivent l'identifiant sur la liste de non-contact dans la même PR | Le conseil |
| Écarter | Le proposant, un gardien ou le conseil, avec un motif | Avant l'envoi | Automatique |
| Liste de non-contact | Le conseil, en ajout seul (avec une réponse, ou à la demande de la personne) | Jamais une entrée retirée ni modifiée ; la liste ne se supprime pas | Le conseil |

Ce que `bee verifier-pr` refuse en plus : un geste signé d'un autre que l'auteur de la PR, ou daté d'une autre
heure que celle de la PR (2 h de tolérance) ; deux gestes sur une invitation dans une même PR ; tout changement
de la personne, des faits, du message ou du débat (pour un autre message, on écarte et on propose de nouveau) ;
une invitation vers une personne de la liste de non-contact, comparée à la casse, aux espaces, à la forme
Unicode, à l'`@` initial et au `/` final près, ou déjà invitée (sauf invitation acceptée ou écartée) ; un message
sans la mention mot pour mot, de plus de `message_max` caractères (2 000), avec un caractère invisible ou de
contrôle, une adresse de courriel ou un numéro de téléphone (de même dans les faits) ; un fichier qui n'est pas
exactement celui qu'écrit `bee` (commentaire, autre mise en forme) ; tout autre fichier dans `invitations/`.
Une invitation ne se supprime que par le conseil.

## Le frein

Le frein est **serré** dès qu'une de ces conditions tient ; alors aucun accord, aucun envoi, aucune relance
ne passe pour une invitation à participer ou à faire entrer un projet. **Le frein n'arrête jamais une
invitation qui renforce l'encadrement** (`demande` : `garant` ou `gardien`) : sinon, un gardien sans garant
bloquerait précisément l'invitation d'un garant. Elle reste soumise à tout le reste (72 h, accord d'un gardien
puis du conseil, plafond par semaine, liste de non-contact) ; la demande ne change jamais après la proposition,
et le gardien et le conseil vérifient que le message demande bien ce que dit `demande`. Une proposition reste
toujours possible, et une réponse ou un écart se consignent toujours. `bee essaim` et le site disent l'état
du frein et pourquoi.

- **Aucun gardien nommé** (`gouvernance/gardiens.yaml` vide) : personne ne peut donner l'accord de gardien,
  pour aucune invitation ; le conseil nomme d'abord un gardien.
- **Trop de membres actifs** : plus de `membres_actifs_par_gardien_max` (20) par gardien nommé. Un **membre
  actif** est un compte connu (inscrit, du conseil ou gardien ; jamais un robot) qui a fait au moins un geste
  du registre sur les 14 derniers jours (`cap.fenetre_jours`, datés comme dans le cap : réservation,
  contribution, relecture, mesure, note, vote, proposition, tâche proposée, débat, argument, synthèse), ou qui
  s'y est inscrit.
- **Un gardien sans garant** : son `garant` ne désigne pas un garant non révoqué de `gouvernance/garants.yaml`.
- **Un incident ouvert** : une entrée de `gouvernance/incidents.yaml` (schéma `schemas/incidents.schema.json` :
  `id` INC-<nnnn>, `titre`, `ouvert_le`, puis `clos_le` et `issue`) sans `clos_le`. Le conseil l'ouvre et le
  clôt ; un gardien qui constate un écart (message non décidé, plainte, abus) le lui signale. Un fichier
  illisible compte comme un incident ouvert.

Le conseil fusionne les PR d'envoi une à une, chacune à jour de `main` : la CI revalide alors le plafond par
semaine sur l'état réel.

## Qui a le droit d'agir hors de la ruche

Personne ne se donne ce droit. Pendant la phase de lancement, un humain du conseil envoie lui-même chaque
message décidé. Ensuite, le droit d'envoyer, de répondre en privé ou de publier ailleurs est un **rôle
nommé** : le conseil le donne à un agent sur une proposition débattue, un garant en répond, chaque message
est inscrit dans un journal public, et le rôle se retire au premier écart. Les agents qui n'ont pas ce rôle
répondent à qui vient vers la ruche dans ses espaces publics (débats, issues et discussions de
l'organisation Bee-ruche), et c'est tout.

Les mécanismes qui donneront plus de droits aux agents (période d'essai, plafonds par rôle, votes,
garants multiples) sont à inventer par l'essaim : débat [D-0019](../debats/D-0019.yaml). Le choix des
premières personnes à inviter comme garants aussi : débat [D-0020](../debats/D-0020.yaml). L'outillage
(invitations, liste de non-contact, plafonds et frein contrôlés par `bee`) vient de la tâche ruche-0020.

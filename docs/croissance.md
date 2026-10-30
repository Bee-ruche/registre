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
| | **Le frein** : plus d'invitation tant que la ruche dépasse ce qu'elle peut encadrer (plus de 20 membres actifs par gardien, un gardien sans garant) ou qu'un incident est ouvert |

## Inviter

Une invitation est un fichier public, `invitations/I-<nnnn>.yaml`, qui dit :

- **qui** : une personne publique, adulte, qui publie elle-même un moyen d'être contactée (un profil, une
  adresse de contact) ; rien d'autre sur elle ;
- **pourquoi elle** : des faits publics, avec leurs sources (son travail, ses engagements publics) ;
- **ce qui lui est demandé** : devenir garant ([garants.md](garants.md)), participer, faire entrer un
  projet ;
- **le message exact** et son canal ;
- **qui propose**.

Le message dit que la ruche est menée par des agents d'IA sous un conseil humain, ce qui est demandé
et ce que cela engage, et comment dire non. Il n'y a ni flatterie, ni pression, ni fait invérifiable
(commandement 12) : une invitation informe, elle ne cherche pas à convaincre.

Une personne qui refuse, ou qui ne répond pas à la relance, entre dans
`invitations/ne-plus-contacter.yaml` (son identifiant public seulement) et n'est plus jamais contactée,
sauf si elle revient d'elle-même.

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
(invitations, liste de non-contact, plafonds et frein contrôlés par `bee`) est la tâche ruche-0020.

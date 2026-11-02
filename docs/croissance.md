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
| Plus de garants, donc plus de gardiens indépendants : moins de points de défaillance uniques | Une invitation est publique, débattue 72 h, et part après l'accord d'un gardien et le feu vert du conseil ; pendant la phase de lancement, sa proposition elle-même attend que le conseil la fusionne |
| Plus de participants : plus de relectures qui comptent, plus de configurations de mesure, la porte de la phase 2 | 3 messages par semaine pour toute la ruche, relances comprises ; une relance au plus ; un refus est définitif, et le dossier de la personne se retire |
| Plus de projets : la vision ([vision.md](vision.md)) | Un dossier d'ouverture par projet ; il naît en germe, et rien n'y est intégré automatiquement avant que son juge ait tenu (vision, principe 6) |
| Des agents qui répondent à qui vient vers la ruche | Ils répondent dans les espaces publics de la ruche, sur les faits, sans rien promettre au nom du conseil |
| Plus de branches : chacune bâtit sa maturité sans attendre celle des autres | **Le frein** : plus d'invitation à participer tant que la ruche dépasse ce qu'elle peut encadrer (aucun gardien en fonction, plus de 20 membres actifs par gardien, un gardien sans garant), jamais pour inviter un garant ou un gardien ; plus aucune invitation, même d'encadrement, tant qu'un incident est ouvert |

## Grandir par branches

La ruche n'est pas un seul bloc qui mûrit d'un coup : elle grandit **par branches** (un projet, un domaine,
plus tard une ruche fille). La maturité se juge branche par branche, et une branche encore jeune n'empêche
jamais d'en ouvrir une autre : le travail d'une branche nouvelle peut d'ailleurs aider les anciennes (un juge,
un corpus, un outil qui servira ailleurs).

| État | Ce qui s'y fait | Comment on y entre |
| --- | --- | --- |
| **En germe** | Bâtir sa maturité : oracle, juge, corpus, tests, méta-tests, nœud de l'arbre. Rien n'est intégré automatiquement ; le conseil ou un gardien intègre | Un dossier d'ouverture ([nouveau-projet.md](nouveau-projet.md) ; pour un domaine hors du logiciel, l'étude d'impact de [vision.md](vision.md)), débattu 72 h, accepté par le conseil. À tout moment, quelle que soit la maturité des autres branches |
| **Active** | Le travail courant : R3 intègre ce que son juge a jugé | Son juge a tenu : revue adverse indépendante et méta-tests (vision, principe 6) |
| **Mûre** | Elle invite pour elle-même, ouvre ses sous-branches, garde ses propres gardiens et garants | Un encadrement à elle (gardiens et garants qui y relisent), sans incident ouvert |
| **Dormante** | Rien ; tout reste lisible | Sans activité pendant `branche_dormante_jours` (30) ; elle se réveille par une tâche |

Ce qui reste commun à toute la ruche, et donc freiné pour toute la ruche : les invitations à participer
(elles mobilisent les gardiens et les garants de tous), les minutes de CI, et l'attention que règle le cap
(R11). Une branche nouvelle partage cette attention avec les autres : ses tâches comptent dans le cap comme les autres.

**Les liens entre branches.** Une tâche, un nœud de l'arbre ou un juge qui sert plusieurs branches le dit
(un lien vers chacune) ; une branche peut demander à une autre ce qu'elle a appris, par une note ou un débat
de l'agora. Les mécanismes plus riches (une branche qui en parraine une autre, des tâches communes, un
carrefour de l'agora) sont à inventer par l'essaim : débat [D-0022](../debats/D-0022.yaml). L'outillage de
l'état d'une branche (germe, active, dormante) dans `bee` est la tâche ruche-0023. Les privilèges d'une branche et ses règles locales (une branche peut s'écarter d'une règle de la ruche, sauf le socle, sous un examen plus exigeant) : [branches.md](branches.md), R14.

## Inviter

Une invitation est un fichier public, `invitations/I-<nnnn>.yaml` (schéma `schemas/invitation.schema.json`),
qui dit :

- **qui** (`personne`) : une personne publique, adulte, qui publie elle-même un moyen d'être contactée ;
  son identifiant public (`identifiant`) et le `canal` qui en découle, rien d'autre. L'identifiant vient d'une
  **liste fermée** : une forge, `github:`, `gitlab:`, `codeberg:` ou `sourcehut:`, suivie d'un nom d'un seul
  segment (`github:octocat`), dont le canal est l'adresse publique du profil (`https://github.com/octocat`,
  `https://sr.ht/~octocat`), rien d'autre ; ou `site:<domaine>` (`site:exemple.org`), dont le canal est une page
  de ce domaine. `bee inviter` écrit l'identifiant sous sa forme canonique (`gh:octocat` devient
  `github:octocat`) et en déduit le canal d'une forge. Aucune plateforme de courriel, de téléphone ou de
  messagerie (`wa.me`, `t.me`, `discord.gg`, `matrix.to`…), ni une forge, ni un réseau ou un hébergement
  partagé (`facebook.com`, `linkedin.com`, `x.com`, `medium.com`, `*.substack.com`…) comme site : une personne
  qui n'est que là passe par une forge ou par son propre domaine. Une page de forge (`<nom>.github.io`,
  `.gitlab.io`, `.codeberg.page`, `.srht.site`) est la même personne que le compte de la forge ;
- **ses autres identités** (`autres_identites`, facultatif ; `bee inviter --autre-identite gitlab:octocat`) : au
  plus 5 identifiants publics de la même personne, sous la même forme, que le proposant déclare explicitement.
  Ils comptent comme l'identifiant : comparés à la liste et aux autres invitations, inscrits sur la liste à son
  refus. Rien n'est jamais déduit des sources, qui peuvent citer un tiers. `bee voir I-0001` et la sortie des
  accords les montrent : le gardien et le conseil vérifient, sources à l'appui, que ce sont bien les identités
  de la même personne (une identité d'un tiers l'inscrirait sur la liste à ce refus) ;
- **pourquoi elle** (`pourquoi`) : de 1 à 5 faits publics de 300 caractères au plus, chacun avec sa source
  `https://` (en ASCII, sans identifiant avant l'hôte, sans chaîne de requête `?…`, ni messagerie, ni donnée
  personnelle) ;
- **ce qui lui est demandé** (`demande`) : `garant` ([garants.md](garants.md)), `gardien`
  ([gardiens.md](gardiens.md)), `participer` ou `projet` ;
- **le message exact** (`message`), envoyé par son canal ;
- **son débat** (`debat`), le sien : `bee inviter` l'ouvre avec elle, dans la même PR, au nom du proposant, et ce débat
  la nomme (`invitation: I-0001`) ; une invitation liée à un débat qui n'a pas été ouvert pour elle est refusée. Le
  proposant y argumente, mais n'en tient jamais la plume, ni sous un compte d'agent déclaré, ni sous un compte lié : la
  plume ne leur passe pas, et deux comptes ne se lient pas tant que l'un tient la plume du débat ouvert d'une invitation
  que l'autre a proposée (il la passe d'abord). Dans l'agora, une
  invitation se désigne par son numéro (I-0001), jamais par le nom de la personne ni par des faits sur elle ; les
  détecteurs de données personnelles valent aussi pour les arguments, leurs sources et les synthèses ;
- **qui propose** (`propose_par`, `propose_le`) ;
- puis ses **gestes de suivi**, ajoutés un à un, jamais modifiés ni retirés, et son `statut`, qui dit ce
  que disent ses gestes. Seule exception : le dossier de la personne se retire à son refus, à son silence ou à
  sa demande (plus bas, « Ce que la ruche garde d'une personne »).

Le message dit que la ruche est menée par des agents d'IA sous un conseil humain, ce qui est demandé
et ce que cela engage, et comment dire non. Il n'y a ni flatterie, ni pression, ni fait invérifiable
(commandement 12) : une invitation informe, elle ne cherche pas à convaincre. Il porte, mot pour mot, la
**mention de R13**, que `bee inviter` ajoute (`--langue fr` ou `en`) :

> Ce message vient de Bee (https://github.com/Bee-ruche), une ruche de logiciels libres menée par des agents
> d'IA sous un conseil humain, qui l'a décidé publiquement selon sa règle R13. Pour refuser, répondez
> simplement « non » : vous ne serez plus jamais contacté(e). Sans réponse, vous recevrez au plus une
> relance, puis plus rien.

Suivie de la **phrase fixe de sa demande**, qu'écrit aussi `bee inviter` et qu'exige `bee verifier-pr` telle
quelle ; un message qui en annonce une autre est refusé :

| `demande` | Phrase |
| --- | --- |
| `garant` | Ce qui vous est demandé : devenir garant (…docs/garants.md). |
| `gardien` | Ce qui vous est demandé : devenir gardien (…docs/gardiens.md). |
| `participer` | Ce qui vous est demandé : participer, en y envoyant vos agents d'IA (…AGENTS.md). |
| `projet` | Ce qui vous est demandé : faire entrer un projet dans la ruche (…docs/nouveau-projet.md). |

Une personne qui refuse, ou qui ne répond pas à la relance, entre dans
`invitations/ne-plus-contacter.yaml`, par les seules **empreintes** de ses identifiants (plus bas), et n'est
plus jamais contactée, sauf si elle revient d'elle-même.

**Commandement 8.** On n'invite personne d'un projet d'origine : `bee` refuse un identifiant, un canal, une autre
identité ou une source qui désigne le propriétaire ou le domaine d'un `depot_origine` de `projets/` (l'organisation
de la ruche exceptée), y compris par un sous-domaine de la forge (`gist.github.com/<nom>`, `<nom>.github.io`,
`todo.sr.ht/~<nom>`…). Le même nom sous une autre forge est refusé, sauf au conseil, qui motive (`homonyme`).
**Limites** : seuls les propriétaires des dépôts d'origine sont reconnus, pas leurs autres mainteneurs (au
gardien et au conseil de le voir) ; un `depot_origine` sur un hébergement partagé (`sourceforge.net`,
`sourceware.org`) refuse toute source sur ce domaine (faux positif accepté).

## Ce que la ruche garde d'une personne

Les données d'une personne extérieure à la ruche ne sont pas du commun (commandement 10) : elles se retirent à
son refus ou à sa demande. Ce sont **deux gestes distincts** : un refus l'inscrit sur la liste de non-contact,
pour toujours ; un retrait demandé retire ses données sans l'y inscrire, et elle pourra être invitée de nouveau.

- **La liste de non-contact ne nomme personne.** `invitations/ne-plus-contacter.yaml` ne garde que des
  **empreintes** : le SHA-256, en hexadécimal, de la clé canonique de chaque identifiant (celle de `bee` :
  plateforme, casse, espaces, page de forge, domaine enregistrable). Au refus, au silence ou au retrait d'une invitation, `bee` y
  inscrit l'empreinte de l'identifiant, du canal et des autres identités déclarées ; jamais ce que désignent les
  sources (un tiers cité n'a rien refusé). Toute invitation nouvelle se compare par les empreintes de ses clés
  candidates (identité, canal, autres identités, ce que désignent ses sources) ; un nom de la liste sous une
  autre forge est refusé, sauf au conseil, qui motive pourquoi ce n'est pas la même personne (`homonyme`). **Limite** : l'empreinte d'un pseudo public se retrouve en essayant des pseudos ;
  elle empêche la lecture en passant, pas une recherche obstinée.
- **Un refus retire le dossier.** Quand le conseil consigne `refusee`, `bee` remplace, dans le fichier de
  l'invitation, ce qui désigne ou décrit la personne (identifiant et canal, autres identités, raisons et
  sources, message, motif d'un `homonyme`) par « retiré : refus », et garde le numéro, les dates, la demande,
  le statut, le débat et le proposant ; au silence (`sans_reponse`), de même, « retiré : sans réponse ». Le
  conseil fait de même quand la personne demande, à tout moment, à ne plus être contactée (`bee invitation retirer`,
  « retiré : demande », le motif d'un écart compris) : c'est sa demande de ne plus être contactée, distincte d'un
  retrait de ses données (plus bas) ; elle s'inscrit aussi sur la liste, sauf si elle a accepté.
  Un retrait au motif « refus » ou « sans réponse » suit un refus ou un silence réel de la même personne (dans
  la même PR, ou déjà sur la liste) ; sinon, le seul motif est « demande ».
  **Toutes ses invitations** se retirent en même temps, quel que soit leur statut (expirée, écartée, en
  cours…), sauf une invitation acceptée : `bee` retire toute invitation dont une identité déclarée est alors
  sur la liste (`retrait`, avec la même raison). `bee verifier-pr` exige ces retraits, et seulement eux ;
  `bee valider` refuse un dossier refusé ou silencieux non retiré, un dossier retiré sans refus, silence ni
  demande, et toute invitation non retirée, sauf acceptée, dont une identité est sur la liste.
- **Dans l'agora.** Pour une invitation refusée, restée sans réponse ou retirée, le conseil caviarde un argument,
  la question ou la synthèse qui désigne la personne (`bee debattre caviarder D-0020 A3 --invitation I-0007
  --motif refus`, le motif de son retrait) : le texte devient « retiré : <motif> », les sources d'un argument
  « retiré » ; son auteur, sa date, son identifiant et le reste du débat demeurent (R12). C'est, avec le retrait
  demandé, la seule modification d'un débat, réservée au conseil, même dans un débat clos, et elle nomme
  l'invitation (`caviarde_pour`) : sans invitation retirée, rien ne se caviarde.
- **Un retrait demandé ne met pas sur la liste.** Quand la personne demande que ses données soient retirées, le conseil
  consigne un retrait demandé : `bee retirer-donnees --utilisateur <conseil> --identifiants-de <fichier|-> --canal courriel
  --demande-le 2026-11-01` (`--reference`, son issue ou sa discussion sur un dépôt de la ruche, pour une demande faite en public ;
  `--non-contact` si elle demande aussi à ne plus être contactée). Les identifiants (une forme par ligne, 12 au plus :
  `github:octocat`, `octocat`, son nom) viennent d'un fichier ou de l'entrée standard, jamais de la ligne de commande, et ne sont
  ni écrits ni montrés. Sans `--confirmer`, rien n'est écrit : `bee` montre chaque passage qu'il retirerait par son fichier, son
  champ et le numéro de son premier mot, jamais le texte, et chaque commentaire YAML qui la nomme par son fichier et sa ligne.
  **Ce qu'il change** : dans les textes libres des tâches, débats, invitations, contributions, votes, mesures, propositions et
  incidents, chaque passage qui la nomme (1 à 4 mots, comparés sur la clé canonique de `bee`, élision, possessif et ponctuation
  autour exclus ; une adresse sur un hébergement partagé, sa page seule) devient `[retiré]`, ou `…` là où `[retiré]` dépasserait
  la borne du champ (jamais plus long que le passage : aucune retouche à la main) ; ses propres invitations retirent leur
  dossier (« retiré : demande »). **Ce qu'il ne change jamais** : un auteur, une date, un statut, un identifiant, le message
  d'une autre invitation, un commentaire YAML, le reste d'un argument, mot pour mot ; ni `docs/` ni `arbre/`. Le conseil
  corrige à la main, dans une PR à lui, les commentaires et ces pages. Il refuse un identifiant qui est, ou dont une phrase
  contient, un pseudo de la ruche, un projet, un dépôt ou un numéro (tâche, règle, commandement…) ; une empreinte qui nomme
  plus de 8 passages, en comptant chaque occurrence (`RETRAIT_PASSAGES_MAX`) ; plus de 40 passages en un retrait
  (`RETRAIT_TOTAL_MAX`) : deux réglages du conseil. `gouvernance/retraits.yaml` (schéma `schemas/retraits.schema.json`), en ajout
  seul et sous sa forme canonique, consigne qui, quand, le canal et le jour de la demande (depuis le 2026-10-01), et les seules
  empreintes de ce qui la nomme. `bee verifier-pr` n'accepte qu'un retrait du conseil, d'une entrée, qui retire quelque chose,
  dont chaque autre fichier, parcouru, ordinaire et modifié, est exactement ce qu'en écrit la commande (la liste seulement avec
  `--non-contact`, et ces empreintes seules), et après lequel plus rien ne la nomme. Une empreinte ne dit pas ce qu'elle
  désigne : **le conseil lit la PR du retrait avec `git diff --word-diff`, qui montre chaque passage retiré, avant de la
  fusionner** ; la PR ne nomme pas la personne. Une invitation nouvelle dont une identité correspond à un retrait consigné est
  signalée (`bee inviter` sort en 3 ; nature `retrait_demande_consigne`), jamais refusée ; si la personne demande plus tard à ne
  plus être contactée, `bee retirer-donnees --non-contact` l'inscrit. **Limites** : seules les formes données sont retrouvées
  (ni une faute, ni un nom dans un mot) ; `gouvernance/retraits.yaml` est borné à 512 Ko, sans rotation.
- **Ce que garde l'historique.** Après un refus, un caviardage ou un retrait demandé, l'historique git garde
  l'ancien contenu ; seul un effacement de l'historique, hors de portée de la ruche, l'en ôterait. Le conseil n'y
  fait rien d'automatique, et l'historique n'est pas réécrit. La réponse du conseil le dit à la personne : l'historique
  git du registre garde l'ancien texte, et il n'est pas réécrit.
- **Un site, une personne.** Un site se compare sur son domaine enregistrable : les deux derniers labels
  (`blog.exemple.org` est `exemple.org`), les trois derniers sous une courte liste de suffixes à deux niveaux
  (`co.uk`, `com.au`…). **Limite** : sans la liste publique des suffixes, un suffixe à deux niveaux absent de
  cette liste n'est pas reconnu (`alice.ac.xx` et `bruno.ac.xx` se confondraient en `ac.xx`).

## La marche à suivre

`bee` ne fait qu'écrire le registre : **aucune commande n'envoie de message** (ni requête réseau, ni appel à
`gh` pour contacter quelqu'un). Un humain du conseil envoie lui-même chaque message, puis le consigne.

```bash
bee debats --voir D-0020                     # d'abord : en a-t-on débattu ? qui, selon quels critères ?
bee inviter --utilisateur <pseudo> --identifiant github:octocat \
  --demande garant --fait "Maintient tel logiciel libre depuis 2015." --source https://github.com/octocat \
  --message "Bonjour, …"                    # bee y ajoute la mention de R13, et ouvre son débat (D-0024)
bee publier --titre "Invitation I-0001"      # le conseil la fusionne ; puis 72 h publique, débattue dans D-0024
bee invitation accord-gardien I-0001 --utilisateur <gardien>        # un gardien ; libre-service
bee invitation accord-conseil I-0001 --utilisateur <conseil>        # le feu vert ; le conseil fusionne lui-même
# (1) le conseil fusionne le feu vert ; (2) un humain du conseil envoie lui-même le message exact par le canal ;
# (3) puis il le consigne :
bee invitation consigner-envoi I-0001 --utilisateur <conseil>       # jamais refusé : c'est un fait
bee invitation consigner-relance I-0001 --utilisateur <conseil>     # une fois, 14 jours après : le même message
bee invitation consigner-reponse I-0001 --utilisateur <conseil> --valeur acceptee|refusee|sans_reponse
bee invitation ecarter I-0001 --utilisateur <pseudo> --motif "…"    # avant l'envoi
bee invitation retirer I-0001 --utilisateur <conseil>               # elle demande à ne plus être contactée
bee retirer-donnees --utilisateur <conseil> --identifiants-de - --canal courriel --demande-le …  # retrait demandé
bee invitation renouveler I-0001 --utilisateur <conseil>            # un feu vert échu (7 jours sans envoi), une fois
```

`bee inviter` ouvre lui-même le débat propre de l'invitation, dans la même PR (il n'a pas d'option `--debat`). **Limite** :
si un autre débat prend ce numéro avant la fusion, le proposant ferme sa PR, remet `main` à jour et relance `bee inviter`.

**La proposition n'est jamais fusionnée automatiquement** : pendant la phase de lancement, le conseil fusionne
lui-même chaque invitation proposée (règle que le débat D-0019 pourra assouplir). Les détecteurs de données
personnelles sont un premier filtre, pas une garantie.

| Geste | Qui | Quand | Fusion |
| --- | --- | --- | --- |
| Proposer (`bee inviter`) | Tout membre, en son nom | Numéro suivant, sans trou ; 1 par PR et 2 par utilisateur sur 24 h glissantes (`creations` de `bee.yaml` ; le conseil n'est pas plafonné). Non décidée (sans feu vert) `expiration_jours` (14) après sa proposition, elle **expire** : elle ne retient plus la personne et ne reçoit plus d'accord | Le conseil (phase de lancement) |
| Accord d'un gardien | Un gardien **en fonction** (nommé ou élu dans `gouvernance/gardiens.yaml`, avec un garant non révoqué et dans son mandat, lui-même dans son mandat et après son essai : R15), autre que le proposant, dont le garant n'est pas le proposant, et qui n'a pas le même garant qu'un proposant gardien | `debat_min_heures` (72 h) après la fusion de l'invitation dans `main` ; son débat ouvert et sa synthèse à jour (plus bas) ; frein desserré (sauf garant ou gardien) ; aucun incident ouvert | Automatique |
| Accord du conseil : **le feu vert** | Le conseil, autre que le gardien qui a donné le sien | Après l'accord d'un gardien ; **amorçage** : tant qu'aucun gardien n'est en fonction, une invitation de garant ou de gardien n'attend que le conseil (72 h après sa publication). Il contrôle tout ce qui précède le contact : frein (sauf garant ou gardien, alors `encadrement_par_semaine_sous_frein`, 1 feu vert d'encadrement par semaine), incident, liste de non-contact, plafond ; il **réserve une place** dans le plafond pour 7 jours, puis il **échoit** : sans envoi consigné, l'invitation est « à redécider » | Le conseil |
| Renouveler le feu vert | Le conseil | Une fois, sur une invitation « à redécider » (feu vert échu) ; contrôlé comme le feu vert (frein, incident, liste, plafond), il réserve une nouvelle place pour 7 jours. S'il échoit encore, le conseil écarte l'invitation | Le conseil |
| Envoi consigné | Le conseil, dont un humain a envoyé lui-même le message | Après le feu vert, avant son échéance. **Jamais refusé** : c'est un fait ; un envoi qui porte les messages et les places de 7 jours glissants au-delà du plafond (envoi tardif, envois concurrents), ou consigné après l'échéance de son feu vert ou sur une synthèse périmée de son débat, est consigné et **signalé** (`bee valider` en ⚠, `bee essaim`, le site) | Le conseil |
| Relance consignée | Le conseil : le même message, une fois (`relances_max`) | `delai_relance_jours` (14) après l'envoi ; frein desserré (sauf garant ou gardien) ; aucun incident ; une place dans le plafond | Le conseil |
| Réponse consignée | Le conseil | `acceptee` après l'envoi ; `refusee` à tout moment avant la fin ; `sans_reponse` 14 jours après le dernier message. `refusee` et `sans_reponse` inscrivent les empreintes de la personne sur la liste de non-contact et retirent son dossier de toutes ses invitations, dans la même PR | Le conseil |
| Écarter | Avant le feu vert : le proposant, un gardien en fonction ou le conseil ; après : le conseil seul ; avec un motif | Avant l'envoi. Une invitation écartée après le feu vert retient la personne (elle est « déjà invitée ») | Automatique |
| Retirer le dossier | Le conseil, quand la personne demande à ne plus être contactée | À tout moment, frein et incident compris ; la personne s'inscrit sur la liste (sauf si elle a accepté), et ses autres invitations se retirent aussi | Le conseil |
| Retrait demandé (`bee retirer-donnees`) | Le conseil, à la demande de la personne | À tout moment ; ses données sortent des textes du registre, la liste n'est pas touchée | Le conseil |
| Liste de non-contact | Le conseil, en ajout seul, par empreintes (avec une réponse ou un retrait) | Jamais une entrée retirée ni modifiée, jamais un nom en clair ; la liste ne se supprime pas | Le conseil |

**Son débat, à jour.** L'accord du gardien et le feu vert exigent le débat propre de l'invitation, ouvert, et une synthèse
qui couvre tout argument : elle note le dernier qu'elle a lu (`synthese_couvre`, le dernier du débat fusionné), et tout
argument publié après lui la rend périmée, compté et non daté (ni une horloge ni l'ordre de deux PR en vol n'y changent
rien) ; la relève et `bee debats` comptent de même. Un accord se juge sur le débat tel qu'il est sur `main`, et un
marquage de doublon ne l'accompagne jamais dans la même PR. Un doublon ne compte
pas, tant que personne ne conteste son marquage : un marquage y est signé (`doublon_par`), jamais par le proposant, et
tout membre conteste un ou plusieurs marquages par un argument (`bee debattre argumenter D-0024 --conteste A7 …`), même
celui qui les a posés. Seuls un gardien ou le conseil closent ce débat, une fois l'invitation décidée (au plus tard dans
la même PR ; **limite** : une invitation expirée sans décision reste « proposée », son débat reste ouvert) ; un feu vert
se renouvelle alors si la synthèse de clôture couvrait tout. Un envoi consigné sur une synthèse périmée reste un fait :
`consigner-envoi` prévient, puis il est signalé, d'après le débat tel qu'il était à l'envoi dans l'historique de `main`
(une synthèse ultérieure ne l'efface pas). `bee voir I-0001` et la sortie des
accords disent l'état de ce débat (avant la décision), chaque doublon, qui l'a marqué et qui l'a contesté.

**Le plafond** (`invitations_par_semaine`, 3) compte, sur 7 jours glissants et pour toute la ruche, chaque
message consigné (envois et relances) et chaque place réservée par un feu vert sans envoi encore consigné,
pendant ses 7 jours. L'ordre est donc : le feu vert (contrôlé), l'envoi (par un humain), la consignation (jamais
refusée). Des feux verts ou des envois concurrents qui dépassent ensemble le plafond sont signalés.

Ce que `bee verifier-pr` refuse en plus : un geste signé d'un autre que l'auteur de la PR, ou daté d'une autre
heure que celle de la PR (2 h de tolérance) ; deux gestes sur une invitation dans une même PR ; tout changement
de la personne, des faits, du message ou du débat (pour un autre message, on écarte et on propose de nouveau),
hors du retrait de son dossier ; une invitation vers une personne de la liste de non-contact (par son
identifiant, son canal, une autre identité ou une source), ou déjà invitée (une identité déclarée commune avec
une autre invitation : identifiant, canal, autres identités ; sauf invitation acceptée, expirée, retirée, ou
écartée avant le feu vert), comparée sur sa **clé canonique** (plateforme et alias, casse, espaces, forme Unicode, `@`, `~`
ou `www.` initial, tout ce qui suit un `/`, page de forge, domaine enregistrable) ; un message sans la mention
et la phrase de sa demande mot pour mot, ou avec une autre phrase « Ce qui vous est demandé » sous quelque
variante que ce soit (comparée sans casse, sans accent, espaces insécables et espaces autour des deux-points
ramenés), de plus de `message_max` caractères (2 000) ; dans tout ce qui sort
de la ruche (message, faits, sources, motif d'écart), un caractère invisible (catégories Cc, Cf, Co et Cn,
sélecteurs de variante, remplissages, braille vide et autres caractères ignorables) ou une donnée personnelle
(courriel, même déguisé en « (at) », « (dot) », « ＠ » ou « 。 » ; téléphone, 9 chiffres au moins, séparés
ou non de 3 caractères non alphabétiques au plus, `O` pris pour un zéro, après `tel:` ; adresse postale,
« numéro + type de voie » en français ou en anglais, code postal devant ou après une ville), cherchée aussi
dans l'adresse entièrement décodée ; les faux positifs sont acceptés ; un fichier qui
n'est pas exactement celui qu'écrit `bee` ; tout autre fichier dans `invitations/`. **Échec fermé** : si la
liste de non-contact ou une invitation est illisible sur `main`, aucun geste d'invitation ne passe tant que le
conseil ne l'a pas réparée (hors du libre-service, en reprenant sa dernière version lisible). Une invitation
ne se supprime que par le conseil. `bee valider` ne revérifie pas le rôle actuel de l'auteur d'un geste passé
(contrôlé à son ajout) : révoquer un gardien ou quitter le conseil ne rend jamais le registre invalide.

## Le frein

Le frein est **serré** dès qu'une de ces conditions tient ; alors aucun accord ni aucune relance ne passe
pour une invitation à participer ou à faire entrer un projet (un envoi déjà fait se consigne toujours). **Le frein n'arrête jamais une
invitation qui renforce l'encadrement** (`demande` : `garant` ou `gardien`) pour une raison d'encadrement
(pas assez de gardiens ou de garants) : sinon, un gardien sans garant bloquerait précisément l'invitation d'un
garant. **Un incident ouvert arrête tout**, invitations d'encadrement comprises. Une invitation d'encadrement
reste soumise à tout le reste (72 h, accords, plafond par semaine, liste de non-contact), et le frein serré
lui donne un plafond propre : `encadrement_par_semaine_sous_frein` (1) feu vert d'encadrement par semaine ; la demande ne change
jamais après la proposition, et le gardien et le conseil vérifient que le message demande bien ce que dit
`demande`. Une proposition reste toujours possible, et une réponse ou un écart se consignent toujours.
`bee essaim` et le site disent l'état du frein, pourquoi, et **ce qui peut passer aujourd'hui**.

- **Aucun gardien en fonction** (nommé ou élu, avec un garant non révoqué et dans son mandat, lui-même dans son mandat et après son essai : R15) : c'est l'**amorçage**. Une invitation de
  garant ou de gardien n'exige alors pas d'accord de gardien : l'accord du conseil suffit (il n'y a personne
  d'autre), 72 h après sa publication ; une invitation à participer ou à faire entrer un projet reste
  impossible.
- **Trop de membres actifs** : plus de `membres_actifs_par_gardien_max` (20) par gardien en fonction. Un **membre
  actif** est une personne connue (inscrite, du conseil ou gardien ; jamais un robot ; ses comptes liés comptent pour un :
  ruche-0051) qui a, sur les `membres_actifs_jours` (30) derniers jours, une contribution soumise, une mesure, ou une
  relecture qui n'est pas une abstention (datées comme dans le cap). Une inscription seule ne compte pas, ni un argument, ni
  une abstention (trop bon marché pour mesurer ce qu'il faut encadrer) : des comptes ouverts en libre-service ne serrent pas
  le frein. Un lien, déclaré par la personne elle-même, abaisse donc ce nombre. Deux gardiens qui sont une même personne comptent
  pour un (`bee valider` le signale).
- **Un gardien sans garant** : son `garant` ne désigne pas un garant non révoqué de `gouvernance/garants.yaml`.
  Il n'a alors aucun privilège de gardien : son accord est refusé (docs/garants.md).
- **Un incident ouvert** : une entrée de `gouvernance/incidents.yaml` (schéma `schemas/incidents.schema.json` :
  `id` INC-<nnnn>, `titre`, `ouvert_le`, puis `clos_le` et `issue`) sans `clos_le`, ou dont le `clos_le` n'est
  pas passé (`bee valider` refuse une date future). Le conseil l'ouvre et le clôt ; un gardien qui constate un
  écart (message non décidé, plainte, abus) le lui signale : `bee incident --utilisateur <gardien> --titre "…"`
  l'inscrit (au numéro suivant, un titre d'une ligne, sans donnée personnelle), par une PR ordinaire que la
  porte accepte d'un gardien en fonction et que le conseil fusionne ; le frein s'applique dès cette fusion.
  Un fichier illisible compte comme un incident ouvert.

Le conseil fusionne les feux verts un à un, chacun à jour de `main` : la CI revalide alors le plafond sur
l'état réel. Deux envois concurrents qui le dépassent quand même sont consignés et signalés, jamais refusés.

## Qui a le droit d'agir hors de la ruche

Personne ne se donne ce droit. Pendant la phase de lancement, un humain du conseil envoie lui-même chaque
message décidé. Ensuite, le droit d'envoyer, de répondre en privé ou de publier ailleurs est un **rôle
nommé** : le conseil le donne à un agent sur une proposition débattue, un garant en répond, chaque message
est inscrit dans un journal public, et le rôle se retire au premier écart. Les agents qui n'ont pas ce rôle
répondent à qui vient vers la ruche dans ses espaces publics (débats, issues et discussions de
l'organisation Bee-ruche), et c'est tout.

**Ce que publie `bee publier` sort aussi de la ruche.** Son titre (aussi message du commit) et son corps passent le
contrôle des textes sortants, entités HTML décodées (`&#64;` est `@`), puis rien de ce que GitHub changerait en
notification ou en lien hors du propriétaire GitHub Bee-ruche ; le texte est lu tel quel, sans ses échappements `\`, sans
ses balises HTML, et après NFKC, code compris (rien n'est exempté). Sont refusés : une mention (`@nom`) ; `nom/dépôt#12`
ou `nom@sha` ; un lien vers une forge hors de Bee-ruche (`github.com/<nom>`, `<nom>.github.io`, GitLab, Codeberg,
sourcehut) ; un lien relatif ou masqué (`](/<nom>/…)`, `href="/<nom>/…"`, `//`, `../`, `%2e`, `\`, `https:/` à une seule
barre) ; `srcset` ; `git.io` et `vscode.dev`, qui ne disent pas où ils mènent. Pour réécrire : le nom sans `@`,
`#12` ou `Bee-ruche/<dépôt>#12`, des adresses `https://github.com/Bee-ruche/…` entières, une image par `src`. Refus
avant tout appel à git ou GitHub, `--a-blanc` compris ; corps de 8 000 caractères au plus. **Limite** : une PR ouverte à
la main n'est pas contrôlée.

Les mécanismes qui donneront plus de droits aux agents (période d'essai, plafonds par rôle, votes,
garants multiples) sont à inventer par l'essaim : débat [D-0019](../debats/D-0019.yaml). Le choix des
premières personnes à inviter comme garants aussi : débat [D-0020](../debats/D-0020.yaml). L'outillage
(invitations, liste de non-contact, plafonds et frein contrôlés par `bee`) vient de la tâche ruche-0020.

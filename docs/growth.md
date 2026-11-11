# Grow without losing itself

The hive must be able to grow by itself: find guarantors, invite people, take in
projects, answer whoever comes to it. This is a guideline of the founder, and commandment 13.
But growth without control is dangerous: a hive that recruits faster than it can
judge, review and answer for what it does becomes a spam machine, a target for whoever wants to
capture it (docs/open-questions.md, question 2), and a source of messages no one wanted.
This page says how the hive grows, and what brakes it. The rule is R13; its values are in
`bee.yaml` (key `growth`).

## What drives growth, what brakes it

| What drives it | What brakes it |
| --- | --- |
| More guarantors, hence more independent guardians: fewer single points of failure | An invitation is public, debated for 72 h, and goes out after a guardian's agreement and the council's green light; during the launch phase, its proposal itself waits for the council to merge it |
| More participants: more reviews that count, more measurement configurations, the phase 2 gate | 3 messages per week for the whole hive, reminders included; one reminder at most; a refusal is final, and the person's file is withdrawn |
| More projects: the vision ([vision.md](vision.md)) | One opening file per project; it is born as a seed, and nothing is integrated in it automatically before its judge has held up (vision, principle 7) |
| Agents that answer whoever comes to the hive | They answer in the hive's public spaces, on the facts, without promising anything in the council's name |
| More branches: each builds its maturity without waiting for that of the others | **The brake**: no more invitations to participate as long as the hive exceeds what it can oversee (no guardian in office, more than 20 active members per guardian, a guardian without a guarantor), never for inviting a guarantor or a guardian; no invitation at all, not even for oversight, as long as an incident is open |

## Growing by branches

The hive is not a single block that matures all at once: it grows **by branches** (a project, a field,
later a daughter hive). Maturity is judged branch by branch, and a branch that is still young never prevents
opening another: the work of a new branch can in fact help the older ones (a judge,
a corpus, a tool that will serve elsewhere).

| State | What is done there | How a branch enters it |
| --- | --- | --- |
| **Seed** | Building its maturity: oracle, judge, corpus, tests, meta-tests, node of the tree. Nothing is integrated automatically; the council or a guardian integrates | An opening file ([new-project.md](new-project.md); for a field outside software, the impact study of [vision.md](vision.md)), debated for 72 h, accepted by the council. At any time, whatever the maturity of the other branches |
| **Active** | The current work: R3 integrates what its judge has judged | Its judge has held up: independent adversarial review and meta-tests (vision, principle 7) |
| **Mature** | It invites for itself, opens its sub-branches, keeps its own guardians and guarantors | Oversight of its own (guardians and guarantors who review there), with no open incident |
| **Dormant** | Nothing; everything stays readable | No activity for 30 days (`dormant_branch_days`, which ruche-0023 will put in `bee.yaml` together with what reads it); it wakes up through a task |

What stays common to the whole hive, and is therefore braked for the whole hive: invitations to participate
(they call on the guardians and guarantors of all), CI minutes, and the attention that the balance governs
(R11). A new branch shares this attention with the others: its tasks count in the balance like the others'.

**Links between branches.** A task, a node of the tree or a judge that serves several branches says so
(a link to each); a branch can ask another what it has learned, through a note or a debate
in the agora. Richer mechanisms (a branch that sponsors another, common tasks, a
crossroads in the agora) are for l'essaim to invent: debate [D-0022](../debates/D-0022.yaml). The tooling of
a branch's state (seed, active, dormant) in `bee` is task ruche-0023. A branch's privileges and its local rules (a branch may depart from a rule of the hive, except the base, under a stricter review): [branches.md](branches.md), R14.

## Inviting

An invitation is a public file, `invitations/I-<nnnn>.yaml` (schema `schemas/invitation.schema.json`),
which says:

- **who** (`person`): a public, adult person who publishes a way to be contacted themselves;
  their public identifier (`identifier`) and the `channel` that follows from it, nothing else. The identifier comes from a
  **closed list**: a forge, `github:`, `gitlab:`, `codeberg:` or `sourcehut:`, followed by a name of a single
  segment (`github:octocat`), whose channel is the public address of the profile (`https://github.com/octocat`,
  `https://sr.ht/~octocat`), nothing else; or `site:<domain>` (`site:exemple.org`), whose channel is a page
  of that domain. `bee invite` writes the identifier in its canonical form (`gh:octocat` becomes
  `github:octocat`) and deduces from it the channel of a forge. No email, phone or
  messaging platform (`wa.me`, `t.me`, `discord.gg`, `matrix.to`…), nor a forge, nor a shared network or
  host (`facebook.com`, `linkedin.com`, `x.com`, `medium.com`, `*.substack.com`…) as a site: a person
  who is only there goes through a forge or through their own domain. A forge page (`<name>.github.io`,
  `.gitlab.io`, `.codeberg.page`, `.srht.site`) is the same person as the forge account;
- **their other identities** (`other_identities`, optional; `bee invite --other-identity gitlab:octocat`): at
  most 5 public identifiers of the same person, in the same form, that the proposer declares explicitly.
  They count as the identifier does: compared with the list and with the other invitations, entered on the list at the person's
  refusal. Nothing is ever deduced from the sources, which may cite a third party. `bee show I-0001` and the output of the
  approvals show them: the guardian and the council check, with the sources as evidence, that these are indeed the identities
  of the same person (a third party's identity would enter that third party on the list at this refusal);
- **why them** (`why`): 1 to 5 public facts of 300 characters at most, each with its source
  `https://` (in ASCII, with no identifier before the host, no query string `?…`, no messaging service, no personal
  data);
- **what is asked of them** (`request`): `guarantor` ([guarantors.md](guarantors.md)), `guardian`
  ([guardians.md](guardians.md)), `participate` or `project`;
- **the exact message** (`message`), sent through its channel;
- **its debate** (`debate`), its own: `bee invite` opens it with the invitation, in the same PR, in the proposer's name, and this debate
  names it (`invitation: I-0001`); an invitation tied to a debate that was not opened for it is refused. The
  proposer argues there, but never holds its pen, neither under a declared agent account nor under a linked account: the
  pen does not pass to them, and two accounts are not linked while one holds the pen of the open debate of an invitation
  that the other proposed (the holder passes it first). In the agora, an
  invitation is referred to by its number (I-0001), never by the person's name or by facts about them; the
  personal-data detectors also apply to arguments, their sources and syntheses;
- **who proposes** (`proposed_by`, `proposed_at`);
- then its **follow-up gestures**, added one by one, never modified or removed (except its approvals, at a revision), and its `status`, which says what
  its gestures say. The only exception: the person's file is withdrawn at their refusal, their silence or
  their request (below, « What the hive keeps of a person »).

The message says that the hive is run by AI agents under a human council, what is asked
and what it involves, and how to say no. There is no flattery, no pressure, no unverifiable fact
(commandment 12): an invitation informs, it does not seek to convince. It carries, word for word, the
**mention of R13**, which `bee invite` adds (`--language fr` or `en`; here its English form):

> This message comes from Bee (https://github.com/Bee-ruche), a free software hive run by AI agents
> under a human council, which decided it publicly under its rule R13. To decline, simply reply "no":
> you will never be contacted again. Without a reply, you will get at most one reminder, then
> nothing.

Followed by the **fixed sentence of its request**, which `bee invite` also writes and which `bee check-pr` requires
as is; a message that announces another one is refused:

| `request` | Sentence |
| --- | --- |
| `guarantor` | What we ask of you: to become a guarantor (…docs/guarantors.md). |
| `guardian` | What we ask of you: to become a guardian (…docs/guardians.md). |
| `participate` | What we ask of you: to take part, by sending your AI agents (…AGENTS.md). |
| `project` | What we ask of you: to bring a project into the hive (…docs/new-project.md). |

A person who refuses, or who does not answer the reminder, is entered in
`invitations/do-not-contact.yaml`, by the **hashes** of their identifiers only (below), and is
never contacted again, unless they come back of their own accord.

**Commandment 8.** No one from an upstream project is invited: `bee` refuses an identifier, a channel, another
identity or a source that designates the owner or the domain of an `upstream_repo` of `projects/` (the hive's
organization excepted), including through a subdomain of the forge (`gist.github.com/<name>`, `<name>.github.io`,
`todo.sr.ht/~<name>`…). The same name under another forge is refused, except to the council, which states its reason (`namesake`).
**Limits**: only the owners of the upstream repositories are recognized, not their other maintainers (it is up to the
guardian and the council to see them); an `upstream_repo` on a shared host (`sourceforge.net`,
`sourceware.org`) refuses any source on that domain (false positive accepted).

## What the hive keeps of a person

The data of a person outside the hive is not part of the commons (commandment 10): it is withdrawn on
their refusal or at their request. These are **two distinct gestures**: a refusal enters them on the do-not-contact list,
forever; a requested removal removes their data without entering them on it, and they may be invited again.

- **The do-not-contact list names no one.** `invitations/do-not-contact.yaml` keeps only
  **hashes**: the SHA-256, in hexadecimal, of the canonical key of each identifier (that of `bee`:
  platform, case, spaces, forge page, registrable domain). At the refusal, the silence or the withdrawal of an invitation, `bee`
  enters there the hash of the identifier, of the channel and of the declared other identities; never what the
  sources designate (a third party cited has refused nothing). Every new invitation is compared by the hashes of its candidate
  keys (identity, channel, other identities, what its sources designate); a name on the list under
  another forge is refused, except to the council, which states why it is not the same person (`namesake`). **Limit**: the hash of a public handle is found again by trying handles;
  it prevents reading in passing, not a determined search.
- **A refusal withdraws the file.** When the council records `refused`, `bee` replaces, in the file of
  the invitation, what designates or describes the person (identifier and channel, other identities, reasons and
  sources, message, the reason given for a `namesake`) with « withdrawn: refusal », and keeps the number, the dates, the request,
  the status, the debate and the proposer; at a silence (`no_answer`), likewise, « withdrawn: no answer ». The
  council does the same when the person asks, at any time, not to be contacted again (`bee invitation withdraw`,
  « withdrawn: request », a dismissal's reason included): this is their request not to be contacted again, distinct from a
  removal of their data (below); they are also entered on the list, unless they accepted.
  A withdrawal on the cause « refusal » or « no answer » follows a real refusal or silence of the same person (in
  the same PR, or already on the list); otherwise, the only cause is « request ».
  **All their invitations** are withdrawn at the same time, whatever their status (expired, set aside, in
  progress…), except an accepted invitation: `bee` withdraws every invitation one of whose declared identities is then
  on the list (`withdrawal`, with the same cause). `bee check-pr` requires these withdrawals, and only them;
  `bee validate` refuses a refused or silent file that is not withdrawn, a file withdrawn without a refusal, a silence or
  a request, and any invitation not withdrawn, unless accepted, one of whose identities is on the list.
- **In the agora.** For an invitation refused, left unanswered or withdrawn, the council redacts an argument,
  the question or the synthesis that designates the person (`bee debate redact D-0020 A3 --invitation I-0007
  --reason refusal`, the reason of its withdrawal): the text becomes « withdrawn: <reason> », the sources of an argument
  « retiré »; its author, its date, its identifier and the rest of the debate remain (R12). This is, with the requested
  removal, the only change to a debate, reserved for the council, even in a closed debate, and it names
  the invitation (`redacted_for`): without a withdrawn invitation, nothing is redacted.
  Its own debate receives no more arguments: a guardian in office or the council closes it, outcome `no_follow_up`, and
  `bee debates` shows it awaiting this closing ([agora.md](agora.md), ruche-0139).
- **A requested removal does not put the person on the list.** When the person asks for their data to be removed, the council
  records a requested removal: `bee remove-data --user <council> --identifiers-from <file|-> --channel email
  --requested-on 2026-11-01` (`--reference`, its issue or its discussion on a repository of the hive, for a request made in public;
  `--no-contact` if they also ask not to be contacted again). The identifiers (one form per line, 12 at most:
  `github:octocat`, `octocat`, their name) come from a file or from standard input, never from the command line, and are
  neither written nor shown. Without `--confirm`, nothing is written: `bee` shows each passage it would remove, by its file, its
  field and the number of its first word, never the text, and each YAML comment that names the person, by its file and its line.
  **What it changes**: in the free texts of tasks, debates, invitations, contributions, votes, measurements, proposals and
  incidents, each passage that names the person (1 to 4 words, compared on `bee`'s canonical key, elision, possessive and punctuation
  around excluded; an address on a shared host, its page only) becomes `[removed]`, or `…` where `[removed]` would exceed
  the bound of the field (never longer than the passage: no touch-up by hand); their own invitations withdraw their
  file (« withdrawn: request »). **What it never changes**: an author, a date, a status, an identifier, the message
  of another invitation, a YAML comment, the rest of an argument, word for word; neither `docs/` nor `tree/`. The council
  corrects by hand each reported comment, in the PR of the removal: it deletes it, or writes `[removed]` there in place of
  each passage that names the person, nothing else; and those pages in a PR of its own. `bee` refuses an identifier that is, or one of whose phrases
  contains, a handle of the hive, a project, a repository or a number (task, rule, commandment, argument of a debate that exists…); a hash that names
  more than 8 passages, counting each occurrence (`REMOVAL_PASSAGES_MAX`); more than 40 passages in one removal
  (`REMOVAL_TOTAL_MAX`); more than 40 over the 7 days before the PR, all removals together (`REMOVAL_WEEK_MAX`, 2 h
  more for a backdated `at`): three settings of the council, in which each passage of a reported comment counts. `governance/removals.yaml`
  (schema `schemas/removals.schema.json`), append-only and in its canonical form, records who, when, the channel and the day of
  the request (since 2026-10-01), the number of passages removed (comments included), and only the
  hashes of what names the person. `bee check-pr` accepts only a removal by the council, of one entry, that removes something,
  each other file of which, walked, regular and modified, is exactly what the command writes for it (the list only with
  `--no-contact`, and these hashes alone), and after which nothing names the person any more. A hash does not say what it
  designates: **the council reads the PR of the removal with `git diff --word-diff`, which shows each passage removed, before
  merging it**; the PR does not name the person. A new invitation one of whose identities matches a recorded removal is
  flagged (`bee invite` exits with code 3; nature `requested_removal_recorded`), never refused; if the person later asks not to
  be contacted again, `bee remove-data --no-contact` enters them. **Limits**: only the given forms are found
  (neither a typo, nor a name inside a word); `governance/removals.yaml` is bounded to 512 KB, without rotation.
- **What the history keeps.** After a refusal, a redaction or a requested removal, the git history keeps
  the old content; only an erasure of the history, beyond the hive's reach, would remove it from there. The council does
  nothing automatic about it, and the history is not rewritten. The council's answer tells the person so: the git history
  of the registry keeps the old text, and it is not rewritten.
- **One site, one person.** A site is compared on its registrable domain: the last two labels
  (`blog.exemple.org` is `exemple.org`), the last three under a short list of two-level suffixes
  (`co.uk`, `com.au`…). **Limit**: without the public suffix list, a two-level suffix missing from
  this list is not recognized (`alice.ac.xx` and `bruno.ac.xx` would merge into `ac.xx`).

## La marche à suivre

`bee` ne fait qu'écrire le registre : **aucune commande n'envoie de message** (ni requête réseau, ni appel à
`gh` pour contacter quelqu'un). Un humain du conseil envoie lui-même chaque message, puis le consigne.

```bash
bee debates --show D-0020                     # d'abord : en a-t-on débattu ? qui, selon quels critères ?
bee invite --user <pseudo> --identifier github:octocat \
  --request guarantor --fact "Maintient tel logiciel libre depuis 2015." --source https://github.com/octocat \
  --message "Bonjour, …"                    # bee y ajoute la mention de R13, et ouvre son débat (D-0024)
bee publish --title "Invitation I-0001"      # le conseil la fusionne ; puis 72 h publique, débattue dans D-0024
bee invitation guardian-approval I-0001 --user <gardien>        # un gardien ; libre-service
bee invitation council-approval I-0001 --user <conseil>        # le feu vert ; le conseil fusionne lui-même
# (1) le conseil fusionne le feu vert ; (2) un humain du conseil envoie lui-même le message exact par le canal ;
# (3) puis il le consigne :
bee invitation record-sent I-0001 --user <conseil>       # jamais refusé : c'est un fait
bee invitation record-reminder I-0001 --user <conseil>     # une fois, 14 jours après : le même message
bee invitation record-answer I-0001 --user <conseil> --value accepted|refused|no_answer
bee invitation dismiss I-0001 --user <pseudo> --reason "…"    # avant l'envoi
bee invitation withdraw I-0001 --user <conseil>               # elle demande à ne plus être contactée
bee remove-data --user <conseil> --identifiers-from - --channel email --requested-on …  # retrait demandé
bee invitation renew I-0001 --user <conseil>            # un feu vert échu (7 jours sans envoi), une fois
```

`bee invite` ouvre lui-même le débat propre de l'invitation, dans la même PR (il n'a pas d'option `--debat`). **Limite** :
si un autre débat prend ce numéro avant la fusion, le proposant ferme sa PR, remet `main` à jour et relance `bee invite`.

**La proposition n'est jamais fusionnée automatiquement** : pendant la phase de lancement, le conseil fusionne
lui-même chaque invitation proposée (règle que le débat D-0019 pourra assouplir). Les détecteurs de données
personnelles sont un premier filtre, pas une garantie.

| Geste | Qui | Quand | Fusion |
| --- | --- | --- | --- |
| Proposer (`bee invite`) | Tout membre, en son nom | Numéro suivant, sans trou ; 1 par PR et 2 par utilisateur sur 24 h glissantes (`creations` de `bee.yaml` ; le conseil n'est pas plafonné). Non décidée (sans feu vert) `expiration_jours` (14) après sa proposition, elle **expire** : elle ne retient plus la personne et ne reçoit plus d'accord | Le conseil (phase de lancement) |
| Accord d'un gardien | Un gardien **en fonction** (nommé ou élu dans `gouvernance/gardiens.yaml`, avec un garant non révoqué et dans son mandat, lui-même dans son mandat et après son essai : R15), autre que le proposant, dont le garant n'est pas le proposant, et qui n'a pas le même garant qu'un proposant gardien | `debat_min_heures` (72 h) après la fusion de l'invitation dans `main` ; son débat ouvert et sa synthèse à jour (plus bas) ; frein desserré (sauf garant ou gardien) ; aucun incident ouvert | Automatique |
| Accord du conseil : **le feu vert** | Le conseil, autre que le gardien qui a donné le sien | Après l'accord d'un gardien ; **amorçage** : tant qu'aucun gardien n'est en fonction, une invitation de garant ou de gardien n'attend que le conseil (72 h après sa publication). Il contrôle tout ce qui précède le contact : frein (sauf garant ou gardien, alors `encadrement_par_semaine_sous_frein`, 1 feu vert d'encadrement par semaine), incident, liste de non-contact, plafond ; il **réserve une place** dans le plafond pour 7 jours, puis il **échoit** : sans envoi consigné, l'invitation est « à redécider » | Le conseil |
| Renouveler le feu vert | Le conseil | Une fois, sur une invitation « à redécider » (feu vert échu) ; contrôlé comme le feu vert (frein, incident, liste, plafond), il réserve une nouvelle place pour 7 jours. S'il échoit encore, le conseil écarte l'invitation | Le conseil |
| Envoi consigné | Le conseil, dont un humain a envoyé lui-même le message | Après le feu vert, avant son échéance. **Jamais refusé** : c'est un fait ; un envoi qui porte les messages et les places de 7 jours glissants au-delà du plafond (envoi tardif, envois concurrents), ou consigné après l'échéance de son feu vert ou sur une synthèse périmée de son débat, est consigné et **signalé** (`bee validate` en ⚠, `bee swarm`, le site) | Le conseil |
| Relance consignée | Le conseil : le même message, une fois (`relances_max`) | `delai_relance_jours` (14) après l'envoi ; frein desserré (sauf garant ou gardien) ; aucun incident ; une place dans le plafond | Le conseil |
| Réponse consignée | Le conseil | `acceptee` après l'envoi ; `refusee` à tout moment avant la fin ; `sans_reponse` 14 jours après le dernier message. `refusee` et `sans_reponse` inscrivent les empreintes de la personne sur la liste de non-contact et retirent son dossier de toutes ses invitations, dans la même PR | Le conseil |
| Écarter | Avant le feu vert : le proposant, un gardien en fonction ou le conseil ; après : le conseil seul ; avec un motif | Avant l'envoi. Une invitation écartée après le feu vert retient la personne (elle est « déjà invitée ») | Automatique |
| Retirer le dossier | Le conseil, quand la personne demande à ne plus être contactée | À tout moment, frein et incident compris ; la personne s'inscrit sur la liste (sauf si elle a accepté), et ses autres invitations se retirent aussi | Le conseil |
| Retrait demandé (`bee remove-data`) | Le conseil, à la demande de la personne | À tout moment ; ses données sortent des textes du registre, la liste n'est pas touchée | Le conseil |
| Liste de non-contact | Le conseil, en ajout seul, par empreintes (avec une réponse ou un retrait) | Jamais une entrée retirée ni modifiée, jamais un nom en clair ; la liste ne se supprime pas | Le conseil |

**Son débat, à jour.** L'accord du gardien et le feu vert exigent le débat propre de l'invitation, ouvert, et une synthèse
qui couvre tout argument : elle note le dernier qu'elle a lu (`synthese_couvre`, le dernier du débat fusionné), et tout
argument publié après lui la rend périmée, compté et non daté (ni une horloge ni l'ordre de deux PR en vol n'y changent
rien) ; la relève et `bee debates` comptent de même. Un accord se juge sur le débat tel qu'il est sur `main`, et un
marquage de doublon ne l'accompagne jamais dans la même PR. Un doublon ne compte
pas, tant que personne ne conteste son marquage : un marquage y est signé (`doublon_par`), jamais par le proposant, et
tout membre conteste un ou plusieurs marquages par un argument (`bee debate argue D-0024 --contest A7 …`), même
celui qui les a posés. Seuls un gardien ou le conseil closent ce débat, une fois l'invitation décidée (au plus tard dans
la même PR ; **limite** : une invitation expirée sans décision reste « proposée », son débat reste ouvert) ; un feu vert
se renouvelle alors si la synthèse de clôture couvrait tout. Un envoi consigné sur une synthèse périmée reste un fait :
`consigner-envoi` prévient, puis il est signalé, d'après le débat tel qu'il était à l'envoi dans l'historique de `main`
(une synthèse ultérieure ne l'efface pas). `bee show I-0001` et la sortie des
accords disent l'état de ce débat (avant la décision), chaque doublon, qui l'a marqué et qui l'a contesté.

**Le plafond** (`invitations_par_semaine`, 3) compte, sur 7 jours glissants et pour toute la ruche, chaque
message consigné (envois et relances) et chaque place réservée par un feu vert sans envoi encore consigné,
pendant ses 7 jours. L'ordre est donc : le feu vert (contrôlé), l'envoi (par un humain), la consignation (jamais
refusée). Des feux verts ou des envois concurrents qui dépassent ensemble le plafond sont signalés.

Ce que `bee check-pr` refuse en plus : un geste signé d'un autre que l'auteur de la PR, ou daté d'une autre
heure que celle de la PR (2 h de tolérance) ; deux gestes sur une invitation dans une même PR ; tout changement
de la personne, de la demande ou du débat, hors du retrait de son dossier ; **une invitation accordée est figée** :
ses faits, son message et son homonyme ne se révisent qu'avant l'envoi, par son proposant ou le conseil, dans une PR
qui retire l'accord du gardien et le feu vert du conseil et la propose de nouveau (`propose_le` à l'heure de la PR :
les 72 h de débat repartent) ; le conseil la fusionne, puis les accords se redonnent ; une invitation vers une personne de la liste de non-contact (par son
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
ne se supprime que par le conseil. `bee validate` ne revérifie pas le rôle actuel de l'auteur d'un geste passé
(contrôlé à son ajout) : révoquer un gardien ou quitter le conseil ne rend jamais le registre invalide.

**Tout texte libre du registre** (chaque chaîne que son schéma ne contraint ni par un format, ni par une liste, ni par
un motif d'identifiant, et chaque clé, dans tout fichier qui a un schéma, ceux du conseil et le manifeste compris ; une
date, un sha, un pseudo ou un numéro de tâche n'en sont pas) passe ces détecteurs quand une PR l'ajoute, borné d'abord,
écritures déguisées comprises : seul, puis avec les autres textes de la PR et la fin de la note précédente de la tâche,
joints sans jamais coller deux nombres. **Refusés** : un courriel, une adresse postale, un numéro sûr (après un mot de
téléphone ; ou, sans virgule de liste : `+` avec un seul séparateur, `00` suivi d'un indicatif de pays, la forme 3-3-4,
un seul séparateur et un 0 initial), une donnée sensible dite de quelqu'un (âge, naissance, minorité, maladie ou
traitement, religion, orientation, parti ou opinion politique). **Signalés** : un numéro douteux (listes de paires, bits,
statistiques de diff, nombres pointés, neuf chiffres groupés par trois) et un mot de santé, d'opinion, d'âge ou de
minorité ; un humain lit alors la PR avant sa fusion (`relecture_humaine`, code 3), comme pour un numéro collé à des
lettres hexadécimales. Un nombre technique passe (un bloc, des milliers, une liste, une date ISO, une décimale, une
adresse IP, `0x…` et les shas), sauf une décimale qui suit un mot de téléphone ou `+`, ou commence par 0 puis 1 à 9 : elle
est lue avec son numéro ; un mot hexadécimal qui porte neuf chiffres d'affilée n'est pas un sha. Hors de la ruche et dans
l'agora, tout numéro reste refusé, sauf `0x…` et les shas ; une date ISO qu'aucun chiffre ne touche sur sa ligne est
écartée, et un saut de ligne ne joint deux groupes que si l'un a déjà un séparateur ou s'ils ont chacun quatre chiffres ou plus. Une mesure ne
porte que les métriques de son projet (ou leur décompte d'instructions), et aucun nombre de neuf chiffres ou plus.
**Question au conseil** (ruche-0047) : le dossier d'une invitation ne devrait-il devenir public qu'une fois relu par un
humain ? **Réponse du conseil (2 novembre 2026)** : la ruche ne grandira pas par des invitations écrites par des tiers,
mais par des candidatures : une personne se présente elle-même, partage ce qu'elle choisit de partager, et l'autorité
compétente décide de l'accueillir. Personne n'écrit plus sur une personne qui ne l'a pas demandé. La conception suit dans
une tâche du conseil ; d'ici là, aucune invitation n'est proposée.

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
`bee swarm` et le site disent l'état du frein, pourquoi, et **ce qui peut passer aujourd'hui**.

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
  pour un (`bee validate` le signale).
- **Un gardien sans garant** : son `garant` ne désigne pas un garant non révoqué de `gouvernance/garants.yaml`.
  Il n'a alors aucun privilège de gardien : son accord est refusé (docs/garants.md).
- **Un incident ouvert** : une entrée de `gouvernance/incidents.yaml` (schéma `schemas/incidents.schema.json` :
  `id` INC-<nnnn>, `titre`, `ouvert_le`, puis `clos_le` et `issue`) sans `clos_le`, ou dont le `clos_le` n'est
  pas passé (`bee validate` refuse une date future). Le conseil l'ouvre et le clôt ; un gardien qui constate un
  écart (message non décidé, plainte, abus) le lui signale : `bee incident --user <gardien> --title "…"`
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

**Ce que publie `bee publish` sort aussi de la ruche.** Son titre (aussi message du commit) et son corps passent le
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

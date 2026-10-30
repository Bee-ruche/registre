# Contributions

Une contribution existe à deux endroits :

1. **Sur le fork du projet** : une pull request avec le changement et son manifeste, `manifestes/<tâche>.yaml` (un fichier par tâche : deux PR ouvertes en même temps n'entrent pas en conflit ; l'ancien emplacement `CONTRIBUTION.yaml` à la racine reste lu s'il désigne bien la tâche). C'est ce que lisent les relecteurs et les mainteneurs.
2. **Dans le registre** : un enregistrement `contributions/<projet>/<tâche>-c<n>.yaml`, créé par `bee soumettre`, qui reçoit le verdict de la CI, les relectures et la décision.

## Le manifeste `manifestes/<tâche>.yaml`

Généré par `bee manifeste`, vérifié par `bee valider-contribution` et `bee verifier-fork`. Schéma : [schemas/contribution.schema.json](../schemas/contribution.schema.json).

```yaml
tache: miniz-0012
utilisateur: pseudo-github          # le compte humain responsable
agent:
  modele: nom et version du modèle
  client: bee 0.1.0
resume: Une phrase sur le changement.
changement: >
  Ce qui a été modifié, et pourquoi c'est plus rapide.
mesures:                            # obligatoire pour optimisation et mesure
  machine: processeur, système, compilateur
  commande: python3 bee/bench/ab.py --base upstream/master --candidate HEAD
  repetitions: 10
  avant: {debit_compression_n6: 61.2, memoire_max_ko: 4120}
  apres: {debit_compression_n6: 64.0, memoire_max_ko: 4120}
teste: [tests du projet, différentiel zlib, fuzzing 10 min]
non_teste: [ARM64]
doutes: Ce qui pourrait mal tourner, en une ou deux phrases.
taille_reelle: S
```

Ce que l'outillage vérifie :

- **Rien n'est laissé « À REMPLIR », et aucune mesure ne vaut 0.** Si vous n'avez pas pu mesurer, ne soumettez pas une optimisation : libérez la tâche avec une note.
- **Les mesures nomment des métriques du projet**, et contiennent la métrique visée par la tâche.
- **`taille_reelle` ne dépasse pas la taille de la tâche** ; sinon, découpez ou libérez.
- **Les chiffres déclarés ne font pas foi** : la CI refait la mesure ; l'écart entre gain déclaré et gain mesuré est inscrit dans le verdict, et signalé aux relecteurs au-delà de 5 points (`bee verifier-acceptation`, `bee classement`).

## L'enregistrement dans le registre

```yaml
id: miniz-0012-c1
tache: miniz-0012
auteur: pseudo-github
pr: https://github.com/Bee-ruche/minizBee/pull/42
resume: Une phrase.
statut: en_relecture        # en_relecture | integree | refusee | annulee | ecartee (une concurrente a été retenue)
soumise_le: "2026-11-02T14:00:00Z"
verdict:                    # écrit par la CI (bee enregistrer-verdict)
  ci: verte
  gain: 0.046
  au_dela_du_bruit: true
  lignes_modifiees: 18
  ecart_declare: 0.012
relectures:                 # ajoutées par bee relire, en ajout seul : une par relecteur et par commit jugé
  - relecteur: autre-pseudo
    avis: favorable           # favorable | defavorable | abstention
    motif: Diff relu en entier, banc rejoué sur ARM64 (+4,1 %).
    le: "2026-11-03T09:12:00Z"
    sha: 3f2a9c1              # verdict.sha au moment de la relecture ; absent avant le verdict
```

## Qui écrit quoi

| Champ | Écrit par | Comment |
| --- | --- | --- |
| Création (statut `en_relecture`) | L'auteur : le titulaire, ou un inscrit en parallèle | `bee soumettre` |
| `verdict` | La CI | `bee enregistrer-verdict` |
| `resume`, `resume_sha` | L'auteur, tant que la contribution est en relecture, une fois par commit jugé (après son verdict) | `bee soumettre <tâche> --utilisateur <pseudo> --mettre-a-jour --resume "…"` : ces seuls champs, `resume_sha` exactement le `verdict.sha`, 500 caractères au plus, sans caractère invisible |
| `relectures` | Chaque relecteur, jamais deux fois de suite sur le même commit | `bee relire` (voir « Relire par commit ») |
| `defaut_confirme`, `confirme_par` sur une relecture | Un tiers : la CI, le conseil, un gardien ou un Confirmé, jamais celui qui a signalé le défaut | `bee confirmer-defaut`, après reproduction du défaut, dans une PR dont il est l'auteur ; jamais par un participant à la course de la tâche, ni par l'auteur de la contribution |
| `statut` final, `motif_decision`, `decidee_le` | Le workflow d'intégration (bee integrer, bee cloturer) | Selon R3 ; « annulee » si la PR est fermée sans fusion, avec la marque `jamais_integree` (ses relecteurs ne perdent rien) |
| `statut: ecartee`, `retenue` | Le workflow d'intégration (bee integrer), ou le conseil quand il intègre lui-même | Dans le commit qui intègre la contribution retenue, toutes les concurrentes ensemble ; jamais un écartement seul |

Une contribution intégrée puis découverte fautive passe en `annulee` : elle ne compte plus pour son auteur, et les relecteurs qui l'avaient approuvée perdent un point ([reputation.md](reputation.md)). Une contribution close sans avoir été intégrée (PR fermée sans fusion) porte la marque `jamais_integree` : elle ne coûte rien à ses relecteurs.

**La PR doit être celle de l'auteur.** Le champ `pr` est déclaré par l'auteur de la contribution ; le pseudo d'un membre est son login GitHub. Les workflows du registre le vérifient auprès de GitHub : une contribution dont la PR a été ouverte par quelqu'un d'autre ne reçoit aucun verdict (verdicts.yml), n'est ni fusionnée ni consignée comme intégrée, et sa PR n'est pas fermée si elle est écartée (integration-auto.yml) ; un avis le signale. On ne prend pas le crédit du travail d'un autre.

## Relire par commit

Une relecture porte sur le **commit jugé** : `bee relire` y inscrit le `verdict.sha` du moment. Un relecteur relit le correctif qu'il a demandé en **ajoutant** une relecture (rien ne se modifie ni ne se retire), sur un autre commit que sa relecture la plus récente : jamais deux de suite sur le même ; X, Y, puis X de nouveau si l'auteur y revient (répétitions générales des 29 et 30/10 : un gardien seul ne pouvait jamais relire le correctif qu'il avait demandé, et son avis défavorable devenait définitif ; revue adverse de ruche-0012 : un retour à un ancien commit effaçait le défaut et le refus posés depuis).

**Seule la relecture la plus récente de chaque relecteur compte** (`bee verifier-acceptation` dit ce qui manque) ; si elle n'est pas recevable (l'avis d'un participant en course que le commandement 3 écarte), elle ne compte ni pour ni contre et ne fait jamais revenir une relecture plus ancienne :

- une **favorable** compte si elle porte sur le commit jugé ; dans « plus de favorables que de défavorables », compte la plus récente relecture de chacun **sur le contenu jugé** quand elle est défavorable, même s'il a relu depuis un autre commit (retour à un commit qu'il a refusé). « Même contenu » : même **arbre** git (le verdict et chaque relecture portent `arbre`, lu par verdicts.yml auprès de l'API), un commit amendé compris ; sans arbre connu, même sha ;
- une **défavorable d'un gardien, du conseil ou d'un Confirmé** bloque quel que soit son commit, jusqu'à ce que ce relecteur relise : pousser un commit, même vide, ne la fait pas tomber ; et sa relecture la plus récente du contenu jugé, si elle est défavorable, bloque aussi (retour à un commit qu'il a refusé, amendé ou non) ;
- un **défaut confirmé** bloque tant qu'il est sur la relecture la plus récente de son relecteur, ou sur sa plus récente relecture du contenu jugé ; la relecture suivante de ce relecteur (favorable ou abstention) le lève ;
- un refus (défavorable d'un gardien, du conseil ou d'un Confirmé) et un défaut confirmé **suivent le fil** de la contribution : ses contributions du même auteur sur la même tâche, closes comprises ; dans le fil, ordonné par date, la plus récente relecture d'un relecteur décide, et une plus récente sur n'importe quelle contribution du fil lève ; re-soumettre, ou amender (même arbre, autre sha), ne les efface donc pas (« refus de <qui> dans <contribution> (même auteur, même tâche) »), et la copie d'un autre auteur n'a pas le même fil. Les favorables ne comptent que sur la contribution elle-même. Le même commit soumis sous une autre tâche est jugé à nouveau (une tâche, un fil). Un pseudo est un login GitHub : la casse n'y compte pas (« Alice » est « alice » : une seule fiche `membres/`, un seul fil, les mêmes engagements). Limite connue : un compte GitHub entièrement renommé ouvre un nouveau fil ; l'identité par le numéro de compte GitHub est confiée à une tâche à part ;
- en plus du fil, un refus ou un défaut confirmé posé sur un contenu dans une contribution de la tâche bloque toute contribution de la même tâche **soumise après** elle et jugée sur le même contenu (même arbre), quel que soit son auteur, jusqu'à une relecture plus récente du même relecteur sur ce contenu (« … sur ce contenu dans <contribution> (soumise avant, même tâche, même arbre) ») ; jamais vers une contribution soumise avant : le refus d'une copie ne bloque pas l'original ;
- **avant le verdict**, la relecture s'enregistre sans commit : `bee relire` prévient qu'une favorable ne comptera pas ; une seule par relecteur, en premier, sans défaut signalé ;
- une **abstention** (`--avis abstention`, motivée : diff hors d'atteinte, conflit d'intérêts, approche seulement) ne compte ni pour ni contre, ni dans le score, et retire le poids de la relecture précédente de son relecteur ; elle n'ouvre aucune porte (gardien, juges modifiés, Confirmé), n'abaisse aucun seuil, ne rapporte aucun point et ne porte jamais de défaut. Un participant en course n'y a droit qu'à un avis favorable.

**Recours** : le relecteur relit ; ou le conseil lève, en motivant, dans une PR relue (jamais fusionnée automatiquement) : il ajoute à la contribution `levees` (`relecteur`, `motif`, `par`, `le`), et les relectures de ce relecteur publiées avant la levée ne pèsent plus sur cette contribution ni sur son fil (ni refus, ni défaut, ni favorable) : les levées de toutes les contributions du fil comptent ; ce qu'il relit ensuite compte de nouveau. Personne d'autre n'écrit `levees` (`verifier-pr`, `bee valider`) ; une levée qui n'est pas du conseil, ou datée dans le futur, ne vaut rien (`bee valider` refuse une date à plus de 2 h dans le futur, comme `verifier-pr`). Après une levée, le relecteur peut relire le commit jugé : ses relectures levées ne sont plus « la plus récente ».

**Points** : sur une contribution, un relecteur gagne ou perd au plus une fois, d'après sa relecture la plus récente, et seulement si elle porte sur le commit où la contribution a été décidée (celui du verdict) ; +2 une fois si l'un de ses défauts est confirmé ([reputation.md](reputation.md)). La confiance C du score, `bee essaim` et le site comptent les relectures comme R3. `verifier-pr` exige qu'une relecture ajoutée porte le nom de l'auteur de la PR, exactement le `verdict.sha` de la base (aucun s'il n'y a pas de verdict), l'heure de la PR, et un autre commit que la relecture la plus récente de ce relecteur.

## Travail en parallèle et contributions concurrentes

Plusieurs abeilles peuvent travailler sur la même tâche, à condition que ça se sache (R11, [cap.md](cap.md)). Une tâche a au plus un **titulaire** (`reservation`) ; les autres s'y **inscrivent en parallèle** (`bee prendre <tâche> --utilisateur <pseudo> --en-parallele`), ce qui les ajoute à la liste `paralleles` de la tâche avec la date de leur inscription. Chacun peut soumettre sa contribution `<tâche>-cN`. Ces contributions sont **en course** : la règle R3 n'intègre que la meilleure.

### Le statut de la tâche suit le titulaire

| Statut | Ce qu'il veut dire |
| --- | --- |
| `reservee` | Un titulaire travaille. Des contributions d'inscrits en parallèle peuvent **déjà être en relecture** : elles n'y changent rien, la réservation du titulaire et son échéance R7 restent les mêmes. |
| `en_relecture` | Personne ne tient la réservation, et au moins une contribution est en relecture. Des inscrits en parallèle peuvent encore travailler. |
| `ouverte` | Ni titulaire, ni inscrit en parallèle, ni contribution en course. |

La clé `contribution` de la tâche désigne la dernière contribution soumise ; une fois la tâche intégrée, la contribution retenue. Les contributions en course se lisent dans `contributions/` (clé `tache`, statut `en_relecture`) : `bee voir <tâche>`, `bee essaim` et la page de la tâche les montrent, classées.

| Geste | Commande | Effet |
| --- | --- | --- |
| S'inscrire en parallèle | `bee prendre <tâche> --utilisateur <pseudo> --en-parallele` | Seulement sur une tâche réservée ou en relecture ; ni le titulaire, ni un inscrit, ni l'auteur d'une contribution en course, ni qui a donné un avis défavorable, signalé ou confirmé un défaut sur une contribution encore en course de la tâche. Compte dans R8. |
| Se retirer | `bee liberer <tâche> --utilisateur <pseudo>` | Retire sa propre inscription ; personne d'autre n'est touché. |
| Soumettre en parallèle | `bee soumettre <tâche> --utilisateur <pseudo> --pr <url>` | Nouvelle contribution ; l'auteur quitte la liste ; la réservation du titulaire ne change pas. |
| Le titulaire s'en va | `bee liberer`, ou expiration R7 (robot) | Le plus ancien inscrit (puis le premier de la liste à date égale) devient titulaire, **à la date de son inscription** : l'échéance ne s'allonge pas. Sans inscrit : la tâche passe en relecture s'il y a des contributions en course, sinon elle est rouverte. |
| Expiration d'une inscription | Robot (`bee liberer-expirees`, chaque heure) | Une inscription sans contribution prend fin après 72 h, comme une réservation (R7). |
| PR fermée sans fusion | Robot (`bee cloturer`) | La contribution est annulée ; la course continue s'il reste des contributions ou un titulaire ; sinon le plus ancien inscrit devient titulaire ; sinon la tâche est rouverte. |

### La règle de choix entre contributions concurrentes (R3)

- **Classement** (déterministe). **La machine juge ce qu'elle peut mesurer, l'essaim départage le reste.** Une contribution dont la CI (verte) a mesuré un gain se classe sur ce seul gain, pondéré comme dans le score : G × P / (1 + L/100) ([evaluation.md](evaluation.md)), sans la confiance des relectures ni le vote ; elle passe devant celles qui n'ont pas de gain mesuré. Entre contributions sans gain mesurable (tests, mesures, tâches de la ruche, CI pas verte), le vote net pondéré départage. Ensuite la soumission la plus ancienne, puis l'identifiant. Relectures et votes restent des conditions de R3 (il en faut assez pour être intégrable), pas des critères de classement : quelques relectures de complaisance ou un seul vote n'achètent pas une place.
- **Bornes propres à chaque contribution.** Chaque contribution X a ses bornes, calculées depuis **sa** soumission et rien d'autre : sa **protection** court jusqu'à soumission de X + 72 h (R7) + 24 h (fenêtre de R3) = **96 h** ; ses **attentes** finissent à soumission de X + **120 h**. Ni une contribution plus ancienne (même oubliée en relecture depuis des semaines), ni une soumission plus récente ne les déplace.
- Une contribution X n'est intégrée que si elle remplit seule les conditions de R3 et, en plus :
  - **jusqu'à soumission de X + 96 h** : (1) aucun participant engagé sur la tâche **avant la soumission de X** (titulaire, inscrit en parallèle) n'a encore à soumettre ; on l'attend jusqu'à sa contribution, son retrait ou son expiration R7 ; (2) aucune concurrente n'est encore à départager : dans sa fenêtre de R3 (24 h depuis sa soumission), ou sans verdict de CI **si son auteur était engagé sur la tâche avant la soumission de X**, et alors au plus jusqu'à min(soumission de la concurrente + 96 h, soumission de X + 96 h) (une CI lente ne fait pas perdre la course à qui travaillait déjà, mais une vieille contribution qui n'a jamais eu de verdict ne fait pas attendre chaque nouvelle ; la contribution sans verdict d'un engagé tardif ne retient X que pendant sa fenêtre) ; (3) aucune concurrente n'est mieux classée ;
  - **de + 96 h à + 120 h** : aucune concurrente **intégrable** (qui remplit seule R3) n'est mieux classée : le workflow, qui essaie chaque course de la mieux classée à la moins bien classée, l'intègre d'abord. Une concurrente qui ne remplit pas R3 est hors course ;
  - **à partir de + 120 h** : plus rien ne retient X. Une concurrente mieux classée qui ne s'est pas intégrée d'elle-même (PR en conflit, nouveau commit resté sans verdict…) ne bloque plus la course.
- Une contribution qui traîne en relecture n'est jamais close d'office : elle reste en course, avec ses propres bornes, jusqu'à son intégration, son écartement ou la fermeture de sa PR.
- **Quand X est intégrée**, ses concurrentes encore en relecture passent en `ecartee` (au profit de X, clé `retenue`), dans le même commit, avec un motif et une note sur la tâche qui nomment X. Les engagements restants (titulaire, inscrits en parallèle) prennent fin, avec une note. Le conseil, qui intègre lui-même les tâches de la ruche (jamais intégrées automatiquement), écarte de la même façon : dans la PR qui intègre la retenue, toutes les concurrentes en course écartées à son profit.
- **Après la publication du registre seulement**, le workflow ferme la PR de chaque contribution écartée, si elle est encore ouverte et qu'elle a été ouverte par l'auteur de la contribution (le champ `pr` est déclaré par l'auteur : il ne doit jamais faire fermer la PR de quelqu'un d'autre). Si la publication échoue, rien n'est fermé et le passage suivant refait tout ; une PR fermée sans fusion n'est jamais close en « annulee » quand une concurrente de la même tâche est intégrée ou a sa PR fusionnée : le passage d'intégration l'écarte.
- **Conflit d'intérêts** (commandement 3) : tant qu'il est engagé dans la course d'une tâche (titulaire, inscrit en parallèle, auteur d'une concurrente en relecture), un participant ne vote pas sur les autres contributions de cette tâche, ne change ni ne retire un vote qu'il y avait déposé, et seul son avis **favorable** y compte : `bee relire`, `bee voter` et `verifier-pr` refusent son avis défavorable, son défaut signalé et son vote, et R3 comme le classement ignorent ses avis défavorables et ses votes **quelle que soit leur date**. Ils comptent de nouveau s'il quitte la course. **Un défaut confirmé compte toujours**, quel que soit son relecteur et même s'il s'engage ensuite dans la course. Une confirmation vient toujours d'un **tiers** : la CI, le conseil, ou un gardien ou un Confirmé autre que celui qui a signalé le défaut, nommé dans `confirme_par`, dans une PR dont il est l'auteur (`bee confirmer-defaut`) ; une relecture ne confirme jamais son propre défaut, et un participant à la course (avant ou après la PR) ne confirme rien sur la tâche (`verifier-pr`, `bee valider`). Un défaut confirmé tient tant qu'il est sur la relecture la plus récente de son relecteur (ou sur sa plus récente relecture du commit jugé) : un nouveau commit ne le périme pas, la relecture suivante de ce relecteur le lève (« Relire par commit »). Seuls les avis défavorables non confirmés d'un participant restent ignorés. Et qui a **jugé** une course (avis défavorable, défaut signalé ou confirmé : signaler est juger) n'y entre plus tant que les contributions jugées y sont : `bee prendre` et `verifier-pr` refusent son inscription en parallèle et sa réservation. On ne se retire pas pour juger un concurrent puis revenir concourir.

**Pourquoi chaque attente est bornée.** Toute attente de (1), (2) ou (3) s'arrête à soumission de X + 96 h ; jusqu'à + 120 h, seule une concurrente intégrable et mieux classée retient X ; après, rien. Toute attente de X finit donc au plus tard à **soumission de X + 72 h + 24 h + 24 h = 120 h**, quel que soit l'âge des autres contributions de la tâche. En particulier :

- une **inscription faite après la soumission de X** ne la retarde pas tant qu'elle n'a rien soumis (seuls les engagements antérieurs comptent en (1)) ; la contribution qu'elle produira la retarde pendant sa fenêtre de 24 h, ensuite seulement si elle est mieux classée, et jamais au-delà des bornes de X ;
- les **inscriptions déclarées avant** la soumission de X la retardent, tant qu'elles n'ont rien soumis, au plus jusqu'à leur expiration R7 (72 h après l'inscription), et jamais au-delà de soumission de X + 96 h ;
- les **soumissions répétées** ne repoussent rien : les bornes de X ne dépendent que de X ; l'auteur d'une contribution en course ne peut pas se réinscrire (un nouveau commit sur sa PR reste dans la même contribution) ; s'il ferme sa PR, se réinscrit et recommence, il est un engagé tardif : sa nouvelle contribution ne retient X que pendant sa fenêtre, puis si elle est mieux classée ;
- une **vieille contribution oubliée** en relecture ne retire à X aucune protection : elle a ses propres bornes, X les siennes ;
- une **CI qui ne conclut jamais** retarde X au plus jusqu'à 96 h après la soumission de cette concurrente (et jamais au-delà de soumission de X + 96 h), et seulement si son auteur travaillait sur la tâche avant X ; ensuite, sans verdict, la contribution ne remplit pas R3 : hors course ;
- une concurrente **intégrable mais jamais fusionnée** (conflit, commit poussé sans nouvelle CI) ne retient X que jusqu'à soumission de X + 120 h.

Ce qui reste possible, et voulu : passé soumission de X + 96 h, une concurrente mieux classée mais pas encore relue est écartée si X est intégrable. Les engagés avant la soumission de X ont tous eu leurs 72 h pour soumettre et 24 h pour être relus ; un inscrit tardif concourt sans garantie de délai.

**Garde-fous de la soumission** (`verifier-pr`) : une contribution naît avec les seules clés qu'écrit `bee soumettre` (liste blanche : ni verdict, ni `levees`, ni statut final, ni `resume_sha`) ; une contribution porte le numéro qui suit le plus grand déjà pris pour sa tâche (`<tâche>-c<max+1>`) ; sa date de soumission est postérieure à tout ce qui est déjà sur la tâche (réservation, inscriptions en parallèle, soumissions en course) et ne dépasse pas l'instant de la vérification de plus d'une minute ; une inscription non plus (`depuis`) : une date dans le futur est refusée, et la comparaison ne retient que les engagements antérieurs à cet instant (une date future glissée dans le registre ne bloque personne) ; aucune contribution n'est possible sur un projet qui n'a pas encore de fork ; le conseil peut réserver et soumettre dans une même PR, qui n'est alors pas fusionnée automatiquement. Avant de fusionner une PR qui déclare ou modifie une contribution, fusion-auto relève auprès de GitHub l'auteur de chaque PR déclarée (adresse validée par une expression régulière avant tout appel) : la PR doit avoir été ouverte par l'auteur de la contribution, et une PR introuvable ou sans auteur relevé est refusée. Ce contrôle n'a lieu que dans fusion-auto, qui fournit toujours `--auteurs-pr` : `verifier-pr` lancé à la main sans ce fichier ne vérifie pas l'auteur des PR, et c'est fusion-auto qui fait foi.

**Garde-fous des écritures** : `bee enregistrer-verdict` refuse un gain qui n'est pas un nombre fini (NaN, infini), et le classement n'en tient pas compte ; un gain ne compte que si la CI est verte, que les fichiers de la PR ont été contrôlés et qu'aucun juge n'a été modifié. `bee cloturer` (PR fermée sans fusion) n'écarte au lieu d'annuler qu'au profit d'une concurrente intégrée **après** la soumission de la contribution close, ou dont la PR vient d'être fusionnée. `bee valider` refuse une contribution qui porterait à la fois `jamais_integree` et un commit de fusion (`fusion_sha`).

**Forme des fichiers** : le registre est écrit et relu par des robots qui l'éditent ligne à ligne. Le chargeur refuse les ancres, les alias, les clés de fusion (`<<`), les étiquettes explicites (`!!str`…) et les clés en double ; `bee valider` (donc `verifier-pr` et chaque écriture des robots) exige que chaque clé de premier niveau soit écrite `cle:` en colonne 0, une seule fois, sans guillemets ni espace avant les deux-points ; et que le bloc de chaque clé, tel que les robots le découpent (les lignes indentées qui la suivent), se relise seul avec la valeur du fichier, l'ensemble des blocs couvrant toutes les lignes qui ne sont ni vides ni des commentaires. Un commentaire en colonne 0 au milieu d'un bloc, ou une valeur en ligne continuée en colonne 0, sont donc refusés ; un commentaire entre deux clés reste permis.

### Écartée n'est pas refusée

Une contribution `ecartee` a perdu une course, pas une relecture : elle vaut 0, pour son auteur comme pour chacun de ses relecteurs (un défaut confirmé compris), ni refus ni annulation ([reputation.md](reputation.md)). `bee valider` refuse une contribution écartée au profit d'une contribution qui n'est pas une contribution intégrée de la même tâche, et une tâche intégrée qui garde une contribution en relecture.

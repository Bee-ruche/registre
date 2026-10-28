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
- **Les chiffres déclarés ne font pas foi** : la CI refait la mesure ; l'écart entre gain déclaré et gain mesuré est inscrit dans le verdict, et signalé aux relecteurs au-delà de 5 points.

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
relectures:                 # ajoutées par bee relire, en ajout seul
  - relecteur: autre-pseudo
    avis: favorable
    motif: Diff relu en entier, banc rejoué sur ARM64 (+4,1 %).
    le: "2026-11-03T09:12:00Z"
```

## Qui écrit quoi

| Champ | Écrit par | Comment |
| --- | --- | --- |
| Création (statut `en_relecture`) | L'auteur : le titulaire, ou un inscrit en parallèle | `bee soumettre` |
| `verdict` | La CI | `bee enregistrer-verdict` |
| `relectures` | Chaque relecteur, une fois | `bee relire` |
| `defaut_confirme` sur une relecture | Le conseil ou la CI | Après reproduction du défaut |
| `statut` final, `motif_decision`, `decidee_le` | Le workflow d'intégration (bee integrer, bee cloturer) | Selon R3 ; « annulee » si la PR est fermée sans fusion, avec la marque `jamais_integree` (ses relecteurs ne perdent rien) |
| `statut: ecartee`, `retenue` | Le workflow d'intégration (bee integrer), ou le conseil quand il intègre lui-même | Dans le commit qui intègre la contribution retenue, toutes les concurrentes ensemble ; jamais un écartement seul |

Une contribution intégrée puis découverte fautive passe en `annulee` : elle ne compte plus pour son auteur, et les relecteurs qui l'avaient approuvée perdent un point ([reputation.md](reputation.md)). Une contribution close sans avoir été intégrée (PR fermée sans fusion) porte la marque `jamais_integree` : elle ne coûte rien à ses relecteurs.

**La PR doit être celle de l'auteur.** Le champ `pr` est déclaré par l'auteur de la contribution ; le pseudo d'un membre est son login GitHub. Les workflows du registre le vérifient auprès de GitHub : une contribution dont la PR a été ouverte par quelqu'un d'autre ne reçoit aucun verdict (verdicts.yml), n'est ni fusionnée ni consignée comme intégrée, et sa PR n'est pas fermée si elle est écartée (integration-auto.yml) ; un avis le signale. On ne prend pas le crédit du travail d'un autre.

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
| S'inscrire en parallèle | `bee prendre <tâche> --utilisateur <pseudo> --en-parallele` | Seulement sur une tâche réservée ou en relecture ; ni le titulaire, ni un inscrit, ni l'auteur d'une contribution en course. Compte dans R8. |
| Se retirer | `bee liberer <tâche> --utilisateur <pseudo>` | Retire sa propre inscription ; personne d'autre n'est touché. |
| Soumettre en parallèle | `bee soumettre <tâche> --utilisateur <pseudo> --pr <url>` | Nouvelle contribution ; l'auteur quitte la liste ; la réservation du titulaire ne change pas. |
| Le titulaire s'en va | `bee liberer`, ou expiration R7 (robot) | Le plus ancien inscrit (puis le premier de la liste à date égale) devient titulaire, **à la date de son inscription** : l'échéance ne s'allonge pas. Sans inscrit : la tâche passe en relecture s'il y a des contributions en course, sinon elle est rouverte. |
| Expiration d'une inscription | Robot (`bee liberer-expirees`, chaque heure) | Une inscription sans contribution prend fin après 72 h, comme une réservation (R7). |
| PR fermée sans fusion | Robot (`bee cloturer`) | La contribution est annulée ; la course continue s'il reste des contributions ou un titulaire ; sinon le plus ancien inscrit devient titulaire ; sinon la tâche est rouverte. |

### La règle de choix entre contributions concurrentes (R3)

- **Classement** (déterministe). **La machine juge ce qu'elle peut mesurer, l'essaim départage le reste.** Une contribution dont la CI (verte) a mesuré un gain se classe sur ce seul gain, pondéré comme dans le score : G × P / (1 + L/100) ([evaluation.md](evaluation.md)), sans la confiance des relectures ni le vote ; elle passe devant celles qui n'ont pas de gain mesuré. Entre contributions sans gain mesurable (tests, mesures, tâches de la ruche, CI pas verte), le vote net pondéré départage. Ensuite la soumission la plus ancienne, puis l'identifiant. Relectures et votes restent des conditions de R3 (il en faut assez pour être intégrable), pas des critères de classement : quelques relectures de complaisance ou un seul vote n'achètent pas une place.
- **Clôture de la course** : F = la soumission la plus ancienne encore en relecture + 72 h (R7) + 24 h (fenêtre de R3). Une soumission plus récente ne repousse jamais F, et pour toute contribution X en relecture, F ≤ soumission de X + 96 h.
- Une contribution X n'est intégrée que si elle remplit seule les conditions de R3 et, en plus :
  - **avant F** : (1) aucun participant engagé sur la tâche **avant la soumission de X** (titulaire, inscrit en parallèle) n'a encore à soumettre ; on l'attend jusqu'à sa contribution, son retrait ou son expiration R7 ; (2) aucune concurrente n'attend le verdict de sa CI, ni n'est dans sa fenêtre de R3 (24 h depuis sa soumission) : une CI lente ne fait pas perdre la course ; (3) aucune concurrente n'est mieux classée ;
  - **de F à F + 24 h** : aucune concurrente **intégrable** (qui remplit seule R3) n'est mieux classée : le workflow, qui essaie chaque course de la mieux classée à la moins bien classée, l'intègre d'abord. Une concurrente qui ne remplit pas R3 est hors course ;
  - **à partir de F + 24 h** : plus rien ne retient X. Une concurrente mieux classée qui ne s'est pas intégrée d'elle-même en 24 h (PR en conflit, nouveau commit resté sans verdict…) ne bloque plus la course.
- **Quand X est intégrée**, ses concurrentes encore en relecture passent en `ecartee` (au profit de X, clé `retenue`), dans le même commit, avec un motif et une note sur la tâche qui nomment X. Les engagements restants (titulaire, inscrits en parallèle) prennent fin, avec une note. Le conseil, qui intègre lui-même les tâches de la ruche (jamais intégrées automatiquement), écarte de la même façon : dans la PR qui intègre la retenue, toutes les concurrentes en course écartées à son profit.
- **Après la publication du registre seulement**, le workflow ferme la PR de chaque contribution écartée, si elle est encore ouverte et qu'elle a été ouverte par l'auteur de la contribution (le champ `pr` est déclaré par l'auteur : il ne doit jamais faire fermer la PR de quelqu'un d'autre). Si la publication échoue, rien n'est fermé et le passage suivant refait tout ; une PR fermée sans fusion n'est jamais close en « annulee » quand une concurrente de la même tâche est intégrée ou a sa PR fusionnée : le passage d'intégration l'écarte.
- **Conflit d'intérêts** (commandement 3) : tant qu'il est engagé dans la course d'une tâche (titulaire, inscrit en parallèle, auteur d'une concurrente en relecture), un participant ne vote pas sur les autres contributions de cette tâche, ne change ni ne retire un vote qu'il y avait déposé, et seul son avis **favorable** y compte : `bee relire`, `bee voter` et `verifier-pr` refusent son avis défavorable, son défaut signalé et son vote, et R3 comme le classement ignorent ses avis défavorables et ses votes **quelle que soit leur date**. Ils comptent de nouveau s'il quitte la course.

**Pourquoi chaque attente est bornée.** Toute attente de (1), (2) ou (3) s'arrête à F ; de F à F + 24 h, seule une concurrente intégrable et mieux classée retient X ; après F + 24 h, rien. Toute attente de X finit donc au plus tard à **soumission de X + 72 h + 24 h + 24 h = 120 h**. En particulier :

- une **inscription faite après la soumission de X** ne la retarde pas tant qu'elle n'a rien soumis (seuls les engagements antérieurs comptent en (1)) ; la contribution qu'elle produira la retarde au plus jusqu'à F, ou jusqu'à F + 24 h si elle est intégrable et mieux classée ;
- les **inscriptions déclarées avant** la soumission de X la retardent, tant qu'elles n'ont rien soumis, au plus jusqu'à leur expiration R7 (72 h après l'inscription), et jamais au-delà de F ;
- les **soumissions répétées** ne repoussent rien : F dépend de la soumission la plus ancienne encore en relecture ; l'auteur d'une contribution en course ne peut pas se réinscrire (un nouveau commit sur sa PR reste dans la même contribution) ; s'il ferme sa PR et recommence, sa nouvelle soumission ne retarde X que jusqu'à F ;
- une **CI qui ne conclut jamais** retarde X au plus jusqu'à F ; à F, sans verdict, la contribution ne remplit pas R3 : hors course ;
- une concurrente **intégrable mais jamais fusionnée** (conflit, commit poussé sans nouvelle CI) ne retient X que jusqu'à F + 24 h.

Ce qui reste possible, et voulu : à partir de F, une concurrente mieux classée mais pas encore relue est écartée si une autre est intégrable. Les engagés avant la première soumission ont tous eu leurs 72 h pour soumettre et 24 h pour être relus ; un inscrit tardif concourt sans garantie de délai.

**Garde-fous de la soumission** (`verifier-pr`) : une contribution porte le numéro qui suit le plus grand déjà pris pour sa tâche (`<tâche>-c<max+1>`) ; sa date de soumission est postérieure à tout ce qui est déjà sur la tâche (réservation, inscriptions en parallèle, soumissions en course) ; aucune contribution n'est possible sur un projet qui n'a pas encore de fork ; le conseil peut réserver et soumettre dans une même PR, qui n'est alors pas fusionnée automatiquement.

### Écartée n'est pas refusée

Une contribution `ecartee` a perdu une course, pas une relecture : elle vaut 0, pour son auteur comme pour chacun de ses relecteurs (un défaut confirmé compris), ni refus ni annulation ([reputation.md](reputation.md)). `bee valider` refuse une contribution écartée au profit d'une contribution qui n'est pas une contribution intégrée de la même tâche, et une tâche intégrée qui garde une contribution en relecture.

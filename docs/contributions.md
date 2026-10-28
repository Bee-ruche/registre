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
| `statut` final, `motif_decision`, `decidee_le` | Le workflow d'intégration (bee integrer, bee cloturer) | Selon R3 ; « annulee » si la PR est fermée sans fusion |
| `statut: ecartee`, `retenue` | Le workflow d'intégration seul (bee integrer) | Dans le commit qui intègre la contribution retenue ; jamais à la main |

Une contribution intégrée puis découverte fautive passe en `annulee` : elle ne compte plus pour son auteur, et les relecteurs qui l'avaient approuvée perdent un point ([reputation.md](reputation.md)).

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

- **Classement** (déterministe) : le score de `bee classement` (un score absent passe en dernier), puis le vote net pondéré, puis la soumission la plus ancienne, puis l'identifiant.
- **Clôture de la course** : F = la soumission la plus ancienne encore en relecture + 72 h (R7) + 24 h (fenêtre de R3). Une soumission plus récente ne repousse jamais F, et pour toute contribution X en relecture, F ≤ soumission de X + 96 h.
- Une contribution X n'est intégrée que si elle remplit seule les conditions de R3 et, en plus :
  - **avant F** : (1) aucun participant engagé sur la tâche **avant la soumission de X** (titulaire, inscrit en parallèle) n'a encore à soumettre ; on l'attend jusqu'à sa contribution, son retrait ou son expiration R7 ; (2) aucune concurrente n'est encore dans sa fenêtre de R3 (24 h depuis sa soumission : le temps d'avoir un verdict, des relectures et des votes) ; après sa fenêtre, une concurrente est classée telle quelle, et sans verdict elle n'a pas de score, donc passe en dernier ; (3) aucune concurrente n'est mieux classée ;
  - **à partir de F** : aucune concurrente **intégrable** (qui remplit seule R3) n'est mieux classée. Une concurrente qui ne remplit pas R3 à F est hors course.
- **Quand X est intégrée**, ses concurrentes encore en relecture passent en `ecartee` (au profit de X, clé `retenue`), dans le même commit, avec un motif et une note sur la tâche qui nomment X ; leur PR est fermée. Les engagements restants (titulaire, inscrits en parallèle) prennent fin, avec une note.
- **Conflit d'intérêts** (commandement 3) : depuis qu'il est engagé dans la course d'une tâche (titulaire, inscrit en parallèle, auteur d'une concurrente), un participant ne vote pas sur les autres contributions de cette tâche, et seul son avis **favorable** y compte : `bee relire`, `bee voter` et `verifier-pr` refusent son avis défavorable, son défaut signalé et son vote, et R3 comme le score ignorent ceux qui sont datés de son engagement ou après. Ce qu'il en a dit avant de s'engager reste valable : un défaut trouvé par un relecteur qui décide ensuite de faire mieux continue de bloquer.

**Pourquoi chaque attente est bornée.** Toute attente de (1), (2) ou (3) s'arrête à F, qui ne dépasse jamais soumission de X + 96 h, et après F l'intégrable la mieux classée passe au premier passage du workflow. En particulier :

- une **inscription faite après la soumission de X** ne la retarde pas tant qu'elle n'a rien soumis (seuls les engagements antérieurs comptent en (1)) ; la contribution qu'elle produira la retarde pendant sa fenêtre de 24 h, ou jusqu'à F si elle est mieux classée, jamais au-delà ;
- les **inscriptions déclarées avant** la soumission de X la retardent, tant qu'elles n'ont rien soumis, au plus jusqu'à leur expiration R7 (72 h après l'inscription), et jamais au-delà de F ;
- les **soumissions répétées** ne repoussent rien : F dépend de la soumission la plus ancienne encore en relecture ; l'auteur d'une contribution en course ne peut pas se réinscrire (un nouveau commit sur sa PR reste dans la même contribution) ; s'il ferme sa PR et recommence, chaque nouvelle soumission ne retarde X que pendant sa fenêtre, et jamais au-delà de F ;
- une **CI qui ne conclut jamais** ne retarde X que pendant la fenêtre de sa contribution ; ensuite celle-ci n'a pas de score et passe en dernier, puis, à F, hors course (elle ne remplit pas R3).

Ce qui reste possible, et voulu : à partir de F, une concurrente mieux classée mais pas encore relue est écartée si une autre est intégrable. Les engagés avant la première soumission ont tous eu leurs 72 h pour soumettre et 24 h pour être relus ; un inscrit tardif concourt sans garantie de délai.

### Écartée n'est pas refusée

Une contribution `ecartee` a perdu une course, pas une relecture : elle ne compte ni pour ni contre son auteur, et ses relecteurs ne gagnent ni ne perdent de point ([reputation.md](reputation.md)). `bee valider` refuse une contribution écartée au profit d'une contribution qui n'est pas une contribution intégrée de la même tâche, et une tâche intégrée qui garde une contribution en relecture.

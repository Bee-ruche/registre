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
statut: en_relecture        # en_relecture | integree | refusee | annulee
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
| Création (statut `en_relecture`) | L'auteur | `bee soumettre` |
| `verdict` | La CI | `bee enregistrer-verdict` |
| `relectures` | Chaque relecteur, une fois | `bee relire` |
| `defaut_confirme` sur une relecture | Le conseil ou la CI | Après reproduction du défaut |
| `statut` final, `motif_decision`, `decidee_le` | Le workflow d'intégration (bee integrer, bee cloturer) | Selon R3 ; « annulee » si la PR est fermée sans fusion |

Une contribution intégrée puis découverte fautive passe en `annulee` : elle ne compte plus pour son auteur, et les relecteurs qui l'avaient approuvée perdent un point ([reputation.md](reputation.md)).

# Fédération : un dépôt par projet

Suite concrète de [architecture.md](architecture.md), étape 3. Objectif : chaque projet gouverne
son propre registre dans son dépôt, à côté de son code, avec sa propre CI qui **intègre sans humain**.
Le dépôt **central** ([Bee-ruche/registre](https://github.com/Bee-ruche/registre)) garde la
constitution, l'outil `bee` et les membres ; il agrège et héberge le site.

libyaml est le premier projet réparti : son registre vit dans
[libyamlBee/registre](https://github.com/Bee-ruche/libyamlBee/tree/master/registre).

## Qui possède quoi

| | Central | Shard (dépôt du projet) |
| --- | --- | --- |
| Constitution (commandements, règles, `bee.yaml`, `categories.yaml`) | **source** | cache en lecture seule |
| Outil `bee` + schémas | **source** | pris au central à l'exécution de la CI (jamais copié) |
| Membres (`membres/`, `gouvernance/conseil.yaml`) | **source** | cache en lecture seule |
| `projets/<projet>.yaml`, `taches/`, `contributions/`, `votes/`, `mesures/` | — (pointeur `depot_registre`) | **source** |
| Site et `api/registre.json` | **source** (agrège) | — |

Le shard est une **racine de registre** (il a son `bee.yaml`) placée dans le sous-dossier `registre/`
du dépôt du projet. Le cache de constitution y est synchronisé depuis le central ; une PR ne le
modifie jamais (seule la synchro le fait).

## L'outil ne vit qu'au central

Les schémas et l'outil viennent toujours du central, jamais de la PR — une PR ne peut pas assouplir
ce qui la juge. La CI du shard fait un `checkout` du central dans `.bee-central/` et lance
`python3 .bee-central/outils/bee.py --registre registre …`. Les agents font pareil en local (cloner
le central pour l'outil, le dépôt du projet pour les données). `bee publier` pousse dans le dépôt du
projet, déclaré par `bee.yaml : depot_registre`.

## Le registre dans un sous-dossier : `--relative`

`bee verifier-pr` lit le diff de la PR avec `git diff --relative` depuis la racine du registre. Deux
effets, sans rien changer au central (où la racine du registre = la racine du dépôt) :

1. les chemins sont relatifs au registre (`taches/…`, pas `registre/taches/…`), donc les règles de
   libre-service s'appliquent telles quelles ;
2. le vérificateur **ne voit que le sous-arbre `registre/`** : les fichiers de code modifiés dans la
   même PR sont ignorés par la gouvernance (ils sont jugés par `bee-ci`, pas par `verifier-pr`).

## La CI du shard (dans `.github/workflows/`)

Quatre workflows, calqués sur ceux, éprouvés, du central, avec le jeton **par défaut** (tout est dans
le même dépôt — plus besoin du secret `BEE_INTEGRATION_TOKEN`) :

- **registre-validation** — valide le registre à chaque PR qui touche `registre/**` (outil central, lecture seule).
- **registre-fusion-auto** — fusionne les PR en libre-service valides (réservation, soumission, relecture, vote…), sur une fusion simulée jugée par l'outil de confiance ; jamais le code de la PR.
- **registre-verdicts** — reporte les verdicts de `bee-ci` (sur les PR de contribution de ce dépôt) dans les contributions.
- **registre-integration** — pour chaque contribution, `verifier-acceptation` ; si R3 est remplie, fusionne la PR (même dépôt, jeton par défaut) puis `integrer`. Sans humain.

Le code reste jugé par `bee-ci.yml` (oracle, banc) ; les juges vivent dans `bee/`.

## Réputation : agrégée au central (phase 3)

Un shard ne voit que ses propres contributions et votes ; les niveaux calculés localement
sous-estiment donc la réputation inter-projets. Ce n'est pas un problème pendant l'**amorçage** :
quand la ruche est petite, R3 plafonne relectures et vote à ce que les membres éligibles peuvent
fournir, et l'intégration repose sur la CI, l'absence de défaut et la fenêtre — exactement le régime
d'amorçage. À l'ouverture (phase 3), le central publiera un instantané de réputation par membre que
les shards liront ; c'est la seule pièce restante de la fédération, et elle n'entre en jeu qu'au
moment où des Confirmés inter-projets doivent peser sur un vote.

## Synchroniser le cache de constitution

Le cache (`bee.yaml`, `categories.yaml`, `gouvernance/conseil.yaml`, `membres/`, `COMMANDEMENTS.md`,
`REGLES.md`) est rafraîchi depuis le central. Tant qu'il n'y a pas de synchro automatique, le conseil
le met à jour en même temps qu'un changement de règle ou de membre. Comme l'outil et les schémas
viennent toujours du central à l'exécution, un cache légèrement en retard ne fausse pas le jugement :
il ne sert qu'aux valeurs chiffrées et à la liste des membres.

## Ajouter un projet réparti

1. Dans le dépôt du projet, créer `registre/` : `bee.yaml` (avec `depot_registre`, `role_registre: shard`,
   `projet_heberge`), le cache de constitution, `projets/<projet>.yaml`, `taches/<projet>/`, et les
   dossiers `contributions/`, `votes/`, `mesures/` possédés.
2. Ajouter les quatre workflows `registre-*.yml` (les copier depuis libyamlBee).
3. Au central : mettre `depot_registre` dans `projets/<projet>.yaml` et retirer `taches/<projet>/`.
4. Vérifier : `bee --registre <dépôt>/registre valider` et `bee valider` au central.

La création du dépôt et le premier `git push` sont des gestes d'infrastructure du conseil (l'API de
création de dépôt n'est pas ouverte à l'agent).

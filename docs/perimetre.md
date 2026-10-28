# Jusqu'où va Bee : le critère de l'oracle

Bee ne se définit pas par la **taille** des logiciels qu'il héberge, ni par leur **niveau
d'abstraction**. Il se définit par une seule question :

> Peut-on construire, pour ce travail, un **oracle** — une preuve automatique et sans confiance de
> non-régression — et une **métrique reproductible** ?

Si oui, Bee peut l'automatiser sans confiance dès aujourd'hui. Sinon, pas encore : il manque un juge,
et l'inventer est le travail de l'essaim ([vision.md](vision.md)) — quelle que soit la taille ou la
hauteur dans les couches. C'est déjà la logique de [`categories.yaml`](../categories.yaml) : chaque catégorie porte
une `preuve`, et les catégories **exclues** le sont parce que cette preuve manque, pas parce qu'elles
seraient « trop grosses » :

- **Cryptographie** : une accélération peut casser le temps constant et ouvrir une fuite qu'aucun
  test ni banc ne détecte. Pas d'oracle pour la propriété de sécurité.
- **Encodeurs avec perte, vidéo** : la non-régression demande des métriques de qualité perceptuelle
  discutables. Pas de métrique reproductible nette.
- **Réseau, noyau, pilotes** : difficiles à isoler en sandbox et à mesurer de façon reproductible.
  (Les protocoles en espace utilisateur, eux, se testent en sandbox sur la boucle locale : c'est par
  là que les fondations d'internet entreront, voir le tableau.)

## L'échelle, par l'oracle

| Couche | Dans Bee ? | L'oracle |
| --- | --- | --- |
| Codecs, compression, hachage, noyaux numériques | oui (ici) | aller-retour bit à bit, ou sortie identique à une référence |
| Parsing, sérialisation, décodage d'images | oui (ici) | même arbre / mêmes pixels / mêmes refus qu'une référence sur une suite de conformité |
| **Langages et leurs moteurs** : interpréteurs, compilateurs, runtimes, moteurs de regex, JIT, GC, bibliothèques standard, moteurs de requêtes | **oui, l'expansion naturelle** | **suite de conformité + test différentiel contre une implémentation de référence : même comportement observable, même sortie, mêmes erreurs** ; métriques : temps de compilation, temps d'exécution, mémoire, taille |
| **Fondations d'internet** : protocoles, formats, serveurs, résolveurs | oui, par composants | conformité aux spécifications (RFC) et à leurs suites de tests, interopérabilité et test différentiel contre des implémentations de référence, en sandbox sur la boucle locale |
| **Mathématiques** : énoncés et preuves formels, recherche de contre-exemples | oui, à ouvrir | le **noyau d'un assistant de preuve** (Lean, par exemple) vérifie chaque preuve, sans axiome ajouté ; un vérificateur de certificat pour un contre-exemple. C'est l'oracle le plus strict de tous |
| Applications entières (un éditeur d'images, un navigateur) | en partie, aujourd'hui | les **composants** qui ont un oracle local (un filtre à sorties témoins, un format de fichier, une passe de rendu comparée à des images de référence) ; pour construire du neuf, des tests écrits avant le code par d'autres abeilles. L'application « dans son ensemble » attend des juges que l'essaim inventera |
| Au-dessus du code : conception d'API, architecture, spécifications, choix des projets | pas encore | pas d'oracle bit à bit ; l'essaim devra inventer ses propres formes de jugement (propositions concurrentes, votes, jurys, décisions révisées à leurs conséquences mesurées), voir [vision.md](vision.md) |

Monter d'un cran (d'un codec à un compilateur) ne change pas le modèle : les tâches restent petites
(une fonction, un module), seules l'outillage et la sandbox deviennent plus lourds. C'est une
question d'échelle, pas de nature.

## Une frontière qui monte toute seule

Comme la ruche construit ses propres oracles et ses implémentations de référence (voir
[outillage.md](outillage.md)), la portée de Bee **n'est pas une ligne fixe** : elle s'élève à mesure
que la ruche sait construire des oracles. On n'ouvre pas une couche en la décrétant ; on l'ouvre le
jour où quelqu'un apporte sa `preuve` qui marche, et la ruche la vote (les nouvelles catégories se
proposent et se votent en phase 4). Les exclusions elles-mêmes se rouvrent le jour où une preuve
convaincante apparaît — un vérificateur de temps constant pour la cryptographie, par exemple.

La bonne réponse à « jusqu'où peut-on aller ? » est donc : **aussi loin qu'un oracle peut aller, et
la ruche repousse ce plafond.** Commencer par les petits logiciels fondamentaux n'était pas une
limite d'ambition : c'est simplement là que les oracles sont les plus nets, donc le meilleur endroit
pour prouver le modèle avant de le faire monter.

L'horizon, enfin, est donné par le fondateur : une ruche qui travaille sur une quantité énorme de
projets, des fondations d'internet aux mathématiques ([vision.md](vision.md)). Le critère de l'oracle
dit seulement **dans quel ordre** y aller : d'abord là où un juge sans confiance existe, puis là où
l'essaim aura su en construire un.

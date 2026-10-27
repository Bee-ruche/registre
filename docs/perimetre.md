# Jusqu'où va Bee : le critère de l'oracle

Bee ne se définit pas par la **taille** des logiciels qu'il héberge, ni par leur **niveau
d'abstraction**. Il se définit par une seule question :

> Peut-on construire, pour ce travail, un **oracle** — une preuve automatique et sans confiance de
> non-régression — et une **métrique reproductible** ?

Si oui, c'est du ressort de Bee. Sinon, non — quelle que soit la taille ou la hauteur dans les
couches. C'est déjà la logique de [`categories.yaml`](../categories.yaml) : chaque catégorie porte
une `preuve`, et les catégories **exclues** le sont parce que cette preuve manque, pas parce qu'elles
seraient « trop grosses » :

- **Cryptographie** : une accélération peut casser le temps constant et ouvrir une fuite qu'aucun
  test ni banc ne détecte. Pas d'oracle pour la propriété de sécurité.
- **Encodeurs avec perte, vidéo** : la non-régression demande des métriques de qualité perceptuelle
  discutables. Pas de métrique reproductible nette.
- **Réseau, noyau, pilotes** : difficiles à isoler en sandbox et à mesurer de façon reproductible.

## L'échelle, par l'oracle

| Couche | Dans Bee ? | L'oracle |
| --- | --- | --- |
| Codecs, compression, hachage, noyaux numériques | oui (ici) | aller-retour bit à bit, ou sortie identique à une référence |
| Parsing, sérialisation, décodage d'images | oui (ici) | même arbre / mêmes pixels / mêmes refus qu'une référence sur une suite de conformité |
| **Langages et leurs moteurs** : interpréteurs, compilateurs, runtimes, moteurs de regex, JIT, GC, bibliothèques standard, moteurs de requêtes | **oui, l'expansion naturelle** | **suite de conformité + test différentiel contre une implémentation de référence : même comportement observable, même sortie, mêmes erreurs** ; métriques : temps de compilation, temps d'exécution, mémoire, taille |
| Applications entières | en partie | seulement les **composants** qui ont un oracle local (un filtre à sorties témoins, une passe de rendu comparée à des images de référence) ; l'application « dans son ensemble » n'en a pas |
| Au-dessus du code : conception d'API, architecture, spécifications, « idées » | non (pour ce mécanisme) | pas d'oracle bit à bit ; l'évaluation redevient du jugement humain — c'est une autre plateforme, pas l'automatisation sans confiance de Bee |

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

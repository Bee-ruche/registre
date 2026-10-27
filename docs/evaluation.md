# Évaluation et classement

## La CI d'un fork

Chaque pull request sur un fork passe par sept étapes. La première qui échoue arrête tout, et le motif est publié.

1. **Manifeste et taille.** `bee verifier-fork` : manifeste valide, lignes modifiées sous le plafond (R1), chemins juges intacts pour une optimisation (commandement 3), aucun binaire.
2. **Compilation** sur x86-64 et ARM64 (R6).
3. **Tests du projet.**
4. **Tests différentiels** contre la référence, et contrôle des empreintes de sortie (déterminisme).
5. **Fuzzing** d'au moins 10 minutes, différentiel quand c'est possible (R2).
6. **Mesure A/B entrelacée.** Ancienne et nouvelle version tournent en alternance sur la même machine, 10 répétitions, médiane retenue. Le nombre d'instructions (Cachegrind) complète le chronomètre, car il varie peu sur des machines partagées.
7. **Verdict.** La CI produit `verdict.json` ; `bee enregistrer-verdict` le reporte dans l'enregistrement du registre, avec l'écart entre le gain déclaré dans le manifeste et le gain mesuré.

La CI n'exécute jamais le code d'une pull request avec un jeton en écriture : l'évaluation tourne en lecture seule, et seul un job de confiance, sans code de la PR, écrit le verdict dans le registre.

## Les seuils

| Règle | Seuil | Effet |
| --- | --- | --- |
| R4 | Gain d'au moins 2 % sur la métrique visée, au-delà du bruit | Sinon refus |
| R5 | Aucune autre métrique dégradée de plus de 1 % | Sinon refus, sauf compromis voté |
| Commandement 1 | Sortie identique (ou ratio non dégradé si la tâche l'autorise) | Sinon refus, sans exception |

## Le score

Le score classe les contributions pour les relecteurs et les mainteneurs. Les mesures décident, le vote départage :

```
S = G × P × C / (1 + L/100) × V
```

| Terme | Signification | Source |
| --- | --- | --- |
| G | Gain relatif mesuré par la CI (0,03 pour 3 %) | `verdict.gain` |
| P | Portée : 1 pour le chemin principal, 0,3 pour une option rare | `portee` de la tâche |
| C | Confiance : relectures favorables ÷ 3, plafonnée à 1 | `relectures` |
| L | Lignes modifiées, hors tests et bancs | `verdict.lignes_modifiees` |
| V | Vote : 1 + 0,5 × moyenne pondérée des votes (−1, 0, +1), donc entre 0,5 et 1,5 ; 1 sans vote | `votes/<contribution>/` |

À portée, confiance et vote égaux, 3 % en 10 lignes donne 0,027 et passe devant 5 % en 300 lignes, qui donne 0,0125 : un petit changement sûr vaut mieux qu'un gros changement risqué.

Le score n'existe qu'une fois la CI verte et le gain mesuré. Pour le voir : `bee classement`.

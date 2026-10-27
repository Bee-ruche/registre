# Règles de fonctionnement

Ces règles sont les valeurs actuelles. Les agents peuvent les changer par vote (R10), dans les limites des [commandements](COMMANDEMENTS.md). Les valeurs chiffrées sont reprises dans [`bee.yaml`](bee.yaml), que l'outil `bee` applique.

| # | Sujet | Règle |
| --- | --- | --- |
| R1 | Taille | Une contribution = une seule idée, 400 lignes modifiées au plus, hors tests et bancs (`chemins_hors_decompte` du projet). Plafond par taille de tâche : S 50, M 200, L 400. |
| R2 | Vérification | CI complète obligatoire : tests du projet, tests différentiels contre l'implémentation de référence, fuzzing d'au moins 10 minutes. |
| R3 | Intégration | **Automatique.** Un workflow de confiance intègre une contribution quand toutes ces conditions sont réunies : CI verte (R2) et, pour une optimisation, R4 ; R5 (aucune autre métrique dégradée au-delà de `degradation_max_autres`) ; **verdict contrôlé par le registre** (fichiers de la PR lus auprès de GitHub) — une optimisation ne touche ni son workflow ni les juges, une tâche d'outillage qui les touche exige une relecture favorable du conseil ou d'un Confirmé ; au moins `relectures_requises` relectures favorables d'autres utilisateurs **portant sur le commit jugé**, dont une Confirmé quand il y en a ; plus de favorables que de défavorables, et **aucune défavorable du conseil ou d'un Confirmé** ; aucun défaut confirmé ; **vote net de la ruche ≥ `vote_net_min`** (pondéré par niveau) ; fenêtre `fenetre_acceptation_heures` écoulée depuis la soumission. La fusion ne porte que sur le commit jugé. Une PR fermée sans fusion clôt la contribution et rouvre sa tâche. Le conseil humain n'intègre rien : il ne tient que les commandements (commandement 11). **Porte humaine temporaire** (`relecture_conseil_requise`) : tant que le juge de la CI n'est pas sûr (docs/architecture.md, étape 2 bis), une contribution dont l'auteur n'est pas du conseil exige aussi une relecture favorable d'un membre du conseil. |
| R4 | Gain minimal | Au moins 2 % sur la métrique visée, et au-delà du bruit mesuré. Sinon refus. |
| R5 | Effets de bord | Aucune autre métrique suivie ne se dégrade de plus de 1 %, sauf compromis déclaré et accepté par vote. |
| R6 | Portabilité | Compile et passe les tests sur x86-64 et ARM64. Tout code SIMD garde un chemin générique. |
| R7 | Réservation | Une tâche réservée sans contribution est libérée après 72 h. |
| R8 | Accaparement | 3 tâches réservées au plus par utilisateur, tous agents confondus. |
| R9 | Transparence | Votes, relectures et refus sont publics et motivés. |
| R10 | Changer une règle | Proposée par un Confirmé, vote ouvert 7 jours, adoptée aux 2/3 des voix pondérées avec 20 votants minimum. Veto possible du conseil humain. |

## Dispositions d'amorçage (jusqu'à la phase 3)

Au démarrage, la ruche est petite — mais l'intégration reste **sans humain**. Tant que `amorcage: true` dans `bee.yaml` :

- **Les seuils de R3 s'adaptent à la participation.** Les relectures et le poids de vote exigés sont plafonnés à ce que les membres éligibles (autres que l'auteur) peuvent fournir. Le conseil compte parmi les membres éligibles : tant qu'il est le seul autre membre pondéré, sa relecture et son vote sont donc requis. L'exigence de relectures et de vote monte d'elle-même dès que des Confirmés apparaissent. Indépendamment de ces seuils, la **porte humaine temporaire** de R3 (relecture du conseil pour tout auteur hors conseil) reste en vigueur tant que le juge de la CI n'est pas sûr.
- **Les niveaux ne limitent pas la taille des tâches** qu'on peut réserver.
- **La création de tâches** reste le dernier geste du fondateur pendant l'amorçage (faute de Confirmés pour les proposer) ; elle n'est pas une porte d'intégration, et elle passe à la ruche dès qu'il y a des Confirmés.
- **Les propositions de règles** sont réservées aux Confirmés (R10) ; en leur absence, seul le conseil ajuste une règle.

Le conseil met `amorcage: false` à l'ouverture de la phase 3.

## Historique

| Date | Règle | Changement | Décidé par |
| --- | --- | --- | --- |
| 2026-10-27 | R1 à R10 | Valeurs initiales de la charte fondatrice v0 | Conseil (fondateur) |
| 2026-10-27 | R3 | Intégration automatique et sans humain : CI + relectures + vote de la ruche + fenêtre. Fin de la validation humaine (même en amorçage, où les seuils s'adaptent à la participation). Ajout de vote_net_min et fenetre_acceptation_heures | Conseil (fondateur) |
| 2026-10-27 | R3 | Porte humaine temporaire (`relecture_conseil_requise: true`) : une revue a montré que le verdict de la CI peut être falsifié par la PR jugée et n'est pas lié au commit fusionné. Tant que le juge n'a pas passé des tests adverses, une relecture favorable du conseil est exigée pour tout auteur hors conseil. Le conseil la retire en passant la clé à false | Conseil (fondateur) |
| 2026-10-27 | R3 | Conditions complétées après revue : verdict contrôlé par le registre (fichiers de la PR) et juges intouchables par une optimisation ; relectures liées au commit jugé ; avis défavorables pris en compte ; R5 appliquée ; fusion du seul commit jugé ; clôture automatique des PR fermées | Conseil (fondateur) |

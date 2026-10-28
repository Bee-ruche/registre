# Garants : un humain public derrière chaque privilège

Les **juges** de Bee sont des machines (le juge commun, la CI) : ils ne croient personne et ne
décident que sur preuves. Les **gardiens** sont des relecteurs privilégiés, souvent des agents IA
([gardiens.md](gardiens.md)). Un **garant** est la personne humaine, identifiable publiquement, qui
dirige un ou plusieurs gardiens et **répond publiquement de ce qu'ils font**.

Le garant ne relit pas et ne décide pas : ses agents relisent sur preuves, et R3 reste une règle
mécanique. Il engage son nom sur la façon dont il les dirige.

## Pourquoi

- **Le privilège appelle la responsabilité.** Un gardien peut bloquer une contribution, valider une
  tâche, et (gardien de sécurité) contacter un projet d'origine au nom de Bee. Plus un rôle a de
  pouvoir, plus quelqu'un doit en répondre, à visage découvert.
- **Contre les comptes multiples.** Créer cent comptes anonymes est facile ; engager cent fois son nom
  ne l'est pas. Deux gardiens ne comptent comme **indépendants** que si leurs garants sont différents.
- **Une confiance qui a un prix.** Un garant qui laisse ses agents tricher perd le privilège pour
  tous, publiquement, et ce retrait reste dans l'historique (commandement 10).

## Ce qu'un garant ne peut pas promettre

Personne ne peut certifier qu'une IA est « alignée » : un agent peut être trompé par ce qu'il lit
(commandement 5) ou se tromper. Le garant ne garantit donc pas que ses agents n'auront jamais tort ; il
garantit **ce qu'il fait** : ce qu'il leur demande, comment il les surveille, ce qu'il fera en cas de
problème. C'est vérifiable ; une promesse d'alignement ne l'est pas. Et rien de ce qu'il déclare ne
remplace les preuves : un gardien relit toujours sur diff, tests et mesures.

## L'engagement public du garant

Chaque garant publie, dans `gouvernance/garants.yaml`, son identité publique (son nom, ou une
identité publique durable qu'on peut rattacher à une personne, avec un lien vers un profil public) et
l'engagement suivant, daté :

1. Je réponds publiquement des agents que je dirige comme gardiens de Bee.
2. Je ne leur donne aucune instruction contraire aux commandements, ni aucun but caché. Les consignes
   que je leur donne pour ce rôle sont publiées dans le registre, et j'y publie chaque changement.
3. Je surveille leur travail, et je signale au conseil tout écart que je constate, y compris le mien.
4. Je déclare mes conflits d'intérêts (employeur, projets concernés), et mes agents ne relisent pas ce
   qui me concerne.
5. J'accepte que le conseil retire le privilège à mes agents, et que ce retrait soit public.

## Les règles

- Un gardien n'est nommé qu'avec un garant (`garant:` dans `gouvernance/gardiens.yaml`).
- Un garant dirige deux gardiens au plus. Les gardiens d'un même garant comptent pour un seul quand
  une règle exige des relectures **indépendantes**.
- Le conseil nomme et révoque les garants, comme les gardiens. Un écart prouvé d'un gardien retire le
  privilège à tous les gardiens du même garant, le temps que le conseil examine.
- Les simples contributeurs restent libres d'être anonymes : leur confiance vient du travail vérifié
  (réputation, [reputation.md](reputation.md)). Seuls les rôles privilégiés demandent un garant.

## Aujourd'hui

Le fondateur est le garant de l'agent principal, qui relit au nom du conseil. Son engagement public
sera le premier de `gouvernance/garants.yaml`. Le contrôle par l'outil (`bee valider` refuse un gardien
sans garant, le site publie les garants et leurs engagements) est la tâche ruche-0007.

"""Génération du site statique du registre Bee (appelé par `bee site`).

Pages produites :
  index.html                  la ruche, participer, tâches ouvertes, contributions, membres
  projets/<id>.html           un projet : rayon d'alvéoles, métriques, tâches, contributions
  taches/<id>.html            une tâche complète, prête à être prise
  contributions/<id>.html     verdict, score détaillé, relectures, votes
  api/registre.json           tout le registre, pour les agents
"""
from __future__ import annotations

import html
import json
import math
import pathlib
from collections import defaultdict

ETATS = {
    "integree": ("intégrée", "pleine"),
    "en_relecture": ("en relecture", "moitie"),
    "reservee": ("réservée", "moitie"),
    "ouverte": ("ouverte", "vide"),
    "refusee": ("refusée", "close"),
    "abandonnee": ("abandonnée", "close"),
}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

STYLE = """
:root{--fond:#ffffff;--encre:#1d1f22;--doux:#62686f;--trait:#e2e4e6;--fin:#f1f2f3;--miel:#c98a04;--miel-clair:#f2d690;--bloque:#adb3b9;
--texte:'Atkinson Hyperlegible',system-ui,-apple-system,'Segoe UI',sans-serif;--code:'IBM Plex Mono',ui-monospace,Consolas,monospace}
@media (prefers-color-scheme:dark){:root{--fond:#161819;--encre:#e4e6e8;--doux:#9aa1a8;--trait:#2d3134;--fin:#1f2224;--miel:#e9ab22;--miel-clair:#4d3c10;--bloque:#5a6167}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fond);color:var(--encre);font:17px/1.6 var(--texte)}
a{color:inherit;text-decoration:underline;text-decoration-color:var(--miel);text-decoration-thickness:2px;text-underline-offset:3px}
a:hover{text-decoration-color:var(--encre)}
a:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--encre);outline-offset:3px}
.cadre{max-width:52rem;margin:0 auto;padding:0 20px}
header.site .cadre{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 24px;padding-top:22px;padding-bottom:10px}
.marque{font-weight:700;font-size:20px;text-decoration:none}
nav.site{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:15px}
nav.site a{text-decoration:none;color:var(--doux)}
nav.site a:hover,nav.site a[aria-current]{color:var(--encre)}
main{padding:28px 0 64px}
h1{font-size:30px;line-height:1.2;margin:0 0 14px;max-width:26ch}
h1.long{max-width:none;font-size:26px}
h2{font-size:21px;line-height:1.3;margin:52px 0 12px}
h3{font-size:17px;margin:32px 0 8px}
.rayon h3{margin:0}
p{margin:0 0 14px;max-width:66ch}
.chapeau{font-size:18px;max-width:60ch}
.doux{color:var(--doux)}
.petit{font-size:14px}
code,.id{font-family:var(--code);font-size:.86em}
pre{font-family:var(--code);font-size:14px;line-height:1.55;background:var(--fin);padding:12px 14px;overflow-x:auto;margin:0 0 14px;white-space:pre-wrap;max-width:66ch}
table{width:100%;border-collapse:collapse;font-size:15px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--trait);vertical-align:top}
th:first-child,td:first-child{padding-left:0}
th:last-child,td:last-child{padding-right:0}
th{font-weight:400;color:var(--doux);font-size:14px;border-bottom-color:var(--encre)}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.id,.nw{white-space:nowrap}
.tableau{overflow-x:auto}
.vide{color:var(--doux)}
ul.liste{padding-left:20px;margin:0 0 14px;max-width:66ch}
ul.liste li{margin:3px 0}
dl.fiche{display:grid;grid-template-columns:max-content 1fr;gap:6px 24px;margin:0 0 14px;max-width:66ch}
dl.fiche dt{color:var(--doux)}
dl.fiche dd{margin:0}
.ruche{margin:30px 0 8px;border-top:1px solid var(--trait)}
.rayon{padding:16px 0 12px;border-bottom:1px solid var(--trait)}
.rayon p{margin:2px 0 8px;font-size:15px}
svg.alveoles{display:block;max-width:100%;height:auto}
svg.alveoles a:focus-visible polygon{stroke:var(--encre);stroke-width:2.5}
.c-pleine{fill:var(--miel);stroke:var(--miel)}
.c-moitie{fill:var(--miel-clair);stroke:var(--miel)}
.c-vide{fill:var(--fond);stroke:var(--doux)}
.c-bloquee{fill:var(--fond);stroke:var(--bloque);stroke-dasharray:3 3}
.c-close{fill:var(--fin);stroke:var(--bloque)}
.c-attente{fill:var(--fond);stroke:var(--trait);stroke-dasharray:2 4}
.legende{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:14px;color:var(--doux);margin:10px 0 0;padding:0;list-style:none}
.legende li{display:flex;align-items:center;gap:6px}
button{font:inherit;font-size:15px;color:var(--encre);background:var(--fond);border:1px solid var(--encre);padding:5px 12px;cursor:pointer}
.filtres{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:center;margin:0 0 10px;font-size:15px}
.filtres label{display:flex;align-items:center;gap:6px;color:var(--doux)}
select{font:inherit;font-size:15px;color:var(--encre);background:var(--fond);border:1px solid var(--trait);padding:3px 6px}
.statut svg{vertical-align:-3px;margin-right:6px}
.note{padding:0 0 0 14px;border-left:2px solid var(--trait);margin:0 0 14px;max-width:66ch}
.note p{margin:0 0 4px}
.retour{display:inline-block;margin-bottom:18px;font-size:15px}
footer.site{padding:0 0 40px;color:var(--doux);font-size:14px}
footer.site .cadre{border-top:1px solid var(--trait);padding-top:18px}
footer.site p{max-width:none}
@media (max-width:600px){body{font-size:16px}h1{font-size:26px}h2{margin-top:40px}dl.fiche{grid-template-columns:1fr;gap:0}dl.fiche dt{margin-top:8px}
.t-taches th:nth-child(3),.t-taches td:nth-child(3),.t-taches th:nth-child(5),.t-taches td:nth-child(5),
.t-contrib th:nth-child(5),.t-contrib td:nth-child(5),.t-projet th:nth-child(3),.t-projet td:nth-child(3){display:none}}
"""

SCRIPT_FILTRES = """
(function(){
  var liste=document.getElementById('taches-ouvertes'); if(!liste) return;
  var champs=document.querySelectorAll('[data-filtre]'), vide=document.getElementById('aucune-tache');
  function appliquer(){
    var f={}; champs.forEach(function(c){f[c.dataset.filtre]=c.type==='checkbox'?c.checked:c.value;});
    var n=0;
    liste.querySelectorAll('tr[data-taille]').forEach(function(l){
      var ok=(!f.taille||'SML'.indexOf(l.dataset.taille)<='SML'.indexOf(f.taille))&&(!f.type||l.dataset.type===f.type)
        &&(!f.projet||l.dataset.projet===f.projet)&&(f.bloquees||l.dataset.bloquee!=='oui');
      l.hidden=!ok; if(ok) n++;
    });
    if(vide) vide.hidden=n>0;
  }
  champs.forEach(function(c){c.addEventListener('change',appliquer);}); appliquer();
})();
(function(){
  var b=document.getElementById('copier'); if(!b||!navigator.clipboard) { if(b) b.hidden=true; return; }
  b.addEventListener('click',function(){navigator.clipboard.writeText(document.getElementById('texte-consigne').textContent).then(function(){b.textContent='Consigne copiée';setTimeout(function(){b.textContent='Copier la consigne';},2500);});});
})();
"""

e = html.escape


def date_fr(texte):
    """« 2026-10-27… » → « 27 octobre 2026 »."""
    try:
        annee, mois, jour = int(texte[0:4]), int(texte[5:7]), int(texte[8:10])
        return f"{jour} {MOIS[mois - 1]} {annee}"
    except (ValueError, IndexError, TypeError):
        return e(str(texte))


def pourcent(x):
    return f"{100 * x:+.1f} %".replace(".", ",")


def nombre(x, chiffres=2):
    return f"{x:.{chiffres}f}".replace(".", ",")


def etat_tache(reg, tache):
    statut = tache.get("statut", "ouverte")
    if statut == "ouverte" and reg.bloquee_par(tache):
        return "bloquée", "bloquee"
    return ETATS.get(statut, (statut, "vide"))


def alveole(cx, cy, r, classe, lien=None, etiquette=""):
    points = " ".join(f"{cx + r * math.cos(math.radians(60 * k - 30)):.1f},{cy + r * math.sin(math.radians(60 * k - 30)):.1f}" for k in range(6))
    forme = f'<polygon points="{points}" class="c-{classe}" stroke-width="1.5"><title>{e(etiquette)}</title></polygon>'
    if lien:
        return f'<a href="{e(lien)}" aria-label="{e(etiquette)}">{forme}</a>'
    return forme


def rayon_svg(reg, taches, prefixe, colonnes=14, r=15):
    """Un rayon d'alvéoles : une alvéole par tâche, dans l'ordre des identifiants."""
    largeur = math.sqrt(3) * r
    cases = list(taches) or [None] * 6
    lignes = max(1, math.ceil(len(cases) / colonnes))
    w = colonnes * largeur + largeur / 2 + 4
    h = (lignes - 1) * 1.5 * r + 2 * r + 4
    formes = []
    for i, t in enumerate(cases):
        ligne, colonne = divmod(i, colonnes)
        cx = 2 + largeur / 2 + colonne * largeur + (largeur / 2 if ligne % 2 else 0)
        cy = 2 + r + ligne * 1.5 * r
        if t is None:
            formes.append(alveole(cx, cy, r - 1.5, "attente", etiquette="Pas encore de tâche"))
        else:
            libelle, classe = etat_tache(reg, t)
            formes.append(alveole(cx, cy, r - 1.5, classe, f"{prefixe}taches/{t['id']}.html", f"{t['id']}, {libelle} : {t.get('titre', '')}"))
    titre = "Tâches du projet" if taches else "Aucune tâche pour l'instant"
    return f'<svg class="alveoles" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" role="group" aria-label="{titre}">{"".join(formes)}</svg>'


def legende():
    elements = [("pleine", "intégrée"), ("moitie", "réservée ou en relecture"), ("vide", "ouverte"), ("bloquee", "attend une autre tâche")]
    morceaux = []
    for classe, texte in elements:
        morceaux.append(f'<li><svg width="18" height="20" viewBox="0 0 18 20" aria-hidden="true">{alveole(9, 10, 8, classe)}</svg>{texte}</li>')
    return f'<ul class="legende">{"".join(morceaux)}</ul>'


def page(titre, corps, profondeur, actif, reg, horodatage):
    p = "../" * profondeur
    organisation = reg.config.get("organisation", "")
    depot = f"https://github.com/{organisation}/registre" if organisation and organisation != "A_DEFINIR" else ""
    liens = [("index.html", "La ruche", "accueil"), ("index.html#taches", "Tâches", "taches"),
             ("index.html#contributions", "Contributions", "contributions"), ("index.html#participer", "Participer", "participer")]
    courant = ' aria-current="page"'
    nav = "".join(f'<a href="{p}{href}"{courant if cle == actif else ""}>{texte}</a>' for href, texte, cle in liens)
    if depot:
        nav += f'<a href="{e(depot)}">Registre sur GitHub</a>'
    pied = (f'<p>Bee est un espace de forks indépendant : aucun projet d\'origine n\'est affilié ni contacté. '
            f'Règles : <a href="{e(depot)}/blob/main/COMMANDEMENTS.md">commandements</a>, <a href="{e(depot)}/blob/main/REGLES.md">règles</a>. '
            f'Données brutes : <a href="{p}api/registre.json">registre.json</a>. Page générée le {date_fr(horodatage)}.</p>') if depot else ""
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{e(titre)}</title>"
        "<meta name='description' content='Des agents IA optimisent les logiciels libres qui font tourner le web, sans changer leur résultat.'>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=IBM+Plex+Mono&display=swap'>"
        f"<style>{STYLE}</style></head><body>"
        f"<header class='site'><div class='cadre'><a class='marque' href='{p}index.html'>Bee</a><nav class='site' aria-label='Navigation'>{nav}</nav></div></header>"
        f"<main><div class='cadre'>{corps.replace(' :', chr(160) + ':').replace(' ;', chr(160) + ';')}</div></main>"
        f"<footer class='site'><div class='cadre'>{pied.replace(' :', chr(160) + ':')}</div></footer>"
        f"<script>{SCRIPT_FILTRES}</script></body></html>"
    )


def tableau(entetes, lignes, vide="Rien pour l'instant.", attributs_tbody="", classe_table=""):
    if not lignes:
        return f"<p class='vide'>{e(vide)}</p>"
    classe = " class='n'"
    tete = "".join(f"<th{classe if numerique else ''} scope='col'>{e(texte)}</th>" for texte, numerique in entetes)
    attribut_table = f" class='{classe_table}'" if classe_table else ""
    return f"<div class='tableau'><table{attribut_table}><thead><tr>{tete}</tr></thead><tbody{attributs_tbody}>{''.join(lignes)}</tbody></table></div>"


STATUTS_CONTRIBUTION = {"en_relecture": "en relecture", "integree": "intégrée", "refusee": "refusée", "annulee": "annulée"}


def generer(bee, reg, sortie):
    sortie = pathlib.Path(sortie)
    for sous in ("projets", "taches", "contributions", "api"):
        (sortie / sous).mkdir(parents=True, exist_ok=True)
    horodatage = bee.en_iso(bee.maintenant())
    niveaux = bee.calculer_niveaux(reg)
    taches = sorted((t for _, t in reg.taches.values() if isinstance(t, dict)), key=lambda t: t.get("id", ""))
    enregistrements = sorted((x for _, x in reg.enregistrements.values() if isinstance(x, dict)), key=lambda x: x.get("id", ""))
    scores = {x["id"]: bee.calculer_score(reg, x, niveaux) for x in enregistrements}
    votes_par_sujet = defaultdict(list)
    for _, v in reg.votes:
        votes_par_sujet[v.get("sujet")].append(v)
    projets = sorted((p for _, p in reg.projets.values() if isinstance(p, dict)), key=lambda p: (p.get("phase_ouverture", 9), p.get("id", "")))
    organisation = reg.config.get("organisation", "")
    depot = f"https://github.com/{organisation}/registre"

    # ---------- index ----------
    corps = [
        "<h1>Des agents IA rendent le web plus rapide, sans rien casser</h1>",
        "<p class='chapeau'>Avant leur reset hebdomadaire, des utilisateurs envoient leurs agents dépenser leurs crédits restants ici. "
        "Chaque agent prend une tâche dans un fork indépendant, optimise, puis prouve que le résultat est identique, bit pour bit.</p>",
        f"<p class='doux petit'>Phase {e(str(reg.config.get('phase', '?')))} de la feuille de route. Chaque alvéole est une tâche ; survolez-la ou suivez-la pour la lire.</p>",
        "<div class='ruche'>",
    ]
    for p in projets:
        siennes = [t for t in taches if t.get("projet") == p.get("id")]
        faites = sum(1 for t in siennes if t.get("statut") == "integree")
        if p.get("statut") == "actif":
            resume = f"{len(siennes)} tâche{'s' if len(siennes) > 1 else ''}, {faites} intégrée{'s' if faites > 1 else ''}"
        else:
            resume = f"ouvre en phase {p.get('phase_ouverture')}"
        categorie = reg.categories.get(p.get("categorie"), {}).get("nom", p.get("categorie", ""))
        corps.append(
            f"<section class='rayon' aria-labelledby='r-{e(p['id'])}'><h3 id='r-{e(p['id'])}'><a href='projets/{e(p['id'])}.html'>{e(p.get('nom', p['id']))}</a></h3>"
            f"<p class='doux'>{e(categorie)}, {e(resume)}</p>{rayon_svg(reg, siennes, '') if siennes else ''}</section>")
    corps.append("</div>")
    corps.append(legende())

    corps.append(
        "<section id='participer' aria-labelledby='titre-participer'>"
        "<h2 id='titre-participer'>Envoyer son agent</h2>"
        "<p>Ouvrez votre agent (Claude Code par exemple) dans un dossier vide et donnez-lui cette consigne, en remplaçant le pseudo :</p>"
        f"<pre id='texte-consigne'>Participe au projet Bee. Clone {e(depot)}, lis AGENTS.md et suis-le. "
        "Mon pseudo GitHub est &lt;pseudo&gt;. Taille maximale : S. Si tu ne peux pas finir, libère la tâche avec une note.</pre>"
        "<p><button type='button' id='copier'>Copier la consigne</button></p>"
        f"<p class='petit'>Votre agent tourne chez vous, sur votre abonnement : Bee ne reçoit aucune clé. Détails : "
        f"<a href='{e(depot)}/blob/main/UTILISATEURS.md'>envoyer son agent</a>, <a href='{e(depot)}/blob/main/AGENTS.md'>guide de l'agent</a>.</p>"
        "</section>")

    ouvertes = [t for t in taches if t.get("statut") == "ouverte"]
    corps.append("<h2 id='taches'>Tâches ouvertes</h2>")
    if ouvertes:
        types = sorted({t.get("type") for t in ouvertes})
        noms_projets = sorted({t.get("projet") for t in ouvertes})
        corps.append(
            "<div class='filtres' role='group' aria-label='Filtrer les tâches'>"
            "<label>Taille maximale <select data-filtre='taille'><option value=''>toutes</option><option>S</option><option>M</option><option>L</option></select></label>"
            "<label>Type <select data-filtre='type'><option value=''>tous</option>" + "".join(f"<option>{e(x)}</option>" for x in types) + "</select></label>"
            "<label>Projet <select data-filtre='projet'><option value=''>tous</option>" + "".join(f"<option>{e(x)}</option>" for x in noms_projets) + "</select></label>"
            "<label><input type='checkbox' data-filtre='bloquees' checked> montrer celles qui attendent une autre tâche</label></div>")
        lignes = []
        for t in sorted(ouvertes, key=lambda t: (-float(t.get("portee", 0)), t["id"])):
            bloquee = reg.bloquee_par(t)
            attente = f"<div class='doux petit'>attend {', '.join(e(d) for d in bloquee)}</div>" if bloquee else ""
            lignes.append(
                f"<tr data-taille='{e(t.get('taille', ''))}' data-type='{e(t.get('type', ''))}' data-projet='{e(t.get('projet', ''))}' data-bloquee='{'oui' if bloquee else 'non'}'>"
                f"<td><a class='id' href='taches/{e(t['id'])}.html'>{e(t['id'])}</a></td><td>{e(t.get('titre', ''))}{attente}</td>"
                f"<td>{e(t.get('type', ''))}</td><td>{e(t.get('taille', ''))}</td><td class='n'>{nombre(float(t.get('portee', 0)), 1)}</td></tr>")
        corps.append(tableau([("Tâche", False), ("Titre", False), ("Type", False), ("Taille", False), ("Portée", True)], lignes, attributs_tbody=" id='taches-ouvertes'", classe_table="t-taches"))
        corps.append("<p id='aucune-tache' class='vide' hidden>Aucune tâche ouverte ne correspond à ces filtres.</p>")
    else:
        corps.append("<p class='vide'>Aucune tâche ouverte pour l'instant. Relisez une contribution, ou revenez plus tard.</p>")

    en_cours = [t for t in taches if t.get("statut") in ("reservee", "en_relecture")]
    if en_cours:
        corps.append("<h3>En cours</h3>")
        lignes = []
        for t in en_cours:
            qui = (t.get("reservation") or {}).get("utilisateur")
            if not qui and t.get("contribution") in reg.enregistrements:
                qui = reg.enregistrements[t["contribution"]][1].get("auteur")
            libelle, _ = etat_tache(reg, t)
            lignes.append(f"<tr><td><a class='id' href='taches/{e(t['id'])}.html'>{e(t['id'])}</a></td><td>{e(t.get('titre', ''))}</td><td class='nw'>{e(libelle)}</td><td>{e(qui or '')}</td></tr>")
        corps.append(tableau([("Tâche", False), ("Titre", False), ("Statut", False), ("Par", False)], lignes))

    corps.append("<h2 id='contributions'>Contributions</h2>")
    corps.append("<p class='doux'>Classées par score : le gain mesuré par la CI, pondéré par la portée et la confiance des relecteurs, divisé par la taille du changement, puis ajusté par le vote des agents.</p>")
    lignes = []
    for x in sorted(enregistrements, key=lambda x: -(scores[x["id"]]["S"] if scores[x["id"]] else -1)):
        s = scores[x["id"]]
        lignes.append(
            f"<tr><td class='n'>{nombre(s['S'], 4) if s else '—'}</td><td><a class='id' href='contributions/{e(x['id'])}.html'>{e(x['id'])}</a>"
            f"<div class='doux petit'>{e(x.get('resume', ''))}</div></td><td>{e(x.get('auteur', ''))}</td>"
            f"<td class='n'>{pourcent(s['G']) if s else '—'}</td><td class='n'>{len(x.get('relectures') or [])}</td><td class='nw'>{e(STATUTS_CONTRIBUTION.get(x.get('statut', ''), x.get('statut', '')))}</td></tr>")
    corps.append(tableau([("Score", True), ("Contribution", False), ("Auteur", False), ("Gain", True), ("Relectures", True), ("Statut", False)], lignes,
                         vide="Aucune contribution pour l'instant : la première sera l'outillage d'évaluation de miniz.", classe_table="t-contrib"))

    corps.append("<h2 id='membres'>Membres</h2>")
    lignes = [f"<tr><td>{e(pseudo)}</td><td>{e(niveaux[pseudo]['niveau'])}</td><td class='n'>{niveaux[pseudo]['integrees']}</td><td class='n'>{niveaux[pseudo]['relectures']}</td></tr>"
              for pseudo in sorted(reg.membres, key=lambda p: (-niveaux[p]["integrees"], p))]
    corps.append(tableau([("Membre", False), ("Niveau", False), ("Intégrées", True), ("Relectures", True)], lignes,
                         vide="Aucun membre inscrit pour l'instant. Chaque compte humain a une voix, quel que soit le nombre de ses agents."))
    (sortie / "index.html").write_text(page("Bee, la ruche des agents", "".join(corps), 0, "accueil", reg, horodatage), encoding="utf-8")

    # ---------- projets ----------
    for p in projets:
        siennes = [t for t in taches if t.get("projet") == p.get("id")]
        categorie = reg.categories.get(p.get("categorie"), {})
        fork = f"<a href='{e(p['fork'])}'>{e(p['fork'])}</a>" if p.get("fork") else "pas encore créé"
        c = [f"<a class='retour' href='../index.html'>La ruche</a>",
             f"<h1>{e(p.get('nom', p['id']))}</h1>",
             f"<p class='chapeau'>{e(categorie.get('nom', p.get('categorie', '')))}. Fork indépendant, non affilié au "
             f"<a href='{e(p.get('depot_origine', ''))}'>projet d'origine</a>.</p>",
             (rayon_svg(reg, siennes, "../", colonnes=16, r=15) + legende()) if siennes else "",
             "<h2>Fiche</h2><dl class='fiche'>",
             f"<dt>Fork</dt><dd>{fork}</dd>",
             f"<dt>Licence</dt><dd>{e(p.get('licence', ''))}</dd>",
             f"<dt>Statut</dt><dd>{'actif' if p.get('statut') == 'actif' else 'ouvre en phase ' + str(p.get('phase_ouverture'))}</dd>",
             f"<dt>Référence</dt><dd>{e(p.get('reference', ''))}</dd>",
             f"<dt>Dans le périmètre</dt><dd>{e(', '.join(p.get('perimetre') or []))}</dd>",
             f"<dt>Hors périmètre</dt><dd>{e(', '.join(p.get('hors_perimetre') or []))}</dd>",
             f"<dt>Preuve exigée</dt><dd>{e(categorie.get('preuve', ''))}</dd>",
             f"<dt>Mainteneur</dt><dd>palier {e(p.get('palier_mainteneur', 'aucun'))}</dd></dl>",
             "<h2>Métriques suivies</h2>"]
        c.append(tableau([("Métrique", False), ("Mesure", False), ("Unité", False), ("Meilleur", False)],
                         [f"<tr><td><code>{e(m['id'])}</code></td><td>{e(m.get('description', ''))}</td><td>{e(m.get('unite', ''))}</td>"
                          f"<td>{'plus haut' if m.get('sens') == 'plus_haut' else 'plus bas'}</td></tr>" for m in p.get("metriques") or []]))
        c.append("<p class='doux petit'>Une optimisation ne peut pas modifier ces chemins, qui la jugent : " + ", ".join(f"<code>{e(x)}</code>" for x in p.get("chemins_juges") or []) + ".</p>")
        c.append("<h2>Tâches</h2>")
        lignes = []
        for t in siennes:
            libelle, classe = etat_tache(reg, t)
            lignes.append(f"<tr><td><a class='id' href='../taches/{e(t['id'])}.html'>{e(t['id'])}</a></td><td>{e(t.get('titre', ''))}</td>"
                          f"<td>{e(t.get('type', ''))}</td><td>{e(t.get('taille', ''))}</td><td><span class='statut'><svg width='14' height='16' viewBox='0 0 14 16' aria-hidden='true'>{alveole(7, 8, 6, classe)}</svg>{e(libelle)}</span></td></tr>")
        c.append(tableau([("Tâche", False), ("Titre", False), ("Type", False), ("Taille", False), ("Statut", False)], lignes, vide="Aucune tâche pour ce projet pour l'instant.", classe_table="t-projet"))
        (sortie / "projets" / f"{p['id']}.html").write_text(page(f"{p.get('nom', p['id'])}, projet Bee", "".join(c), 1, "", reg, horodatage), encoding="utf-8")

    # ---------- tâches ----------
    for t in taches:
        libelle, classe = etat_tache(reg, t)
        c = [f"<a class='retour' href='../projets/{e(t.get('projet', ''))}.html'>{e(reg.projets.get(t.get('projet'), (None, {}))[1].get('nom', t.get('projet', '')))}</a>",
             f"<p class='id doux'>{e(t['id'])}</p><h1 class='long'>{e(t.get('titre', ''))}</h1>",
             f"<p class='statut'><svg width='18' height='20' viewBox='0 0 18 20' aria-hidden='true'>{alveole(9, 10, 8, classe)}</svg>"
             f"{e(libelle.capitalize())}. Tâche de type {e(t.get('type', ''))}, taille {e(t.get('taille', ''))} "
             f"({bee.LIGNES_MAX.get(t.get('taille'), '?')} lignes modifiées au plus), portée {nombre(float(t.get('portee', 0)), 1)}.</p>"]
        if t.get("reservation"):
            c.append(f"<p class='doux'>Réservée par {e(t['reservation'].get('utilisateur', ''))} depuis le {date_fr(t['reservation'].get('depuis', ''))}.</p>")
        if t.get("contribution"):
            c.append(f"<p>Contribution : <a class='id' href='../contributions/{e(t['contribution'])}.html'>{e(t['contribution'])}</a></p>")
        c.append("<h2>Contexte</h2>" + "".join(f"<p>{e(par.strip())}</p>" for par in str(t.get("contexte", "")).split("\n\n") if par.strip()))
        c.append("<h2>Critères d'acceptation</h2><ul class='liste'>" + "".join(f"<li>{e(x)}</li>" for x in t.get("critere_acceptation") or []) + "</ul>")
        fichiers = ", ".join(f"<code>{e(f)}</code>" for f in t.get("fichiers") or []) or "—"
        metrique = f"<code>{e(t['metrique'])}</code>" if t.get("metrique") else "—"
        fiche = [f"<dt>Fichiers</dt><dd>{fichiers}</dd>",
                 f"<dt>Hors périmètre</dt><dd>{e(', '.join(t.get('hors_perimetre') or [])) or '—'}</dd>",
                 f"<dt>Métrique visée</dt><dd>{metrique}</dd>"]
        if t.get("sortie_compressee"):
            fiche.append(f"<dt>Sortie compressée</dt><dd>{'doit rester identique, octet pour octet' if t['sortie_compressee'] == 'identique' else 'peut changer si le ratio ne se dégrade pas'}</dd>")
        if t.get("depend_de"):
            fiche.append("<dt>Dépend de</dt><dd>" + ", ".join(f"<a class='id' href='{e(d)}.html'>{e(d)}</a> ({e(etat_tache(reg, reg.taches[d][1])[0]) if d in reg.taches else 'inconnue'})" for d in t["depend_de"]) + "</dd>")
        fiche.append(f"<dt>Créée</dt><dd>le {date_fr(t.get('cree_le', ''))} par {e(t.get('cree_par', ''))}</dd>")
        c.append("<h2>Détails</h2><dl class='fiche'>" + "".join(fiche) + "</dl>")
        if t.get("notes"):
            c.append("<h2>Notes des agents</h2>" + "".join(
                f"<div class='note'><p class='doux'>{e(n.get('par', ''))}, le {date_fr(n.get('le', ''))}</p><p>{e(n.get('texte', ''))}</p></div>" for n in t["notes"]))
        if t.get("statut") == "ouverte":
            c.append("<h2>La prendre</h2><p>Depuis votre clone du registre, après avoir lu <a href='" + e(depot) + "/blob/main/AGENTS.md'>le guide de l'agent</a> :</p>"
                     f"<pre>python3 outils/bee.py voir {e(t['id'])}\npython3 outils/bee.py prendre {e(t['id'])} --utilisateur &lt;pseudo&gt;</pre>")
        (sortie / "taches" / f"{t['id']}.html").write_text(page(f"{t['id']} : {t.get('titre', '')}", "".join(c), 1, "taches", reg, horodatage), encoding="utf-8")

    # ---------- contributions ----------
    for x in enregistrements:
        s = scores[x["id"]]
        verdict = x.get("verdict") or {}
        c = [f"<a class='retour' href='../taches/{e(x.get('tache', ''))}.html'>Tâche {e(x.get('tache', ''))}</a>",
             f"<p class='id doux'>{e(x['id'])}</p><h1 class='long'>{e(x.get('resume') or 'Contribution ' + x['id'])}</h1>",
             f"<p>Par {e(x.get('auteur', ''))}, soumise le {date_fr(x.get('soumise_le', ''))}. Statut : {e(STATUTS_CONTRIBUTION.get(x.get('statut', ''), x.get('statut', '')))}. "
             f"<a href='{e(x.get('pr', ''))}'>Pull request</a>.</p>", "<h2>Verdict de la CI</h2>"]
        if verdict:
            lignes = [f"<dt>CI</dt><dd>{e(verdict.get('ci', ''))}{(' (échec : ' + e(verdict['etape_en_echec']) + ')') if verdict.get('etape_en_echec') else ''}</dd>",
                      f"<dt>Gain mesuré</dt><dd>{pourcent(verdict['gain']) if verdict.get('gain') is not None else '—'}"
                      f"{'' if verdict.get('au_dela_du_bruit', True) else ', dans le bruit'}</dd>",
                      f"<dt>Lignes modifiées</dt><dd>{verdict.get('lignes_modifiees', '—')}</dd>"]
            if verdict.get("amorcage"):
                lignes.append("<dt>Amorçage</dt><dd>oui : cette contribution apporte ses propres juges, qui l'ont évaluée ; elle doit être relue de près</dd>")
            if verdict.get("ecart_declare") is not None:
                lignes.append(f"<dt>Écart avec le gain déclaré</dt><dd>{nombre(100 * verdict['ecart_declare'], 1)} points</dd>")
            if verdict.get("execution"):
                lignes.append(f"<dt>Exécution</dt><dd><a href='{e(verdict['execution'])}'>journal de la CI</a></dd>")
            c.append("<dl class='fiche'>" + "".join(lignes) + "</dl>")
        else:
            c.append("<p class='vide'>La CI du fork n'a pas encore publié de verdict.</p>")
        c.append("<h2>Score</h2>")
        if s:
            c.append(tableau([("Terme", False), ("Valeur", True), ("Signification", False)], [
                f"<tr><td>G</td><td class='n'>{nombre(s['G'], 4)}</td><td>gain relatif mesuré par la CI</td></tr>",
                f"<tr><td>P</td><td class='n'>{nombre(s['P'], 2)}</td><td>portée de la tâche</td></tr>",
                f"<tr><td>C</td><td class='n'>{nombre(s['C'], 2)}</td><td>relectures favorables ÷ 3, plafonnée à 1</td></tr>",
                f"<tr><td>L</td><td class='n'>{s['L']}</td><td>lignes modifiées, hors tests et bancs</td></tr>",
                f"<tr><td>V</td><td class='n'>{nombre(s['V'], 2)}</td><td>vote des agents, de 0,5 à 1,5</td></tr>",
                f"<tr><td><b>S</b></td><td class='n'><b>{nombre(s['S'], 4)}</b></td><td>G × P × C ÷ (1 + L/100) × V</td></tr>"]))
        else:
            c.append("<p class='vide'>Pas de score tant que la CI n'a pas mesuré un gain.</p>")
        c.append("<h2>Relectures</h2>")
        if x.get("relectures"):
            c.append("".join(f"<div class='note'><p class='doux'>{e(r.get('relecteur', ''))}, avis {e(r.get('avis', ''))}, le {date_fr(r.get('le', ''))}"
                             f"{', défaut signalé' if r.get('defaut_signale') else ''}{', défaut confirmé' if r.get('defaut_confirme') else ''}</p><p>{e(r.get('motif', ''))}</p></div>"
                             for r in x["relectures"]))
        else:
            c.append("<p class='vide'>Aucune relecture pour l'instant.</p>")
        votes = votes_par_sujet.get(x["id"], [])
        c.append(f"<h2>Votes</h2><p>{'Aucun vote' if not votes else str(len(votes)) + (' votes' if len(votes) > 1 else ' vote')}"
                 + (" : " + ", ".join(f"{e(v.get('votant', ''))} ({v.get('valeur', 0):+d})" for v in votes) if votes else "") + ".</p>")
        (sortie / "contributions" / f"{x['id']}.html").write_text(page(f"{x['id']}, contribution Bee", "".join(c), 1, "contributions", reg, horodatage), encoding="utf-8")

    # ---------- API ----------
    donnees = {
        "genere_le": horodatage,
        "phase": reg.config.get("phase"),
        "organisation": organisation,
        "registre": depot,
        "guide_agent": f"{depot}/blob/main/AGENTS.md",
        "projets": projets,
        "taches": [{**t, "bloquee_par": reg.bloquee_par(t), "page": f"taches/{t['id']}.html"} for t in taches],
        "contributions": [{**x, "score": scores[x["id"]], "page": f"contributions/{x['id']}.html"} for x in enregistrements],
        "membres": [{"pseudo": p, **niveaux[p]} for p in sorted(reg.membres)],
    }
    (sortie / "api" / "registre.json").write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
    (sortie / ".nojekyll").write_text("", encoding="utf-8")
    return sortie / "index.html"

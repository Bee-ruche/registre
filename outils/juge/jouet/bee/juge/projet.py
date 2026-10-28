"""Greffon du projet jouet (rle) pour le juge commun Bee : modèle d'un greffon et sujet des méta-tests.

Un greffon est lu par le juge commun depuis la BASE de la PR, jamais depuis la PR. Il ne voit les
sorties du conteneur qu'à travers lecture.Sorties et n'exécute rien de ce que le conteneur a produit.
Il ne fait confiance qu'à la base (A) et à lui-même (ici, un codec de référence écrit en Python).
"""

import zlib

from entrees import Entree, perturber
from lecture import Erreur, Refus

RLE_OK, RLE_INVALIDE, RLE_TAMPON_TROP_PETIT = 0, -1, -2


def compresser(d):
    """Codec de référence, identique octet pour octet à rle.c de la base (sinon : juge mal monté)."""
    sortie = bytearray(len(d).to_bytes(4, "little"))

    def litteraux(debut, fin):
        while debut < fin:
            k = min(128, fin - debut)
            sortie.append(k - 1)
            sortie.extend(d[debut:debut + k])
            debut += k

    i = debut = 0
    while i < len(d):
        plage = 1
        while i + plage < len(d) and plage < 130 and d[i + plage] == d[i]:
            plage += 1
        if plage >= 3:
            litteraux(debut, i)
            sortie += bytes([plage + 125, d[i]])
            i += plage
            debut = i
        else:
            i += plage
    litteraux(debut, len(d))
    return bytes(sortie) + zlib.crc32(d).to_bytes(4, "little")


def decompresser(z):
    """Décompression de référence ; None si le flux est invalide."""
    if len(z) < 8:
        return None
    longueur, i, sortie = int.from_bytes(z[:4], "little"), 4, bytearray()
    while i < len(z) - 4 and len(sortie) < longueur:
        c = z[i]
        i += 1
        if c < 128:
            if i + c + 1 > len(z) - 4:
                return None
            sortie += z[i:i + c + 1]
            i += c + 1
        else:
            if i >= len(z) - 4:
                return None
            sortie += bytes([z[i]]) * (c - 125)
            i += 1
    if len(sortie) != longueur or i != len(z) - 4 or zlib.crc32(bytes(sortie)) != int.from_bytes(z[-4:], "little"):
        return None
    return bytes(sortie)


class Projet:
    NOM = "jouet"
    PAQUETS = []                       # l'image commune suffit
    SOURCES = ["rle.c", "rle.h"]
    SOURCES_REQUISES = ["rle.c", "rle.h"]
    OUTILLAGE = ["bee/juge"]
    EN_TETES_BASE = ["rle.h"]
    CONSTRUIRE = "bee/juge/construire.sh"
    PREFIXES = ("rle_",)
    PERMIS = ()
    COTES = ("f", "z")
    SCENARIOS = {"compression": "f", "decompression": "z"}
    INSTRUCTIONS = ("compression", "decompression")
    METRIQUES = [
        ("debit_compression", "plus_haut", "Mo/s"),
        ("debit_decompression", "plus_haut", "Mo/s"),
        ("ratio", "plus_haut", "ratio"),
        ("memoire_max_ko", "plus_bas", "Ko"),
    ]
    METHODE = {"memoire": "ru_maxrss du processus du scénario « compression », lu par wait4"}

    def __init__(self, options):
        self.identique = options.pop("sortie_compressee", "identique") == "identique"
        if options:
            raise Erreur("options inconnues : " + ", ".join(sorted(options)))
        self.VERIFICATION = {"sortie_compressee": "identique" if self.identique else "peut_changer"}

    # -------------------------------------------------------------- entrées

    def corpus(self, outillage):
        """Corpus fixe, décrit ici (un vrai projet le lit dans bee/corpus/ de la base)."""
        texte = ("le juge commun lit les sorties sans les croire ; " * 40).encode()
        fichiers = [texte, bytes(range(256)) * 16, b"\x00" * 5000 + b"\x01" * 3, b"ab" * 3000, bytes(300) + texte]
        fichiers += [bytes((i * 7) % 251 for i in range(n)) for n in (1, 2, 127, 128, 129, 130, 131, 4096)]
        return [(f"k{i:03d}", d) for i, d in enumerate(fichiers)]

    def aleatoires(self, rng):
        e = [b"", rng.randbytes(1), rng.randbytes(rng.randint(2, 300))]
        for _ in range(3):
            bloc = bytearray()
            while len(bloc) < rng.randint(1000, 60000):
                bloc += bytes([rng.randrange(4)]) * rng.choice([1, 2, 3, 129, 130, 131, rng.randint(1, 400)])
            e.append(bytes(bloc))
        e.append(rng.randbytes(rng.randint(10000, 50000)))
        return [(f"a{i:03d}", d) for i, d in enumerate(e)]

    def flux(self, rng, originaux):
        """Flux produits ICI par le codec de référence, valides et invalides : (nom, flux, tampon, original ou None)."""
        resultat = [(f"z{i:03d}", compresser(d), len(d), d) for i, (_, d) in enumerate(originaux)]
        valides = [r for r in resultat if r[2] > 0]
        for k in range(min(10, len(valides))):
            _, z, taille, _ = valides[(k * 3) % len(valides)]
            genre, nom = k % 5, f"y{k:03d}"
            if genre == 0:
                resultat.append((nom, z[:rng.randrange(1, len(z))], taille, None))
            elif genre == 1:
                b = bytearray(z)
                b[rng.randrange(4, len(z))] ^= 1 << rng.randrange(8)
                resultat.append((nom, bytes(b), taille, None))
            elif genre == 2:
                resultat.append((nom, z, taille - 1, None))
            elif genre == 3:
                resultat.append((nom, z + rng.randbytes(3), taille, None))
            else:
                resultat.append((nom, rng.randbytes(rng.randint(8, 500)), 1000, None))
        return resultat

    def entrees(self, fichiers, flux):
        return [Entree("f", nom, d, len(d), d) for nom, d in fichiers] + \
               [Entree("z", nom, z, taille, original) for nom, z, taille, original in flux]

    def verification(self, rng, corpus):
        fichiers = corpus + self.aleatoires(rng)
        return self.entrees(fichiers, self.flux(rng, fichiers))

    def repetition(self, rng, corpus):
        perturbes = perturber(rng, corpus)
        return self.entrees(perturbes, [(nom, compresser(d), len(d), d) for nom, d in perturbes])

    def instructions(self, rng, corpus, prefixe):
        return self.repetition(rng, [(nom, d[:prefixe]) for nom, d in corpus])

    # -------------------------------------------------------------- vérification

    def compressee(self, a, b, relatif, original):
        sortie_b = b.exiger("f", relatif)
        if self.identique:
            if sortie_b != a.exiger("f", relatif):
                raise Refus(f"sortie compressée différente de la base : {relatif}")
        elif decompresser(sortie_b) != original:
            raise Refus(f"la sortie compressée ne redonne pas l'original : {relatif}")
        return len(sortie_b)

    def verifier(self, a, b, entrees):
        comparees = 0
        for e in entrees:
            if e.cote == "f":
                if a.exiger("f", f"c/{e.nom}") != compresser(e.donnees):
                    raise Erreur(f"la base ne donne pas la sortie de référence pour {e.nom} : juge mal monté")
                self.compressee(a, b, f"c/{e.nom}", e.donnees)
            else:
                code_a, _ = a.statut("z", f"e/{e.nom}")
                code_b, _ = b.statut("z", f"e/{e.nom}")
                if code_a != code_b:
                    raise Refus(f"décompression de {e.nom} : code {code_b}, la base donne {code_a}")
                sa, sb = a.exiger("z", f"d/{e.nom}"), b.exiger("z", f"d/{e.nom}")
                if code_a == RLE_OK:
                    if sa != sb:
                        raise Refus(f"décompression de {e.nom} différente de la base")
                    if e.attendu is not None and sa != e.attendu:
                        raise Erreur(f"la base ne redonne pas l'original de {e.nom} : juge mal monté")
                elif sa[:min(len(sa), len(sb))] != sb[:min(len(sa), len(sb))]:
                    raise Refus(f"décompression de {e.nom} en erreur : octets produits différents de la base")
            comparees += 1
        return comparees

    def fixes(self, sorties, corpus):
        total = sum(len(d) for _, d in corpus)
        compresse = sum(len(sorties.exiger("f", f"c/{nom}")) for nom, _ in corpus)
        return {"ratio": total / compresse if compresse else None}

    def scenario(self, s, a, b, entrees, mesure):
        cpu = mesure["utilisateur_s"] + mesure["systeme_s"]
        traites = comparees = 0
        if s == "compression":
            for e in entrees:
                if e.cote == "f":
                    self.compressee(a, b, f"compression/c/{e.nom}", e.donnees)
                    traites += len(e.donnees)
                    comparees += 1
            return {"debit_compression": traites / 1e6 / cpu if cpu > 0 else None, "memoire_max_ko": mesure["maxrss_ko"]}, comparees
        for e in entrees:
            if e.cote == "z":
                if b.exiger("z", f"decompression/d/{e.nom}") != e.attendu:
                    raise Refus(f"décompression mesurée de {e.nom} différente de l'original")
                traites += len(e.attendu)
                comparees += 1
        return {"debit_decompression": traites / 1e6 / cpu if cpu > 0 else None}, comparees

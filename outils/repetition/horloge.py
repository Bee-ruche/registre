"""Horloge de la ruche simulée : temps réel décalé de etat/horloge (secondes ajoutées), en UTC ISO."""
import datetime as dt, os, pathlib
f = pathlib.Path(os.environ["BEE_SIMU"]) / "etat/horloge"
decalage = int(f.read_text().strip()) if f.exists() else 0
print((dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=decalage)).strftime("%Y-%m-%dT%H:%M:%SZ"))

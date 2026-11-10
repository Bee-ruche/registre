"""Horloge de la ruche simulée : temps réel décalé de state/clock (secondes ajoutées), en UTC ISO."""
import datetime as dt, os, pathlib
f = pathlib.Path(os.environ["BEE_SIM"]) / "state/clock"
offset = int(f.read_text().strip()) if f.exists() else 0
print((dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=offset)).strftime("%Y-%m-%dT%H:%M:%SZ"))

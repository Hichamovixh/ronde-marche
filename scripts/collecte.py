#!/usr/bin/env python3
"""Collecte les données de marché et l'index des rapports pour le site.

Sans dépendance externe. Une source en panne ne bloque pas le reste :
la dernière valeur connue est conservée et signalée comme ancienne.
Code de sortie 1 uniquement si aucun instrument n'a pu être récupéré.
"""
import csv
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent / "site"
FICHIER_MARCHE = RACINE / "data" / "marche.json"
FICHIER_RAPPORTS = RACINE / "data" / "rapports.json"
DOSSIER_RAPPORTS = RACINE / "rapports"
POINTS_SERIE = 60
AGENT = "Mozilla/5.0 (compatible; ronde-marche/1.0)"

# variation : "pct" (variation relative) ou "pts" (écart en points de pourcentage).
INSTRUMENTS = [
    {"id": "sp500", "nom": "S&P 500", "groupe": "Actions", "unite": "pts", "variation": "pct",
     "sources": [("yahoo", "^GSPC"), ("stooq", "^spx")]},
    {"id": "nasdaq", "nom": "Nasdaq Composite", "groupe": "Actions", "unite": "pts", "variation": "pct",
     "sources": [("yahoo", "^IXIC"), ("stooq", "^ndq")]},
    {"id": "cac40", "nom": "CAC 40", "groupe": "Actions", "unite": "pts", "variation": "pct",
     "sources": [("yahoo", "^FCHI"), ("stooq", "^cac")]},
    {"id": "stoxx50", "nom": "Euro Stoxx 50", "groupe": "Actions", "unite": "pts", "variation": "pct",
     "sources": [("yahoo", "^STOXX50E")]},
    {"id": "nikkei", "nom": "Nikkei 225", "groupe": "Actions", "unite": "pts", "variation": "pct",
     "sources": [("yahoo", "^N225"), ("stooq", "^nkx")]},
    {"id": "emergents", "nom": "Émergents (ETF EEM)", "groupe": "Actions", "unite": "$", "variation": "pct",
     "sources": [("yahoo", "EEM")]},
    {"id": "us10", "nom": "Taux américain à 10 ans", "groupe": "Taux", "unite": "%", "variation": "pts",
     "sources": [("yahoo", "^TNX")]},
    {"id": "ez10", "nom": "Taux zone euro à 10 ans (AAA)", "groupe": "Taux", "unite": "%", "variation": "pts",
     "sources": [("bce", "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y")]},
    {"id": "bce", "nom": "Taux de dépôt de la BCE", "groupe": "Taux", "unite": "%", "variation": "pts",
     "sources": [("bce", "FM/D.U2.EUR.4F.KR.DFR.LEV")]},
    {"id": "or", "nom": "Or", "groupe": "Matières premières", "unite": "$", "variation": "pct",
     "sources": [("yahoo", "GC=F"), ("stooq", "xauusd")]},
    {"id": "argent", "nom": "Argent", "groupe": "Matières premières", "unite": "$", "variation": "pct",
     "sources": [("yahoo", "SI=F"), ("stooq", "xagusd")]},
    {"id": "brent", "nom": "Pétrole Brent", "groupe": "Matières premières", "unite": "$", "variation": "pct",
     "sources": [("yahoo", "BZ=F")]},
    {"id": "eurusd", "nom": "EUR/USD", "groupe": "Devises", "unite": "$", "variation": "pct",
     "sources": [("bce", "EXR/D.USD.EUR.SP00.A"), ("yahoo", "EURUSD=X")]},
    {"id": "btc", "nom": "Bitcoin", "groupe": "Crypto", "unite": "€", "variation": "pct",
     "sources": [("yahoo", "BTC-EUR")]},
    {"id": "eth", "nom": "Ethereum", "groupe": "Crypto", "unite": "€", "variation": "pct",
     "sources": [("yahoo", "ETH-EUR")]},
]


def telecharger(url):
    requete = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(requete, timeout=25) as reponse:
        return reponse.read().decode("utf-8")


def yahoo(symbole):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(symbole, safe='')}?range=4mo&interval=1d")
    resultat = json.loads(telecharger(url))["chart"]["result"][0]
    clotures = resultat["indicators"]["quote"][0]["close"]
    serie = {}
    for horodatage, valeur in zip(resultat["timestamp"], clotures):
        if valeur is not None:
            jour = datetime.fromtimestamp(horodatage, timezone.utc).date().isoformat()
            serie[jour] = float(valeur)
    return sorted(serie.items())


def stooq(symbole):
    url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(symbole, safe='')}&i=d"
    lignes = csv.DictReader(io.StringIO(telecharger(url)))
    return [(l["Date"], float(l["Close"])) for l in lignes if l.get("Close")][-90:]


def bce(cle):
    flux, serie = cle.split("/", 1)
    url = (f"https://data-api.ecb.europa.eu/service/data/{flux}/{serie}"
           "?lastNObservations=90&format=csvdata")
    lignes = csv.DictReader(io.StringIO(telecharger(url)))
    return [(l["TIME_PERIOD"], float(l["OBS_VALUE"])) for l in lignes if l.get("OBS_VALUE")]


FOURNISSEURS = {"yahoo": yahoo, "stooq": stooq, "bce": bce}
NOMS_SOURCES = {"yahoo": "Yahoo Finance", "stooq": "Stooq", "bce": "Banque centrale européenne"}


def variation_7j(serie, mode):
    """Compare le dernier point au dernier point daté d'au moins 7 jours avant."""
    dernier_jour, derniere = serie[-1]
    limite = (date.fromisoformat(dernier_jour) - timedelta(days=7)).isoformat()
    anciens = [valeur for jour, valeur in serie if jour <= limite]
    if not anciens:
        return None
    reference = anciens[-1]
    if mode == "pts":
        return round(derniere - reference, 3)
    if reference <= 0:
        return None
    return round((derniere / reference - 1) * 100, 2)


def construire(instrument, serie, source):
    if len(serie) < 2:
        raise ValueError("série trop courte")
    if any(valeur < 0 for _, valeur in serie) or serie[-1][1] == 0:
        raise ValueError("valeur aberrante")
    serie = sorted(serie)
    return {
        "id": instrument["id"], "nom": instrument["nom"], "groupe": instrument["groupe"],
        "unite": instrument["unite"], "mode_variation": instrument["variation"],
        "valeur": serie[-1][1], "date": serie[-1][0],
        "variation_7j": variation_7j(serie, instrument["variation"]),
        "serie": [[jour, round(valeur, 4)] for jour, valeur in serie[-POINTS_SERIE:]],
        "source": NOMS_SOURCES[source], "statut": "ok",
    }


def recuperer(instrument):
    erreurs = []
    for source, symbole in instrument["sources"]:
        try:
            return construire(instrument, FOURNISSEURS[source](symbole), source)
        except Exception as erreur:  # une source en panne ne doit jamais bloquer les autres
            erreurs.append(f"{source}: {erreur}")
    raise RuntimeError(" ; ".join(erreurs))


def collecter(precedent=None, maintenant=None):
    maintenant = maintenant or datetime.now(timezone.utc)
    anciens = {i["id"]: i for i in (precedent or {}).get("instruments", [])}
    instruments, reussites = [], 0
    for instrument in INSTRUMENTS:
        try:
            instruments.append(recuperer(instrument))
            reussites += 1
        except Exception as erreur:
            print(f"ÉCHEC {instrument['id']} : {erreur}", file=sys.stderr)
            if instrument["id"] in anciens:
                instruments.append({**anciens[instrument["id"]], "statut": "ancien"})
    return {"maj": maintenant.isoformat(timespec="seconds"), "instruments": instruments}, reussites


def indexer_rapports(dossier=DOSSIER_RAPPORTS):
    rapports = []
    for fichier in sorted(dossier.glob("*.md"), reverse=True):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", fichier.name):
            continue
        titre = next((l[2:].strip() for l in fichier.read_text("utf-8").splitlines()
                      if l.startswith("# ")), f"Ronde du {fichier.stem}")
        rapports.append({"date": fichier.stem, "titre": titre, "fichier": f"rapports/{fichier.name}"})
    return rapports


def ecrire(chemin, contenu):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=1) + "\n", "utf-8")


def main():
    precedent = json.loads(FICHIER_MARCHE.read_text("utf-8")) if FICHIER_MARCHE.exists() else None
    donnees, reussites = collecter(precedent)
    ecrire(FICHIER_RAPPORTS, indexer_rapports())
    print(f"{reussites}/{len(INSTRUMENTS)} instruments récupérés")
    if reussites == 0:
        return 1  # on conserve le fichier existant et son horodatage
    ecrire(FICHIER_MARCHE, donnees)
    return 0


if __name__ == "__main__":
    sys.exit(main())

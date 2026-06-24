#!/usr/bin/env python
"""
Analisi dei kebabbari nelle Marche.

Uso:
1. Modifica le variabili nella sezione CONFIGURAZIONE.
2. Esegui:
   py marche_kebab_density.py
"""

from pathlib import Path

from marche_kebab_utils import OVERPASS_URL, esegui_analisi


# =============================================================================
# CONFIGURAZIONE
# =============================================================================

ANNO_ISTAT = 2026
CARTELLA_CACHE = Path("data") / "cache"
CARTELLA_OUTPUT = Path("output") / "marche_kebab"

# True = riscarica ISTAT/OSM anche se i file sono gia' in cache.
RISCARICA_DATI = False

# False = usa solo parole molto specifiche: kebab, kebap, doner, shawarma.
# True = include anche keyword piu' larghe: istanbul, anatolia, turkish.
INCLUDI_KEYWORD_AMPIE = False

# CSV opzionali da Google Places, Registro Imprese o controlli manuali.
# Esempio: CSV_EXTRA_POI = [Path("google_places_marche.csv")]
CSV_EXTRA_POI = []

# Soglia per i conteggi: "high", "medium" o "all".
SOGLIA_CONFIDENZA = "medium"

# Deduplica record con stesso nome entro questa distanza.
DISTANZA_DEDUP_METRI = 50.0

# Scegli cosa generare: "csv", "grafici" oppure "entrambi".
TIPO_OUTPUT = "entrambi"

NUMERO_COMUNI_NEI_GRAFICI = 20


def run():
    return esegui_analisi(
        year=ANNO_ISTAT,
        cache_dir=CARTELLA_CACHE,
        out_dir=CARTELLA_OUTPUT,
        refresh=RISCARICA_DATI,
        include_broad_keywords=INCLUDI_KEYWORD_AMPIE,
        extra_poi_csv=CSV_EXTRA_POI,
        min_confidence=SOGLIA_CONFIDENZA,
        dedupe_distance_meters=DISTANZA_DEDUP_METRI,
        tipo_output=TIPO_OUTPUT,
        chart_top_n=NUMERO_COMUNI_NEI_GRAFICI,
        overpass_url=OVERPASS_URL,
    )


if __name__ == "__main__":
    risultati = run()

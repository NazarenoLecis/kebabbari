"""
Flusso principale dell'analisi kebabbari.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

from marche_kebab_charts import write_charts
from marche_kebab_utils import (
    OVERPASS_URL,
    REGION_NAME,
    assign_comuni_to_pois,
    build_summary_rows,
    dedupe_pois,
    deve_scrivere_csv,
    deve_scrivere_grafici,
    load_comune_shapes,
    load_extra_pois,
    load_osm_pois,
    load_osm_pizzerie_pois,
    load_osm_ristorazione_pois,
    load_population,
    normalize_text,
    normalizza_tipo_output,
    write_csv,
)


# =============================================================================
# CONFIGURAZIONE
# Modifica queste variabili e poi esegui:
# py marche_kebab_runner.py
# =============================================================================

ANNO_ISTAT = 2026
CARTELLA_CACHE = Path("data") / "cache"
CARTELLA_OUTPUT = Path("output") / "marche_kebab"
CARTELLA_OUTPUT_FILE = CARTELLA_OUTPUT / "file"
CARTELLA_OUTPUT_GRAFICI = CARTELLA_OUTPUT / "grafici"

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


def write_outputs(
    file_dir: Path,
    chart_dir: Path,
    pois: list[dict[str, Any]],
    ristorazione_pois: list[dict[str, Any]],
    pizzerie_pois: list[dict[str, Any]],
    comune_rows: list[dict[str, Any]],
    province_rows: list[dict[str, Any]],
    region_row: dict[str, Any],
    year: int,
    include_broad_keywords: bool,
    min_confidence: str,
    dedupe_distance_meters: float,
    overpass_url: str,
    extra_poi_csv: list[Path],
    tipo_output: str,
    chart_top_n: int,
) -> None:
    scrivi_csv = deve_scrivere_csv(tipo_output)
    scrivi_grafici = deve_scrivere_grafici(tipo_output)

    poi_fields = [
        "name",
        "source",
        "source_id",
        "osm_type",
        "osm_id",
        "lat",
        "lon",
        "confidence",
        "matched_terms",
        "amenity",
        "cuisine",
        "addr_street",
        "addr_housenumber",
        "addr_city",
        "phone",
        "website",
        "codice_comune",
        "comune",
        "codice_provincia",
        "provincia",
        "raw_tags_json",
    ]
    ristorazione_fields = [
        "name",
        "source",
        "source_id",
        "osm_type",
        "osm_id",
        "lat",
        "lon",
        "amenity",
        "cuisine",
        "codice_comune",
        "comune",
        "codice_provincia",
        "provincia",
        "raw_tags_json",
    ]
    pizzeria_fields = list(ristorazione_fields)
    summary_fields = [
        "codice_comune",
        "comune",
        "codice_provincia",
        "provincia",
        "popolazione",
        "kebabbari",
        "kebabbari_per_1000",
        "ristoranti_osm",
        "kebabbari_per_100_ristoranti",
        "pizzerie_osm",
        "kebabbari_per_100_pizzerie",
    ]
    province_fields = [
        "codice_provincia",
        "provincia",
        "popolazione",
        "kebabbari",
        "kebabbari_per_1000",
        "ristoranti_osm",
        "kebabbari_per_100_ristoranti",
        "pizzerie_osm",
        "kebabbari_per_100_pizzerie",
    ]

    pois_sorted = sorted(
        pois,
        key=lambda poi: (
            str(poi.get("codice_provincia", "")),
            str(poi.get("comune", "")),
            normalize_text(poi.get("name", "")),
        ),
    )

    if scrivi_csv:
        write_csv(file_dir / "kebabbari_marche.csv", pois_sorted, poi_fields)
        write_csv(
            file_dir / "ristorazione_osm_marche.csv",
            sorted(
                ristorazione_pois,
                key=lambda poi: (
                    str(poi.get("codice_provincia", "")),
                    str(poi.get("comune", "")),
                    normalize_text(poi.get("name", "")),
                ),
            ),
            ristorazione_fields,
        )
        write_csv(
            file_dir / "pizzerie_osm_marche.csv",
            sorted(
                pizzerie_pois,
                key=lambda poi: (
                    str(poi.get("codice_provincia", "")),
                    str(poi.get("comune", "")),
                    normalize_text(poi.get("name", "")),
                ),
            ),
            pizzeria_fields,
        )
        write_csv(file_dir / "distribuzione_kebabbari_comuni.csv", comune_rows, summary_fields)
        write_csv(file_dir / "distribuzione_kebabbari_province.csv", province_rows, province_fields)
        write_csv(file_dir / "distribuzione_kebabbari_regione.csv", [region_row], list(region_row.keys()))

        unassigned = [poi for poi in pois if not poi.get("codice_comune")]
        unassigned_path = file_dir / "kebabbari_non_assegnati.csv"
        if unassigned:
            write_csv(unassigned_path, unassigned, poi_fields)
        elif unassigned_path.exists():
            unassigned_path.unlink()

        metadata = {
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
            "region": REGION_NAME,
            "population_year": year,
            "boundary_year": year,
            "osm_include_broad_keywords": include_broad_keywords,
            "min_confidence_counted": min_confidence,
            "dedupe_distance_meters": dedupe_distance_meters,
            "overpass_url": overpass_url,
            "tipo_output": tipo_output,
            "note": (
                "Kebabbaro is not an official statistical category. "
                "Counts are an operational estimate from the configured sources. "
                "The restaurant denominator is based on OSM amenities: restaurant, fast_food, food_court. "
                "The pizzeria denominator is based on OSM food amenities with pizza/pizzeria in cuisine, name, brand or operator."
            ),
        }
        (file_dir / "metadati.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if scrivi_grafici:
        write_charts(
            chart_dir,
            comune_rows,
            province_rows,
            year,
            extra_poi_csv,
            include_broad_keywords,
            min_confidence,
            chart_top_n,
        )


def esegui_analisi(
    year: int,
    cache_dir: Path,
    file_dir: Path,
    chart_dir: Path,
    refresh: bool,
    include_broad_keywords: bool,
    extra_poi_csv: list[Path],
    min_confidence: str,
    dedupe_distance_meters: float,
    tipo_output: str,
    chart_top_n: int,
    overpass_url: str,
) -> dict[str, Any]:
    start = time.time()
    tipo_output = normalizza_tipo_output(tipo_output)
    scrivi_csv = deve_scrivere_csv(tipo_output)
    scrivi_grafici = deve_scrivere_grafici(tipo_output)

    print(f"Regione: {REGION_NAME}")
    print(f"Anno ISTAT: {year}")
    print(f"Output richiesto: {tipo_output}")

    population = load_population(year, cache_dir, refresh)
    comuni = load_comune_shapes(year, cache_dir, refresh)
    osm_pois = load_osm_pois(
        cache_dir,
        refresh,
        include_broad_keywords,
        overpass_url,
    )
    ristorazione_pois = load_osm_ristorazione_pois(cache_dir, refresh, overpass_url)
    pizzerie_pois = load_osm_pizzerie_pois(cache_dir, refresh, overpass_url)
    extra_pois = load_extra_pois(extra_poi_csv)

    pois = dedupe_pois(osm_pois + extra_pois, dedupe_distance_meters)
    assign_comuni_to_pois(pois, comuni, population)
    assign_comuni_to_pois(ristorazione_pois, comuni, population)
    assign_comuni_to_pois(pizzerie_pois, comuni, population)

    comune_rows, province_rows, region_row = build_summary_rows(
        population,
        pois,
        ristorazione_pois,
        pizzerie_pois,
        min_confidence,
    )

    write_outputs(
        file_dir,
        chart_dir,
        pois,
        ristorazione_pois,
        pizzerie_pois,
        comune_rows,
        province_rows,
        region_row,
        year,
        include_broad_keywords,
        min_confidence,
        dedupe_distance_meters,
        overpass_url,
        extra_poi_csv,
        tipo_output,
        chart_top_n,
    )

    print("")
    print("Output:")
    if scrivi_csv:
        print(f"- {file_dir / 'kebabbari_marche.csv'}")
        print(f"- {file_dir / 'ristorazione_osm_marche.csv'}")
        print(f"- {file_dir / 'pizzerie_osm_marche.csv'}")
        print(f"- {file_dir / 'distribuzione_kebabbari_comuni.csv'}")
        print(f"- {file_dir / 'distribuzione_kebabbari_province.csv'}")
        print(f"- {file_dir / 'distribuzione_kebabbari_regione.csv'}")
    if scrivi_grafici:
        print(f"- {chart_dir / 'grafico_province_per_1000.png'}")
        print(f"- {chart_dir / 'grafico_province_per_100_ristoranti.png'}")
        print(f"- {chart_dir / 'grafico_province_per_100_pizzerie.png'}")
        print(f"- {chart_dir / 'grafico_comuni_per_numero.png'}")
        print(f"- {chart_dir / 'grafico_comuni_per_1000.png'}")
        print(f"- {chart_dir / 'grafico_comuni_per_100_ristoranti.png'}")
        print(f"- {chart_dir / 'grafico_comuni_per_100_pizzerie.png'}")
    print("")
    print(
        f"Totale conteggiato ({min_confidence}+): "
        f"{region_row['kebabbari']} kebabbari, "
        f"{region_row['kebabbari_per_1000']} per 1.000 abitanti, "
        f"{region_row['kebabbari_per_100_ristoranti']} per 100 ristoranti OSM, "
        f"{region_row['kebabbari_per_100_pizzerie']} per 100 pizzerie OSM."
    )
    print(f"Tempo: {time.time() - start:.1f}s")
    return {
        "pois": pois,
        "ristorazione_pois": ristorazione_pois,
        "pizzerie_pois": pizzerie_pois,
        "comuni": comune_rows,
        "province": province_rows,
        "regione": region_row,
    }


def run() -> dict[str, Any]:
    return esegui_analisi(
        year=ANNO_ISTAT,
        cache_dir=CARTELLA_CACHE,
        file_dir=CARTELLA_OUTPUT_FILE,
        chart_dir=CARTELLA_OUTPUT_GRAFICI,
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

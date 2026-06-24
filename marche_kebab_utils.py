#!/usr/bin/env python
"""
Stima dei kebabbari nelle Marche e tasso per 1.000 abitanti.

Base replicabile:
- OpenStreetMap/Overpass per i POI kebab.
- ISTAT Demo POSAS per la popolazione comunale.
- ISTAT confini amministrativi per assegnare ogni POI al comune.

Arricchimenti opzionali:
- CSV esterni da Google Places, Registro Imprese/InfoCamere o controlli manuali.
  Il CSV deve avere almeno name e coordinate lat/lon, oppure un codice_comune.

Questo file contiene funzioni di supporto.
La configurazione resta in marche_kebab_density.py.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import struct
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REGION_CODE = "11"
REGION_NAME = "Marche"
MARCHE_BBOX = (42.65, 12.15, 44.25, 14.05)  # south, west, north, east

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

PROVINCES = {
    "041": "Pesaro_e_Urbino",
    "042": "Ancona",
    "043": "Macerata",
    "044": "Ascoli_Piceno",
    "109": "Fermo",
}

PROVINCE_NAMES = {
    "041": "Pesaro e Urbino",
    "042": "Ancona",
    "043": "Macerata",
    "044": "Ascoli Piceno",
    "109": "Fermo",
}

STRICT_TERMS = ("kebab", "kebap", "kebabberia", "doner", "shawarma")
BROAD_TERMS = ("istanbul", "anatolia", "turkish")

STRICT_OVERPASS_REGEX = r"kebab|kebap|kebabberia|d.ner|shawarma"
BROAD_OVERPASS_REGEX = r"istanbul|anatolia|turkish"

FOOD_AMENITY_REGEX = r"^(fast_food|restaurant|food_court|cafe|bar)$"
RISTORAZIONE_AMENITY_REGEX = r"^(restaurant|fast_food|food_court)$"

CONFIDENCE_RANK = {
    "high": 3,
    "external": 2,
    "medium": 2,
    "low": 1,
}


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def to_int(value: Any) -> int:
    if value is None:
        return 0
    text = str(value).strip().replace(".", "").replace(",", "")
    return int(text) if text else 0


def make_request(
    url: str,
    data: bytes | None = None,
    timeout: int = 120,
    content_type: str | None = None,
) -> bytes:
    headers = {
        "User-Agent": "marche-kebab-density/1.0 (+local research script)",
    }
    if content_type:
        headers["Content-Type"] = content_type

    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} while requesting {url}: {detail[:500]}") from exc


def cached_get(url: str, cache_path: Path, refresh: bool) -> bytes:
    if cache_path.exists() and not refresh:
        return cache_path.read_bytes()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Download: {url}")
    payload = make_request(url)
    cache_path.write_bytes(payload)
    return payload


def population_zip_url(year: int, province_code: str, province_slug: str) -> str:
    return (
        "https://demo.istat.it/data/posas/"
        f"POSAS_{year}_it_{province_code}_{province_slug}.zip"
    )


def boundaries_zip_url(year: int) -> str:
    return (
        "https://www.istat.it/storage/cartografia/confini_amministrativi/"
        f"generalizzati/{year}/Limiti0101{year}_g.zip"
    )


def load_population(year: int, cache_dir: Path, refresh: bool) -> dict[str, dict[str, Any]]:
    population: dict[str, dict[str, Any]] = {}

    for province_code, province_slug in PROVINCES.items():
        url = population_zip_url(year, province_code, province_slug)
        zip_bytes = cached_get(
            url,
            cache_dir / f"POSAS_{year}_it_{province_code}_{province_slug}.zip",
            refresh,
        )

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            csv_name = next(
                name for name in archive.namelist() if name.lower().endswith(".csv")
            )
            text = archive.read(csv_name).decode("utf-8-sig")

        reader = csv.reader(io.StringIO(text), delimiter=";")
        next(reader, None)  # titolo
        header = next(reader)
        positions = {name: idx for idx, name in enumerate(header)}

        code_col = positions["Codice comune"]
        name_col = positions["Comune"]
        total_col = positions["Totale"]

        totals: dict[str, int] = defaultdict(int)
        names: dict[str, str] = {}

        for row in reader:
            if not row or len(row) <= total_col:
                continue
            code = row[code_col].strip()
            if not code:
                continue
            if len(row) > 2 and row[2].strip() == "999":
                continue
            names[code] = row[name_col].strip()
            totals[code] += to_int(row[total_col])

        for code, total in totals.items():
            population[code] = {
                "codice_comune": code,
                "comune": names[code],
                "codice_provincia": province_code,
                "provincia": PROVINCE_NAMES[province_code],
                "popolazione": total,
            }

    return population


def parse_dbf(dbf_bytes: bytes, encoding: str = "utf-8") -> list[dict[str, Any] | None]:
    record_count = struct.unpack("<I", dbf_bytes[4:8])[0]
    header_length = struct.unpack("<H", dbf_bytes[8:10])[0]
    record_length = struct.unpack("<H", dbf_bytes[10:12])[0]

    fields = []
    pos = 32
    while dbf_bytes[pos] != 0x0D:
        descriptor = dbf_bytes[pos : pos + 32]
        name = descriptor[0:11].split(b"\x00", 1)[0].decode("ascii", errors="ignore")
        field_type = chr(descriptor[11])
        length = descriptor[16]
        decimals = descriptor[17]
        fields.append((name, field_type, length, decimals))
        pos += 32

    records: list[dict[str, Any] | None] = []
    for index in range(record_count):
        start = header_length + index * record_length
        record = dbf_bytes[start : start + record_length]
        if not record or record[0:1] == b"*":
            records.append(None)
            continue

        values: dict[str, Any] = {}
        offset = 1
        for name, field_type, length, decimals in fields:
            raw_bytes = record[offset : offset + length]
            offset += length
            raw = raw_bytes.decode(encoding, errors="replace").strip()

            if field_type in {"N", "F"}:
                if raw == "":
                    value: Any = None
                elif decimals == 0 and "." not in raw:
                    value = int(raw)
                else:
                    value = float(raw)
            else:
                value = raw
            values[name] = value
        records.append(values)

    return records


def parse_shp_polygons(shp_bytes: bytes) -> list[dict[str, Any] | None]:
    shapes: list[dict[str, Any] | None] = []
    pos = 100

    while pos + 8 <= len(shp_bytes):
        _record_number, content_words = struct.unpack(">ii", shp_bytes[pos : pos + 8])
        pos += 8
        content_length = content_words * 2
        end = pos + content_length
        if end > len(shp_bytes):
            break

        shape_type = struct.unpack("<i", shp_bytes[pos : pos + 4])[0]
        pos += 4

        if shape_type == 0:
            shapes.append(None)
            pos = end
            continue

        if shape_type not in {5, 15, 25}:
            raise ValueError(f"Unsupported shapefile shape type: {shape_type}")

        minx, miny, maxx, maxy = struct.unpack("<dddd", shp_bytes[pos : pos + 32])
        pos += 32
        num_parts, num_points = struct.unpack("<ii", shp_bytes[pos : pos + 8])
        pos += 8

        parts = list(struct.unpack(f"<{num_parts}i", shp_bytes[pos : pos + 4 * num_parts]))
        pos += 4 * num_parts

        points: list[tuple[float, float]] = []
        for _ in range(num_points):
            x, y = struct.unpack("<dd", shp_bytes[pos : pos + 16])
            points.append((x, y))
            pos += 16

        rings = []
        for part_index, start_index in enumerate(parts):
            stop_index = parts[part_index + 1] if part_index + 1 < len(parts) else num_points
            ring = points[start_index:stop_index]
            if len(ring) >= 3:
                rings.append(ring)

        shapes.append({"bbox": (minx, miny, maxx, maxy), "rings": rings})
        pos = end

    return shapes


def load_comune_shapes(year: int, cache_dir: Path, refresh: bool) -> list[dict[str, Any]]:
    url = boundaries_zip_url(year)
    zip_bytes = cached_get(url, cache_dir / f"Limiti0101{year}_g.zip", refresh)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        shp_name = next(
            name
            for name in archive.namelist()
            if name.lower().endswith(".shp") and "com0101" in name.lower()
        )
        dbf_name = shp_name[:-4] + ".dbf"
        shp_bytes = archive.read(shp_name)
        dbf_bytes = archive.read(dbf_name)

    attrs = parse_dbf(dbf_bytes)
    shapes = parse_shp_polygons(shp_bytes)
    if len(attrs) != len(shapes):
        raise RuntimeError(
            f"ISTAT shapefile mismatch: {len(attrs)} DBF rows vs {len(shapes)} shapes"
        )

    comuni: list[dict[str, Any]] = []
    for attr, shape in zip(attrs, shapes):
        if not attr or not shape:
            continue
        if str(attr.get("COD_REG")) != REGION_CODE:
            continue

        province_code = f"{int(attr['COD_PROV']):03d}"
        code = str(attr.get("PRO_COM_T") or f"{int(attr['PRO_COM']):06d}").zfill(6)
        comuni.append(
            {
                "code": code,
                "name": str(attr["COMUNE"]),
                "province_code": province_code,
                "province_name": PROVINCE_NAMES.get(province_code, province_code),
                "bbox": shape["bbox"],
                "rings": shape["rings"],
            }
        )

    return comuni


def build_overpass_query(
    include_broad_keywords: bool,
    snapshot_date: str | None = None,
    timeout_seconds: int = 90,
) -> str:
    keyword_regex = STRICT_OVERPASS_REGEX
    if include_broad_keywords:
        keyword_regex = f"{keyword_regex}|{BROAD_OVERPASS_REGEX}"

    date_clause = f'[date:"{snapshot_date}"]' if snapshot_date else ""
    if snapshot_date:
        south, west, north, east = MARCHE_BBOX
        preamble = ""
        scope = f"({south},{west},{north},{east})"
    else:
        preamble = (
            'area["boundary"="administrative"]["admin_level"="4"]'
            '["ISO3166-2"="IT-57"]->.searchArea;'
        )
        scope = "(area.searchArea)"

    return f"""
[out:json][timeout:{timeout_seconds}]{date_clause};
{preamble}
(
  nwr["amenity"~"{FOOD_AMENITY_REGEX}"]["cuisine"~"{keyword_regex}", i]{scope};
  nwr["amenity"~"{FOOD_AMENITY_REGEX}"]["name"~"{keyword_regex}", i]{scope};
  nwr["amenity"~"{FOOD_AMENITY_REGEX}"]["alt_name"~"{keyword_regex}", i]{scope};
  nwr["amenity"~"{FOOD_AMENITY_REGEX}"]["brand"~"{keyword_regex}", i]{scope};
  nwr["amenity"~"{FOOD_AMENITY_REGEX}"]["operator"~"{keyword_regex}", i]{scope};
  nwr["shop"]["cuisine"~"{keyword_regex}", i]{scope};
  nwr["shop"]["name"~"{keyword_regex}", i]{scope};
  nwr["shop"]["brand"~"{keyword_regex}", i]{scope};
  nwr["shop"]["operator"~"{keyword_regex}", i]{scope};
);
out center tags;
""".strip()


def fetch_osm_payload(
    cache_dir: Path,
    refresh: bool,
    include_broad_keywords: bool,
    overpass_url: str,
    snapshot_date: str | None = None,
) -> dict[str, Any]:
    cache_prefix = "osm_kebab_marche_broad" if include_broad_keywords else "osm_kebab_marche"
    if snapshot_date:
        cache_prefix += "_" + snapshot_date[:10]
    cache_name = cache_prefix + ".json"
    cache_path = cache_dir / cache_name
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))

    query_timeout = 45 if snapshot_date else 90
    query = build_overpass_query(include_broad_keywords, snapshot_date, query_timeout)
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    if snapshot_date:
        print(f"Download: OpenStreetMap via Overpass ({snapshot_date[:10]})", flush=True)
    else:
        print("Download: OpenStreetMap via Overpass", flush=True)
    payload = make_request(
        overpass_url,
        data=body,
        timeout=75 if snapshot_date else 180,
        content_type="application/x-www-form-urlencoded; charset=utf-8",
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(payload)
    return json.loads(payload.decode("utf-8"))


def build_ristorazione_overpass_query() -> str:
    return f"""
[out:json][timeout:90];
area["boundary"="administrative"]["admin_level"="4"]["ISO3166-2"="IT-57"]->.searchArea;
(
  nwr["amenity"~"{RISTORAZIONE_AMENITY_REGEX}"](area.searchArea);
);
out center tags;
""".strip()


def fetch_osm_ristorazione_payload(
    cache_dir: Path,
    refresh: bool,
    overpass_url: str,
) -> dict[str, Any]:
    cache_path = cache_dir / "osm_ristorazione_marche.json"
    if cache_path.exists() and not refresh:
        return json.loads(cache_path.read_text(encoding="utf-8"))

    query = build_ristorazione_overpass_query()
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    print("Download: OpenStreetMap ristorazione via Overpass")
    payload = make_request(
        overpass_url,
        data=body,
        timeout=180,
        content_type="application/x-www-form-urlencoded; charset=utf-8",
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(payload)
    return json.loads(payload.decode("utf-8"))


def matched_terms(text: str, include_broad_keywords: bool) -> list[str]:
    terms = list(STRICT_TERMS)
    if include_broad_keywords:
        terms.extend(BROAD_TERMS)
    found = [term for term in terms if term in text]
    return sorted(set(found))


def element_lat_lon(element: dict[str, Any]) -> tuple[float, float] | None:
    if element.get("type") == "node":
        lat = element.get("lat")
        lon = element.get("lon")
    else:
        center = element.get("center") or {}
        lat = center.get("lat")
        lon = center.get("lon")

    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def osm_element_to_poi(
    element: dict[str, Any],
    include_broad_keywords: bool,
) -> dict[str, Any] | None:
    coordinates = element_lat_lon(element)
    if coordinates is None:
        return None
    lat, lon = coordinates

    tags = element.get("tags") or {}
    searchable_values = [
        tags.get("name"),
        tags.get("alt_name"),
        tags.get("official_name"),
        tags.get("brand"),
        tags.get("operator"),
        tags.get("cuisine"),
    ]
    normalized = normalize_text(" ".join(str(value or "") for value in searchable_values))
    terms = matched_terms(normalized, include_broad_keywords)
    if not terms:
        return None

    cuisine_text = normalize_text(tags.get("cuisine", ""))
    name_text = normalize_text(
        " ".join(
            str(tags.get(key, ""))
            for key in ("name", "alt_name", "official_name", "brand", "operator")
        )
    )

    strict_hit = any(term in cuisine_text or term in name_text for term in STRICT_TERMS)
    confidence = "high" if strict_hit else "medium"

    return {
        "name": tags.get("name") or tags.get("brand") or tags.get("operator") or "",
        "source": "osm",
        "source_id": f"{element.get('type')}/{element.get('id')}",
        "osm_type": element.get("type", ""),
        "osm_id": element.get("id", ""),
        "lat": lat,
        "lon": lon,
        "confidence": confidence,
        "matched_terms": "|".join(terms),
        "amenity": tags.get("amenity", ""),
        "cuisine": tags.get("cuisine", ""),
        "addr_street": tags.get("addr:street", ""),
        "addr_housenumber": tags.get("addr:housenumber", ""),
        "addr_city": tags.get("addr:city", ""),
        "phone": tags.get("phone") or tags.get("contact:phone") or "",
        "website": tags.get("website") or tags.get("contact:website") or "",
        "codice_comune": "",
        "comune": "",
        "codice_provincia": "",
        "provincia": "",
        "raw_tags_json": json.dumps(tags, ensure_ascii=False, sort_keys=True),
    }


def osm_element_to_ristorazione_poi(element: dict[str, Any]) -> dict[str, Any] | None:
    coordinates = element_lat_lon(element)
    if coordinates is None:
        return None
    lat, lon = coordinates

    tags = element.get("tags") or {}
    return {
        "name": tags.get("name") or tags.get("brand") or tags.get("operator") or "",
        "source": "osm",
        "source_id": f"{element.get('type')}/{element.get('id')}",
        "osm_type": element.get("type", ""),
        "osm_id": element.get("id", ""),
        "lat": lat,
        "lon": lon,
        "amenity": tags.get("amenity", ""),
        "cuisine": tags.get("cuisine", ""),
        "codice_comune": "",
        "comune": "",
        "codice_provincia": "",
        "provincia": "",
        "raw_tags_json": json.dumps(tags, ensure_ascii=False, sort_keys=True),
    }


def load_osm_pois(
    cache_dir: Path,
    refresh: bool,
    include_broad_keywords: bool,
    overpass_url: str,
    snapshot_date: str | None = None,
) -> list[dict[str, Any]]:
    payload = fetch_osm_payload(
        cache_dir,
        refresh,
        include_broad_keywords,
        overpass_url,
        snapshot_date,
    )
    pois_by_id: dict[str, dict[str, Any]] = {}
    for element in payload.get("elements", []):
        poi = osm_element_to_poi(element, include_broad_keywords)
        if poi:
            pois_by_id[poi["source_id"]] = poi
    return list(pois_by_id.values())


def load_osm_ristorazione_pois(
    cache_dir: Path,
    refresh: bool,
    overpass_url: str,
) -> list[dict[str, Any]]:
    payload = fetch_osm_ristorazione_payload(cache_dir, refresh, overpass_url)
    pois_by_id: dict[str, dict[str, Any]] = {}
    for element in payload.get("elements", []):
        poi = osm_element_to_ristorazione_poi(element)
        if poi:
            pois_by_id[poi["source_id"]] = poi
    return list(pois_by_id.values())


def pick_column(row: dict[str, str], candidates: tuple[str, ...]) -> str:
    lookup = {normalize_text(key): key for key in row.keys()}
    for candidate in candidates:
        key = lookup.get(normalize_text(candidate))
        if key is not None:
            return row.get(key, "")
    return ""


def load_extra_pois(paths: list[Path]) -> list[dict[str, Any]]:
    pois: list[dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                name = pick_column(row, ("name", "nome", "denominazione", "insegna"))
                lat_raw = pick_column(row, ("lat", "latitude", "y"))
                lon_raw = pick_column(row, ("lon", "lng", "longitude", "x"))
                code = pick_column(
                    row,
                    ("codice_comune", "codice istat comune", "pro_com_t", "istat"),
                )
                if not name and not code:
                    continue

                lat = float(lat_raw) if lat_raw else None
                lon = float(lon_raw) if lon_raw else None
                if (lat is None or lon is None) and not code:
                    continue

                source = pick_column(row, ("source", "fonte")) or path.stem
                source_id = (
                    pick_column(row, ("source_id", "place_id", "id", "id_impresa"))
                    or f"{path.stem}:{len(pois) + 1}"
                )
                terms = matched_terms(normalize_text(name), include_broad_keywords=True)

                pois.append(
                    {
                        "name": name,
                        "source": source,
                        "source_id": source_id,
                        "osm_type": "",
                        "osm_id": "",
                        "lat": lat,
                        "lon": lon,
                        "confidence": "external",
                        "matched_terms": "|".join(terms),
                        "amenity": "",
                        "cuisine": "",
                        "addr_street": pick_column(row, ("addr_street", "via", "indirizzo")),
                        "addr_housenumber": pick_column(row, ("addr_housenumber", "civico")),
                        "addr_city": pick_column(row, ("addr_city", "comune", "city")),
                        "phone": pick_column(row, ("phone", "telefono")),
                        "website": pick_column(row, ("website", "sito")),
                        "codice_comune": str(code).strip().zfill(6) if code else "",
                        "comune": "",
                        "codice_provincia": "",
                        "provincia": "",
                        "raw_tags_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
                    }
                )
    return pois


def point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    count = len(ring)
    if count < 3:
        return False

    previous_x, previous_y = ring[-1]
    for current_x, current_y in ring:
        if (current_y > y) != (previous_y > y):
            intersection_x = (
                (previous_x - current_x) * (y - current_y) / (previous_y - current_y)
                + current_x
            )
            if x < intersection_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def point_in_comune(lon: float, lat: float, comune: dict[str, Any]) -> bool:
    minx, miny, maxx, maxy = comune["bbox"]
    if lon < minx or lon > maxx or lat < miny or lat > maxy:
        return False

    inside = False
    for ring in comune["rings"]:
        if point_in_ring(lon, lat, ring):
            inside = not inside
    return inside


def latlon_to_utm32n(lat: float, lon: float) -> tuple[float, float]:
    """Convert WGS84 latitude/longitude to UTM zone 32N (EPSG:32632)."""
    semi_major_axis = 6_378_137.0
    flattening = 1 / 298.257223563
    scale = 0.9996
    false_easting = 500_000.0
    lon_origin = math.radians(9.0)

    eccentricity_sq = flattening * (2 - flattening)
    second_eccentricity_sq = eccentricity_sq / (1 - eccentricity_sq)

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    tan_lat = math.tan(lat_rad)

    n_value = semi_major_axis / math.sqrt(1 - eccentricity_sq * sin_lat * sin_lat)
    t_value = tan_lat * tan_lat
    c_value = second_eccentricity_sq * cos_lat * cos_lat
    a_value = cos_lat * (lon_rad - lon_origin)

    e2 = eccentricity_sq
    e4 = e2 * e2
    e6 = e4 * e2
    meridional_arc = semi_major_axis * (
        (1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * lat_rad
        - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * lat_rad)
        + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * lat_rad)
        - (35 * e6 / 3072) * math.sin(6 * lat_rad)
    )

    easting = false_easting + scale * n_value * (
        a_value
        + (1 - t_value + c_value) * a_value**3 / 6
        + (
            5
            - 18 * t_value
            + t_value**2
            + 72 * c_value
            - 58 * second_eccentricity_sq
        )
        * a_value**5
        / 120
    )
    northing = scale * (
        meridional_arc
        + n_value
        * tan_lat
        * (
            a_value**2 / 2
            + (5 - t_value + 9 * c_value + 4 * c_value**2) * a_value**4 / 24
            + (
                61
                - 58 * t_value
                + t_value**2
                + 600 * c_value
                - 330 * second_eccentricity_sq
            )
            * a_value**6
            / 720
        )
    )
    return easting, northing


def coordinates_for_comune_shapes(
    lat: float,
    lon: float,
    comuni: list[dict[str, Any]],
) -> tuple[float, float]:
    if not comuni:
        return lon, lat
    sample_bbox = comuni[0]["bbox"]
    projected = max(abs(value) for value in sample_bbox) > 1000
    if projected:
        return latlon_to_utm32n(lat, lon)
    return lon, lat


def assign_comuni_to_pois(
    pois: list[dict[str, Any]],
    comuni: list[dict[str, Any]],
    population: dict[str, dict[str, Any]],
) -> None:
    shapes_by_code = {comune["code"]: comune for comune in comuni}

    for poi in pois:
        code = str(poi.get("codice_comune") or "").strip().zfill(6)
        if code and code in shapes_by_code:
            comune = shapes_by_code[code]
        else:
            lat = poi.get("lat")
            lon = poi.get("lon")
            comune = None
            if lat is not None and lon is not None:
                x, y = coordinates_for_comune_shapes(float(lat), float(lon), comuni)
                for candidate in comuni:
                    if point_in_comune(x, y, candidate):
                        comune = candidate
                        break

        if comune is None:
            continue

        poi["codice_comune"] = comune["code"]
        poi["comune"] = population.get(comune["code"], {}).get("comune", comune["name"])
        poi["codice_provincia"] = comune["province_code"]
        poi["provincia"] = comune["province_name"]


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def dedupe_pois(pois: list[dict[str, Any]], distance_meters: float) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    exact_ids: set[tuple[str, str]] = set()

    for poi in pois:
        exact_key = (str(poi.get("source", "")), str(poi.get("source_id", "")))
        if exact_key[0] and exact_key[1] and exact_key in exact_ids:
            continue

        name_key = normalize_text(poi.get("name", ""))
        duplicate = None
        if name_key and poi.get("lat") is not None and poi.get("lon") is not None:
            for existing in accepted:
                existing_name_key = normalize_text(existing.get("name", ""))
                if existing_name_key != name_key:
                    continue
                if existing.get("lat") is None or existing.get("lon") is None:
                    continue
                distance = haversine_meters(
                    float(poi["lat"]),
                    float(poi["lon"]),
                    float(existing["lat"]),
                    float(existing["lon"]),
                )
                if distance <= distance_meters:
                    duplicate = existing
                    break

        if duplicate is None:
            accepted.append(poi)
            if exact_key[0] and exact_key[1]:
                exact_ids.add(exact_key)
            continue

        sources = set(str(duplicate.get("source", "")).split("|"))
        sources.add(str(poi.get("source", "")))
        duplicate["source"] = "|".join(sorted(source for source in sources if source))
        duplicate["source_id"] = f"{duplicate.get('source_id', '')}|{poi.get('source_id', '')}"

        if CONFIDENCE_RANK.get(str(poi.get("confidence")), 0) > CONFIDENCE_RANK.get(
            str(duplicate.get("confidence")), 0
        ):
            duplicate["confidence"] = poi["confidence"]

    return accepted


def confidence_threshold(name: str) -> int:
    if name == "high":
        return CONFIDENCE_RANK["high"]
    if name == "medium":
        return CONFIDENCE_RANK["medium"]
    return 0


def build_summary_rows(
    population: dict[str, dict[str, Any]],
    pois: list[dict[str, Any]],
    ristorazione_pois: list[dict[str, Any]],
    min_confidence: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    threshold = confidence_threshold(min_confidence)
    countable_pois = [
        poi
        for poi in pois
        if poi.get("codice_comune")
        and CONFIDENCE_RANK.get(str(poi.get("confidence")), 0) >= threshold
    ]
    counts_by_comune = Counter(str(poi["codice_comune"]) for poi in countable_pois)
    ristoranti_by_comune = Counter(
        str(poi["codice_comune"]) for poi in ristorazione_pois if poi.get("codice_comune")
    )

    comune_rows: list[dict[str, Any]] = []
    for code, info in sorted(
        population.items(),
        key=lambda item: (item[1]["codice_provincia"], item[1]["comune"]),
    ):
        population_value = int(info["popolazione"])
        count = counts_by_comune.get(code, 0)
        ristoranti = ristoranti_by_comune.get(code, 0)
        rate_population = count / population_value * 1000 if population_value else 0
        rate_ristoranti = count / ristoranti * 100 if ristoranti else 0
        comune_rows.append(
            {
                "codice_comune": code,
                "comune": info["comune"],
                "codice_provincia": info["codice_provincia"],
                "provincia": info["provincia"],
                "popolazione": population_value,
                "kebabbari": count,
                "kebabbari_per_1000": f"{rate_population:.4f}",
                "ristoranti_osm": ristoranti,
                "kebabbari_per_100_ristoranti": f"{rate_ristoranti:.4f}",
            }
        )

    province_totals: dict[str, dict[str, Any]] = {}
    for row in comune_rows:
        province_code = row["codice_provincia"]
        target = province_totals.setdefault(
            province_code,
            {
                "codice_provincia": province_code,
                "provincia": row["provincia"],
                "popolazione": 0,
                "kebabbari": 0,
                "ristoranti_osm": 0,
            },
        )
        target["popolazione"] += int(row["popolazione"])
        target["kebabbari"] += int(row["kebabbari"])
        target["ristoranti_osm"] += int(row["ristoranti_osm"])

    province_rows = []
    for row in sorted(province_totals.values(), key=lambda item: item["codice_provincia"]):
        rate_population = row["kebabbari"] / row["popolazione"] * 1000 if row["popolazione"] else 0
        rate_ristoranti = (
            row["kebabbari"] / row["ristoranti_osm"] * 100 if row["ristoranti_osm"] else 0
        )
        row = dict(row)
        row["kebabbari_per_1000"] = f"{rate_population:.4f}"
        row["kebabbari_per_100_ristoranti"] = f"{rate_ristoranti:.4f}"
        province_rows.append(row)

    region_population = sum(int(row["popolazione"]) for row in comune_rows)
    region_count = sum(int(row["kebabbari"]) for row in comune_rows)
    region_ristoranti = sum(int(row["ristoranti_osm"]) for row in comune_rows)
    region_rate = region_count / region_population * 1000 if region_population else 0
    region_rate_ristoranti = (
        region_count / region_ristoranti * 100 if region_ristoranti else 0
    )
    region_row = {
        "regione": REGION_NAME,
        "popolazione": region_population,
        "kebabbari": region_count,
        "kebabbari_per_1000": f"{region_rate:.4f}",
        "ristoranti_osm": region_ristoranti,
        "kebabbari_per_100_ristoranti": f"{region_rate_ristoranti:.4f}",
    }

    return comune_rows, province_rows, region_row


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def normalizza_tipo_output(tipo_output: str) -> str:
    valore = str(tipo_output).strip().lower()
    valori_validi = {"csv", "grafici", "entrambi"}
    if valore not in valori_validi:
        raise ValueError(
            "TIPO_OUTPUT deve essere uno tra: 'csv', 'grafici', 'entrambi'."
        )
    return valore


def deve_scrivere_csv(tipo_output: str) -> bool:
    return tipo_output in {"csv", "entrambi"}


def deve_scrivere_grafici(tipo_output: str) -> bool:
    return tipo_output in {"grafici", "entrambi"}

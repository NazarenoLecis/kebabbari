"""
Funzioni per generare grafici SVG dell'analisi kebabbari.
"""

from __future__ import annotations

from html import escape as html_escape
from pathlib import Path
from typing import Any


def format_int_it(value: Any) -> str:
    return f"{int(value):,}".replace(",", ".")


def format_rate_it(value: Any) -> str:
    return f"{float(value):.4f}".replace(".", ",")


def parse_rate(value: Any) -> float:
    return float(str(value).replace(",", "."))


def truncate_label(value: Any, max_chars: int = 38) -> str:
    text = str(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def chart_footer(year: int, extra_poi_csv: list[Path]) -> str:
    sources = [
        "OpenStreetMap/Overpass",
        f"ISTAT Demo POSAS {year}",
        f"ISTAT confini amministrativi {year}",
    ]
    if extra_poi_csv:
        sources.append("CSV esterni indicati dall'utente")
    return "Fonti: " + "; ".join(sources) + ". Elaborazione di Nazareno Lecis"


def write_horizontal_bar_chart(
    path: Path,
    title: str,
    subtitle: str,
    rows: list[dict[str, Any]],
    x_axis_label: str,
    footer: str,
    bar_color: str,
    notes: list[str] | None = None,
) -> None:
    width = 1200
    margin_left = 330
    margin_right = 230
    margin_top = 142
    row_height = 36
    bar_height = 22
    footer_lines = list(notes or []) + [footer]
    footer_height = 44 + 18 * len(footer_lines)
    plot_width = width - margin_left - margin_right
    chart_rows = rows if rows else [{"label": "Nessun dato", "value": 0, "value_label": ""}]
    height = margin_top + len(chart_rows) * row_height + footer_height

    max_value = max(float(row["value"]) for row in chart_rows)
    axis_max = max_value if max_value > 0 else 1.0

    svg: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        ),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        (
            '<style>'
            '.title{font:700 28px Arial,sans-serif;fill:#1f2933}'
            '.subtitle{font:400 15px Arial,sans-serif;fill:#52616b}'
            '.axis{font:400 12px Arial,sans-serif;fill:#697985}'
            '.label{font:600 14px Arial,sans-serif;fill:#1f2933}'
            '.value{font:600 13px Arial,sans-serif;fill:#1f2933}'
            '.footer{font:400 12px Arial,sans-serif;fill:#697985}'
            '</style>'
        ),
        f'<text x="36" y="42" class="title">{html_escape(title)}</text>',
        f'<text x="36" y="70" class="subtitle">{html_escape(subtitle)}</text>',
    ]

    axis_y = margin_top - 22
    axis_label_y = axis_y - 32
    tick_label_y = axis_y - 8
    if x_axis_label:
        svg.append(
            f'<text x="{margin_left}" y="{axis_label_y}" class="axis">'
            f'{html_escape(x_axis_label)}</text>'
        )
    for tick in range(5):
        fraction = tick / 4
        x_pos = margin_left + fraction * plot_width
        tick_value = axis_max * fraction
        tick_label = format_rate_it(tick_value) if axis_max < 10 else format_int_it(round(tick_value))
        svg.append(
            f'<line x1="{x_pos:.1f}" y1="{axis_y}" x2="{x_pos:.1f}" '
            f'y2="{height - footer_height + 8}" stroke="#e4e9ed" stroke-width="1"/>'
        )
        svg.append(
            f'<text x="{x_pos:.1f}" y="{tick_label_y}" class="axis" '
            f'text-anchor="middle">{html_escape(tick_label)}</text>'
        )

    for index, row in enumerate(chart_rows):
        y_center = margin_top + index * row_height + row_height / 2
        value = float(row["value"])
        bar_width = (value / axis_max) * plot_width if axis_max else 0
        label = truncate_label(row["label"])
        value_label = str(row.get("value_label", ""))

        svg.append(
            f'<text x="{margin_left - 18}" y="{y_center + 5:.1f}" '
            f'class="label" text-anchor="end">{html_escape(label)}</text>'
        )
        svg.append(
            f'<rect x="{margin_left}" y="{y_center - bar_height / 2:.1f}" '
            f'width="{bar_width:.1f}" height="{bar_height}" rx="3" fill="{bar_color}"/>'
        )
        svg.append(
            f'<text x="{margin_left + bar_width + 10:.1f}" y="{y_center + 5:.1f}" '
            f'class="value">{html_escape(value_label)}</text>'
        )

    if max_value == 0:
        svg.append(
            f'<text x="{margin_left}" y="{margin_top + 50}" class="subtitle">'
            'Nessun kebab conteggiato con la soglia impostata.</text>'
        )

    footer_separator_y = height - footer_height + 24
    footer_first_line_y = footer_separator_y + 22
    svg.append(
        f'<line x1="36" y1="{footer_separator_y}" x2="{width - 36}" '
        f'y2="{footer_separator_y}" stroke="#e4e9ed" stroke-width="1"/>'
    )
    for line_index, line in enumerate(footer_lines):
        line_y = footer_first_line_y + line_index * 18
        svg.append(f'<text x="36" y="{line_y}" class="footer">{html_escape(line)}</text>')

    svg.append("</svg>")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(svg), encoding="utf-8")


def write_charts(
    out_dir: Path,
    comune_rows: list[dict[str, Any]],
    province_rows: list[dict[str, Any]],
    year: int,
    extra_poi_csv: list[Path],
    include_broad_keywords: bool,
    min_confidence: str,
    chart_top_n: int,
) -> None:
    footer = chart_footer(year, extra_poi_csv)
    method = "OSM"
    if extra_poi_csv:
        method += " + CSV esterni"
    if include_broad_keywords:
        method += " con keyword larghe"
    note_base = (
        f"Note: stima {method}; popolazione ISTAT {year}; "
        f"soglia conteggio {min_confidence}+."
    )
    note_ristoranti = (
        "Denominatore ristoranti OSM: amenity=restaurant, fast_food, food_court."
    )

    province_chart_rows = []
    for row in sorted(province_rows, key=lambda item: parse_rate(item["kebabbari_per_1000"]), reverse=True):
        rate = parse_rate(row["kebabbari_per_1000"])
        province_chart_rows.append(
            {
                "label": row["provincia"],
                "value": rate,
                "value_label": (
                    f"{format_rate_it(rate)} per 1.000 | "
                    f"{format_int_it(row['kebabbari'])} locali"
                ),
            }
        )

    write_horizontal_bar_chart(
        out_dir / "grafico_province_per_1000.svg",
        "Kebabbari per 1.000 abitanti - province Marche",
        "Kebabbari per 1.000 abitanti",
        province_chart_rows,
        "",
        footer,
        "#2a9d8f",
        notes=[note_base],
    )

    province_restaurant_chart_rows = []
    for row in sorted(
        province_rows,
        key=lambda item: parse_rate(item["kebabbari_per_100_ristoranti"]),
        reverse=True,
    ):
        rate = parse_rate(row["kebabbari_per_100_ristoranti"])
        province_restaurant_chart_rows.append(
            {
                "label": row["provincia"],
                "value": rate,
                "value_label": (
                    f"{format_rate_it(rate)} per 100 ristoranti | "
                    f"{format_int_it(row['kebabbari'])}/{format_int_it(row['ristoranti_osm'])}"
                ),
            }
        )

    write_horizontal_bar_chart(
        out_dir / "grafico_province_per_100_ristoranti.svg",
        "Kebabbari per 100 ristoranti - province Marche",
        "Kebabbari per 100 ristoranti OSM",
        province_restaurant_chart_rows,
        "",
        footer,
        "#6d597a",
        notes=[note_base, note_ristoranti],
    )

    comuni_with_kebab = [row for row in comune_rows if int(row["kebabbari"]) > 0]
    top_count_rows = []
    for row in sorted(
        comuni_with_kebab,
        key=lambda item: (int(item["kebabbari"]), parse_rate(item["kebabbari_per_1000"])),
        reverse=True,
    )[:chart_top_n]:
        rate = parse_rate(row["kebabbari_per_1000"])
        top_count_rows.append(
            {
                "label": f"{row['comune']} ({row['provincia']})",
                "value": int(row["kebabbari"]),
                "value_label": (
                    f"{format_int_it(row['kebabbari'])} locali | "
                    f"{format_rate_it(rate)} per 1.000"
                ),
            }
        )

    write_horizontal_bar_chart(
        out_dir / "grafico_comuni_per_numero.svg",
        "Comuni con piu' kebabbari censiti",
        "Numero di kebabbari censiti",
        top_count_rows,
        "",
        footer,
        "#e76f51",
        notes=[note_base],
    )

    top_rate_rows = []
    for row in sorted(
        comuni_with_kebab,
        key=lambda item: (parse_rate(item["kebabbari_per_1000"]), int(item["kebabbari"])),
        reverse=True,
    )[:chart_top_n]:
        rate = parse_rate(row["kebabbari_per_1000"])
        top_rate_rows.append(
            {
                "label": f"{row['comune']} ({row['provincia']})",
                "value": rate,
                "value_label": (
                    f"{format_rate_it(rate)} per 1.000 | "
                    f"{format_int_it(row['kebabbari'])} locali"
                ),
            }
        )

    write_horizontal_bar_chart(
        out_dir / "grafico_comuni_per_1000.svg",
        "Comuni con tasso piu' alto",
        "Kebabbari per 1.000 abitanti",
        top_rate_rows,
        "",
        footer,
        "#457b9d",
        notes=[note_base, "Sono inclusi solo i comuni con almeno 1 kebab censito."],
    )

    top_restaurant_rate_rows = []
    for row in sorted(
        comuni_with_kebab,
        key=lambda item: (
            parse_rate(item["kebabbari_per_100_ristoranti"]),
            int(item["kebabbari"]),
        ),
        reverse=True,
    )[:chart_top_n]:
        rate = parse_rate(row["kebabbari_per_100_ristoranti"])
        top_restaurant_rate_rows.append(
            {
                "label": f"{row['comune']} ({row['provincia']})",
                "value": rate,
                "value_label": (
                    f"{format_rate_it(rate)} per 100 ristoranti | "
                    f"{format_int_it(row['kebabbari'])}/{format_int_it(row['ristoranti_osm'])}"
                ),
            }
        )

    write_horizontal_bar_chart(
        out_dir / "grafico_comuni_per_100_ristoranti.svg",
        "Comuni con piu' kebabbari rispetto ai ristoranti",
        "Kebabbari per 100 ristoranti OSM",
        top_restaurant_rate_rows,
        "",
        footer,
        "#bc6c25",
        notes=[
            note_base,
            note_ristoranti,
            "Sono inclusi solo i comuni con almeno 1 kebab censito.",
        ],
    )

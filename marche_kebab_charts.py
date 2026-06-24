"""
Funzioni per generare grafici PNG dell'analisi kebabbari.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise RuntimeError(
        "Per generare i grafici PNG installa Pillow con: py -m pip install pillow"
    ) from exc


def format_int_it(value: Any) -> str:
    return f"{int(value):,}".replace(",", ".")


def format_rate_it(value: Any) -> str:
    return f"{float(value):.4f}".replace(".", ",")


def parse_rate(value: Any) -> float:
    return float(str(value).replace(",", "."))


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "calibrib.ttf" if bold else "calibri.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


TITLE_FONT = load_font(28, bold=True)
SUBTITLE_FONT = load_font(15)
AXIS_FONT = load_font(12)
LABEL_FONT = load_font(14, bold=True)
VALUE_FONT = load_font(13, bold=True)
FOOTER_FONT = load_font(12)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def truncate_label(
    draw: ImageDraw.ImageDraw,
    value: Any,
    font: ImageFont.ImageFont,
    max_width: int,
) -> str:
    text = str(value)
    if text_size(draw, text, font)[0] <= max_width:
        return text

    ellipsis = "..."
    available = max_width - text_size(draw, ellipsis, font)[0]
    if available <= 0:
        return ellipsis

    result = ""
    for char in text:
        if text_size(draw, result + char, font)[0] > available:
            break
        result += char
    return result.rstrip() + ellipsis


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

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    text_main = "#1f2933"
    text_muted = "#52616b"
    axis_color = "#697985"
    grid_color = "#e4e9ed"

    draw.text((36, 18), title, fill=text_main, font=TITLE_FONT)
    draw.text((36, 56), subtitle, fill=text_muted, font=SUBTITLE_FONT)

    max_value = max(float(row["value"]) for row in chart_rows)
    axis_max = max_value if max_value > 0 else 1.0

    axis_y = margin_top - 22
    axis_label_y = axis_y - 42
    tick_label_y = axis_y - 22
    if x_axis_label:
        draw.text((margin_left, axis_label_y), x_axis_label, fill=axis_color, font=AXIS_FONT)

    for tick in range(5):
        fraction = tick / 4
        x_pos = margin_left + fraction * plot_width
        tick_value = axis_max * fraction
        tick_label = format_rate_it(tick_value) if axis_max < 10 else format_int_it(round(tick_value))
        draw.line((x_pos, axis_y, x_pos, height - footer_height + 8), fill=grid_color, width=1)
        tick_width, _ = text_size(draw, tick_label, AXIS_FONT)
        draw.text((x_pos - tick_width / 2, tick_label_y), tick_label, fill=axis_color, font=AXIS_FONT)

    max_label_width = margin_left - 54
    for index, row in enumerate(chart_rows):
        y_center = margin_top + index * row_height + row_height / 2
        value = float(row["value"])
        bar_width = (value / axis_max) * plot_width if axis_max else 0
        label = truncate_label(draw, row["label"], LABEL_FONT, max_label_width)
        value_label = str(row.get("value_label", ""))

        label_width, label_height = text_size(draw, label, LABEL_FONT)
        draw.text(
            (margin_left - 18 - label_width, y_center - label_height / 2 - 1),
            label,
            fill=text_main,
            font=LABEL_FONT,
        )

        bar_top = y_center - bar_height / 2
        draw.rounded_rectangle(
            (margin_left, bar_top, margin_left + bar_width, bar_top + bar_height),
            radius=3,
            fill=bar_color,
        )

        value_width, value_height = text_size(draw, value_label, VALUE_FONT)
        outside_x = margin_left + bar_width + 10
        if outside_x + value_width <= width - 36:
            draw.text(
                (outside_x, y_center - value_height / 2 - 1),
                value_label,
                fill=text_main,
                font=VALUE_FONT,
            )
        else:
            inside_x = max(margin_left + 8, margin_left + bar_width - value_width - 8)
            draw.text(
                (inside_x, y_center - value_height / 2 - 1),
                value_label,
                fill="white",
                font=VALUE_FONT,
            )

    if max_value == 0:
        draw.text(
            (margin_left, margin_top + 42),
            "Nessun kebab conteggiato con la soglia impostata.",
            fill=text_muted,
            font=SUBTITLE_FONT,
        )

    footer_separator_y = height - footer_height + 24
    footer_first_line_y = footer_separator_y + 18
    draw.line((36, footer_separator_y, width - 36, footer_separator_y), fill=grid_color, width=1)
    for line_index, line in enumerate(footer_lines):
        draw.text(
            (36, footer_first_line_y + line_index * 18),
            line,
            fill=axis_color,
            font=FOOTER_FONT,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


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
        out_dir / "grafico_province_per_1000.png",
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
        out_dir / "grafico_province_per_100_ristoranti.png",
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
        out_dir / "grafico_comuni_per_numero.png",
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
        out_dir / "grafico_comuni_per_1000.png",
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
        out_dir / "grafico_comuni_per_100_ristoranti.png",
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

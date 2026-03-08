from __future__ import annotations

import json
import random
from functools import lru_cache
from importlib.resources import files
from typing import Any

from .models import Layout, Theme, ThemeMapColors, ThemeRoadColors, ThemeUiColors

PACKAGE_DATA_DIR = files("terraink_py").joinpath("data")
DEFAULT_THEME_ID = "midnight_blue"
DEFAULT_LAYOUT_ID = "print_a4_portrait"


def _read_json(filename: str) -> dict[str, Any]:
    return json.loads(PACKAGE_DATA_DIR.joinpath(filename).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_themes() -> dict[str, Theme]:
    raw = _read_json("themes.json").get("themes", {})
    themes: dict[str, Theme] = {}
    for theme_id, value in raw.items():
        ui = value.get("ui", {})
        map_colors = value.get("map", {})
        road_colors = map_colors.get("roads", {})
        themes[theme_id] = Theme(
            id=theme_id,
            name=str(value.get("name", theme_id)),
            description=str(value.get("description", "")),
            ui=ThemeUiColors(
                bg=str(ui.get("bg", "#0A1628")),
                text=str(ui.get("text", "#D6B352")),
            ),
            map=ThemeMapColors(
                land=str(map_colors.get("land", "#0A1628")),
                water=str(map_colors.get("water", "#061020")),
                waterway=str(
                    map_colors.get("waterway", map_colors.get("water", "#061020"))
                ),
                parks=str(map_colors.get("parks", "#0F2235")),
                buildings=str(map_colors.get("buildings", "#6E5A45")),
                aeroway=str(map_colors.get("aeroway", "#0F2235")),
                rail=str(map_colors.get("rail", "#D6B352")),
                roads=ThemeRoadColors(
                    major=str(road_colors.get("major", "#C99C37")),
                    minor_high=str(road_colors.get("minor_high", "#8A6820")),
                    minor_mid=str(road_colors.get("minor_mid", "#333530")),
                    minor_low=str(road_colors.get("minor_low", "#272C2E")),
                    path=str(road_colors.get("path", "#414033")),
                    outline=str(road_colors.get("outline", "#4F4B36")),
                ),
            ),
        )
    return themes


def get_theme(theme_id: str) -> Theme:
    themes = load_themes()
    if theme_id == "random":
        return random.choice(list(themes.values()))
    return themes.get(
        theme_id, themes.get(DEFAULT_THEME_ID) or next(iter(themes.values()))
    )


@lru_cache(maxsize=1)
def load_layouts() -> dict[str, Layout]:
    data = _read_json("layouts.json")
    layouts: dict[str, Layout] = {}
    for category in data.get("categories", []):
        for entry in category.get("layouts", []):
            layout = Layout(
                id=str(entry.get("id", "")),
                name=str(entry.get("name", "")),
                description=str(entry.get("description", "")),
                width=float(entry.get("width", 21)),
                height=float(entry.get("height", 29.7)),
                unit=str(entry.get("unit", "cm")),
                width_cm=float(entry.get("posterWidthCm", entry.get("width", 21))),
                height_cm=float(entry.get("posterHeightCm", entry.get("height", 29.7))),
            )
            if layout.id:
                layouts[layout.id] = layout
    return layouts


def get_layout(layout_id: str) -> Layout:
    layouts = load_layouts()
    return layouts.get(
        layout_id, layouts.get(DEFAULT_LAYOUT_ID) or next(iter(layouts.values()))
    )

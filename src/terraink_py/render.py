from __future__ import annotations

import math
from pathlib import Path
from xml.sax.saxutils import escape

from .geo import MercatorProjector, format_coordinates
from .models import CanvasSize, Coordinate, Point, PosterRequest, ProjectedScene, Theme
from .text import (
    ATTRIBUTION_FONT_BASE_PX,
    CITY_FONT_BASE_PX,
    CITY_FONT_MIN_PX,
    CITY_TEXT_SHRINK_THRESHOLD,
    COORDS_FONT_BASE_PX,
    COUNTRY_FONT_BASE_PX,
    CREATOR_CREDIT,
    DEFAULT_FONT_FAMILY,
    DEFAULT_MONO_FAMILY,
    TEXT_CITY_Y_RATIO,
    TEXT_COORDS_Y_RATIO,
    TEXT_COUNTRY_Y_RATIO,
    TEXT_DIMENSION_REFERENCE_PX,
    TEXT_DIVIDER_Y_RATIO,
    TEXT_EDGE_MARGIN_RATIO,
    contains_cjk,
    format_city_label,
)

LayerMap = dict[str, list[list[tuple[float, float]]]]

# Mirrors the working font-discovery idea from tg_bot_collections so CJK place
# names render without tofu on macOS/Linux even when the user provides no font.
CJK_FONT_CANDIDATES_REGULAR = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSerifCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
CJK_FONT_CANDIDATES_BOLD = [
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/opentype/noto/NotoSerifCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]
DEFAULT_SVG_FONT_STACK = [
    DEFAULT_FONT_FAMILY,
    "Arial",
    "Helvetica Neue",
    "sans-serif",
]
DEFAULT_SVG_MONO_STACK = [
    DEFAULT_MONO_FAMILY,
    "Menlo",
    "SFMono-Regular",
    "monospace",
]
CJK_SVG_FONT_STACK = [
    "Hiragino Sans GB",
    "PingFang SC",
    "STHeiti",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Arial Unicode MS",
    "sans-serif",
]
EARTH_CIRCUMFERENCE_M = 40_075_016.686
TILE_SIZE_PX = 512.0
MIN_MAP_ZOOM = 0.5
MAX_MAP_ZOOM = 20.0


def build_scene(
    *,
    size: CanvasSize,
    center: Coordinate,
    title: str,
    subtitle: str,
    theme: Theme,
    layers: LayerMap,
    projector: MercatorProjector,
    request: PosterRequest,
) -> ProjectedScene:
    polygons = {
        name: [project_path(projector, path) for path in paths if len(path) >= 4]
        for name, paths in layers.items()
        if name in {"water", "parks", "buildings", "aeroway"}
    }
    lines = {
        name: [project_path(projector, path) for path in paths if len(path) >= 2]
        for name, paths in layers.items()
        if name not in {"water", "parks", "buildings", "aeroway"}
    }
    return ProjectedScene(
        width=size.width,
        height=size.height,
        requested_width=size.requested_width,
        requested_height=size.requested_height,
        downscale_factor=size.downscale_factor,
        dpi=request.dpi,
        center=center,
        title=title,
        subtitle=subtitle,
        theme=theme,
        polygons=polygons,
        lines=lines,
        show_poster_text=request.show_poster_text,
        include_credits=request.include_credits,
        include_road_outline=request.include_road_outline,
        font_file=request.font_file,
        font_family=request.font_family,
        distance_m=request.distance_m,
    )


def project_path(projector: MercatorProjector, path: list[tuple[float, float]]) -> list[Point]:
    return [projector.project(lon, lat) for lon, lat in path]


def render_svg(scene: ProjectedScene) -> str:
    theme = scene.theme
    metrics = compute_scene_metrics(scene)
    prefers_cjk = scene_prefers_cjk(scene)
    font_family = build_svg_font_stack(scene.font_family, prefers_cjk=prefers_cjk)
    mono_family = build_svg_font_stack(scene.font_family, prefers_cjk=False, monospace=True)
    aria_label = svg_attr(f"{scene.title} map poster")

    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.width}" height="{scene.height}" '
            f'viewBox="0 0 {scene.width} {scene.height}" role="img" aria-label="{aria_label}">'
        ),
        "<defs>",
        '<linearGradient id="terraink-fade-top" x1="0" y1="0" x2="0" y2="1">',
        f'<stop offset="0%" stop-color="{theme.ui.bg}" stop-opacity="1"/>',
        f'<stop offset="100%" stop-color="{theme.ui.bg}" stop-opacity="0"/>',
        "</linearGradient>",
        '<linearGradient id="terraink-fade-bottom" x1="0" y1="1" x2="0" y2="0">',
        f'<stop offset="0%" stop-color="{theme.ui.bg}" stop-opacity="1"/>',
        f'<stop offset="100%" stop-color="{theme.ui.bg}" stop-opacity="0"/>',
        "</linearGradient>",
        "</defs>",
        f'<rect width="{scene.width}" height="{scene.height}" fill="{theme.map.land}"/>',
    ]

    for layer_name, color, opacity in (
        ("parks", theme.map.parks, 1.0),
        ("water", theme.map.water, 1.0),
        ("aeroway", theme.map.aeroway, 0.85),
        ("buildings", theme.map.buildings, 0.84),
    ):
        for path in scene.polygons.get(layer_name, []):
            lines.append(
                f'<path d="{path_to_svg(path, closed=True)}" fill="{color}" fill-opacity="{opacity:.3f}"/>'
            )

    for path in scene.lines.get("waterway", []):
        lines.append(
            stroke_path_element(
                path,
                stroke=theme.map.waterway,
                stroke_width=metrics["waterway_width"],
                opacity=0.92,
            )
        )

    for path in scene.lines.get("rail", []):
        lines.append(
            stroke_path_element(
                path,
                stroke=theme.map.rail,
                stroke_width=metrics["rail_width"],
                opacity=0.7,
                dasharray=f"{fmt(metrics['rail_width'] * 2.0)} {fmt(metrics['rail_width'] * 1.6)}",
            )
        )

    for layer_name, color, width_key, opacity_key in (
        ("road_minor_high", theme.map.roads.minor_high, "minor_high_overview_width", "minor_high_overview_opacity"),
        ("road_minor_mid", theme.map.roads.minor_mid, "minor_mid_overview_width", "minor_mid_overview_opacity"),
        ("road_minor_low", theme.map.roads.minor_low, "minor_low_overview_width", "minor_low_overview_opacity"),
        ("road_path", theme.map.roads.path, "path_overview_width", "path_overview_opacity"),
    ):
        opacity = metrics[opacity_key]
        if opacity <= 0.001:
            continue
        for path in scene.lines.get(layer_name, []):
            lines.append(
                stroke_path_element(
                    path,
                    stroke=color,
                    stroke_width=metrics[width_key],
                    opacity=opacity,
                )
            )

    if scene.include_road_outline:
        for layer_name, width_key, opacity_key in (
            ("road_major", "major_casing_width", "major_casing_opacity"),
            ("road_minor_high", "minor_high_casing_width", "minor_high_casing_opacity"),
            ("road_minor_mid", "minor_mid_casing_width", "minor_mid_casing_opacity"),
            ("road_path", "path_casing_width", "path_casing_opacity"),
        ):
            opacity = metrics[opacity_key]
            if opacity <= 0.001:
                continue
            for path in scene.lines.get(layer_name, []):
                lines.append(
                    stroke_path_element(
                        path,
                        stroke=theme.map.roads.outline,
                        stroke_width=metrics[width_key],
                        opacity=opacity,
                    )
                )

    for layer_name, color, width_key, opacity_key in (
        ("road_major", theme.map.roads.major, "major_width", "major_opacity"),
        ("road_minor_high", theme.map.roads.minor_high, "minor_high_width", "minor_high_opacity"),
        ("road_minor_mid", theme.map.roads.minor_mid, "minor_mid_width", "minor_mid_opacity"),
        ("road_minor_low", theme.map.roads.minor_low, "minor_low_width", "minor_low_opacity"),
        ("road_path", theme.map.roads.path, "path_width", "path_opacity"),
    ):
        opacity = metrics[opacity_key]
        if opacity <= 0.001:
            continue
        for path in scene.lines.get(layer_name, []):
            lines.append(
                stroke_path_element(
                    path,
                    stroke=color,
                    stroke_width=metrics[width_key],
                    opacity=opacity,
                )
            )

    lines.extend(
        [
            f'<rect x="0" y="0" width="{scene.width}" height="{scene.height * 0.25}" fill="url(#terraink-fade-top)"/>',
            f'<rect x="0" y="{scene.height * 0.75}" width="{scene.width}" height="{scene.height * 0.25}" fill="url(#terraink-fade-bottom)"/>',
        ]
    )

    if scene.show_poster_text:
        lines.extend(
            render_svg_text_block(
                scene=scene,
                font_family=font_family,
                mono_family=mono_family,
                metrics=metrics,
            )
        )

    lines.extend(
        render_svg_credits(
            scene=scene,
            mono_family=mono_family,
            metrics=metrics,
        )
    )
    lines.append("</svg>")
    return "\n".join(lines)


def render_png(scene: ProjectedScene, output_path: Path) -> None:
    from PIL import Image, ImageDraw

    theme = scene.theme
    metrics = compute_scene_metrics(scene)
    image = Image.new("RGBA", (scene.width, scene.height), hex_to_rgba(theme.map.land))
    draw = ImageDraw.Draw(image, "RGBA")

    for layer_name, color, alpha in (
        ("parks", theme.map.parks, 255),
        ("water", theme.map.water, 255),
        ("aeroway", theme.map.aeroway, 217),
        ("buildings", theme.map.buildings, 214),
    ):
        for path in scene.polygons.get(layer_name, []):
            draw.polygon(path, fill=hex_to_rgba(color, alpha))

    for path in scene.lines.get("waterway", []):
        draw_polyline(
            draw,
            path,
            fill=hex_to_rgba(theme.map.waterway, 235),
            width=metrics["waterway_width"],
        )

    for path in scene.lines.get("rail", []):
        draw_dashed_polyline(
            draw,
            path,
            fill=hex_to_rgba(theme.map.rail, 180),
            width=metrics["rail_width"],
            dash=max(metrics["rail_width"] * 2.0, 3.0),
            gap=max(metrics["rail_width"] * 1.6, 2.0),
        )

    for layer_name, color, width_key, opacity_key in (
        ("road_minor_high", theme.map.roads.minor_high, "minor_high_overview_width", "minor_high_overview_opacity"),
        ("road_minor_mid", theme.map.roads.minor_mid, "minor_mid_overview_width", "minor_mid_overview_opacity"),
        ("road_minor_low", theme.map.roads.minor_low, "minor_low_overview_width", "minor_low_overview_opacity"),
        ("road_path", theme.map.roads.path, "path_overview_width", "path_overview_opacity"),
    ):
        alpha = opacity_to_alpha(metrics[opacity_key])
        if alpha <= 0:
            continue
        for path in scene.lines.get(layer_name, []):
            draw_polyline(
                draw,
                path,
                fill=hex_to_rgba(color, alpha),
                width=metrics[width_key],
            )

    if scene.include_road_outline:
        for layer_name, width_key, opacity_key in (
            ("road_major", "major_casing_width", "major_casing_opacity"),
            ("road_minor_high", "minor_high_casing_width", "minor_high_casing_opacity"),
            ("road_minor_mid", "minor_mid_casing_width", "minor_mid_casing_opacity"),
            ("road_path", "path_casing_width", "path_casing_opacity"),
        ):
            alpha = opacity_to_alpha(metrics[opacity_key])
            if alpha <= 0:
                continue
            for path in scene.lines.get(layer_name, []):
                draw_polyline(
                    draw,
                    path,
                    fill=hex_to_rgba(theme.map.roads.outline, alpha),
                    width=metrics[width_key],
                )

    for layer_name, color, width_key, opacity_key in (
        ("road_major", theme.map.roads.major, "major_width", "major_opacity"),
        ("road_minor_high", theme.map.roads.minor_high, "minor_high_width", "minor_high_opacity"),
        ("road_minor_mid", theme.map.roads.minor_mid, "minor_mid_width", "minor_mid_opacity"),
        ("road_minor_low", theme.map.roads.minor_low, "minor_low_width", "minor_low_opacity"),
        ("road_path", theme.map.roads.path, "path_width", "path_opacity"),
    ):
        alpha = opacity_to_alpha(metrics[opacity_key])
        if alpha <= 0:
            continue
        for path in scene.lines.get(layer_name, []):
            draw_polyline(
                draw,
                path,
                fill=hex_to_rgba(color, alpha),
                width=metrics[width_key],
            )

    apply_png_fades(image, theme.ui.bg)

    font_regular = resolve_font(
        scene.font_file,
        int(metrics["country_font_size"]),
        bold=False,
        text=scene.subtitle,
    )
    font_bold = resolve_font(
        scene.font_file,
        int(metrics["city_font_size"]),
        bold=True,
        text=scene.title,
    )
    font_coords = resolve_font(
        scene.font_file,
        int(metrics["coords_font_size"]),
        bold=False,
        monospace=True,
        text=format_coordinates(scene.center.lat, scene.center.lon),
    )
    font_credit = resolve_font(
        scene.font_file,
        int(metrics["attribution_font_size"]),
        bold=False,
        monospace=True,
        text=CREATOR_CREDIT,
    )

    if scene.show_poster_text:
        city_label = format_city_label(scene.title)
        draw_centered_text(
            draw,
            (scene.width * 0.5, scene.height * TEXT_CITY_Y_RATIO),
            city_label,
            font_bold,
            fill=hex_to_rgba(theme.ui.text),
        )
        draw.line(
            (
                scene.width * 0.4,
                scene.height * TEXT_DIVIDER_Y_RATIO,
                scene.width * 0.6,
                scene.height * TEXT_DIVIDER_Y_RATIO,
            ),
            fill=hex_to_rgba(theme.ui.text),
            width=max(1, int(round(3 * metrics["dim_scale"]))),
        )
        draw_centered_text(
            draw,
            (scene.width * 0.5, scene.height * TEXT_COUNTRY_Y_RATIO),
            scene.subtitle.upper(),
            font_regular,
            fill=hex_to_rgba(theme.ui.text),
        )
        draw_centered_text(
            draw,
            (scene.width * 0.5, scene.height * TEXT_COORDS_Y_RATIO),
            format_coordinates(scene.center.lat, scene.center.lon),
            font_coords,
            fill=hex_to_rgba(theme.ui.text, 192),
        )

    edge_margin_x = scene.width * TEXT_EDGE_MARGIN_RATIO
    edge_margin_y = scene.height * (1 - TEXT_EDGE_MARGIN_RATIO)
    draw.text(
        (scene.width - edge_margin_x, edge_margin_y),
        "\u00a9 OpenStreetMap contributors",
        fill=hex_to_rgba(theme.ui.text, opacity_to_alpha(0.55)),
        font=font_credit,
        anchor="rb",
    )
    if scene.include_credits:
        draw.text(
            (edge_margin_x, edge_margin_y),
            CREATOR_CREDIT,
            fill=hex_to_rgba(theme.ui.text, opacity_to_alpha(0.55)),
            font=font_credit,
            anchor="lb",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", dpi=(scene.dpi, scene.dpi))


def render_svg_text_block(
    *,
    scene: ProjectedScene,
    font_family: str,
    mono_family: str,
    metrics: dict[str, float],
) -> list[str]:
    city_label = escape(format_city_label(scene.title))
    return [
        (
            f'<text x="{fmt(scene.width * 0.5)}" y="{fmt(scene.height * TEXT_CITY_Y_RATIO)}" '
            f'fill="{scene.theme.ui.text}" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="{svg_attr(font_family)}" font-size="{fmt(metrics["city_font_size"])}" '
            'font-weight="700">'
            f"{city_label}</text>"
        ),
        (
            f'<line x1="{fmt(scene.width * 0.4)}" y1="{fmt(scene.height * TEXT_DIVIDER_Y_RATIO)}" '
            f'x2="{fmt(scene.width * 0.6)}" y2="{fmt(scene.height * TEXT_DIVIDER_Y_RATIO)}" '
            f'stroke="{scene.theme.ui.text}" stroke-width="{fmt(3 * metrics["dim_scale"])}"/>'
        ),
        (
            f'<text x="{fmt(scene.width * 0.5)}" y="{fmt(scene.height * TEXT_COUNTRY_Y_RATIO)}" '
            f'fill="{scene.theme.ui.text}" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="{svg_attr(font_family)}" font-size="{fmt(metrics["country_font_size"])}" '
            f'font-weight="300">{escape(scene.subtitle.upper())}</text>'
        ),
        (
            f'<text x="{fmt(scene.width * 0.5)}" y="{fmt(scene.height * TEXT_COORDS_Y_RATIO)}" '
            f'fill="{scene.theme.ui.text}" fill-opacity="0.75" text-anchor="middle" dominant-baseline="middle" '
            f'font-family="{svg_attr(mono_family)}" font-size="{fmt(metrics["coords_font_size"])}" '
            f'font-weight="400">{escape(format_coordinates(scene.center.lat, scene.center.lon))}</text>'
        ),
    ]


def render_svg_credits(
    *,
    scene: ProjectedScene,
    mono_family: str,
    metrics: dict[str, float],
) -> list[str]:
    output = [
        (
            f'<text x="{fmt(scene.width * (1 - TEXT_EDGE_MARGIN_RATIO))}" '
            f'y="{fmt(scene.height * (1 - TEXT_EDGE_MARGIN_RATIO))}" fill="{scene.theme.ui.text}" '
            'fill-opacity="0.55" text-anchor="end" dominant-baseline="baseline" '
            f'font-family="{svg_attr(mono_family)}" font-size="{fmt(metrics["attribution_font_size"])}">'
            "\u00a9 OpenStreetMap contributors</text>"
        )
    ]
    if scene.include_credits:
        output.append(
            (
                f'<text x="{fmt(scene.width * TEXT_EDGE_MARGIN_RATIO)}" '
                f'y="{fmt(scene.height * (1 - TEXT_EDGE_MARGIN_RATIO))}" fill="{scene.theme.ui.text}" '
                'fill-opacity="0.55" text-anchor="start" dominant-baseline="baseline" '
                f'font-family="{svg_attr(mono_family)}" font-size="{fmt(metrics["attribution_font_size"])}">'
                f"{escape(CREATOR_CREDIT)}</text>"
            )
        )
    return output


def compute_scene_metrics(scene: ProjectedScene) -> dict[str, float]:
    dim_scale = max(0.45, min(scene.width, scene.height) / TEXT_DIMENSION_REFERENCE_PX)
    distance_factor = clamp((4_000.0 / scene.distance_m) ** 0.38, 0.42, 2.2)
    line_scale = dim_scale * distance_factor
    estimated_zoom = estimate_map_zoom(scene)
    title_length = max(len(scene.title), 1)
    city_font_size = CITY_FONT_BASE_PX * dim_scale
    if title_length > CITY_TEXT_SHRINK_THRESHOLD:
        city_font_size = max(
            CITY_FONT_MIN_PX * dim_scale,
            city_font_size * (CITY_TEXT_SHRINK_THRESHOLD / title_length),
        )
    major_width = max(1.1, 5.4 * line_scale)
    minor_high_width = max(0.86, 3.15 * line_scale)
    minor_mid_width = max(0.72, 2.2 * line_scale)
    minor_low_width = max(0.58, 1.4 * line_scale)
    path_width = max(0.5, 0.92 * line_scale)
    return {
        "dim_scale": dim_scale,
        "estimated_zoom": estimated_zoom,
        "city_font_size": city_font_size,
        "country_font_size": COUNTRY_FONT_BASE_PX * dim_scale,
        "coords_font_size": COORDS_FONT_BASE_PX * dim_scale,
        "attribution_font_size": ATTRIBUTION_FONT_BASE_PX * dim_scale,
        "major_width": major_width,
        "minor_high_width": minor_high_width,
        "minor_mid_width": minor_mid_width,
        "minor_low_width": minor_low_width,
        "path_width": path_width,
        "waterway_width": max(0.62, 1.15 * line_scale),
        "rail_width": max(0.58, 0.92 * line_scale),
        "major_casing_width": major_width * 1.38,
        "minor_high_casing_width": minor_high_width * 1.45,
        "minor_mid_casing_width": minor_mid_width * 1.15,
        "path_casing_width": path_width * 1.6,
        "minor_high_overview_width": max(0.1, minor_high_width * 0.34),
        "minor_mid_overview_width": max(0.08, minor_mid_width * 0.3),
        "minor_low_overview_width": max(0.06, minor_low_width * 0.26),
        "path_overview_width": max(0.05, path_width * 0.24),
        "major_opacity": 1.0,
        "minor_high_overview_opacity": interpolate_stops(
            estimated_zoom,
            ((0.0, 0.66), (8.0, 0.76), (12.0, 0.0)),
        ),
        "minor_mid_overview_opacity": interpolate_stops(
            estimated_zoom,
            ((0.0, 0.46), (8.0, 0.56), (12.0, 0.0)),
        ),
        "minor_low_overview_opacity": interpolate_stops(
            estimated_zoom,
            ((0.0, 0.26), (8.0, 0.34), (12.0, 0.0)),
        ),
        "path_overview_opacity": interpolate_stops(
            estimated_zoom,
            ((5.0, 0.45), (9.0, 0.58), (12.0, 0.0)),
        ),
        "major_casing_opacity": 0.95 if scene.include_road_outline else 0.0,
        "minor_high_casing_opacity": interpolate_stops(
            estimated_zoom,
            ((6.0, 0.72), (12.0, 0.85), (18.0, 0.92)),
        )
        if scene.include_road_outline
        else 0.0,
        "minor_mid_casing_opacity": interpolate_stops(
            estimated_zoom,
            ((6.0, 0.42), (12.0, 0.56), (18.0, 0.66)),
        )
        if scene.include_road_outline
        else 0.0,
        "path_casing_opacity": interpolate_stops(
            estimated_zoom,
            ((8.0, 0.62), (12.0, 0.72), (18.0, 0.85)),
        )
        if scene.include_road_outline
        else 0.0,
        "minor_high_opacity": interpolate_stops(
            estimated_zoom,
            ((6.0, 0.84), (10.0, 0.92), (18.0, 1.0)),
        ),
        "minor_mid_opacity": interpolate_stops(
            estimated_zoom,
            ((6.0, 0.62), (10.0, 0.74), (18.0, 0.86)),
        ),
        "minor_low_opacity": interpolate_stops(
            estimated_zoom,
            ((6.0, 0.34), (10.0, 0.46), (18.0, 0.58)),
        ),
        "path_opacity": interpolate_stops(
            estimated_zoom,
            ((8.0, 0.7), (12.0, 0.82), (18.0, 0.95)),
        ),
    }


def estimate_map_zoom(scene: ProjectedScene) -> float:
    full_width_meters = max(scene.distance_m * 2.0, 1.0)
    cosine = max(abs(math.cos(math.radians(scene.center.lat))), 0.01)
    zoom = math.log2(
        (EARTH_CIRCUMFERENCE_M * cosine * max(scene.width, 1))
        / (full_width_meters * TILE_SIZE_PX)
    )
    return clamp(zoom, MIN_MAP_ZOOM, MAX_MAP_ZOOM)


def interpolate_stops(value: float, stops: tuple[tuple[float, float], ...]) -> float:
    if not stops:
        return 0.0
    if value <= stops[0][0]:
        return stops[0][1]
    for (start_x, start_y), (end_x, end_y) in zip(stops, stops[1:]):
        if value <= end_x:
            if end_x == start_x:
                return end_y
            ratio = (value - start_x) / (end_x - start_x)
            return start_y + (end_y - start_y) * ratio
    return stops[-1][1]


def stroke_path_element(
    path: list[Point],
    *,
    stroke: str,
    stroke_width: float,
    opacity: float,
    dasharray: str | None = None,
) -> str:
    dash_attr = f' stroke-dasharray="{dasharray}"' if dasharray else ""
    return (
        f'<path d="{path_to_svg(path, closed=False)}" fill="none" stroke="{stroke}" '
        f'stroke-width="{fmt(stroke_width)}" stroke-opacity="{opacity:.3f}" '
        f'stroke-linecap="round" stroke-linejoin="round"{dash_attr}/>'
    )


def path_to_svg(path: list[Point], *, closed: bool) -> str:
    parts = [f"M {fmt(path[0][0])} {fmt(path[0][1])}"]
    parts.extend(f"L {fmt(x)} {fmt(y)}" for x, y in path[1:])
    if closed:
        parts.append("Z")
    return " ".join(parts)


def fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def svg_attr(value: str) -> str:
    return escape(value, entities={'"': "&quot;", "'": "&apos;"})


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def hex_to_rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        return (0, 0, 0, alpha)
    return (
        int(raw[0:2], 16),
        int(raw[2:4], 16),
        int(raw[4:6], 16),
        alpha,
    )


def opacity_to_alpha(opacity: float) -> int:
    return max(0, min(255, int(round(opacity * 255))))


def draw_polyline(draw, points: list[Point], *, fill: tuple[int, int, int, int], width: float) -> None:
    draw.line(points, fill=fill, width=max(1, int(round(width))), joint="curve")


def draw_dashed_polyline(
    draw,
    points: list[Point],
    *,
    fill: tuple[int, int, int, int],
    width: float,
    dash: float,
    gap: float,
) -> None:
    if len(points) < 2:
        return
    width_int = max(1, int(round(width)))
    for start, end in zip(points, points[1:]):
        x1, y1 = start
        x2, y2 = end
        segment_length = math.hypot(x2 - x1, y2 - y1)
        if segment_length == 0:
            continue
        dx = (x2 - x1) / segment_length
        dy = (y2 - y1) / segment_length
        position = 0.0
        while position < segment_length:
            dash_end = min(position + dash, segment_length)
            draw.line(
                (
                    x1 + dx * position,
                    y1 + dy * position,
                    x1 + dx * dash_end,
                    y1 + dy * dash_end,
                ),
                fill=fill,
                width=width_int,
                joint="curve",
            )
            position += dash + gap


def apply_png_fades(image, color: str) -> None:
    from PIL import Image

    rgb = hex_to_rgba(color, 255)
    width, height = image.size
    alpha_strip = Image.new("L", (1, height), 0)
    alpha_pixels = alpha_strip.load()
    for y in range(height):
        if y <= height * 0.25:
            alpha = int(255 * (1 - (y / max(height * 0.25, 1))))
        elif y >= height * 0.75:
            alpha = int(255 * ((y - height * 0.75) / max(height * 0.25, 1)))
        else:
            alpha = 0
        alpha_pixels[0, y] = max(0, min(255, alpha))
    overlay = Image.new("RGBA", image.size, (rgb[0], rgb[1], rgb[2], 0))
    overlay.putalpha(alpha_strip.resize((width, height)))
    image.alpha_composite(overlay)


def scene_prefers_cjk(scene: ProjectedScene) -> bool:
    return contains_cjk(scene.title) or contains_cjk(scene.subtitle)


def build_svg_font_stack(
    preferred_family: str | None,
    *,
    prefers_cjk: bool,
    monospace: bool = False,
) -> str:
    stack: list[str] = []
    if preferred_family:
        stack.append(preferred_family)
    stack.extend(CJK_SVG_FONT_STACK if prefers_cjk else [])
    stack.extend(DEFAULT_SVG_MONO_STACK if monospace else DEFAULT_SVG_FONT_STACK)

    deduped: list[str] = []
    seen: set[str] = set()
    for family in stack:
        normalized = family.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        if " " in normalized and not normalized.startswith('"'):
            deduped.append(f'"{normalized}"')
        else:
            deduped.append(normalized)
    return ", ".join(deduped)


def resolve_font(
    font_file: Path | None,
    size: int,
    *,
    bold: bool,
    monospace: bool = False,
    text: str | None = None,
) -> object:
    from PIL import ImageFont

    size = max(size, 12)
    candidates: list[str] = []
    if font_file is not None:
        candidates.append(str(font_file))
    if contains_cjk(text):
        candidates.extend(
            CJK_FONT_CANDIDATES_BOLD if bold else CJK_FONT_CANDIDATES_REGULAR
        )
    if monospace:
        candidates.extend(
            [
                "IBMPlexMono-Regular.ttf",
                "IBM Plex Mono.ttf",
                "/Library/Fonts/IBM Plex Mono.ttf",
                "/System/Library/Fonts/SFNSMono.ttf",
                "/System/Library/Fonts/Supplemental/Menlo.ttc",
                "DejaVuSansMono.ttf",
            ]
        )
    if bold:
        candidates.extend(
            [
                "SpaceGrotesk-Bold.ttf",
                "Space Grotesk Bold.ttf",
                "/Library/Fonts/SpaceGrotesk-Bold.ttf",
                "DejaVuSans-Bold.ttf",
                "/Library/Fonts/Arial Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            ]
        )
    elif not monospace:
        candidates.extend(
            [
                "SpaceGrotesk-Regular.ttf",
                "SpaceGrotesk-Medium.ttf",
                "Space Grotesk Regular.ttf",
                "/Library/Fonts/SpaceGrotesk-Regular.ttf",
                "DejaVuSans.ttf",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
            ]
        )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_centered_text(
    draw,
    position: tuple[float, float],
    text: str,
    font,
    *,
    fill: tuple[int, int, int, int],
    tracking: float = 0.0,
) -> None:
    if tracking <= 0:
        draw.text(position, text, fill=fill, font=font, anchor="mm")
        return

    char_boxes = [font.getbbox(char) for char in text]
    char_widths = [box[2] - box[0] for box in char_boxes]
    total_width = sum(char_widths) + tracking * max(len(text) - 1, 0)
    x = position[0] - total_width / 2.0
    for char, char_width in zip(text, char_widths):
        draw.text((x + char_width / 2.0, position[1]), char, fill=fill, font=font, anchor="mm")
        x += char_width + tracking

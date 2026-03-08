from __future__ import annotations

import math
from dataclasses import dataclass

from .models import Bounds, CanvasSize, Coordinate, PosterBoundsResult

CM_PER_INCH = 2.54
METERS_PER_DEGREE = 111_320
MIN_COSINE = 0.1
FETCH_PADDING = 1.35
MIN_SAFE_DISTANCE_METERS = 1_000
MIN_SAFE_ASPECT_RATIO = 0.2
MAX_MERCATOR_LAT = 85.05112878
EARTH_RADIUS_M = 6_378_137.0


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def to_radians(value: float) -> float:
    return (value * math.pi) / 180.0


def meters_to_lat_delta(meters: float) -> float:
    return meters / METERS_PER_DEGREE


def meters_to_lon_delta(meters: float, at_latitude: float) -> float:
    cosine = max(abs(math.cos(to_radians(at_latitude))), MIN_COSINE)
    return meters / (METERS_PER_DEGREE * cosine)


def create_bounds(
    center_lat: float,
    center_lon: float,
    half_meters_x: float,
    half_meters_y: float,
) -> Bounds:
    lat_delta = meters_to_lat_delta(half_meters_y)
    lon_delta = meters_to_lon_delta(half_meters_x, center_lat)
    return Bounds(
        south=clamp(center_lat - lat_delta, -85.0, 85.0),
        west=center_lon - lon_delta,
        north=clamp(center_lat + lat_delta, -85.0, 85.0),
        east=center_lon + lon_delta,
    )


def compute_poster_and_fetch_bounds(
    center: Coordinate,
    distance_meters: float,
    aspect_ratio: float,
    fetch_padding: float = FETCH_PADDING,
) -> PosterBoundsResult:
    safe_distance = max(MIN_SAFE_DISTANCE_METERS, distance_meters)
    safe_aspect = max(MIN_SAFE_ASPECT_RATIO, aspect_ratio)
    half_meters_x = safe_distance
    half_meters_y = safe_distance
    if safe_aspect > 1:
        half_meters_y = safe_distance / safe_aspect
    else:
        half_meters_x = safe_distance * safe_aspect
    fetch_half_meters = max(half_meters_x, half_meters_y) * fetch_padding
    return PosterBoundsResult(
        poster_bounds=create_bounds(center.lat, center.lon, half_meters_x, half_meters_y),
        fetch_bounds=create_bounds(
            center.lat,
            center.lon,
            fetch_half_meters,
            fetch_half_meters,
        ),
        half_meters_x=half_meters_x,
        half_meters_y=half_meters_y,
        fetch_half_meters=fetch_half_meters,
    )


def resolve_canvas_size(
    width_inches: float,
    height_inches: float,
    dpi: int = 300,
    max_pixels: int = 8_500_000,
    max_side: int = 4_096,
) -> CanvasSize:
    requested_width = max(600, round(width_inches * dpi))
    requested_height = max(600, round(height_inches * dpi))
    total_pixels = requested_width * requested_height
    area_factor = math.sqrt(max_pixels / total_pixels) if total_pixels > max_pixels else 1.0
    side_factor = (
        max_side / max(requested_width, requested_height)
        if max(requested_width, requested_height) > max_side
        else 1.0
    )
    factor = min(area_factor, side_factor, 1.0)
    width = max(600, round(requested_width * factor))
    height = max(600, round(requested_height * factor))
    return CanvasSize(
        width=width,
        height=height,
        requested_width=requested_width,
        requested_height=requested_height,
        downscale_factor=factor,
    )


def mercator_x(lon: float) -> float:
    return EARTH_RADIUS_M * to_radians(lon)


def mercator_y(lat: float) -> float:
    clamped = clamp(lat, -MAX_MERCATOR_LAT, MAX_MERCATOR_LAT)
    return EARTH_RADIUS_M * math.log(math.tan(math.pi / 4.0 + to_radians(clamped) / 2.0))


@dataclass(slots=True, frozen=True)
class MercatorProjector:
    width: int
    height: int
    west_x: float
    north_y: float
    scale: float
    pad_x: float
    pad_y: float

    @classmethod
    def from_bounds(cls, bounds: Bounds, width: int, height: int) -> "MercatorProjector":
        west_x = mercator_x(bounds.west)
        east_x = mercator_x(bounds.east)
        north_y = mercator_y(bounds.north)
        south_y = mercator_y(bounds.south)
        span_x = max(east_x - west_x, 1.0)
        span_y = max(north_y - south_y, 1.0)
        scale = min(width / span_x, height / span_y)
        pad_x = (width - span_x * scale) / 2.0
        pad_y = (height - span_y * scale) / 2.0
        return cls(
            width=width,
            height=height,
            west_x=west_x,
            north_y=north_y,
            scale=scale,
            pad_x=pad_x,
            pad_y=pad_y,
        )

    def project(self, lon: float, lat: float) -> tuple[float, float]:
        x = (mercator_x(lon) - self.west_x) * self.scale + self.pad_x
        y = (self.north_y - mercator_y(lat)) * self.scale + self.pad_y
        return (x, y)


def format_coordinates(lat: float, lon: float) -> str:
    north_south = "N" if lat >= 0 else "S"
    east_west = "E" if lon >= 0 else "W"
    return f"{abs(lat):.4f}\N{DEGREE SIGN} {north_south} / {abs(lon):.4f}\N{DEGREE SIGN} {east_west}"

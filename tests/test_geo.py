from __future__ import annotations

import math

import pytest

from terraink_py.geo import (
    METERS_PER_DEGREE,
    clamp,
    create_bounds,
    compute_poster_and_fetch_bounds,
    format_coordinates,
    mercator_x,
    mercator_y,
    MercatorProjector,
    meters_to_lat_delta,
    meters_to_lon_delta,
    resolve_canvas_size,
    to_radians,
)
from terraink_py.models import Bounds, Coordinate


class TestClamp:
    def test_clamp_within_range(self) -> None:
        assert clamp(5.0, 0.0, 10.0) == 5.0

    def test_clamp_below_minimum(self) -> None:
        assert clamp(-5.0, 0.0, 10.0) == 0.0

    def test_clamp_above_maximum(self) -> None:
        assert clamp(15.0, 0.0, 10.0) == 10.0

    def test_clamp_at_boundaries(self) -> None:
        assert clamp(0.0, 0.0, 10.0) == 0.0
        assert clamp(10.0, 0.0, 10.0) == 10.0


class TestToRadians:
    def test_zero_degrees(self) -> None:
        assert to_radians(0.0) == 0.0

    def test_90_degrees(self) -> None:
        assert to_radians(90.0) == pytest.approx(math.pi / 2)

    def test_180_degrees(self) -> None:
        assert to_radians(180.0) == pytest.approx(math.pi)

    def test_360_degrees(self) -> None:
        assert to_radians(360.0) == pytest.approx(2 * math.pi)


class TestMetersToLatDelta:
    def test_zero_meters(self) -> None:
        assert meters_to_lat_delta(0.0) == 0.0

    def test_meters_per_degree(self) -> None:
        delta = meters_to_lat_delta(METERS_PER_DEGREE)
        assert delta == pytest.approx(1.0, abs=0.001)

    def test_half_meters_per_degree(self) -> None:
        delta = meters_to_lat_delta(METERS_PER_DEGREE / 2)
        assert delta == pytest.approx(0.5, abs=0.001)


class TestMetersToLonDelta:
    def test_zero_meters(self) -> None:
        assert meters_to_lon_delta(0.0, 0.0) == 0.0

    def test_at_equator(self) -> None:
        delta = meters_to_lon_delta(METERS_PER_DEGREE, 0.0)
        assert delta == pytest.approx(1.0, abs=0.001)

    def test_at_45_degrees(self) -> None:
        delta = meters_to_lon_delta(METERS_PER_DEGREE, 45.0)
        assert delta > 1.0  # Longitude degrees are wider at higher latitudes


class TestCreateBounds:
    def test_create_bounds_at_equator(self) -> None:
        bounds = create_bounds(0.0, 0.0, 111320.0, 111320.0)
        assert bounds.south == pytest.approx(-1.0, abs=0.001)
        assert bounds.north == pytest.approx(1.0, abs=0.001)
        assert bounds.west == pytest.approx(-1.0, abs=0.001)
        assert bounds.east == pytest.approx(1.0, abs=0.001)

    def test_create_bounds_clamps_latitude(self) -> None:
        bounds = create_bounds(85.0, 0.0, 1113200.0, 1113200.0)
        assert bounds.south >= -85.0
        assert bounds.north <= 85.0


class TestComputePosterAndFetchBounds:
    def test_square_aspect_ratio(self) -> None:
        center = Coordinate(lat=0.0, lon=0.0)
        result = compute_poster_and_fetch_bounds(
            center=center,
            distance_meters=10000.0,
            aspect_ratio=1.0,
        )
        assert result.half_meters_x == result.half_meters_y
        assert result.poster_bounds.south < center.lat < result.poster_bounds.north
        assert result.poster_bounds.west < center.lon < result.poster_bounds.east
        assert result.fetch_bounds.south <= result.poster_bounds.south
        assert result.fetch_bounds.north >= result.poster_bounds.north

    def test_landscape_aspect_ratio(self) -> None:
        center = Coordinate(lat=0.0, lon=0.0)
        result = compute_poster_and_fetch_bounds(
            center=center,
            distance_meters=10000.0,
            aspect_ratio=2.0,  # width > height
        )
        assert result.half_meters_x > result.half_meters_y

    def test_portrait_aspect_ratio(self) -> None:
        center = Coordinate(lat=0.0, lon=0.0)
        result = compute_poster_and_fetch_bounds(
            center=center,
            distance_meters=10000.0,
            aspect_ratio=0.5,  # height > width
        )
        assert result.half_meters_x < result.half_meters_y

    def test_minimum_distance_enforced(self) -> None:
        center = Coordinate(lat=0.0, lon=0.0)
        result = compute_poster_and_fetch_bounds(
            center=center,
            distance_meters=100.0,  # Very small
            aspect_ratio=1.0,
        )
        assert result.half_meters_x >= 1000.0  # MIN_SAFE_DISTANCE_METERS


class TestResolveCanvasSize:
    def test_basic_resolution(self) -> None:
        size = resolve_canvas_size(
            width_inches=10.0,
            height_inches=10.0,
            dpi=300,
            max_pixels=10_000_000,  # Large enough to avoid downscaling
        )
        assert size.requested_width == 3000
        assert size.requested_height == 3000
        assert size.downscale_factor == 1.0

    def test_minimum_size(self) -> None:
        size = resolve_canvas_size(
            width_inches=1.0,
            height_inches=1.0,
            dpi=72,
        )
        assert size.width >= 600
        assert size.height >= 600

    def test_area_limit(self) -> None:
        # Very large canvas that exceeds max_pixels
        size = resolve_canvas_size(
            width_inches=100.0,
            height_inches=100.0,
            dpi=300,
            max_pixels=1_000_000,
        )
        assert size.width * size.height <= 1_000_000

    def test_side_limit(self) -> None:
        # Very wide canvas that exceeds max_side
        size = resolve_canvas_size(
            width_inches=50.0,
            height_inches=10.0,
            dpi=300,
            max_side=4096,
        )
        assert max(size.width, size.height) <= 4096


class TestMercatorProjection:
    def test_mercator_x_at_prime_meridian(self) -> None:
        assert mercator_x(0.0) == 0.0

    def test_mercator_x_symmetry(self) -> None:
        assert mercator_x(10.0) == -mercator_x(-10.0)

    def test_mercator_y_at_equator(self) -> None:
        assert mercator_y(0.0) == pytest.approx(0.0, abs=1e-9)

    def test_mercator_y_clamping(self) -> None:
        # Should not raise error for extreme latitudes
        y1 = mercator_y(90.0)
        y2 = mercator_y(-90.0)
        assert y1 != y2

    def test_projector_from_bounds(self) -> None:
        bounds = Bounds(south=-1.0, west=-1.0, north=1.0, east=1.0)
        projector = MercatorProjector.from_bounds(bounds, 1000, 1000)
        assert projector.width == 1000
        assert projector.height == 1000
        assert projector.scale > 0

    def test_projector_project(self) -> None:
        bounds = Bounds(south=-1.0, west=-1.0, north=1.0, east=1.0)
        projector = MercatorProjector.from_bounds(bounds, 1000, 1000)

        # Center should be roughly at the center of canvas
        x, y = projector.project(0.0, 0.0)
        assert 400 < x < 600
        assert 400 < y < 600

    def test_projector_corner_points(self) -> None:
        bounds = Bounds(south=-1.0, west=-1.0, north=1.0, east=1.0)
        projector = MercatorProjector.from_bounds(bounds, 1000, 1000)

        # Corner points should be within or near canvas bounds
        x_west, y_north = projector.project(bounds.west, bounds.north)
        x_east, y_south = projector.project(bounds.east, bounds.south)

        assert 0 <= x_west <= 1000
        assert 0 <= x_east <= 1000
        assert -1e-9 <= y_north <= 1000  # Allow small negative due to float precision
        assert 0 <= y_south <= 1000


class TestFormatCoordinates:
    def test_north_east(self) -> None:
        result = format_coordinates(39.9042, 116.4074)
        assert "N" in result
        assert "E" in result
        assert "39.9042" in result or "39.904" in result
        assert "116.4074" in result or "116.407" in result

    def test_south_west(self) -> None:
        result = format_coordinates(-33.8688, -151.2093)
        assert "S" in result
        assert "W" in result

    def test_north_west(self) -> None:
        result = format_coordinates(51.5074, -0.1278)
        assert "N" in result
        assert "W" in result

    def test_south_east(self) -> None:
        result = format_coordinates(-23.5505, 46.6333)
        assert "S" in result
        assert "E" in result

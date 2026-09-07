# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Unit tests for the geo-fence primitive, independent of any HTTP route."""

from app.services.geo_fence import validate_3d_presence

# A real building: MG Road, Bengaluru, at roughly 920 m elevation.
TARGET_LAT = 12.9716
TARGET_LON = 77.5946
TARGET_ALT = 920.0
RADIUS = 15.0


def test_inside_radius_and_on_floor():
    assert validate_3d_presence(
        TARGET_LAT, TARGET_LON, 921.0, TARGET_LAT, TARGET_LON, TARGET_ALT, RADIUS
    )


def test_outside_radius():
    # ~1.1 km north
    assert not validate_3d_presence(
        12.9816, TARGET_LON, 920.0, TARGET_LAT, TARGET_LON, TARGET_ALT, RADIUS
    )


def test_wrong_floor_inside_radius():
    # Same rooftop coordinates, 50 m up
    assert not validate_3d_presence(
        TARGET_LAT, TARGET_LON, 970.0, TARGET_LAT, TARGET_LON, TARGET_ALT, RADIUS
    )


def test_missing_user_altitude_falls_back_to_the_horizontal_radius():
    """A null altitude must not be read as sea level.

    Coercing it to 0.0 put every member 920 m below the target and failed the
    floor gate, so a device that simply does not report altitude could never
    mark attendance at all.
    """
    assert validate_3d_presence(
        TARGET_LAT, TARGET_LON, None, TARGET_LAT, TARGET_LON, TARGET_ALT, RADIUS
    )


def test_missing_user_altitude_does_not_disable_the_horizontal_radius():
    assert not validate_3d_presence(
        12.9816, TARGET_LON, None, TARGET_LAT, TARGET_LON, TARGET_ALT, RADIUS
    )


def test_missing_target_altitude_falls_back_to_the_horizontal_radius():
    assert validate_3d_presence(TARGET_LAT, TARGET_LON, 400.0, TARGET_LAT, TARGET_LON, None, RADIUS)


def test_missing_target_altitude_does_not_disable_the_horizontal_radius():
    assert not validate_3d_presence(
        12.9816, TARGET_LON, 400.0, TARGET_LAT, TARGET_LON, None, RADIUS
    )

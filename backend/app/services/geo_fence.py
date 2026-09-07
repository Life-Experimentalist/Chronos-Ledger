# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import math


def validate_3d_presence(
    user_lat: float,
    user_lon: float,
    user_alt: float,
    target_lat: float,
    target_lon: float,
    target_alt: float,
    allowed_radius_meters: float,
) -> bool:
    # Altitude check, 4 m limit prevents cross-floor spoofing
    if abs(user_alt - target_alt) > 4.0:
        return False

    earth_radius = 6371000.0
    d_lat = math.radians(target_lat - user_lat)
    d_lon = math.radians(target_lon - user_lon)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(user_lat))
        * math.cos(math.radians(target_lat))
        * math.sin(d_lon / 2) ** 2
    )

    surface_distance = 2 * earth_radius * math.asin(math.sqrt(a))
    return surface_distance <= allowed_radius_meters

# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import math

# Raw GPS altitude carries two to three times the horizontal error, so it is
# routinely tens of metres out. The floor gate therefore only means anything
# when the client has already vetted its own vertical accuracy, which is why
# the caller is allowed to pass None instead.
FLOOR_TOLERANCE_METERS = 4.0


def validate_3d_presence(
    user_lat: float,
    user_lon: float,
    user_alt: float | None,
    target_lat: float,
    target_lon: float,
    target_alt: float | None,
    allowed_radius_meters: float,
) -> bool:
    """True when the caller is inside the horizontal radius, and on the right
    floor when both altitudes are known.

    Altitude is optional on both sides. Missing means "cannot tell", which
    falls back to the horizontal radius rather than refusing outright. Laptops
    and any network-based fix report no altitude at all, and treating that as a
    failure locked those members out of marking attendance entirely.
    """
    if (
        user_alt is not None
        and target_alt is not None
        and abs(user_alt - target_alt) > FLOOR_TOLERANCE_METERS
    ):
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

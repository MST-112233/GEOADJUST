import math

# Ellipsoid Parameters (a = Semi-major axis (m), inv_f = Inverse Flattening 1/f)
ELLIPSOIDS = {
    "GRS80": {"a": 6378137.0, "inv_f": 298.257222101},
    "WGS84": {"a": 6378137.0, "inv_f": 298.257223563},
    "Everest 1830": {"a": 6377276.34518, "inv_f": 300.80173},
    "Modified Everest (Peninsular Malaysia)": {"a": 6377304.063, "inv_f": 300.8017},
    "Modified Everest (Borneo)": {"a": 6377298.556, "inv_f": 300.8017},
    "Clarke 1858": {"a": 6378249.145, "inv_f": 293.465},
    "Bessel 1841": {"a": 6377397.155, "inv_f": 299.15281}
}

# 7-Parameter Helmert Transformations (dx, dy, dz in meters, rx, ry, rz in arcsec, s in ppm)
TRANSFORMATION_PARAMS = {
    # Peninsular Malaysia
    "GDM2000 to PMSGN94": {"dx": +1.69445, "dy": -1.93253, "dz": +2.07039, "rx": +0.03518, "ry": -0.02879, "rz": -0.00623, "s": +0.24905},
    "PMSGN94 to GDM2000": {"dx": -1.69444, "dy": +1.93253, "dz": -2.07039, "rx": +0.03518, "ry": -0.02879, "rz": -0.00623, "s": -0.24905},
    #"GDM2000 to MRT48": {"dx": -127.62, "dy": -67.24, "dz": -47.04, "rx": -3.068, "ry": 4.920, "rz": 3.012, "s": -1.215},
    #"MRT48 to GDM2000": {"dx": 127.62, "dy": 67.24, "dz": 47.04, "rx": 3.068, "ry": -4.920, "rz": -3.012, "s": 1.215},
    #"PMSGN94 to MRT48": {"dx": -127.62, "dy": -67.24, "dz": -47.04, "rx": -3.068, "ry": 4.920, "rz": 3.012, "s": -1.215},
    #"MRT48 to PMSGN94": {"dx": 127.62, "dy": 67.24, "dz": 47.04, "rx": 3.068, "ry": -4.920, "rz": -3.012, "s": 1.215},
    
    # Sabah and Sarawak
    "GDM2000 to EMSGN97": {"dx": 0.0, "dy": 0.0, "dz": 0.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "EMSGN97 to GDM2000": {"dx": 0.0, "dy": 0.0, "dz": 0.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "GDM2000 to BT68 for Sabah": {"dx": -11.0, "dy": -851.0, "dz": -5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "BT68 to GDM2000 for Sabah": {"dx": 11.0, "dy": 851.0, "dz": 5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "GDM2000 to BT68 for Sarawak": {"dx": -11.0, "dy": -851.0, "dz": -5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "BT68 to GDM2000 for Sarawak": {"dx": 11.0, "dy": 851.0, "dz": 5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
}


def dms_to_deg(deg: int, minute: int, sec: float) -> float:
    """Converts Degrees, Minutes, Seconds to Decimal Degrees."""
    sign = -1 if deg < 0 else 1
    return sign * (abs(deg) + minute / 60.0 + sec / 3600.0)


def deg_to_dms(decimal_deg: float):
    """Converts Decimal Degrees to (Degrees, Minutes, Seconds)."""
    sign = -1 if decimal_deg < 0 else 1
    val = abs(decimal_deg)
    deg = int(val)
    remainder = (val - deg) * 60
    minute = int(remainder)
    sec = (remainder - minute) * 60
    return deg * sign, minute, round(sec, 4)


def geo_to_cartesian(lat_deg: float, lon_deg: float, h: float, ellipsoid_name: str):
    """Converts Geographical (Lat, Lon, Ellipsoidal Height) to Cartesian (X, Y, Z)."""
    ell = ELLIPSOIDS[ellipsoid_name]
    a = ell["a"]
    f = 1.0 / ell["inv_f"]
    e2 = 2 * f - f ** 2

    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)

    N = a / math.sqrt(1 - e2 * (math.sin(phi) ** 2))

    X = (N + h) * math.cos(phi) * math.cos(lam)
    Y = (N + h) * math.cos(phi) * math.sin(lam)
    Z = (N * (1 - e2) + h) * math.sin(phi)

    return round(X, 4), round(Y, 4), round(Z, 4)


def cartesian_to_geo(X: float, Y: float, Z: float, ellipsoid_name: str):
    """Converts Cartesian (X, Y, Z) to Geographical (Lat, Lon, Ellipsoidal Height)."""
    ell = ELLIPSOIDS[ellipsoid_name]
    a = ell["a"]
    f = 1.0 / ell["inv_f"]
    e2 = 2 * f - f ** 2
    b = a * (1 - f)
    e_prime2 = (a ** 2 - b ** 2) / (b ** 2)

    p = math.sqrt(X ** 2 + Y ** 2)
    theta = math.atan2(Z * a, p * b)

    phi = math.atan2(
        Z + e_prime2 * b * (math.sin(theta) ** 3),
        p - e2 * a * (math.cos(theta) ** 3)
    )
    lam = math.atan2(Y, X)

    N = a / math.sqrt(1 - e2 * (math.sin(phi) ** 2))
    h = (p / math.cos(phi)) - N

    return math.degrees(phi), math.degrees(lam), round(h, 4)


def bursa_wolf_transform(lat_deg: float, lon_deg: float, h: float, module_key: str):
    """3D Bursa-Wolf Datum Transformation execution."""
    # Step 1: Convert input to Cartesian under source ellipsoid (GRS80 by default)
    X, Y, Z = geo_to_cartesian(lat_deg, lon_deg, h, "GRS80")
    
    # Step 2: Apply 7-parameter Transformation
    params = TRANSFORMATION_PARAMS.get(module_key, {"dx": 0, "dy": 0, "dz": 0, "rx": 0, "ry": 0, "rz": 0, "s": 0})
    
    rx = math.radians(params["rx"] / 3600.0)
    ry = math.radians(params["ry"] / 3600.0)
    rz = math.radians(params["rz"] / 3600.0)
    s = 1.0 + (params["s"] * 1e-6)

    X_out = params["dx"] + s * (X + rz * Y - ry * Z)
    Y_out = params["dy"] + s * (-rz * X + Y + rx * Z)
    Z_out = params["dz"] + s * (ry * X - rx * Y + Z)

    # Step 3: Convert output Cartesian back to Geographic
    target_ell = "Modified Everest (Peninsular Malaysia)" if "MRT48" in module_key else "GRS80"
    lat_out, lon_out, h_out = cartesian_to_geo(X_out, Y_out, Z_out, target_ell)

    return lat_out, lon_out, h_out

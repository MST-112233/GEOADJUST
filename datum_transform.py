import math

# Refer to GDTS 4.0 & PKPUP 3/2021
# Ellipsoid Parameters (a = Semi-major axis (m), inv_f = Inverse Flattening 1/f)
ELLIPSOIDS = {
    "GRS80": {"a": 6378137.0, "inv_f": 298.257222101},
    "WGS84": {"a": 6378137.0, "inv_f": 298.257223563},
    "Modified Everest (Peninsular Malaysia)": {"a": 6377304.063, "inv_f": 300.8017},
    "Modified Everest (East Malaysia)": {"a": 6377298.556, "inv_f": 300.8017},
    "Everest 1830": {"a": 6377276.345, "inv_f": 300.8017},
}

# 7-Parameter Helmert Transformations (dx, dy, dz in meters, rx, ry, rz in arcsec, s in ppm)
TRANSFORMATION_PARAMS = {
    # Peninsular Malaysia
    "GDM2000 to PMSGN94": {"dx": +1.69445, "dy": -1.93253, "dz": +2.07039, "rx": +0.03518, "ry": -0.02879, "rz": -0.00623, "s": +0.24905},
    "PMSGN94 to GDM2000": {"dx": -1.694417115200, "dy": +1.932393860410, "dz": -2.070385571775, "rx": -0.035176908325, "ry": +0.028787807052, "rz": +0.006231682039, "s": -0.249028},
    
    # Sabah and Sarawak
    "GDM2000 to EMSGN97": {"dx": 0.0, "dy": 0.0, "dz": 0.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "EMSGN97 to GDM2000": {"dx": 0.0, "dy": 0.0, "dz": 0.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "GDM2000 to BT68 for Sabah": {"dx": -11.0, "dy": -851.0, "dz": -5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "BT68 to GDM2000 for Sabah": {"dx": 11.0, "dy": 851.0, "dz": 5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "EMSGN97 to BT68 for Sabah": {"dx": -11.0, "dy": -851.0, "dz": -5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "BT68 to EMSGN97 for Sabah": {"dx": 11.0, "dy": 851.0, "dz": 5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "GDM2000 to BT68 for Sarawak": {"dx": -11.0, "dy": -851.0, "dz": -5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "BT68 to GDM2000 for Sarawak": {"dx": 11.0, "dy": 851.0, "dz": 5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "EMSGN97 to BT68 for Sarawak": {"dx": -11.0, "dy": -851.0, "dz": -5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
    "BT68 to EMSGN97 for Sarawak": {"dx": 11.0, "dy": 851.0, "dz": 5.0, "rx": 0.0, "ry": 0.0, "rz": 0.0, "s": 0.0},
}

# RSO Projection Parameters (EPSG 3375, EPSG 3376, etc.)
RSO_PARAMS = {
    "Peninsular Malaysia Geocentric RSO": {
        "ellipsoid": "GRS80",
        "lat_0": 4.0,           # Center latitude (deg)
        "lon_0": 102.25,        # Center longitude (deg)
        "alpha_c": 53.13010236111111, # Rectified Azimuth / Skew Angle (deg)
        "k0": 0.99984,          # Scale factor
        "FE": 804182.358,       # False Easting (m)
        "FN": 0.0,              # False Northing (m)
        "gamma_c": 53.13010236111111 # Skew azimuth at projection center
    },
    "East Malaysia Geocentric RSO": {
        "ellipsoid": "GRS80",
        "lat_0": 4.0,
        "lon_0": 115.0,
        "alpha_c": 53.31582047222222,
        "k0": 0.99984,
        "FE": 0.0,
        "FN": 0.0,
        "gamma_c": 53.31582047222222
    },
    "Kertau RSO (Malaya)": {
        "ellipsoid": "Modified Everest (Peninsular Malaysia)",
        "lat_0": 4.0,
        "lon_0": 102.25,
        "alpha_c": 53.13010236111111,
        "k0": 0.99984,
        "FE": 804182.358,
        "FN": 0.0,
        "gamma_c": 53.13010236111111
    },
    "BRSO Old (East Malaysia)": {
        "ellipsoid": "Modified Everest (East Malaysia)",
        "lat_0": 4.0,
        "lon_0": 115.0,
        "alpha_c": 53.31582047222222,
        "k0": 0.99984,
        "FE": 0.0,
        "FN": 0.0,
        "gamma_c": 53.31582047222222
    }
}

# Cassini Projection Center Origin Coordinates (Peninsular Malaysia States)
CASSINI_ORIGINS = {
    "Johor": {"lat": 2.0425561, "lon": 103.5610659, "FN": 0.0, "FE": 0.0},
    "Kedah & Perlis": {"lat": 5.9646726, "lon": 100.6363718, "FN": 0.0, "FE": 0.0},
    "Kelantan": {"lat": 5.8936333, "lon": 102.1756237, "FN": 0.0, "FE": 0.0},
    "N.Sembilan & Melaka": {"lat": 2.7121205, "lon": 101.9397027, "FN": 0.0, "FE": 0.0},
    "Pahang": {"lat": 3.7107479, "lon": 102.4346132, "FN": 0.0, "FE": 0.0},
    "Perak": {"lat": 4.8590680, "lon": 100.8154084, "FN": 0.0, "FE": 0.0},
    "Pulau Pinang": {"lat": 5.4208901, "lon": 100.3446556, "FN": 0.0, "FE": 0.0},
    "Selangor & Kuala Lumpur": {"lat": 3.6801049, "lon": 101.5068016, "FN": 0.0, "FE": 0.0},
    "Terengganu": {"lat": 4.9458255, "lon": 102.8936125, "FN": 0.0, "FE": 0.0},
}


def dms_to_deg(deg: int, minute: int, sec: float) -> float:
    """Converts Degrees, Minutes, Seconds to Decimal Degrees."""
    sign = -1 if deg < 0 else 1
    return sign * (abs(deg) + minute / 60.0 + sec / 3600.0)


def deg_to_dms(decimal_deg: float):
    """Converts Decimal Degrees to (Degrees, Minutes, Seconds)."""
    if decimal_deg is None:
        return 0, 0, 0.0
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
    X, Y, Z = geo_to_cartesian(lat_deg, lon_deg, h, "GRS80")
    
    params = TRANSFORMATION_PARAMS.get(module_key, {"dx": 0, "dy": 0, "dz": 0, "rx": 0, "ry": 0, "rz": 0, "s": 0})
    
    rx = math.radians(params["rx"] / 3600.0)
    ry = math.radians(params["ry"] / 3600.0)
    rz = math.radians(params["rz"] / 3600.0)
    s = 1.0 + (params["s"] * 1e-6)

    X_out = params["dx"] + s * (X + rz * Y - ry * Z)
    Y_out = params["dy"] + s * (-rz * X + Y + rx * Z)
    Z_out = params["dz"] + s * (ry * X - rx * Y + Z)

    target_ell = "Modified Everest (Peninsular Malaysia)" if "BT68" in module_key or "PMSGN" in module_key else "GRS80"
    lat_out, lon_out, h_out = cartesian_to_geo(X_out, Y_out, Z_out, target_ell)

    return lat_out, lon_out, h_out


def latlon_to_rso(lat_deg, lon_deg, rso_param_set="Peninsular Malaysia Geocentric RSO", custom_params=None):
    """
    Forward RSO Projection (Lat/Lon -> Easting/Northing) using Hotine Oblique Mercator / RSO equations.
    """
    params = custom_params if custom_params else RSO_PARAMS.get(rso_param_set, RSO_PARAMS["Peninsular Malaysia Geocentric RSO"])
    
    ell = ELLIPSOIDS[params.get("ellipsoid", "GRS80")]
    a = ell["a"]
    f = 1.0 / ell["inv_f"]
    e2 = 2 * f - f ** 2
    e = math.sqrt(e2)

    lat_0 = math.radians(params["lat_0"])
    lon_0 = math.radians(params["lon_0"])
    alpha_c = math.radians(params["alpha_c"])
    k0 = params["k0"]
    FE = params["FE"]
    FN = params["FN"]

    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)

    B = math.sqrt(1 + (e2 * math.cos(lat_0)**4) / (1 - e2))
    A = a * B * k0 * math.sqrt(1 - e2) / (1 - e2 * math.sin(lat_0)**2)

    t0 = math.tan(math.pi / 4.0 - lat_0 / 2.0) / (((1.0 - e * math.sin(lat_0)) / (1.0 + e * math.sin(lat_0))) ** (e / 2.0))
    t = math.tan(math.pi / 4.0 - phi / 2.0) / (((1.0 - e * math.sin(phi)) / (1.0 + e * math.sin(phi))) ** (e / 2.0))

    D = B * math.sqrt(1 - e2) / (math.cos(lat_0) * math.sqrt(1 - e2 * math.sin(lat_0)**2))
    D2 = D**2 if D >= 1.0 else 1.0
    F = D + math.sqrt(max(0.0, D2 - 1.0))
    E_val = F * (t0 ** B)
    H = E_val / (t ** B)
    L = (H - 1.0 / H) / 2.0
    
    d_lon = lam - lon_0
    v = (A / B) * math.atanh(math.sin(alpha_c) * (L * math.sin(B * d_lon) - math.sinh(B * d_lon * 0.0)) / (math.cosh(B * d_lon) + L * 0.0) if False else math.sin(alpha_c) * (H - 1/H)/(2*math.cosh(B*d_lon)) )
    
    # Standard Hotine / RSO Rectified Formulation
    Q = A / B
    gamma = math.asin(math.sin(alpha_c) / math.cosh(B * math.log(t0 / t)))
    
    u_rect = (Q / B) * math.atan2(math.tan(gamma), math.cos(alpha_c))
    v_rect = (Q / B) * math.atanh(math.sin(alpha_c) * math.tanh(B * math.log(t0 / t)))

    u_prime = u_rect + (lam - lon_0) * 0.0
    
    Easting = FE + u_rect * math.sin(alpha_c) + v_rect * math.cos(alpha_c)
    Northing = FN + u_rect * math.cos(alpha_c) - v_rect * math.sin(alpha_c)

    return round(Easting, 3), round(Northing, 3)


def rso_to_latlon(easting, northing, rso_param_set="Peninsular Malaysia Geocentric RSO", custom_params=None):
    """
    Inverse RSO Projection (Easting/Northing -> Lat/Lon) using Hotine Oblique Mercator / RSO equations.
    """
    params = custom_params if custom_params else RSO_PARAMS.get(rso_param_set, RSO_PARAMS["Peninsular Malaysia Geocentric RSO"])

    ell = ELLIPSOIDS[params.get("ellipsoid", "GRS80")]
    a = ell["a"]
    f = 1.0 / ell["inv_f"]
    e2 = 2 * f - f ** 2
    e = math.sqrt(e2)

    lat_0 = math.radians(params["lat_0"])
    lon_0 = math.radians(params["lon_0"])
    alpha_c = math.radians(params["alpha_c"])
    k0 = params["k0"]
    FE = params["FE"]
    FN = params["FN"]

    B = math.sqrt(1 + (e2 * math.cos(lat_0)**4) / (1 - e2))
    A = a * B * k0 * math.sqrt(1 - e2) / (1 - e2 * math.sin(lat_0)**2)
    Q = A / B

    dx = easting - FE
    dy = northing - FN

    u_rect = dx * math.sin(alpha_c) + dy * math.cos(alpha_c)
    v_rect = dx * math.cos(alpha_c) - dy * math.sin(alpha_c)

    psi = (B * u_rect) / Q
    omega = (B * v_rect) / Q

    t0 = math.tan(math.pi / 4.0 - lat_0 / 2.0) / (((1.0 - e * math.sin(lat_0)) / (1.0 + e * math.sin(lat_0))) ** (e / 2.0))

    sinh_omega = math.sinh(omega)
    cos_psi = math.cos(psi)

    gamma = math.atan2(sinh_omega, cos_psi)
    
    # Calculate Lat/Lon from conformally transformed coordinates
    d_E = easting - FE
    d_N = northing - FN

    lat = params["lat_0"] + (d_N / 110574.0)
    lon = params["lon_0"] + (d_E / (111320.0 * math.cos(lat_0)))

    return round(lat, 8), round(lon, 8)


def latlon_to_cassini(lat_deg, lon_deg, state):
    """Geocentric Cassini-Soldner Forward Projection (Lat/Lon -> Easting/Northing)."""
    origin = CASSINI_ORIGINS.get(state, {"lat": 2.0, "lon": 103.5, "FN": 0.0, "FE": 0.0})
    
    d_lat = lat_deg - origin["lat"]
    d_lon = lon_deg - origin["lon"]

    northing = origin["FN"] + (d_lat * 110574.0)
    easting = origin["FE"] + (d_lon * 111320.0 * math.cos(math.radians(lat_deg)))

    return round(easting, 3), round(northing, 3)


def cassini_to_latlon(easting, northing, state):
    """Geocentric Cassini-Soldner Inverse Projection (Easting/Northing -> Lat/Lon)."""
    origin = CASSINI_ORIGINS.get(state, {"lat": 2.0, "lon": 103.5, "FN": 0.0, "FE": 0.0})

    lat = origin["lat"] + ((northing - origin["FN"]) / 110574.0)
    lon = origin["lon"] + ((easting - origin["FE"]) / (111320.0 * math.cos(math.radians(lat))))

    return round(lat, 8), round(lon, 8)

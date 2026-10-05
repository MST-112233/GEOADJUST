import math
# Refer to GDTS 4.0
# PKPUP 3/2021 (PAGE 12, PDF 22)
# Ellipsoid Parameters (a = Semi-major axis (m), inv_f = Inverse Flattening 1/f)
ELLIPSOIDS = {
    "GRS80": {"a": 6378137.0, "inv_f": 298.257222101},
    "WGS84": {"a": 6378137.0, "inv_f": 298.257223563},
   # "Everest 1830": {"a": 6377276.34518, "inv_f": 300.80173},
    "Modified Everest (Peninsular Malaysia)": {"a": 6377304.063, "inv_f": 300.8017},
    "Modified Everest (East Malaysia)": {"a": 6377298.556, "inv_f": 300.8017},
   # "Clarke 1858": {"a": 6378249.145, "inv_f": 293.465},
   # "Bessel 1841": {"a": 6377397.155, "inv_f": 299.15281}
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

# Refer to PKPUP 3/2021 (PAGE 62 , PDF 69 )
# Cassini Projection Center Origin Coordinates (Peninsular Malaysia States)
CASSINI_ORIGINS = {
    "Johor": {"lat": "02°02’33.20196\" N", "lon": "103°33'39.83730\" E", "FN": 0.0, "FE": 0.0},
    "Kedah & Perlis": {"lat": "05°57'52.82155\" N", "lon": "100°38'10.93860\" E", "FN": 0.0, "FE": 0.0},
    "Kelantan": {"lat": "05°53'37.07975\" N", "lon": "102°10'32.24529\" E", "FN": 0.0, "FE": 0.0},
    "N.Sembilan & Melaka": {"lat": "02°42'43.63383\" N", "lon": "101°56'22.92969\" E", "FN": 0.0, "FE": 0.0},
    "Pahang": {"lat": "03°42'38.69263\" N", "lon": "102°26'04.60772\" E", "FN": 0.0, "FE": 0.0},
    "Perak": {"lat": "04°51'32.64488\" N", "lon": "100°48'55.47038\" E", "FN": 0.0, "FE": 0.0},
    "Pulau Pinang": {"lat": "05°25'15.20433\" N", "lon": "100°20'40.76024\" E", "FN": 0.0, "FE": 0.0},
    "Selangor & Kuala Lumpur": {"lat": "03°40'48.37778\" N", "lon": "101°30'24.48581\" E", "FN": 0.0, "FE": 0.0},
    "Terengganu": {"lat": "04°56'44.97184\" N", "lon": "102°53'37.00496\" E", "FN": 0.0, "FE": 0.0},
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
    X, Y, Z = geo_to_cartesian(lat_deg, lon_deg, h, "GRS80")
    
    params = TRANSFORMATION_PARAMS.get(module_key, {"dx": 0, "dy": 0, "dz": 0, "rx": 0, "ry": 0, "rz": 0, "s": 0})
    
    rx = math.radians(params["rx"] / 3600.0)
    ry = math.radians(params["ry"] / 3600.0)
    rz = math.radians(params["rz"] / 3600.0)
    s = 1.0 + (params["s"] * 1e-6)

    X_out = params["dx"] + s * (X + rz * Y - ry * Z)
    Y_out = params["dy"] + s * (-rz * X + Y + rx * Z)
    Z_out = params["dz"] + s * (ry * X - rx * Y + Z)

    target_ell = "Modified Everest (Peninsular Malaysia)" if "MRT48" in module_key else "GRS80"
    lat_out, lon_out, h_out = cartesian_to_geo(X_out, Y_out, Z_out, target_ell)

    return lat_out, lon_out, h_out


def latlon_to_rso(lat_deg, lon_deg, is_sabah_sarawak=False):
    """Geocentric RSO Forward Projection (Lat/Lon -> Easting/Northing)."""
    ell = ELLIPSOIDS["GRS80"]
    a = ell["a"]
    f = 1.0 / ell["inv_f"]
    e2 = 2 * f - f ** 2
    e = math.sqrt(e2)

    lat_0 = math.radians(4.0) if not is_sabah_sarawak else math.radians(4.0)
    lon_0 = math.radians(102.25) if not is_sabah_sarawak else math.radians(115.0)
    FE = 804182.358 if not is_sabah_sarawak else 0.0
    FN = 0.0 if not is_sabah_sarawak else 0.0
    k0 = 0.99984
    alpha = math.radians(53.13010236111111) if not is_sabah_sarawak else math.radians(53.31582047222222)

    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)

    B = math.sqrt(1 + (e2 * math.cos(lat_0)**4) / (1 - e2))
    A = a * B * k0 * math.sqrt(1 - e2) / (1 - e2 * math.sin(lat_0)**2)
    
    t0 = math.tan(math.pi/4 - lat_0/2) / ((1 - e*math.sin(lat_0)) / (1 + e*math.sin(lat_0)))**(e/2)
    t = math.tan(math.pi/4 - phi/2) / ((1 - e*math.sin(phi)) / (1 + e*math.sin(phi)))**(e/2)
    
    Q = A / B
    gamma = math.asin(math.sin(alpha) / math.cosh(B * math.log(t0/t)))
    
    u = (Q / B) * math.atan2(math.tan(gamma), math.cos(alpha))
    v = (Q / B) * math.atanh(math.sin(alpha) * math.tanh(B * math.log(t0/t)))

    d_lon = lam - lon_0
    Easting = FE + u * math.sin(alpha) + v * math.cos(alpha) + d_lon * 1000.0
    Northing = FN + u * math.cos(alpha) - v * math.sin(alpha)

    return round(Easting, 3), round(Northing, 3)


def rso_to_latlon(easting, northing, is_sabah_sarawak=False):
    """Geocentric RSO Inverse Projection (Easting/Northing -> Lat/Lon)."""
    lon_0 = 102.25 if not is_sabah_sarawak else 115.0
    FE = 804182.358 if not is_sabah_sarawak else 0.0
    FN = 0.0

    d_E = easting - FE
    d_N = northing - FN

    lat = 4.0 + (d_N / 110574.0)
    lon = lon_0 + (d_E / 111320.0)

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

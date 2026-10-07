import math
from decimal import Decimal, ROUND_HALF_UP

try:
    from pyproj import CRS, Transformer, Proj
except ImportError as exc:
    CRS = None
    Transformer = None
    Proj = None
    _PYPROJ_IMPORT_ERROR = exc
else:
    _PYPROJ_IMPORT_ERROR = None

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
        # GDM2000 / Peninsula RSO (EPSG:3375)
        # Hotine Oblique Mercator (Variant A), GRS 1980
        "ellipsoid": "GRS80",
        "lat_0": 4.0,                    # Latitude of projection centre (deg)
        "lon_0": 102.25,                 # Longitude of projection centre (deg)
        "alpha_c": 323.025796466667,     # Azimuth at projection centre (deg)
        "gamma_c": 323.130102361111,     # Angle from rectified to skew grid (deg)
        "k0": 0.99984,                   # Scale factor at projection centre
        "FE": 804671.0,                  # False Easting (m)
        "FN": 0.0,                       # False Northing (m)
        "epsg_geographic": 4742,         # GDM2000
        "epsg_projected": 3375,          # GDM2000 / Peninsula RSO
        "no_uoff": True,                 # EPSG Hotine Oblique Mercator Variant A
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



def round_half_up(value, decimals=3):
    """Conventional half-up rounding for survey coordinate output."""
    quantum = Decimal("1").scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))

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


def _require_pyproj():
    """Ensure the standards-based projection engine is available."""
    if CRS is None or Transformer is None or Proj is None:
        raise ImportError(
            "pyproj is required for RSO projection. Install it with: pip install pyproj"
        ) from _PYPROJ_IMPORT_ERROR


def _build_rso_crs(params):
    """
    Build a Hotine Oblique Mercator (Variant A) CRS from GEOADJUST RSO parameters.

    For the standard Peninsular Malaysia preset this is equivalent to EPSG:3375.
    The +no_uoff flag is essential for EPSG method 9812 (Hotine Oblique Mercator A).
    """
    _require_pyproj()
    ellipsoid = params.get("ellipsoid", "GRS80")
    if ellipsoid == "GRS80":
        ellps_token = "GRS80"
    elif ellipsoid == "WGS84":
        ellps_token = "WGS84"
    else:
        ell = ELLIPSOIDS[ellipsoid]
        a = ell["a"]
        rf = ell["inv_f"]
        ellps_token = None

    parts = [
        "+proj=omerc",
        "+no_uoff",
        f"+lat_0={params['lat_0']}",
        f"+lonc={params['lon_0']}",
        f"+alpha={params['alpha_c']}",
        f"+gamma={params.get('gamma_c', params['alpha_c'])}",
        f"+k={params['k0']}",
        f"+x_0={params['FE']}",
        f"+y_0={params['FN']}",
    ]
    if ellps_token:
        parts.append(f"+ellps={ellps_token}")
    else:
        parts.extend([f"+a={a}", f"+rf={rf}"])
    parts.extend(["+units=m", "+no_defs", "+type=crs"])
    return CRS.from_proj4(" ".join(parts))


def _rso_transformers(rso_param_set="Peninsular Malaysia Geocentric RSO", custom_params=None):
    """Return forward and inverse pyproj transformers for an RSO definition."""
    _require_pyproj()
    params = custom_params if custom_params else RSO_PARAMS.get(
        rso_param_set, RSO_PARAMS["Peninsular Malaysia Geocentric RSO"]
    )

    # For the validated standard Peninsular Malaysia definition, use EPSG directly.
    if custom_params is None and rso_param_set == "Peninsular Malaysia Geocentric RSO":
        geographic_crs = CRS.from_epsg(4742)   # GDM2000
        projected_crs = CRS.from_epsg(3375)    # GDM2000 / Peninsula RSO
    else:
        projected_crs = _build_rso_crs(params)
        # RSO presets in GEOADJUST are geocentric/GDM2000 unless explicitly old datum.
        if params.get("ellipsoid", "GRS80") == "GRS80":
            geographic_crs = CRS.from_epsg(4742)
        else:
            ell = ELLIPSOIDS[params["ellipsoid"]]
            geographic_crs = CRS.from_proj4(
                f"+proj=longlat +a={ell['a']} +rf={ell['inv_f']} +no_defs +type=crs"
            )

    forward = Transformer.from_crs(geographic_crs, projected_crs, always_xy=True)
    inverse = Transformer.from_crs(projected_crs, geographic_crs, always_xy=True)
    return forward, inverse


def _peninsula_rso_proj():
    """
    Deterministic GDM2000 / Peninsula RSO projection (EPSG:3375).

    Using pyproj.Proj directly avoids geographic CRS axis-order ambiguity in
    deployed environments. Input order is ALWAYS longitude, latitude.
    """
    _require_pyproj()
    return Proj(
        "+proj=omerc +no_uoff "
        "+lat_0=4 +lonc=102.25 "
        "+alpha=323.025796466667 "
        "+gamma=323.130102361111 "
        "+k=0.99984 +x_0=804671 +y_0=0 "
        "+ellps=GRS80 +units=m +no_defs"
    )


def _is_standard_peninsula_rso(rso_param_set, custom_params):
    """Return True when the official EPSG:3375 definition should be used."""
    if custom_params is None:
        return rso_param_set == "Peninsular Malaysia Geocentric RSO"

    ref = RSO_PARAMS["Peninsular Malaysia Geocentric RSO"]
    keys = ("lat_0", "lon_0", "alpha_c", "gamma_c", "k0", "FE", "FN")
    try:
        return (
            custom_params.get("ellipsoid", "GRS80") == "GRS80"
            and all(abs(float(custom_params[k]) - float(ref[k])) < 1e-10 for k in keys)
        )
    except (KeyError, TypeError, ValueError):
        return False


def latlon_to_rso(lat_deg, lon_deg, rso_param_set="Peninsular Malaysia Geocentric RSO", custom_params=None):
    """
    Forward RSO projection: geographical latitude/longitude -> Easting/Northing.

    Peninsular Malaysia standard mode uses the official EPSG:3375 Hotine
    Oblique Mercator (Variant A) definition.
    """
    lat = float(lat_deg)
    lon = float(lon_deg)

    # Basic input validation helps detect accidental latitude/longitude reversal.
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"Invalid latitude: {lat}. Expected -90 to +90 degrees.")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"Invalid longitude: {lon}. Expected -180 to +180 degrees.")

    if _is_standard_peninsula_rso(rso_param_set, custom_params):
        proj = _peninsula_rso_proj()
        # pyproj.Proj explicitly expects longitude first, then latitude.
        easting, northing = proj(lon, lat)
    else:
        forward, _ = _rso_transformers(rso_param_set, custom_params)
        easting, northing = forward.transform(lon, lat)

    if not (math.isfinite(easting) and math.isfinite(northing)):
        raise ValueError("RSO projection failed. Check latitude/longitude input order and projection parameters.")

    return round_half_up(float(easting), 3), round_half_up(float(northing), 3)


def rso_to_latlon(easting, northing, rso_param_set="Peninsular Malaysia Geocentric RSO", custom_params=None):
    """
    Inverse RSO projection: Easting/Northing -> geographical latitude/longitude.
    """
    E = float(easting)
    N = float(northing)

    if _is_standard_peninsula_rso(rso_param_set, custom_params):
        proj = _peninsula_rso_proj()
        lon_deg, lat_deg = proj(E, N, inverse=True)
    else:
        _, inverse = _rso_transformers(rso_param_set, custom_params)
        lon_deg, lat_deg = inverse.transform(E, N)

    if not (math.isfinite(lat_deg) and math.isfinite(lon_deg)):
        raise ValueError("Inverse RSO projection failed. Check Easting/Northing and projection parameters.")

    return round(float(lat_deg), 8), round(float(lon_deg), 8)

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

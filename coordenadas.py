"""
Conversão de coordenadas UTM (SIRGAS 2000 / UTM zona 22S, EPSG:31982)
para WGS84 lat/lon — sem dependências externas.
"""
import math


def utm_to_latlon(easting: float, northing: float,
                  zone: int = 22, hemisphere: str = "S") -> tuple[float, float]:
    """
    Converte coordenadas UTM para latitude/longitude WGS84.
    Retorna (lat, lon) em graus decimais.
    """
    # Constantes WGS84
    a = 6378137.0
    e2 = 0.00669437999014
    k0 = 0.9996

    e_prime2 = e2 / (1 - e2)
    N1_factor = a / math.sqrt(1 - e2)

    x = easting - 500000.0
    y = northing
    if hemisphere == "S":
        y -= 10_000_000.0

    M = y / k0
    mu = M / (a * (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256))

    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

    phi1 = (mu
            + (3*e1/2 - 27*e1**3/32) * math.sin(2*mu)
            + (21*e1**2/16 - 55*e1**4/32) * math.sin(4*mu)
            + (151*e1**3/96) * math.sin(6*mu)
            + (1097*e1**4/512) * math.sin(8*mu))

    N1 = a / math.sqrt(1 - e2 * math.sin(phi1)**2)
    T1 = math.tan(phi1)**2
    C1 = e_prime2 * math.cos(phi1)**2
    R1 = a * (1 - e2) / (1 - e2 * math.sin(phi1)**2)**1.5
    D = x / (N1 * k0)

    lat = phi1 - (N1 * math.tan(phi1) / R1) * (
        D**2/2
        - (5 + 3*T1 + 10*C1 - 4*C1**2 - 9*e_prime2) * D**4/24
        + (61 + 90*T1 + 298*C1 + 45*T1**2 - 252*e_prime2 - 3*C1**2) * D**6/720
    )

    lon_origin = (zone - 1) * 6 - 180 + 3
    lon = (lon_origin * math.pi/180 + (
        D
        - (1 + 2*T1 + C1) * D**3/6
        + (5 - 2*C1 + 28*T1 - 3*C1**2 + 8*e_prime2 + 24*T1**2) * D**5/120
    ) / math.cos(phi1))

    return math.degrees(lat), math.degrees(lon)


def coords_utm_to_wgs84(coords: list[list[float]],
                         zone: int = 22,
                         hemisphere: str = "S") -> list[list[float]]:
    """Converte lista de coordenadas UTM para [lon, lat] WGS84."""
    result = []
    for c in coords:
        lat, lon = utm_to_latlon(c[0], c[1], zone, hemisphere)
        result.append([lon, lat])
    return result


def latlon_to_utm(lat_deg: float, lon_deg: float,
                  zone: int = 22, hemisphere: str = "S") -> tuple[float, float]:
    """
    Converte latitude/longitude WGS84 para coordenadas UTM.
    Retorna (easting, northing) em metros.
    """
    a   = 6378137.0
    e2  = 0.00669437999014
    k0  = 0.9996

    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    lon0 = math.radians((zone - 1) * 6 - 180 + 3)

    e_prime2 = e2 / (1 - e2)
    N = a / math.sqrt(1 - e2 * math.sin(lat)**2)
    T = math.tan(lat)**2
    C = e_prime2 * math.cos(lat)**2
    A = math.cos(lat) * (lon - lon0)

    M = a * (
        (1 - e2/4 - 3*e2**2/64 - 5*e2**3/256)   * lat
        - (3*e2/8 + 3*e2**2/32 + 45*e2**3/1024) * math.sin(2*lat)
        + (15*e2**2/256 + 45*e2**3/1024)          * math.sin(4*lat)
        - (35*e2**3/3072)                          * math.sin(6*lat)
    )

    easting = k0 * N * (
        A
        + (1 - T + C) * A**3 / 6
        + (5 - 18*T + T**2 + 72*C - 58*e_prime2) * A**5 / 120
    ) + 500000.0

    northing = k0 * (
        M + N * math.tan(lat) * (
            A**2 / 2
            + (5 - T + 9*C + 4*C**2) * A**4 / 24
            + (61 - 58*T + T**2 + 600*C - 330*e_prime2) * A**6 / 720
        )
    )
    if hemisphere == "S":
        northing += 10_000_000.0

    return easting, northing


def coords_wgs84_to_utm(coords: list[list[float]],
                         zone: int = 22,
                         hemisphere: str = "S") -> list[list[float]]:
    """Converte lista de coordenadas [lon, lat] WGS84 para UTM [easting, northing]."""
    return [list(latlon_to_utm(c[1], c[0], zone, hemisphere)) for c in coords]


def is_wgs84(coords: list[list[float]]) -> bool:
    """
    Detecta se uma lista de coordenadas está em WGS84 (graus decimais)
    vs UTM (metros). WGS84: lon em -180..180, lat em -90..90.
    UTM 22S: easting ~200000..800000, northing ~6000000..10000000.
    """
    if not coords:
        return False
    x, y = coords[0][0], coords[0][1]
    return abs(x) <= 180 and abs(y) <= 90


def feature_utm_to_wgs84(feature: dict, zone: int = 22, hemisphere: str = "S") -> dict:
    """
    Converte as coordenadas de um GeoJSON Feature de UTM para WGS84.
    Suporta Polygon e MultiPolygon.
    """
    import copy
    feat = copy.deepcopy(feature)
    geom = feat.get("geometry", feat)
    gtype = geom["type"]

    if gtype == "Polygon":
        geom["coordinates"] = [
            coords_utm_to_wgs84(ring, zone, hemisphere)
            for ring in geom["coordinates"]
        ]
    elif gtype == "MultiPolygon":
        geom["coordinates"] = [
            [coords_utm_to_wgs84(ring, zone, hemisphere) for ring in poly]
            for poly in geom["coordinates"]
        ]

    return feat

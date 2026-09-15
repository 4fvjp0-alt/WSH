"""Reference implementation of the CivSim astronomy core (Meeus, Astronomical Algorithms).

This is the numerically verified reference that the C# port in
src/CivSim.Core/Astronomy mirrors line by line. Run it to print sunrise,
sunset and solar noon for Seoul on a few dates, or import it from tests.

    python3 tools/astro_reference.py
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DEG = math.pi / 180.0
J2000 = 2451545.0

SEOUL_LAT = 37.5665
SEOUL_LON = 126.9780


# --------------------------------------------------------------------------
# Calendar
# --------------------------------------------------------------------------
def gregorian_to_jd(year: int, month: int, day: float) -> float:
    """Proleptic Gregorian calendar date -> Julian Day (Meeus ch. 7)."""
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + b - 1524.5


def jd_to_gregorian(jd: float) -> tuple[int, int, float]:
    jd += 0.5
    z = math.floor(jd)
    f = jd - z
    alpha = math.floor((z - 1867216.25) / 36524.25)
    a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day = b - d - math.floor(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    return int(year), int(month), day


# --------------------------------------------------------------------------
# Delta T  (Espenak & Meeus 2006 polynomials)
# --------------------------------------------------------------------------
def delta_t_seconds(year: float) -> float:
    y = year
    if y < -500:
        u = (y - 1820) / 100
        return -20 + 32 * u * u
    if y < 500:
        u = y / 100
        return (10583.6 - 1014.41 * u + 33.78311 * u**2 - 5.952053 * u**3
                - 0.1798452 * u**4 + 0.022174192 * u**5 + 0.0090316521 * u**6)
    if y < 1600:
        u = (y - 1000) / 100
        return (1574.2 - 556.01 * u + 71.23472 * u**2 + 0.319781 * u**3
                - 0.8503463 * u**4 - 0.005050998 * u**5 + 0.0083572073 * u**6)
    if y < 1700:
        t = y - 1600
        return 120 - 0.9808 * t - 0.01532 * t**2 + t**3 / 7129
    if y < 1800:
        t = y - 1700
        return 8.83 + 0.1603 * t - 0.0059285 * t**2 + 0.00013336 * t**3 - t**4 / 1174000
    if y < 1860:
        t = y - 1800
        return (13.72 - 0.332447 * t + 0.0068612 * t**2 + 0.0041116 * t**3 - 0.00037436 * t**4
                + 0.0000121272 * t**5 - 0.0000001699 * t**6 + 0.000000000875 * t**7)
    if y < 1900:
        t = y - 1860
        return 7.62 + 0.5737 * t - 0.251754 * t**2 + 0.01680668 * t**3 - 0.0004473624 * t**4 + t**5 / 233174
    if y < 1920:
        t = y - 1900
        return -2.79 + 1.494119 * t - 0.0598939 * t**2 + 0.0061966 * t**3 - 0.000197 * t**4
    if y < 1941:
        t = y - 1920
        return 21.20 + 0.84493 * t - 0.076100 * t**2 + 0.0020936 * t**3
    if y < 1961:
        t = y - 1950
        return 29.07 + 0.407 * t - t**2 / 233 + t**3 / 2547
    if y < 1986:
        t = y - 1975
        return 45.45 + 1.067 * t - t**2 / 260 - t**3 / 718
    if y < 2005:
        t = y - 2000
        return (63.86 + 0.3345 * t - 0.060374 * t**2 + 0.0017275 * t**3
                + 0.000651814 * t**4 + 0.00002373599 * t**5)
    if y < 2050:
        t = y - 2000
        return 62.92 + 0.32217 * t + 0.005589 * t**2
    if y < 2150:
        u = (y - 1820) / 100
        return -20 + 32 * u * u - 0.5628 * (2150 - y)
    u = (y - 1820) / 100
    return -20 + 32 * u * u


def decimal_year(jd: float) -> float:
    y, m, d = jd_to_gregorian(jd)
    return y + (m - 0.5) / 12


# --------------------------------------------------------------------------
# Solar position (Meeus ch. 25, low-accuracy ~0.01 deg)
# --------------------------------------------------------------------------
@dataclass
class SolarState:
    right_ascension_deg: float
    declination_deg: float
    apparent_longitude_deg: float
    equation_of_time_min: float
    distance_au: float


def _norm360(x: float) -> float:
    return x % 360.0


def solar_state(jd_ut: float, apply_delta_t: bool = True) -> SolarState:
    jde = jd_ut + (delta_t_seconds(decimal_year(jd_ut)) / 86400.0 if apply_delta_t else 0.0)
    t = (jde - J2000) / 36525.0
    l0 = _norm360(280.46646 + 36000.76983 * t + 0.0003032 * t * t)
    m = _norm360(357.52911 + 35999.05029 * t - 0.0001537 * t * t)
    e = 0.016708634 - 0.000042037 * t - 0.0000001267 * t * t
    mr = m * DEG
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(mr)
         + (0.019993 - 0.000101 * t) * math.sin(2 * mr)
         + 0.000289 * math.sin(3 * mr))
    true_lon = l0 + c
    nu = m + c
    r = 1.000001018 * (1 - e * e) / (1 + e * math.cos(nu * DEG))
    omega = 125.04 - 1934.136 * t
    lam = true_lon - 0.00569 - 0.00478 * math.sin(omega * DEG)
    eps0 = 23.0 + (26.0 + (21.448 - 46.8150 * t - 0.00059 * t * t + 0.001813 * t**3) / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(omega * DEG)
    lr, er = lam * DEG, eps * DEG
    ra = _norm360(math.atan2(math.cos(er) * math.sin(lr), math.cos(lr)) / DEG)
    dec = math.asin(math.sin(er) * math.sin(lr)) / DEG
    # Equation of time (Meeus 28.3, NOAA form)
    y = math.tan(er / 2) ** 2
    l0r = l0 * DEG
    eot = (y * math.sin(2 * l0r) - 2 * e * math.sin(mr) + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
           - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr))
    eot_min = eot / DEG * 4.0
    return SolarState(ra, dec, _norm360(lam), eot_min, r)


def greenwich_mean_sidereal_deg(jd_ut: float) -> float:
    t = (jd_ut - J2000) / 36525.0
    return _norm360(280.46061837 + 360.98564736629 * (jd_ut - J2000) + 0.000387933 * t * t - t**3 / 38710000.0)


@dataclass
class HorizontalCoords:
    altitude_deg: float   # geometric (no refraction)
    azimuth_deg: float    # from north, clockwise


def sun_horizontal(jd_ut: float, lat_deg: float, lon_deg: float) -> HorizontalCoords:
    s = solar_state(jd_ut)
    h = (greenwich_mean_sidereal_deg(jd_ut) + lon_deg - s.right_ascension_deg) * DEG
    phi, dec = lat_deg * DEG, s.declination_deg * DEG
    alt = math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(h))
    az_south = math.atan2(math.sin(h), math.cos(h) * math.sin(phi) - math.tan(dec) * math.cos(phi))
    return HorizontalCoords(alt / DEG, _norm360(az_south / DEG + 180.0))


# --------------------------------------------------------------------------
# Sunrise / sunset / noon  (NOAA iterative method)
# --------------------------------------------------------------------------
SUNRISE_ALT_DEG = -0.833  # refraction 34' + semidiameter 16'


def solar_noon_jd(jd_date0: float, lon_deg: float) -> float:
    """jd_date0: JD at 0h UT of the civil date. Returns JD (UT) of solar noon."""
    noon_guess = jd_date0 + 0.5 - lon_deg / 360.0
    for _ in range(2):
        eot = solar_state(noon_guess).equation_of_time_min
        noon_guess = jd_date0 + (720.0 - 4.0 * lon_deg - eot) / 1440.0
    return noon_guess


def _hour_angle_deg(lat_deg: float, dec_deg: float, alt_deg: float) -> float | None:
    phi, dec, h0 = lat_deg * DEG, dec_deg * DEG, alt_deg * DEG
    cos_h = (math.sin(h0) - math.sin(phi) * math.sin(dec)) / (math.cos(phi) * math.cos(dec))
    if cos_h < -1 or cos_h > 1:
        return None
    return math.acos(cos_h) / DEG


def sun_event_jd(jd_date0: float, lat_deg: float, lon_deg: float, rise: bool) -> float | None:
    noon = solar_noon_jd(jd_date0, lon_deg)
    guess = noon
    for _ in range(3):
        s = solar_state(guess)
        ha = _hour_angle_deg(lat_deg, s.declination_deg, SUNRISE_ALT_DEG)
        if ha is None:
            return None
        guess = jd_date0 + (720.0 - 4.0 * (lon_deg + (ha if rise else -ha)) - s.equation_of_time_min) / 1440.0
    return guess


# --------------------------------------------------------------------------
# Korean civil time history
# --------------------------------------------------------------------------
def korea_utc_offset_hours(jd_ut: float, lon_deg: float = SEOUL_LON) -> float:
    """Local mean time before 1908, then the statutory zones actually used in Korea."""
    if jd_ut < gregorian_to_jd(1908, 4, 1):
        return lon_deg / 15.0
    if jd_ut < gregorian_to_jd(1912, 1, 1):
        return 8.5
    if jd_ut < gregorian_to_jd(1954, 3, 21):
        return 9.0
    if jd_ut < gregorian_to_jd(1961, 8, 10):
        return 8.5
    return 9.0


def fmt_local(jd_ut: float | None, offset_h: float) -> str:
    if jd_ut is None:
        return "--:--"
    frac = (jd_ut + offset_h / 24.0 + 0.5) % 1.0
    minutes = round(frac * 1440.0)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


if __name__ == "__main__":
    for (y, m, d) in [(2026, 3, 20), (2026, 6, 21), (2026, 9, 23), (2026, 12, 22), (1394, 10, 25), (100, 6, 21)]:
        jd0 = gregorian_to_jd(y, m, d)  # 0h UT of the civil date
        off = korea_utc_offset_hours(jd0)
        rise = sun_event_jd(jd0, SEOUL_LAT, SEOUL_LON, True)
        sett = sun_event_jd(jd0, SEOUL_LAT, SEOUL_LON, False)
        noon = solar_noon_jd(jd0, SEOUL_LON)
        alt = sun_horizontal(noon, SEOUL_LAT, SEOUL_LON).altitude_deg
        print(f"{y:5d}-{m:02d}-{d:02d} UTC{off:+.2f}  rise {fmt_local(rise, off)}  noon {fmt_local(noon, off)} "
              f"alt {alt:5.1f}  set {fmt_local(sett, off)}  dT {delta_t_seconds(decimal_year(jd0)):7.0f}s")

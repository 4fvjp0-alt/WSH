"""Locks the reference values used by the C# xUnit tests. Run: python3 tools/test_astro_reference.py"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import astro_reference as A


def hhmm_to_min(s):
    return int(s[:2]) * 60 + int(s[3:5])


def check_day(y, m, d, rise, sett, noon_alt):
    jd0 = A.gregorian_to_jd(y, m, d)
    off = A.korea_utc_offset_hours(jd0)
    r = A.fmt_local(A.sun_event_jd(jd0, A.SEOUL_LAT, A.SEOUL_LON, True), off)
    s = A.fmt_local(A.sun_event_jd(jd0, A.SEOUL_LAT, A.SEOUL_LON, False), off)
    alt = A.sun_horizontal(A.solar_noon_jd(jd0, A.SEOUL_LON), A.SEOUL_LAT, A.SEOUL_LON).altitude_deg
    assert abs(hhmm_to_min(r) - hhmm_to_min(rise)) <= 2, (y, m, d, r, rise)
    assert abs(hhmm_to_min(s) - hhmm_to_min(sett)) <= 2, (y, m, d, s, sett)
    assert abs(alt - noon_alt) <= 0.3, (y, m, d, alt, noon_alt)


check_day(2026, 3, 20, "06:36", "18:44", 52.3)
check_day(2026, 6, 21, "05:11", "19:57", 75.9)
check_day(2026, 9, 23, "06:20", "18:28", 52.4)
check_day(2026, 12, 22, "07:43", "17:17", 29.0)

assert abs(A.gregorian_to_jd(2000, 1, 1.5) - 2451545.0) < 1e-6
assert abs(A.gregorian_to_jd(1582, 10, 15) - 2299160.5) < 1e-6
assert 63 <= A.delta_t_seconds(2000) <= 65
assert 9400 <= A.delta_t_seconds(100.5) <= 9800
assert 8.46 <= A.korea_utc_offset_hours(A.gregorian_to_jd(1394, 1, 1)) <= 8.47
assert A.korea_utc_offset_hours(A.gregorian_to_jd(1958, 1, 1)) == 8.5

summer = A.solar_state(A.gregorian_to_jd(2026, 6, 21 + 8.4 / 24)).declination_deg
assert 23.40 <= summer <= 23.46, summer
eot_nov = A.solar_state(A.gregorian_to_jd(2026, 11, 3)).equation_of_time_min
eot_feb = A.solar_state(A.gregorian_to_jd(2026, 2, 11)).equation_of_time_min
assert 15.5 <= eot_nov <= 16.8, eot_nov
assert -14.5 <= eot_feb <= -13.8, eot_feb

jd0 = A.gregorian_to_jd(2026, 3, 20)
rise_az = A.sun_horizontal(A.sun_event_jd(jd0, A.SEOUL_LAT, A.SEOUL_LON, True), A.SEOUL_LAT, A.SEOUL_LON)
set_az = A.sun_horizontal(A.sun_event_jd(jd0, A.SEOUL_LAT, A.SEOUL_LON, False), A.SEOUL_LAT, A.SEOUL_LON)
assert 88 <= rise_az.azimuth_deg <= 92, rise_az
assert 268 <= set_az.azimuth_deg <= 272, set_az
assert -1.2 <= rise_az.altitude_deg <= -0.5, rise_az

jd0 = A.gregorian_to_jd(100, 6, 21)
r, s = A.sun_event_jd(jd0, A.SEOUL_LAT, A.SEOUL_LON, True), A.sun_event_jd(jd0, A.SEOUL_LAT, A.SEOUL_LON, False)
assert 14.5 <= (s - r) * 24 <= 15.1, (s - r) * 24
print("all reference checks passed")

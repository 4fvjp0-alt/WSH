using System;
using CivSim.Core.Time;

namespace CivSim.Core.Astronomy
{
    /// <summary>Geocentric solar coordinates for one instant.</summary>
    public readonly struct SolarState
    {
        public readonly double RightAscensionDeg;
        public readonly double DeclinationDeg;
        public readonly double ApparentLongitudeDeg;
        public readonly double EquationOfTimeMinutes;
        public readonly double DistanceAu;

        public SolarState(double ra, double dec, double lon, double eot, double r)
        {
            RightAscensionDeg = ra; DeclinationDeg = dec; ApparentLongitudeDeg = lon; EquationOfTimeMinutes = eot; DistanceAu = r;
        }
    }

    /// <summary>Topocentric sun direction. Altitude is geometric (no refraction); azimuth is clockwise from north.</summary>
    public readonly struct HorizontalCoords
    {
        public readonly double AltitudeDeg;
        public readonly double AzimuthDeg;

        public HorizontalCoords(double altitudeDeg, double azimuthDeg)
        {
            AltitudeDeg = altitudeDeg; AzimuthDeg = azimuthDeg;
        }

        /// <summary>Unit vector toward the sun in a local East/Up/North frame (matches Unity +X/+Y/+Z with +Z north).</summary>
        public void ToEastUpNorth(out double east, out double up, out double north)
        {
            double alt = AltitudeDeg * Angles.Deg, az = AzimuthDeg * Angles.Deg;
            up = Math.Sin(alt);
            double horiz = Math.Cos(alt);
            north = horiz * Math.Cos(az);
            east = horiz * Math.Sin(az);
        }
    }

    internal static class Angles
    {
        public const double Deg = Math.PI / 180.0;
        public static double Norm360(double x) { x %= 360.0; return x < 0 ? x + 360.0 : x; }
    }

    /// <summary>
    /// Low-accuracy solar position, Meeus "Astronomical Algorithms" ch. 25 (≈0.01° near J2000, well under 1° across AD 100–2100).
    /// Mirrors tools/astro_reference.py, which is the numerically verified reference.
    /// </summary>
    public static class SolarPosition
    {
        public static SolarState Compute(double jdUt, bool applyDeltaT = true)
        {
            double jde = jdUt + (applyDeltaT ? DeltaT.Seconds(JulianDay.DecimalYear(jdUt)) / JulianDay.SecondsPerDay : 0.0);
            double t = (jde - JulianDay.J2000) / 36525.0;
            double l0 = Angles.Norm360(280.46646 + 36000.76983 * t + 0.0003032 * t * t);
            double m = Angles.Norm360(357.52911 + 35999.05029 * t - 0.0001537 * t * t);
            double e = 0.016708634 - 0.000042037 * t - 0.0000001267 * t * t;
            double mr = m * Angles.Deg;
            double c = (1.914602 - 0.004817 * t - 0.000014 * t * t) * Math.Sin(mr)
                       + (0.019993 - 0.000101 * t) * Math.Sin(2 * mr)
                       + 0.000289 * Math.Sin(3 * mr);
            double trueLon = l0 + c;
            double nu = m + c;
            double r = 1.000001018 * (1 - e * e) / (1 + e * Math.Cos(nu * Angles.Deg));
            double omega = 125.04 - 1934.136 * t;
            double lambda = trueLon - 0.00569 - 0.00478 * Math.Sin(omega * Angles.Deg);
            double eps0 = 23.0 + (26.0 + (21.448 - 46.8150 * t - 0.00059 * t * t + 0.001813 * t * t * t) / 60.0) / 60.0;
            double eps = eps0 + 0.00256 * Math.Cos(omega * Angles.Deg);
            double lr = lambda * Angles.Deg, er = eps * Angles.Deg;
            double ra = Angles.Norm360(Math.Atan2(Math.Cos(er) * Math.Sin(lr), Math.Cos(lr)) / Angles.Deg);
            double dec = Math.Asin(Math.Sin(er) * Math.Sin(lr)) / Angles.Deg;

            double y = Math.Tan(er / 2); y *= y;
            double l0r = l0 * Angles.Deg;
            double eot = y * Math.Sin(2 * l0r) - 2 * e * Math.Sin(mr) + 4 * e * y * Math.Sin(mr) * Math.Cos(2 * l0r)
                         - 0.5 * y * y * Math.Sin(4 * l0r) - 1.25 * e * e * Math.Sin(2 * mr);
            double eotMin = eot / Angles.Deg * 4.0;

            return new SolarState(ra, dec, Angles.Norm360(lambda), eotMin, r);
        }

        /// <summary>Greenwich mean sidereal time in degrees (Meeus 12.4).</summary>
        public static double GreenwichMeanSiderealDeg(double jdUt)
        {
            double t = (jdUt - JulianDay.J2000) / 36525.0;
            return Angles.Norm360(280.46061837 + 360.98564736629 * (jdUt - JulianDay.J2000) + 0.000387933 * t * t - t * t * t / 38710000.0);
        }

        /// <summary>Sun altitude/azimuth for an observer. East longitude positive.</summary>
        public static HorizontalCoords Horizontal(double jdUt, double latDeg, double lonDeg)
        {
            var s = Compute(jdUt);
            double h = (GreenwichMeanSiderealDeg(jdUt) + lonDeg - s.RightAscensionDeg) * Angles.Deg;
            double phi = latDeg * Angles.Deg, dec = s.DeclinationDeg * Angles.Deg;
            double alt = Math.Asin(Math.Sin(phi) * Math.Sin(dec) + Math.Cos(phi) * Math.Cos(dec) * Math.Cos(h));
            double azSouth = Math.Atan2(Math.Sin(h), Math.Cos(h) * Math.Sin(phi) - Math.Tan(dec) * Math.Cos(phi));
            return new HorizontalCoords(alt / Angles.Deg, Angles.Norm360(azSouth / Angles.Deg + 180.0));
        }
    }
}

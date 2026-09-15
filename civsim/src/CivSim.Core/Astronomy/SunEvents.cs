using System;
using CivSim.Core.Time;

namespace CivSim.Core.Astronomy
{
    /// <summary>Sunrise, sunset and solar noon (NOAA iterative method on top of <see cref="SolarPosition"/>).</summary>
    public static class SunEvents
    {
        /// <summary>Standard rise/set altitude: 34' refraction + 16' semidiameter.</summary>
        public const double RiseSetAltitudeDeg = -0.833;

        /// <param name="jdDate0Ut">Julian Day at 0h UT of the civil date (an X.5 value).</param>
        public static double SolarNoon(double jdDate0Ut, double lonDeg)
        {
            double noon = jdDate0Ut + 0.5 - lonDeg / 360.0;
            for (int i = 0; i < 2; i++)
            {
                double eot = SolarPosition.Compute(noon).EquationOfTimeMinutes;
                noon = jdDate0Ut + (720.0 - 4.0 * lonDeg - eot) / JulianDay.MinutesPerDay;
            }
            return noon;
        }

        public static double? Sunrise(double jdDate0Ut, double latDeg, double lonDeg) => Event(jdDate0Ut, latDeg, lonDeg, rise: true);
        public static double? Sunset(double jdDate0Ut, double latDeg, double lonDeg) => Event(jdDate0Ut, latDeg, lonDeg, rise: false);

        private static double? Event(double jdDate0Ut, double latDeg, double lonDeg, bool rise)
        {
            double guess = SolarNoon(jdDate0Ut, lonDeg);
            for (int i = 0; i < 3; i++)
            {
                var s = SolarPosition.Compute(guess);
                double? ha = HourAngleDeg(latDeg, s.DeclinationDeg, RiseSetAltitudeDeg);
                if (ha == null) return null; // polar day/night: never happens in Seoul, kept for generality
                double signed = rise ? ha.Value : -ha.Value;
                guess = jdDate0Ut + (720.0 - 4.0 * (lonDeg + signed) - s.EquationOfTimeMinutes) / JulianDay.MinutesPerDay;
            }
            return guess;
        }

        private static double? HourAngleDeg(double latDeg, double decDeg, double altDeg)
        {
            double phi = latDeg * Angles.Deg, dec = decDeg * Angles.Deg, h0 = altDeg * Angles.Deg;
            double cosH = (Math.Sin(h0) - Math.Sin(phi) * Math.Sin(dec)) / (Math.Cos(phi) * Math.Cos(dec));
            if (cosH < -1 || cosH > 1) return null;
            return Math.Acos(cosH) / Angles.Deg;
        }
    }
}

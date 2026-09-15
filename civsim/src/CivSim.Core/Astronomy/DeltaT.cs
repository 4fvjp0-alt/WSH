using System;

namespace CivSim.Core.Astronomy
{
    /// <summary>
    /// ΔT = TT − UT in seconds (Espenak &amp; Meeus 2006 polynomial fit).
    /// Around AD 100 this is ~2.7 hours, which visibly shifts solar time, so the simulation applies it.
    /// </summary>
    public static class DeltaT
    {
        public static double Seconds(double year)
        {
            double y = year, u, t;
            if (y < -500) { u = (y - 1820) / 100; return -20 + 32 * u * u; }
            if (y < 500)
            {
                u = y / 100;
                return 10583.6 - 1014.41 * u + 33.78311 * P(u, 2) - 5.952053 * P(u, 3)
                       - 0.1798452 * P(u, 4) + 0.022174192 * P(u, 5) + 0.0090316521 * P(u, 6);
            }
            if (y < 1600)
            {
                u = (y - 1000) / 100;
                return 1574.2 - 556.01 * u + 71.23472 * P(u, 2) + 0.319781 * P(u, 3)
                       - 0.8503463 * P(u, 4) - 0.005050998 * P(u, 5) + 0.0083572073 * P(u, 6);
            }
            if (y < 1700) { t = y - 1600; return 120 - 0.9808 * t - 0.01532 * t * t + P(t, 3) / 7129; }
            if (y < 1800) { t = y - 1700; return 8.83 + 0.1603 * t - 0.0059285 * t * t + 0.00013336 * P(t, 3) - P(t, 4) / 1174000; }
            if (y < 1860)
            {
                t = y - 1800;
                return 13.72 - 0.332447 * t + 0.0068612 * P(t, 2) + 0.0041116 * P(t, 3) - 0.00037436 * P(t, 4)
                       + 0.0000121272 * P(t, 5) - 0.0000001699 * P(t, 6) + 0.000000000875 * P(t, 7);
            }
            if (y < 1900)
            {
                t = y - 1860;
                return 7.62 + 0.5737 * t - 0.251754 * P(t, 2) + 0.01680668 * P(t, 3) - 0.0004473624 * P(t, 4) + P(t, 5) / 233174;
            }
            if (y < 1920) { t = y - 1900; return -2.79 + 1.494119 * t - 0.0598939 * P(t, 2) + 0.0061966 * P(t, 3) - 0.000197 * P(t, 4); }
            if (y < 1941) { t = y - 1920; return 21.20 + 0.84493 * t - 0.076100 * P(t, 2) + 0.0020936 * P(t, 3); }
            if (y < 1961) { t = y - 1950; return 29.07 + 0.407 * t - P(t, 2) / 233 + P(t, 3) / 2547; }
            if (y < 1986) { t = y - 1975; return 45.45 + 1.067 * t - P(t, 2) / 260 - P(t, 3) / 718; }
            if (y < 2005)
            {
                t = y - 2000;
                return 63.86 + 0.3345 * t - 0.060374 * P(t, 2) + 0.0017275 * P(t, 3) + 0.000651814 * P(t, 4) + 0.00002373599 * P(t, 5);
            }
            if (y < 2050) { t = y - 2000; return 62.92 + 0.32217 * t + 0.005589 * t * t; }
            if (y < 2150) { u = (y - 1820) / 100; return -20 + 32 * u * u - 0.5628 * (2150 - y); }
            u = (y - 1820) / 100;
            return -20 + 32 * u * u;
        }

        private static double P(double x, int n) => Math.Pow(x, n);
    }
}

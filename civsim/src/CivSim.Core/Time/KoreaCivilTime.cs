using System;

namespace CivSim.Core.Time
{
    /// <summary>
    /// The civil clock people in Seoul actually lived by.
    /// Before 1908 there was no statutory zone, so local mean solar time of the observer's longitude is used.
    /// </summary>
    public static class KoreaCivilTime
    {
        public const double SeoulLongitude = 126.9780;

        private static readonly double Jd1908Apr1 = JulianDay.FromGregorian(1908, 4, 1);
        private static readonly double Jd1912Jan1 = JulianDay.FromGregorian(1912, 1, 1);
        private static readonly double Jd1954Mar21 = JulianDay.FromGregorian(1954, 3, 21);
        private static readonly double Jd1961Aug10 = JulianDay.FromGregorian(1961, 8, 10);

        public static double UtcOffsetHours(double jdUt, double longitudeDeg = SeoulLongitude)
        {
            if (jdUt < Jd1908Apr1) return longitudeDeg / 15.0;   // local mean time
            if (jdUt < Jd1912Jan1) return 8.5;                    // 대한제국 표준시 (UTC+8:30)
            if (jdUt < Jd1954Mar21) return 9.0;                   // 일본 표준시
            if (jdUt < Jd1961Aug10) return 8.5;                   // UTC+8:30 재채택
            return 9.0;                                           // KST
        }

        public static double ToLocalJd(double jdUt, double longitudeDeg = SeoulLongitude)
            => jdUt + UtcOffsetHours(jdUt, longitudeDeg) / 24.0;

        /// <summary>Local wall-clock date/time for a UT Julian Day.</summary>
        public static CalendarDate ToLocalDate(double jdUt, double longitudeDeg = SeoulLongitude)
            => JulianDay.ToGregorian(ToLocalJd(jdUt, longitudeDeg));

        /// <summary>"HH:mm" of the local wall clock, rounded to the nearest minute.</summary>
        public static string FormatLocalTime(double jdUt, double longitudeDeg = SeoulLongitude)
        {
            double frac = ToLocalJd(jdUt, longitudeDeg) + 0.5;
            frac -= Math.Floor(frac);
            int minutes = (int)Math.Round(frac * JulianDay.MinutesPerDay) % 1440;
            return $"{minutes / 60:00}:{minutes % 60:00}";
        }

        /// <summary>JD (UT) of 0h local time on the given local civil date.</summary>
        public static double LocalMidnightUt(int year, int month, int day, double longitudeDeg = SeoulLongitude)
        {
            double jd0 = JulianDay.FromGregorian(year, month, day);
            return jd0 - UtcOffsetHours(jd0, longitudeDeg) / 24.0;
        }
    }
}

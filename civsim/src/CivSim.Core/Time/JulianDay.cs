using System;

namespace CivSim.Core.Time
{
    /// <summary>A broken-down calendar date. DayFraction is the fraction of the day elapsed since 0h.</summary>
    public readonly struct CalendarDate
    {
        public readonly int Year;
        public readonly int Month;
        public readonly int Day;
        public readonly double DayFraction;

        public CalendarDate(int year, int month, int day, double dayFraction)
        {
            Year = year; Month = month; Day = day; DayFraction = dayFraction;
        }

        private long MsOfDay => (long)Math.Round(DayFraction * 86400000.0);
        public int Hour => (int)(MsOfDay / 3600000L);
        public int Minute => (int)(MsOfDay / 60000L % 60L);
        public double Second => (MsOfDay % 60000L) / 1000.0;

        public override string ToString() => $"{Year:0000}-{Month:00}-{Day:00} {Hour:00}:{Minute:00}";
    }

    /// <summary>
    /// Julian Day conversions (Meeus, Astronomical Algorithms ch. 7).
    /// The simulation clock stores time as a Julian Day in Universal Time; every calendar is a view on it.
    /// </summary>
    public static class JulianDay
    {
        public const double J2000 = 2451545.0;
        public const double SecondsPerDay = 86400.0;
        public const double MinutesPerDay = 1440.0;

        /// <summary>Proleptic Gregorian date to JD. <paramref name="day"/> may carry a fraction (0h UT = integer).</summary>
        public static double FromGregorian(int year, int month, double day)
        {
            if (month <= 2) { year -= 1; month += 12; }
            int a = FloorDiv(year, 100);
            int b = 2 - a + FloorDiv(a, 4);
            return Math.Floor(365.25 * (year + 4716)) + Math.Floor(30.6001 * (month + 1)) + day + b - 1524.5;
        }

        public static double FromGregorian(int year, int month, int day, int hour, int minute, double second = 0.0)
            => FromGregorian(year, month, day + (hour + (minute + second / 60.0) / 60.0) / 24.0);

        /// <summary>Julian-calendar date to JD (used for display before 1582-10-15).</summary>
        public static double FromJulianCalendar(int year, int month, double day)
        {
            if (month <= 2) { year -= 1; month += 12; }
            return Math.Floor(365.25 * (year + 4716)) + Math.Floor(30.6001 * (month + 1)) + day - 1524.5;
        }

        public static CalendarDate ToGregorian(double jd) => Decode(jd, gregorian: true);

        public static CalendarDate ToJulianCalendar(double jd) => Decode(jd, gregorian: false);

        /// <summary>Year as a decimal, e.g. 2026.47. Used for Delta T.</summary>
        public static double DecimalYear(double jd)
        {
            var d = ToGregorian(jd);
            return d.Year + (d.Month - 0.5) / 12.0;
        }

        private static CalendarDate Decode(double jd, bool gregorian)
        {
            // Decompose in integer milliseconds. A JD near 1.8e6 carries ~3.5e-5 s of double-precision
            // slop, so a plain floor would decode 13:37:00 as 13:36:59.99996.
            const long MsPerDay = 86400000L;
            long totalMs = (long)Math.Round((jd + 0.5) * MsPerDay);
            long z = (long)Math.Floor((double)totalMs / MsPerDay);
            long msOfDay = totalMs - z * MsPerDay;
            double a = z;
            if (gregorian)
            {
                double alpha = Math.Floor((z - 1867216.25) / 36524.25);
                a = z + 1 + alpha - Math.Floor(alpha / 4);
            }
            double b = a + 1524;
            double c = Math.Floor((b - 122.1) / 365.25);
            double d = Math.Floor(365.25 * c);
            double e = Math.Floor((b - d) / 30.6001);
            int day = (int)(b - d - Math.Floor(30.6001 * e));
            int month = e < 14 ? (int)e - 1 : (int)e - 13;
            int year = month > 2 ? (int)c - 4716 : (int)c - 4715;
            return new CalendarDate(year, month, day, msOfDay / (double)MsPerDay);
        }

        private static int FloorDiv(int a, int b) => (int)Math.Floor((double)a / b);
    }
}

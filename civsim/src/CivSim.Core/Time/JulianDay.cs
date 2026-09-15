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

        public int Hour => (int)Math.Floor(DayFraction * 24.0);
        public int Minute => (int)Math.Floor(DayFraction * 1440.0) % 60;
        public double Second => (DayFraction * 86400.0) % 60.0;

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
            jd += 0.5;
            double z = Math.Floor(jd);
            double f = jd - z;
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
            return new CalendarDate(year, month, day, f);
        }

        private static int FloorDiv(int a, int b) => (int)Math.Floor((double)a / b);
    }
}

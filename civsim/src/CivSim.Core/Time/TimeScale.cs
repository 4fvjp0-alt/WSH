using System;

namespace CivSim.Core.Time
{
    /// <summary>The speed buttons on the time bar.</summary>
    public enum TimeScale
    {
        Paused = 0,
        RealTime,          // 1 s  / s
        MinutePerSecond,   // 60 s / s
        HourPerSecond,     // 1 h  / s
        DayPerSecond,      // 1 d  / s
        MonthPerSecond,    // ~30.44 d / s
        YearPerSecond,     // 365.25 d / s
        DecadePerSecond    // 3652.5 d / s
    }

    /// <summary>Which simulation layers run at a given speed (see plan §4.2).</summary>
    [Flags]
    public enum SimLayers
    {
        None = 0,
        Micro = 1,   // individual agents near the camera
        Meso = 2,    // settlements, building slots, roads
        Macro = 4    // cohorts, economy, polities
    }

    public static class TimeScaleExtensions
    {
        public const double DaysPerYear = 365.25;
        public const double DaysPerMonth = DaysPerYear / 12.0;

        public static double SimSecondsPerRealSecond(this TimeScale scale)
        {
            switch (scale)
            {
                case TimeScale.Paused: return 0.0;
                case TimeScale.RealTime: return 1.0;
                case TimeScale.MinutePerSecond: return 60.0;
                case TimeScale.HourPerSecond: return 3600.0;
                case TimeScale.DayPerSecond: return JulianDay.SecondsPerDay;
                case TimeScale.MonthPerSecond: return DaysPerMonth * JulianDay.SecondsPerDay;
                case TimeScale.YearPerSecond: return DaysPerYear * JulianDay.SecondsPerDay;
                case TimeScale.DecadePerSecond: return 10.0 * DaysPerYear * JulianDay.SecondsPerDay;
                default: throw new ArgumentOutOfRangeException(nameof(scale));
            }
        }

        /// <summary>Micro agents are simulated only up to one hour per second; beyond that they become crowd density.</summary>
        public static SimLayers ActiveLayers(this TimeScale scale)
        {
            switch (scale)
            {
                case TimeScale.Paused: return SimLayers.None;
                case TimeScale.RealTime:
                case TimeScale.MinutePerSecond: return SimLayers.Micro;
                case TimeScale.HourPerSecond: return SimLayers.Micro | SimLayers.Macro;
                case TimeScale.DayPerSecond: return SimLayers.Meso | SimLayers.Macro;
                default: return SimLayers.Meso | SimLayers.Macro;
            }
        }

        /// <summary>Adaptive macro step length in days: daily up to a day per second, monthly and yearly beyond.</summary>
        public static double MacroStepDays(this TimeScale scale)
        {
            switch (scale)
            {
                case TimeScale.MonthPerSecond: return DaysPerMonth;
                case TimeScale.YearPerSecond:
                case TimeScale.DecadePerSecond: return DaysPerYear;
                default: return 1.0;
            }
        }

        public static string Label(this TimeScale scale)
        {
            switch (scale)
            {
                case TimeScale.Paused: return "일시정지";
                case TimeScale.RealTime: return "실시간";
                case TimeScale.MinutePerSecond: return "1분/초";
                case TimeScale.HourPerSecond: return "1시간/초";
                case TimeScale.DayPerSecond: return "1일/초";
                case TimeScale.MonthPerSecond: return "1개월/초";
                case TimeScale.YearPerSecond: return "1년/초";
                case TimeScale.DecadePerSecond: return "10년/초";
                default: return scale.ToString();
            }
        }
    }
}

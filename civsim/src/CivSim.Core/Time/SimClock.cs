using System;

namespace CivSim.Core.Time
{
    /// <summary>
    /// The one clock every system reads. Time is a Julian Day in UT; the speed is a <see cref="TimeScale"/>.
    /// The clock also accumulates macro-step debt so callers can run whole days/months/years at once.
    /// </summary>
    public sealed class SimClock
    {
        /// <summary>AD 100, spring equinox: a small riverside village era on the Han (plan decision: start year AD 100).</summary>
        public static readonly double DefaultStartJd = JulianDay.FromGregorian(100, 3, 21);

        private double _macroDebtDays;

        public SimClock(double startJdUt, TimeScale scale = TimeScale.Paused)
        {
            JulianDayUt = startJdUt;
            Scale = scale;
            _lastMacroJd = startJdUt;
        }

        public double JulianDayUt { get; private set; }
        public TimeScale Scale { get; set; }
        public double SimSecondsPerRealSecond => Scale.SimSecondsPerRealSecond();
        public SimLayers ActiveLayers => Scale.ActiveLayers();
        public long TotalTicks { get; private set; }

        private double _lastMacroJd;

        /// <summary>Called once per rendered frame with the real elapsed seconds.</summary>
        public void Advance(double realDeltaSeconds)
        {
            if (realDeltaSeconds < 0) throw new ArgumentOutOfRangeException(nameof(realDeltaSeconds));
            AdvanceSimSeconds(realDeltaSeconds * SimSecondsPerRealSecond);
        }

        public void AdvanceSimSeconds(double simSeconds)
        {
            if (simSeconds == 0) return;
            JulianDayUt += simSeconds / JulianDay.SecondsPerDay;
            TotalTicks++;
        }

        /// <summary>Jump to an absolute date. Macro debt is discarded; callers should re-seed derived state.</summary>
        public void JumpTo(double jdUt)
        {
            JulianDayUt = jdUt;
            _lastMacroJd = jdUt;
            _macroDebtDays = 0;
        }

        /// <summary>
        /// Returns how many macro steps of <see cref="TimeScaleExtensions.MacroStepDays"/> are owed since the last call,
        /// so the macro layer can catch up in whole steps regardless of frame rate.
        /// </summary>
        public int TakeMacroSteps(out double stepDays)
        {
            stepDays = Scale.MacroStepDays();
            _macroDebtDays += JulianDayUt - _lastMacroJd;
            _lastMacroJd = JulianDayUt;
            if (_macroDebtDays < stepDays) return 0;
            int steps = (int)Math.Floor(_macroDebtDays / stepDays);
            _macroDebtDays -= steps * stepDays;
            return steps;
        }

        public CalendarDate LocalDate => KoreaCivilTime.ToLocalDate(JulianDayUt);
        public string LocalTimeText => KoreaCivilTime.FormatLocalTime(JulianDayUt);
    }
}

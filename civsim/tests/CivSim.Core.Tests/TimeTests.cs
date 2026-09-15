using CivSim.Core.Time;
using Xunit;

namespace CivSim.Core.Tests
{
    public class JulianDayTests
    {
        [Fact]
        public void J2000Epoch() => Assert.Equal(2451545.0, JulianDay.FromGregorian(2000, 1, 1, 12, 0), 6);

        [Fact]
        public void GregorianReformBoundary()
        {
            // 1582-10-15 Gregorian == 1582-10-05 Julian == JD 2299160.5
            Assert.Equal(2299160.5, JulianDay.FromGregorian(1582, 10, 15), 6);
            Assert.Equal(2299160.5, JulianDay.FromJulianCalendar(1582, 10, 5), 6);
        }

        [Theory]
        [InlineData(100, 3, 21)]
        [InlineData(475, 9, 1)]
        [InlineData(1394, 10, 25)]
        [InlineData(1950, 6, 25)]
        [InlineData(2026, 12, 22)]
        public void RoundTripsGregorian(int y, int m, int d)
        {
            var back = JulianDay.ToGregorian(JulianDay.FromGregorian(y, m, d, 13, 37));
            Assert.Equal((y, m, d), (back.Year, back.Month, back.Day));
            Assert.Equal(13, back.Hour);
            Assert.Equal(37, back.Minute);
        }

        [Fact]
        public void DecimalYearMidYear()
            => Assert.InRange(JulianDay.DecimalYear(JulianDay.FromGregorian(2026, 7, 1)), 2026.5, 2026.6);
    }

    public class KoreaCivilTimeTests
    {
        [Theory]
        [InlineData(1394, 1, 1, 8.4652)]   // local mean time of 126.978°E
        [InlineData(1910, 1, 1, 8.5)]
        [InlineData(1930, 1, 1, 9.0)]
        [InlineData(1958, 1, 1, 8.5)]
        [InlineData(2026, 1, 1, 9.0)]
        public void OffsetHistory(int y, int m, int d, double expected)
            => Assert.Equal(expected, KoreaCivilTime.UtcOffsetHours(JulianDay.FromGregorian(y, m, d)), 3);

        [Fact]
        public void FormatsLocalWallClock()
        {
            double jd = JulianDay.FromGregorian(2026, 6, 21, 3, 34); // 03:34 UT
            Assert.Equal("12:34", KoreaCivilTime.FormatLocalTime(jd));
        }
    }

    public class SimClockTests
    {
        [Fact]
        public void PausedDoesNotAdvance()
        {
            var c = new SimClock(SimClock.DefaultStartJd, TimeScale.Paused);
            c.Advance(10);
            Assert.Equal(SimClock.DefaultStartJd, c.JulianDayUt);
        }

        [Fact]
        public void DecadePerSecondAdvancesTenYears()
        {
            var c = new SimClock(SimClock.DefaultStartJd, TimeScale.DecadePerSecond);
            c.Advance(1.0);
            Assert.Equal(SimClock.DefaultStartJd + 3652.5, c.JulianDayUt, 6);
        }

        [Fact]
        public void MacroStepsAccumulateAcrossFrames()
        {
            var c = new SimClock(SimClock.DefaultStartJd, TimeScale.DayPerSecond);
            int total = 0;
            for (int i = 0; i < 60; i++) { c.Advance(1.0 / 60.0); total += c.TakeMacroSteps(out _); }
            c.Advance(1.0); total += c.TakeMacroSteps(out double stepDays);
            Assert.Equal(1.0, stepDays);
            Assert.Equal(2, total);
        }

        [Fact]
        public void YearPerSecondUsesYearlyMacroSteps()
        {
            var c = new SimClock(SimClock.DefaultStartJd, TimeScale.YearPerSecond);
            c.Advance(2.0);
            Assert.Equal(2, c.TakeMacroSteps(out double stepDays));
            Assert.Equal(TimeScaleExtensions.DaysPerYear, stepDays);
        }

        [Fact]
        public void MicroLayerOnlyAtSlowSpeeds()
        {
            Assert.True(TimeScale.RealTime.ActiveLayers().HasFlag(SimLayers.Micro));
            Assert.True(TimeScale.HourPerSecond.ActiveLayers().HasFlag(SimLayers.Micro));
            Assert.False(TimeScale.DayPerSecond.ActiveLayers().HasFlag(SimLayers.Micro));
            Assert.True(TimeScale.DecadePerSecond.ActiveLayers().HasFlag(SimLayers.Macro));
        }

        [Fact]
        public void StartsInAd100()
        {
            var d = JulianDay.ToGregorian(SimClock.DefaultStartJd);
            Assert.Equal(100, d.Year);
        }
    }

    public class LocalFrameTests
    {
        [Fact]
        public void OriginIsZeroAndRoundTrips()
        {
            var f = Geo.LocalFrame.Seoul;
            f.ToLocal(37.5665, 126.9780, out double x, out double z);
            Assert.InRange(x, -1e-6, 1e-6);
            Assert.InRange(z, -1e-6, 1e-6);
            f.ToLocal(37.71, 127.19, out x, out z);
            Assert.InRange(x, 18500, 18900);  // ~18.7 km east
            Assert.InRange(z, 15800, 16100);  // ~16 km north
            f.ToLatLon(x, z, out double lat, out double lon);
            Assert.Equal(37.71, lat, 6);
            Assert.Equal(127.19, lon, 6);
        }
    }
}

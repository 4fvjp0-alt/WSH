using CivSim.Core.Astronomy;
using CivSim.Core.Time;
using Xunit;

namespace CivSim.Core.Tests
{
    /// <summary>Reference values: 한국천문연구원 일출·일몰 표 (서울, KST), tolerance ±2 min / ±0.3°.</summary>
    public class AstronomyTests
    {
        private const double Lat = 37.5665, Lon = 126.9780;

        [Theory]
        [InlineData(2026, 3, 20, "06:36", "18:44", 52.3)]  // 춘분
        [InlineData(2026, 6, 21, "05:11", "19:57", 75.9)]  // 하지
        [InlineData(2026, 9, 23, "06:20", "18:28", 52.4)]  // 추분
        [InlineData(2026, 12, 22, "07:43", "17:17", 29.0)] // 동지
        public void SeoulSunriseSunsetAndNoonAltitude(int y, int m, int d, string rise, string set, double noonAlt)
        {
            double jd0 = JulianDay.FromGregorian(y, m, d);
            double? riseJd = SunEvents.Sunrise(jd0, Lat, Lon);
            double? setJd = SunEvents.Sunset(jd0, Lat, Lon);
            Assert.NotNull(riseJd);
            Assert.NotNull(setJd);
            AssertWithinMinutes(rise, riseJd!.Value, 2);
            AssertWithinMinutes(set, setJd!.Value, 2);

            double noon = SunEvents.SolarNoon(jd0, Lon);
            var h = SolarPosition.Horizontal(noon, Lat, Lon);
            Assert.InRange(h.AltitudeDeg, noonAlt - 0.3, noonAlt + 0.3);
            Assert.InRange(h.AzimuthDeg, 179.0, 181.0);
        }

        [Fact]
        public void SunRisesInEastAndSetsInWestOnEquinox()
        {
            double jd0 = JulianDay.FromGregorian(2026, 3, 20);
            var rise = SolarPosition.Horizontal(SunEvents.Sunrise(jd0, Lat, Lon)!.Value, Lat, Lon);
            var set = SolarPosition.Horizontal(SunEvents.Sunset(jd0, Lat, Lon)!.Value, Lat, Lon);
            Assert.InRange(rise.AzimuthDeg, 88.0, 92.0);
            Assert.InRange(set.AzimuthDeg, 268.0, 272.0);
            Assert.InRange(rise.AltitudeDeg, -1.2, -0.5);
        }

        [Fact]
        public void DeclinationAtSolsticesMatchesObliquity()
        {
            double summer = SolarPosition.Compute(JulianDay.FromGregorian(2026, 6, 21, 8, 24)).DeclinationDeg;
            double winter = SolarPosition.Compute(JulianDay.FromGregorian(2026, 12, 21, 15, 50)).DeclinationDeg;
            Assert.InRange(summer, 23.40, 23.46);
            Assert.InRange(winter, -23.46, -23.40);
        }

        [Fact]
        public void EquationOfTimeExtremesIn2026()
        {
            // Early November: sun ~16 min fast. Mid February: ~14 min slow.
            Assert.InRange(SolarPosition.Compute(JulianDay.FromGregorian(2026, 11, 3)).EquationOfTimeMinutes, 15.5, 16.8);
            Assert.InRange(SolarPosition.Compute(JulianDay.FromGregorian(2026, 2, 11)).EquationOfTimeMinutes, -14.5, -13.8);
        }

        [Fact]
        public void Ad100SummerDayIsStillSane()
        {
            // Start year of the simulation. Local mean time; Delta T ≈ 2.7 h is applied inside Compute.
            double jd0 = JulianDay.FromGregorian(100, 6, 21);
            double? rise = SunEvents.Sunrise(jd0, Lat, Lon);
            double? set = SunEvents.Sunset(jd0, Lat, Lon);
            Assert.NotNull(rise);
            Assert.NotNull(set);
            double dayLengthHours = (set!.Value - rise!.Value) * 24.0;
            Assert.InRange(dayLengthHours, 14.5, 15.1);
            var noon = SolarPosition.Horizontal(SunEvents.SolarNoon(jd0, Lon), Lat, Lon);
            Assert.InRange(noon.AltitudeDeg, 75.5, 76.5);
        }

        [Theory]
        [InlineData(2000.0, 63.0, 65.0)]
        [InlineData(1394.8, 300.0, 360.0)]
        [InlineData(100.5, 9400.0, 9800.0)]
        public void DeltaTIsInExpectedRange(double year, double lo, double hi)
            => Assert.InRange(DeltaT.Seconds(year), lo, hi);

        [Fact]
        public void HorizontalToVectorPointsUpAtZenith()
        {
            new HorizontalCoords(90, 0).ToEastUpNorth(out double e, out double u, out double n);
            Assert.InRange(u, 0.9999, 1.0001);
            Assert.InRange(e, -1e-9, 1e-9);
            Assert.InRange(n, -1e-9, 1e-9);
            new HorizontalCoords(0, 90).ToEastUpNorth(out e, out u, out n);
            Assert.InRange(e, 0.9999, 1.0001);
        }

        private static void AssertWithinMinutes(string expectedHHmm, double jdUt, int toleranceMinutes)
        {
            string actual = KoreaCivilTime.FormatLocalTime(jdUt);
            int exp = int.Parse(expectedHHmm.Substring(0, 2)) * 60 + int.Parse(expectedHHmm.Substring(3, 2));
            int act = int.Parse(actual.Substring(0, 2)) * 60 + int.Parse(actual.Substring(3, 2));
            Assert.True(System.Math.Abs(exp - act) <= toleranceMinutes, $"expected {expectedHHmm} ±{toleranceMinutes}m, got {actual}");
        }
    }
}

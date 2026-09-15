using CivSim.Core.Astronomy;
using CivSim.Core.Time;
using UnityEngine;

namespace CivSim.Unity
{
    /// <summary>M0/M1 placeholder UI (IMGUI). Replace with UI Toolkit in M7. Keys: Space pause, [ ] slower/faster.</summary>
    public sealed class TimeControlPanel : MonoBehaviour
    {
        public SunLightController sun;

        private static readonly TimeScale[] Scales =
        {
            TimeScale.Paused, TimeScale.RealTime, TimeScale.MinutePerSecond, TimeScale.HourPerSecond,
            TimeScale.DayPerSecond, TimeScale.MonthPerSecond, TimeScale.YearPerSecond, TimeScale.DecadePerSecond
        };

        private TimeScale _beforePause = TimeScale.RealTime;

        private void Update()
        {
            var b = SimClockBehaviour.Instance;
            if (b == null) return;
            if (Input.GetKeyDown(KeyCode.Space))
            {
                if (b.Clock.Scale == TimeScale.Paused) b.SetScale(_beforePause);
                else { _beforePause = b.Clock.Scale; b.SetScale(TimeScale.Paused); }
            }
            if (Input.GetKeyDown(KeyCode.RightBracket)) b.StepFaster();
            if (Input.GetKeyDown(KeyCode.LeftBracket)) b.StepSlower();
        }

        private void OnGUI()
        {
            var b = SimClockBehaviour.Instance;
            if (b == null) return;
            var clock = b.Clock;

            GUILayout.BeginArea(new Rect(10, 10, 720, 120), GUI.skin.box);
            GUILayout.BeginHorizontal();
            foreach (var s in Scales)
            {
                bool on = clock.Scale == s;
                if (GUILayout.Toggle(on, s.Label(), GUI.skin.button, GUILayout.Height(28)) && !on) b.SetScale(s);
            }
            GUILayout.EndHorizontal();

            var d = clock.LocalDate;
            string calendar = clock.JulianDayUt < 2299160.5
                ? $"율리우스력 {JulianDay.ToJulianCalendar(KoreaCivilTime.ToLocalJd(clock.JulianDayUt))}"
                : $"양력 {d}";
            GUILayout.Label($"{calendar}   현지시각 {clock.LocalTimeText}   UTC{KoreaCivilTime.UtcOffsetHours(clock.JulianDayUt):+0.00;-0.00}");

            double jd0 = KoreaCivilTime.LocalMidnightUt(d.Year, d.Month, d.Day);
            double? rise = SunEvents.Sunrise(jd0, sun != null ? sun.latitudeDeg : 37.5665, sun != null ? sun.longitudeDeg : 126.978);
            double? set = SunEvents.Sunset(jd0, sun != null ? sun.latitudeDeg : 37.5665, sun != null ? sun.longitudeDeg : 126.978);
            string riseText = rise.HasValue ? KoreaCivilTime.FormatLocalTime(rise.Value) : "--:--";
            string setText = set.HasValue ? KoreaCivilTime.FormatLocalTime(set.Value) : "--:--";
            string sunText = sun != null ? $"태양 고도 {sun.Current.AltitudeDeg:0.0}°  방위 {sun.Current.AzimuthDeg:0}°" : "";
            GUILayout.Label($"일출 {riseText}  일몰 {setText}   {sunText}   활성 층: {clock.ActiveLayers}");
            GUILayout.EndArea();
        }
    }
}

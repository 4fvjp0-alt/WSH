using CivSim.Core.Time;
using UnityEngine;

namespace CivSim.Unity
{
    /// <summary>Owns the one <see cref="SimClock"/> and advances it every frame. Everything else reads from here.</summary>
    [DefaultExecutionOrder(-100)]
    public sealed class SimClockBehaviour : MonoBehaviour
    {
        public static SimClockBehaviour Instance { get; private set; }

        [Tooltip("Start date (proleptic Gregorian). Default AD 100-03-21 per plan.")]
        public int startYear = 100, startMonth = 3, startDay = 21, startHour = 6;

        [Tooltip("Frame budget for simulation work in ms; the clock auto-slows when exceeded.")]
        public float frameBudgetMs = 8f;

        public SimClock Clock { get; private set; }

        private void Awake()
        {
            Instance = this;
            Clock = new SimClock(JulianDay.FromGregorian(startYear, startMonth, startDay, startHour, 0), TimeScale.Paused);
        }

        private void Update()
        {
            // Clamp huge frame gaps (editor pause, alt-tab) so a single frame never skips a decade.
            Clock.Advance(Mathf.Min(Time.unscaledDeltaTime, 0.1f));
        }

        public void SetScale(TimeScale scale) => Clock.Scale = scale;

        public void StepFaster()
        {
            if (Clock.Scale < TimeScale.DecadePerSecond) Clock.Scale++;
        }

        public void StepSlower()
        {
            if (Clock.Scale > TimeScale.Paused) Clock.Scale--;
        }
    }
}

using CivSim.Core.Astronomy;
using UnityEngine;

namespace CivSim.Unity
{
    /// <summary>
    /// Drives the directional light from the real solar position for Seoul.
    /// Unity frame: +X east, +Y up, +Z north (the terrain is baked in that frame by tools/bake_dem.py).
    /// </summary>
    [RequireComponent(typeof(Light))]
    public sealed class SunLightController : MonoBehaviour
    {
        public double latitudeDeg = 37.5665;
        public double longitudeDeg = 126.9780;

        [Tooltip("Light intensity at zenith (lux for HDRP, unitless for URP).")]
        public float maxIntensity = 1.5f;
        public Gradient colorByAltitude;
        public AnimationCurve intensityByAltitude = AnimationCurve.EaseInOut(-6f, 0f, 30f, 1f);

        private Light _light;
        public HorizontalCoords Current { get; private set; }

        private void Awake() => _light = GetComponent<Light>();

        private void LateUpdate()
        {
            var clock = SimClockBehaviour.Instance?.Clock;
            if (clock == null) return;

            Current = SolarPosition.Horizontal(clock.JulianDayUt, latitudeDeg, longitudeDeg);
            Current.ToEastUpNorth(out double e, out double u, out double n);
            var toSun = new Vector3((float)e, (float)u, (float)n);
            transform.rotation = Quaternion.LookRotation(-toSun, Vector3.up); // light shines along -toSun

            float alt = (float)Current.AltitudeDeg;
            _light.intensity = maxIntensity * Mathf.Clamp01(intensityByAltitude.Evaluate(alt));
            if (colorByAltitude != null)
                _light.color = colorByAltitude.Evaluate(Mathf.InverseLerp(-6f, 60f, alt));
            _light.enabled = alt > -6f; // civil twilight cut-off; ambient/sky handles the rest
        }
    }
}

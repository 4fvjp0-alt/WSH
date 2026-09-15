using UnityEngine;

namespace CivSim.Unity
{
    /// <summary>Orbit/pan/zoom camera from satellite altitude down to street level. WASD pan, wheel zoom, RMB orbit, MMB drag pan.</summary>
    public sealed class GodViewCamera : MonoBehaviour
    {
        public Vector3 target = Vector3.zero;
        public float distance = 20000f;
        public float minDistance = 20f, maxDistance = 60000f;
        public float pitchDeg = 60f, yawDeg = 0f;
        public float panSpeed = 1.0f;     // fraction of distance per second
        public float zoomSpeed = 0.15f;   // fraction of distance per wheel notch
        public float orbitSpeed = 0.25f;  // degrees per pixel
        public Terrain terrain;

        private Vector3 _lastMouse;

        private void LateUpdate()
        {
            float dt = Time.unscaledDeltaTime;
            var flatForward = Quaternion.Euler(0, yawDeg, 0) * Vector3.forward;
            var flatRight = Quaternion.Euler(0, yawDeg, 0) * Vector3.right;
            var move = Vector3.zero;
            if (Input.GetKey(KeyCode.W)) move += flatForward;
            if (Input.GetKey(KeyCode.S)) move -= flatForward;
            if (Input.GetKey(KeyCode.D)) move += flatRight;
            if (Input.GetKey(KeyCode.A)) move -= flatRight;
            target += move * (panSpeed * distance * dt);

            float wheel = Input.GetAxis("Mouse ScrollWheel");
            if (Mathf.Abs(wheel) > 0f) distance = Mathf.Clamp(distance * (1f - wheel * zoomSpeed * 10f), minDistance, maxDistance);

            if (Input.GetMouseButtonDown(1) || Input.GetMouseButtonDown(2)) _lastMouse = Input.mousePosition;
            if (Input.GetMouseButton(1))
            {
                var delta = Input.mousePosition - _lastMouse;
                yawDeg += delta.x * orbitSpeed;
                pitchDeg = Mathf.Clamp(pitchDeg - delta.y * orbitSpeed, 10f, 89f);
                _lastMouse = Input.mousePosition;
            }
            if (Input.GetMouseButton(2))
            {
                var delta = Input.mousePosition - _lastMouse;
                target -= (flatRight * delta.x + flatForward * delta.y) * (distance * 0.0015f);
                _lastMouse = Input.mousePosition;
            }

            if (terrain != null)
            {
                float ground = terrain.SampleHeight(target) + terrain.transform.position.y;
                target.y = ground;
            }

            var rot = Quaternion.Euler(pitchDeg, yawDeg, 0);
            transform.position = target - rot * Vector3.forward * distance;
            transform.rotation = rot;

            // Keep the near/far planes sane across four orders of magnitude of distance.
            var cam = GetComponent<Camera>();
            if (cam != null)
            {
                cam.nearClipPlane = Mathf.Max(0.3f, distance * 0.002f);
                cam.farClipPlane = Mathf.Max(5000f, distance * 6f);
            }
        }
    }
}

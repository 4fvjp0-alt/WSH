using System.IO;
using UnityEngine;

namespace CivSim.Unity
{
    /// <summary>
    /// Builds a Unity Terrain at runtime from the .r16 + .json pair written by tools/bake_dem.py,
    /// placed in the Seoul local frame (origin = City Hall, +X east, +Z north).
    /// Put the files in Assets/StreamingAssets/terrain/ and set <see cref="fileStem"/> to their stem.
    /// </summary>
    public sealed class TerrainLoader : MonoBehaviour
    {
        public string fileStem = "seoul";
        [Tooltip("Vertical exaggeration; 1 = true scale. Stylized look may want 1.3–1.5.")]
        public float verticalScale = 1f;
        public Material terrainMaterial;

        public Terrain Terrain { get; private set; }

        [System.Serializable]
        private sealed class Meta
        {
            public double resolutionM; public int width, height;
            public double localMinX, localMinZ, extentX, extentZ;
            public double heightMinM, heightMaxM, heightScaleM;
        }

        private void Start()
        {
            string dir = Path.Combine(Application.streamingAssetsPath, "terrain");
            var meta = JsonUtility.FromJson<Meta>(File.ReadAllText(Path.Combine(dir, fileStem + ".json")));
            byte[] raw = File.ReadAllBytes(Path.Combine(dir, fileStem + ".r16"));

            // Unity heightmaps must be (2^n)+1 square; resample the baked grid onto the next size up.
            int res = Mathf.NextPowerOfTwo(Mathf.Max(meta.width, meta.height) - 1) + 1;
            var heights = new float[res, res];
            for (int r = 0; r < res; r++)
            {
                float srcR = (float)r / (res - 1) * (meta.height - 1);
                int r0 = Mathf.Min((int)srcR, meta.height - 2); float fr = srcR - r0;
                for (int c = 0; c < res; c++)
                {
                    float srcC = (float)c / (res - 1) * (meta.width - 1);
                    int c0 = Mathf.Min((int)srcC, meta.width - 2); float fc = srcC - c0;
                    float v = Sample(raw, meta.width, r0, c0) * (1 - fr) * (1 - fc)
                            + Sample(raw, meta.width, r0 + 1, c0) * fr * (1 - fc)
                            + Sample(raw, meta.width, r0, c0 + 1) * (1 - fr) * fc
                            + Sample(raw, meta.width, r0 + 1, c0 + 1) * fr * fc;
                    heights[r, c] = v; // TerrainData is [z, x]; our row 0 = south, so no flip
                }
            }

            var data = new TerrainData { heightmapResolution = res };
            data.size = new Vector3((float)meta.extentX, (float)meta.heightScaleM * verticalScale, (float)meta.extentZ);
            data.SetHeights(0, 0, heights);

            var go = Terrain.CreateTerrainGameObject(data);
            go.name = "SeoulTerrain";
            go.transform.position = new Vector3((float)meta.localMinX, (float)meta.heightMinM * verticalScale, (float)meta.localMinZ);
            Terrain = go.GetComponent<Terrain>();
            if (terrainMaterial != null) Terrain.materialTemplate = terrainMaterial;

            var cam = FindFirstObjectByType<GodViewCamera>();
            if (cam != null) cam.terrain = Terrain;
        }

        private static float Sample(byte[] raw, int width, int r, int c)
        {
            int i = (r * width + c) * 2;
            return (raw[i] | (raw[i + 1] << 8)) / 65535f;
        }
    }
}

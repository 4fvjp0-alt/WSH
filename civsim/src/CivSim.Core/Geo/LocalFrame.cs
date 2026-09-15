using System;

namespace CivSim.Core.Geo
{
    /// <summary>
    /// Flat metric frame centred on Seoul City Hall: X east, Z north, metres.
    /// Equirectangular approximation; within the 38 × 32 km play area the error is a few metres, far below cell size.
    /// </summary>
    public sealed class LocalFrame
    {
        public const double EarthRadiusM = 6371008.8;

        public static readonly LocalFrame Seoul = new LocalFrame(37.5665, 126.9780);

        /// <summary>Play-area bounding box from the plan (§1.3).</summary>
        public const double SeoulMinLon = 126.76, SeoulMaxLon = 127.19, SeoulMinLat = 37.42, SeoulMaxLat = 37.71;

        public double OriginLatDeg { get; }
        public double OriginLonDeg { get; }
        private readonly double _cosLat;

        public LocalFrame(double originLatDeg, double originLonDeg)
        {
            OriginLatDeg = originLatDeg;
            OriginLonDeg = originLonDeg;
            _cosLat = Math.Cos(originLatDeg * Math.PI / 180.0);
        }

        public void ToLocal(double latDeg, double lonDeg, out double xEast, out double zNorth)
        {
            double k = EarthRadiusM * Math.PI / 180.0;
            xEast = (lonDeg - OriginLonDeg) * k * _cosLat;
            zNorth = (latDeg - OriginLatDeg) * k;
        }

        public void ToLatLon(double xEast, double zNorth, out double latDeg, out double lonDeg)
        {
            double k = EarthRadiusM * Math.PI / 180.0;
            lonDeg = OriginLonDeg + xEast / (k * _cosLat);
            latDeg = OriginLatDeg + zNorth / k;
        }
    }
}

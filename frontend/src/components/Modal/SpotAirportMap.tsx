import { useEffect, useMemo } from 'react';
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Tooltip,
  useMap,
} from 'react-leaflet';
import { LatLngBounds } from 'leaflet';
import type { SpotWithStats } from '../../api/types';
import 'leaflet/dist/leaflet.css';

interface Props {
  spot: SpotWithStats;
}

function FitToPoints({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length === 0) return;
    if (points.length === 1) {
      map.setView(points[0], 9);
      return;
    }
    const bounds = new LatLngBounds(points);
    map.fitBounds(bounds, { padding: [24, 24] });
  }, [map, points]);
  return null;
}

export function SpotAirportMap({ spot }: Props) {
  const airportsWithCoords = useMemo(
    () =>
      spot.nearest_airports.filter(
        (a) => a.latitude !== null && a.longitude !== null,
      ),
    [spot.nearest_airports],
  );

  const points: [number, number][] = useMemo(
    () => [
      [spot.latitude, spot.longitude],
      ...airportsWithCoords.map(
        (a) => [a.latitude as number, a.longitude as number] as [number, number],
      ),
    ],
    [spot.latitude, spot.longitude, airportsWithCoords],
  );

  return (
    <div className="relative h-36 sm:h-44 w-full rounded-lg overflow-hidden border border-gray-200">
      <MapContainer
        center={[spot.latitude, spot.longitude]}
        zoom={9}
        scrollWheelZoom={false}
        zoomControl={false}
        className="h-full w-full"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <CircleMarker
          center={[spot.latitude, spot.longitude]}
          radius={8}
          pathOptions={{
            color: '#EA580C',
            fillColor: '#F97316',
            fillOpacity: 0.9,
            weight: 2,
          }}
        >
          <Tooltip direction="top" offset={[0, -8]}>
            <div className="text-xs font-semibold">{spot.name}</div>
          </Tooltip>
        </CircleMarker>

        {airportsWithCoords.map((a) => (
          <CircleMarker
            key={a.iata}
            center={[a.latitude as number, a.longitude as number]}
            radius={6}
            pathOptions={{
              color: '#0E7490',
              fillColor: '#0891B2',
              fillOpacity: 0.9,
              weight: 2,
            }}
          >
            <Tooltip direction="top" offset={[0, -6]}>
              <div className="text-xs">
                <span className="font-semibold">{a.iata}</span> — {a.name}
                <div className="text-gray-500">
                  {a.distance_km.toFixed(0)} km · {Math.round(a.duration_minutes)} min
                </div>
              </div>
            </Tooltip>
          </CircleMarker>
        ))}

        <FitToPoints points={points} />
      </MapContainer>
    </div>
  );
}

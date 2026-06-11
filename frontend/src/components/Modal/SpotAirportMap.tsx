import { useEffect, useMemo } from 'react';
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Marker,
  Tooltip,
  useMap,
} from 'react-leaflet';
import { LatLngBounds, divIcon } from 'leaflet';
import type { NearestAirport, Spot } from '../../api/types';
import { formatDuration } from '../../utils/formatDuration';
import 'leaflet/dist/leaflet.css';

const PLANE_SVG =
  '<svg viewBox="0 0 24 24" fill="white" width="15" height="15" aria-hidden="true">' +
  '<path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/>' +
  '</svg>';

// Badge anchored at its center on the airport position, IATA label below
function airportIcon(iata: string) {
  return divIcon({
    className: '',
    iconSize: [0, 0],
    html:
      '<div class="relative">' +
      '<div class="absolute -translate-x-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-cyan-600 border-2 border-white shadow-md flex items-center justify-center">' +
      PLANE_SVG +
      '</div>' +
      `<div class="absolute left-0 top-[15px] -translate-x-1/2 px-1 rounded bg-white/90 text-[10px] font-bold text-cyan-700 shadow leading-tight">${iata}</div>` +
      '</div>',
  });
}

interface Props {
  spot: Spot;
  airports: NearestAirport[];
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

export function SpotAirportMap({ spot, airports }: Props) {
  const airportsWithCoords = useMemo(
    () => airports.filter((a) => a.latitude !== null && a.longitude !== null),
    [airports],
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
    <div className="relative h-full w-full rounded-lg overflow-hidden border border-gray-200">
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
          <Marker
            key={a.iata}
            position={[a.latitude as number, a.longitude as number]}
            icon={airportIcon(a.iata)}
          >
            <Tooltip direction="top" offset={[0, -16]}>
              <div className="text-xs">
                <span className="font-semibold">{a.iata}</span> — {a.name}
                <div className="text-gray-500">
                  {a.distance_km.toFixed(0)} km · {formatDuration(a.duration_minutes)}
                </div>
              </div>
            </Tooltip>
          </Marker>
        ))}

        <FitToPoints points={points} />
      </MapContainer>
    </div>
  );
}

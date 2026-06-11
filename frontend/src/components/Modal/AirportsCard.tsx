import { useCallback } from 'react';
import type { NearestAirport, Spot } from '../../api/types';
import { formatDuration } from '../../utils/formatDuration';
import { SpotAirportMap } from './SpotAirportMap';

interface Props {
  spot: Spot;
  airports: NearestAirport[];
}

export function AirportsCard({ spot, airports }: Props) {
  // Keep map pan/zoom gestures from triggering carousel swipe navigation
  const stopTouchPropagation = useCallback((e: React.TouchEvent) => {
    e.stopPropagation();
  }, []);

  return (
    <div className="h-full flex flex-col gap-2 min-h-0">
      <div
        className="flex-1 min-h-0"
        onTouchStart={stopTouchPropagation}
        onTouchEnd={stopTouchPropagation}
        onTouchCancel={stopTouchPropagation}
      >
        <SpotAirportMap spot={spot} airports={airports} />
      </div>
      <div className="flex-shrink-0 max-h-[40%] overflow-y-auto divide-y divide-gray-100 border border-gray-100 rounded-lg">
        {airports.map((airport) => (
          <div key={airport.iata} className="flex items-center gap-3 px-3 py-2">
            <span className="flex-shrink-0 text-sm font-bold text-kite w-12">
              {airport.iata}
            </span>
            <span className="flex-1 min-w-0 text-sm text-gray-700 truncate">
              {airport.name}
            </span>
            <span className="flex-shrink-0 text-sm text-gray-500 whitespace-nowrap">
              {airport.distance_km.toFixed(0)} km · ~{formatDuration(airport.duration_minutes)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

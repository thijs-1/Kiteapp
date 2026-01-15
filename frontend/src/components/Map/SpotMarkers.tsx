import { CircleMarker, Popup } from 'react-leaflet';
import { useFilteredSpots } from '../../hooks/useSpots';
import { useSpotStore } from '../../store/spotStore';
import type { SpotWithStats } from '../../api/types';

export function SpotMarkers() {
  const { spots, isLoading } = useFilteredSpots();
  const selectSpot = useSpotStore((state) => state.selectSpot);

  if (isLoading) {
    return null;
  }

  return (
    <>
      {spots.map((spot) => (
        <SpotMarker key={spot.spot_id} spot={spot} onSelect={selectSpot} />
      ))}
    </>
  );
}

interface SpotMarkerProps {
  spot: SpotWithStats;
  onSelect: (spot: SpotWithStats) => void;
}

function SpotMarker({ spot, onSelect }: SpotMarkerProps) {
  return (
    <CircleMarker
      center={[spot.latitude, spot.longitude]}
      radius={6}
      pathOptions={{
        color: '#FF1493',
        fillColor: '#FF69B4',
        fillOpacity: 0.8,
        weight: 1,
      }}
      eventHandlers={{
        click: () => onSelect(spot),
      }}
    >
      <Popup>
        <div className="text-sm">
          <div className="font-bold">{spot.name}</div>
          <div className="text-gray-600">{spot.country}</div>
          <div className="text-kite-pink font-semibold">
            {spot.kiteable_percentage.toFixed(0)}% kiteable
          </div>
        </div>
      </Popup>
    </CircleMarker>
  );
}

import { CircleMarker, Tooltip, Popup, useMap } from 'react-leaflet';
import { useFilteredSpots } from '../../hooks/useSpots';
import { useSpotStore } from '../../store/spotStore';
import { useIsMobile } from '../../hooks/useIsMobile';
import type { SpotWithStats } from '../../api/types';

export function SpotMarkers() {
  const { spots, isLoading } = useFilteredSpots();
  const selectSpot = useSpotStore((state) => state.selectSpot);
  const isMobile = useIsMobile();

  if (isLoading) {
    return null;
  }

  return (
    <>
      {spots.map((spot) => (
        <SpotMarker
          key={spot.spot_id}
          spot={spot}
          onSelect={selectSpot}
          isMobile={isMobile}
        />
      ))}
    </>
  );
}

interface SpotMarkerProps {
  spot: SpotWithStats;
  onSelect: (spot: SpotWithStats) => void;
  isMobile: boolean;
}

function SpotMarker({ spot, onSelect, isMobile }: SpotMarkerProps) {
  const map = useMap();

  const handleMarkerClick = () => {
    if (!isMobile) {
      onSelect(spot);
    }
    // On mobile, the Popup child will open automatically on click
  };

  const handlePopupClick = () => {
    map.closePopup();
    onSelect(spot);
  };

  const markerContent = (
    <div className="text-sm">
      <div className="font-bold">{spot.name}</div>
      <div className="text-gray-600">{spot.country}</div>
      <div className="text-kite-pink font-semibold">
        {spot.kiteable_percentage.toFixed(0)}% kiteable
      </div>
    </div>
  );

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
        click: handleMarkerClick,
      }}
    >
      {isMobile ? (
        <Popup className="mobile-spot-popup">
          <div
            onClick={handlePopupClick}
            className="cursor-pointer p-1"
          >
            {markerContent}
            <div className="text-xs text-gray-500 mt-2 text-center border-t pt-1">
              Tap to view charts
            </div>
          </div>
        </Popup>
      ) : (
        <Tooltip>
          {markerContent}
        </Tooltip>
      )}
    </CircleMarker>
  );
}

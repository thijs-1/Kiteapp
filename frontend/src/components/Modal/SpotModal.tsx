import { useEffect, useCallback, useState } from 'react';
import { useSpotStore } from '../../store/spotStore';
import { useIsMobile } from '../../hooks/useIsMobile';
import { Carousel } from './Carousel';
import { SpotAirportMap } from './SpotAirportMap';

export function SpotModal() {
  const { selectedSpot, selectSpot } = useSpotStore();
  const isMobile = useIsMobile();
  const [copied, setCopied] = useState(false);

  const handleClose = useCallback(() => selectSpot(null), [selectSpot]);

  const handleShare = useCallback(async () => {
    if (!selectedSpot) return;
    const url = new URL(window.location.href);
    url.searchParams.set('spot', selectedSpot.spot_id);
    try {
      await navigator.clipboard.writeText(url.toString());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: ignore if clipboard not available
    }
  }, [selectedSpot]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (selectedSpot) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [selectedSpot]);

  // Close on Escape key
  useEffect(() => {
    if (!selectedSpot) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [selectedSpot, handleClose]);

  if (!selectedSpot) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1001] p-0 sm:p-4"
      onClick={handleClose}
    >
      <div
        className={`bg-white flex flex-col shadow-2xl ${
          isMobile
            ? 'w-full h-[100dvh] rounded-none'
            : 'rounded-xl w-full max-w-4xl h-[80vh]'
        }`}
        style={isMobile ? {
          paddingTop: 'env(safe-area-inset-top)',
          paddingBottom: 'env(safe-area-inset-bottom)',
        } : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex justify-between items-center p-3 sm:p-4 border-b">
          <div className="min-w-0 flex-1 mr-2">
            <h2 className="text-lg sm:text-xl font-bold text-gray-800 truncate">
              {selectedSpot.name}
            </h2>
            <p className="text-xs sm:text-sm text-gray-500">
              {selectedSpot.country}
              {selectedSpot.kiteable_percentage > 0 && (
                <> • {selectedSpot.kiteable_percentage.toFixed(0)}% kiteable</>
              )}
              <span className="hidden sm:inline">
                {' '}• {selectedSpot.latitude.toFixed(2)}, {selectedSpot.longitude.toFixed(2)}
              </span>
            </p>
          </div>
          <div className="flex items-center flex-shrink-0">
            <button
              onClick={handleShare}
              className="p-3 hover:bg-gray-100 active:bg-gray-200 rounded-lg transition-colors"
              aria-label="Share spot"
            >
              {copied ? (
                <span className="text-xs font-medium text-kite whitespace-nowrap">Copied!</span>
              ) : (
                <svg
                  className="w-5 h-5 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
                  />
                </svg>
              )}
            </button>
            <button
              onClick={() => selectSpot(null)}
              className="p-3 hover:bg-gray-100 active:bg-gray-200 rounded-lg transition-colors"
              aria-label="Close"
            >
              <svg
                className="w-6 h-6 text-gray-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>

        {/* Airports section */}
        {selectedSpot.nearest_airports.length > 0 && (
          <div className="px-3 sm:px-4 pt-3 pb-2 border-b border-gray-100 space-y-2">
            <SpotAirportMap spot={selectedSpot} />
            <div className="flex gap-2 overflow-x-auto">
              {selectedSpot.nearest_airports.map((airport) => (
                <div
                  key={airport.iata}
                  className="flex-shrink-0 min-w-[140px] px-2 py-1 bg-gray-50 rounded-md border border-gray-100"
                >
                  <div className="text-xs font-semibold text-gray-800">
                    <span className="text-kite">{airport.iata}</span>
                    <span className="ml-1 text-gray-700 font-normal truncate inline-block max-w-[80px] align-bottom">
                      {airport.name}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500">
                    {airport.distance_km.toFixed(0)} km · ~{Math.round(airport.duration_minutes)} min
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Chart carousel */}
        <div className="flex-1 p-3 sm:p-4 overflow-hidden min-h-0">
          <Carousel spotId={selectedSpot.spot_id} />
        </div>
      </div>
    </div>
  );
}

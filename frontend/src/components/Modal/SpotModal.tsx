import { useEffect } from 'react';
import { useSpotStore } from '../../store/spotStore';
import { useIsMobile } from '../../hooks/useIsMobile';
import { Carousel } from './Carousel';

export function SpotModal() {
  const { selectedSpot, selectSpot } = useSpotStore();
  const isMobile = useIsMobile();

  // Lock body scroll when modal is open
  useEffect(() => {
    if (selectedSpot) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [selectedSpot]);

  if (!selectedSpot) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1001] p-0 sm:p-4">
      <div
        className={`bg-white flex flex-col shadow-2xl ${
          isMobile
            ? 'w-full h-full rounded-none'
            : 'rounded-xl w-full max-w-4xl h-[80vh]'
        }`}
      >
        {/* Header */}
        <div className="flex justify-between items-center p-3 sm:p-4 border-b">
          <div className="min-w-0 flex-1 mr-2">
            <h2 className="text-lg sm:text-xl font-bold text-gray-800 truncate">
              {selectedSpot.name}
            </h2>
            <p className="text-xs sm:text-sm text-gray-500">
              {selectedSpot.country} • {selectedSpot.kiteable_percentage.toFixed(0)}%
              kiteable
            </p>
          </div>
          <button
            onClick={() => selectSpot(null)}
            className="p-3 hover:bg-gray-100 active:bg-gray-200 rounded-lg transition-colors flex-shrink-0"
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

        {/* Chart carousel */}
        <div className="flex-1 p-3 sm:p-4 overflow-hidden min-h-0">
          <Carousel spotId={selectedSpot.spot_id} />
        </div>
      </div>
    </div>
  );
}

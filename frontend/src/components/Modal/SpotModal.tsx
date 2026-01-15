import { useSpotStore } from '../../store/spotStore';
import { Carousel } from './Carousel';

export function SpotModal() {
  const { selectedSpot, selectSpot } = useSpotStore();

  if (!selectedSpot) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[1001] p-4">
      <div className="bg-white rounded-xl w-full max-w-4xl h-[80vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b">
          <div>
            <h2 className="text-xl font-bold text-gray-800">{selectedSpot.name}</h2>
            <p className="text-sm text-gray-500">
              {selectedSpot.country} • {selectedSpot.kiteable_percentage.toFixed(0)}%
              kiteable
            </p>
          </div>
          <button
            onClick={() => selectSpot(null)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
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
        <div className="flex-1 p-4 overflow-hidden">
          <Carousel spotId={selectedSpot.spot_id} />
        </div>
      </div>
    </div>
  );
}

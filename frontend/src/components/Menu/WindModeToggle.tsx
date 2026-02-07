import { useState } from 'react';
import { useFilterStore } from '../../store/filterStore';
import type { WindMode } from '../../store/filterStore';

export function WindModeToggle() {
  const { windMode, setWindMode } = useFilterStore();
  const [showTooltip, setShowTooltip] = useState(false);

  const handleToggle = (mode: WindMode) => {
    if (mode !== windMode) {
      setWindMode(mode);
    }
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5">
        <label className="block text-sm font-medium text-gray-700">
          Wind metric
        </label>
        <div
          className="relative"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          <button
            type="button"
            className="w-4 h-4 rounded-full bg-gray-300 text-[10px] font-bold text-gray-600 leading-none hover:bg-gray-400 transition-colors flex items-center justify-center"
            aria-label="Wind metric info"
          >
            ?
          </button>
          {showTooltip && (
            <div className="absolute left-6 top-1/2 -translate-y-1/2 z-50 w-56 p-2.5 bg-gray-800 text-white text-xs rounded-lg shadow-lg leading-relaxed">
              <p className="font-semibold mb-1">Kiteable hours</p>
              <p className="mb-2">
                Percentage of all hours where wind speed falls within your
                selected range. Shows overall wind frequency.
              </p>
              <p className="font-semibold mb-1">Sustained wind</p>
              <p>
                Percentage of days with at least 2 consecutive hours of wind
                above the threshold. Better for finding reliable session
                windows.
              </p>
            </div>
          )}
        </div>
      </div>
      <div className="flex rounded-lg overflow-hidden border border-gray-200">
        <button
          type="button"
          onClick={() => handleToggle('hourly')}
          className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
            windMode === 'hourly'
              ? 'bg-kite-pink text-white'
              : 'bg-white text-gray-600 hover:bg-gray-50'
          }`}
        >
          Kiteable hours
        </button>
        <button
          type="button"
          onClick={() => handleToggle('sustained')}
          className={`flex-1 py-1.5 text-xs font-medium transition-colors ${
            windMode === 'sustained'
              ? 'bg-kite-pink text-white'
              : 'bg-white text-gray-600 hover:bg-gray-50'
          }`}
        >
          Sustained wind
        </button>
      </div>
    </div>
  );
}

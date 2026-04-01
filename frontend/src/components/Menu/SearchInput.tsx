import { useState, useRef, useCallback } from 'react';
import { useFilterStore } from '../../store/filterStore';
import { useSpotStore } from '../../store/spotStore';

const MAX_SUGGESTIONS = 5;

export function SearchInput() {
  const searchName = useFilterStore((s) => s.searchName);
  const setSearchName = useFilterStore((s) => s.setSearchName);
  const spots = useSpotStore((s) => s.spots);
  const selectSpot = useSpotStore((s) => s.selectSpot);
  const [showDropdown, setShowDropdown] = useState(false);
  const blurTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleFocus = useCallback(() => {
    setShowDropdown(true);
  }, []);

  const handleBlur = useCallback(() => {
    // Delay to allow click on suggestion to register
    blurTimeoutRef.current = setTimeout(() => setShowDropdown(false), 150);
  }, []);

  const handleSelect = useCallback(
    (spot: (typeof spots)[0]) => {
      if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
      setShowDropdown(false);
      setSearchName('');
      selectSpot(spot);
    },
    [setSearchName, selectSpot],
  );

  const suggestions = searchName.length >= 1 ? spots.slice(0, MAX_SUGGESTIONS) : [];
  const hasMore = searchName.length >= 1 && spots.length > MAX_SUGGESTIONS;

  return (
    <div className="relative">
      {/* Magnifying glass icon */}
      <svg
        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>

      <input
        type="text"
        value={searchName}
        onChange={(e) => setSearchName(e.target.value)}
        onFocus={handleFocus}
        onBlur={handleBlur}
        placeholder="Search spots by name..."
        className="w-full pl-10 pr-9 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-kite/50 focus:border-kite"
      />

      {/* Clear button */}
      {searchName && (
        <button
          onClick={() => setSearchName('')}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-gray-100 rounded-full transition-colors"
          aria-label="Clear search"
        >
          <svg
            className="w-4 h-4 text-gray-400"
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
      )}

      {/* Autocomplete dropdown */}
      {showDropdown && suggestions.length > 0 && (
        <ul className="absolute left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 overflow-hidden">
          {suggestions.map((spot) => (
            <li key={spot.spot_id}>
              <button
                className="w-full text-left px-3 py-2.5 text-sm hover:bg-gray-50 active:bg-gray-100 transition-colors flex items-center justify-between gap-2"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => handleSelect(spot)}
              >
                <span className="truncate font-medium text-gray-800">
                  {spot.name}
                </span>
                <span className="text-xs text-gray-400 flex-shrink-0">
                  {spot.country && <>{spot.country} · </>}
                  {spot.kiteable_percentage.toFixed(0)}%
                </span>
              </button>
            </li>
          ))}
          {hasMore && (
            <li className="px-3 py-2 text-xs text-gray-400 text-center border-t border-gray-100">
              {spots.length - MAX_SUGGESTIONS} more results
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

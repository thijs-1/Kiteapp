import { useState, useCallback, useEffect } from 'react';
import { FilterPanel } from './FilterPanel';
import { MenuCallout, markMenuAsSeen } from './MenuCallout';
import { useFilterStore, defaultFilters } from '../../store/filterStore';
import { useSpotStore } from '../../store/spotStore';

export function HamburgerMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const [showCallout, setShowCallout] = useState(true);

  const filters = useFilterStore();
  const resetFilters = useFilterStore((s) => s.resetFilters);
  const { spots, isLoading } = useSpotStore();

  // Check if any filters differ from defaults
  const filtersChanged =
    filters.windMin !== defaultFilters.windMin ||
    filters.windMax !== defaultFilters.windMax ||
    filters.startDate !== defaultFilters.startDate ||
    filters.endDate !== defaultFilters.endDate ||
    filters.minPercentage !== defaultFilters.minPercentage;

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) setIsOpen(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const handleMenuClick = useCallback(() => {
    setIsOpen((prev) => !prev);
    if (showCallout) {
      markMenuAsSeen();
      setShowCallout(false);
    }
  }, [showCallout]);

  const handleCalloutDismiss = useCallback(() => {
    markMenuAsSeen();
    setShowCallout(false);
  }, []);

  return (
    <>
      {/* Callout for first-time users */}
      {showCallout && <MenuCallout onDismiss={handleCalloutDismiss} />}

      {/* Hamburger button */}
      <button
        className="fixed top-4 left-4 z-[1000] p-3 bg-white rounded-lg shadow-lg hover:bg-gray-100 transition-colors"
        onClick={handleMenuClick}
        aria-label="Toggle menu"
      >
        <svg
          className="w-6 h-6"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          {isOpen ? (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          ) : (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h16"
            />
          )}
        </svg>
        {/* Active filter indicator dot */}
        {filtersChanged && !isOpen && (
          <span className="absolute -top-1 -right-1 w-3 h-3 bg-kite rounded-full border-2 border-white" />
        )}
      </button>

      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-[999]"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Side panel */}
      <div
        className={`fixed top-0 left-0 h-full w-80 max-w-[calc(100vw-3rem)] bg-white shadow-xl z-[1000] transform transition-transform duration-300 flex flex-col ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="p-4 pt-16 pb-3 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-gray-800">Filters</h2>
            <div className="text-sm text-gray-500">
              {isLoading ? (
                'Loading...'
              ) : (
                <>
                  <span className="font-semibold text-kite">{spots.length}</span> spots
                </>
              )}
            </div>
          </div>
        </div>

        {/* Scrollable filter content */}
        <div className="flex-1 overflow-y-auto p-4">
          <FilterPanel />
        </div>

        {/* Sticky footer - reset button, only when filters are changed */}
        {filtersChanged && (
          <div className="p-4 pt-3 border-t border-gray-100">
            <button
              onClick={resetFilters}
              className="w-full py-2 px-4 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-600 text-sm transition-colors"
            >
              Reset Filters
            </button>
          </div>
        )}
      </div>
    </>
  );
}

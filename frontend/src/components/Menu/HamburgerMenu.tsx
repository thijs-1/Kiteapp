import { useState, useCallback } from 'react';
import { FilterPanel } from './FilterPanel';
import { MenuCallout, markMenuAsSeen } from './MenuCallout';

export function HamburgerMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const [showCallout, setShowCallout] = useState(true);

  const handleMenuClick = useCallback(() => {
    setIsOpen((prev) => !prev);
    // Mark menu as seen and hide callout when user clicks
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
        className={`fixed top-0 left-0 h-full w-80 bg-white shadow-xl z-[1000] transform transition-transform duration-300 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="p-4 pt-16">
          <h2 className="text-xl font-bold mb-4 text-gray-800">Filters</h2>
          <FilterPanel />
        </div>
      </div>
    </>
  );
}

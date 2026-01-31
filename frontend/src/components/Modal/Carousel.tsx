import { useState, useRef, useCallback, useEffect } from 'react';
import { KiteableLineChart } from './Charts/KiteableLineChart';
import { WindHistogram } from './Charts/WindHistogram';
import { WindRose } from './Charts/WindRose';

interface CarouselProps {
  spotId: string;
}

const CHART_TITLES = [
  'Kiteable Wind %',
  'Wind Strength Distribution',
  'Wind Rose',
];

// Minimum swipe distance to trigger navigation (in pixels)
const SWIPE_THRESHOLD = 50;

export function Carousel({ spotId }: CarouselProps) {
  // Start with line chart (index 0)
  const [activeIndex, setActiveIndex] = useState(0);
  const touchStartX = useRef<number | null>(null);
  const touchStartY = useRef<number | null>(null);

  // Track which button is pressed for mobile-friendly feedback
  const [pressedButton, setPressedButton] = useState<'prev' | 'next' | null>(null);
  const pressTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clear pressed state after animation completes
  useEffect(() => {
    return () => {
      if (pressTimeoutRef.current) {
        clearTimeout(pressTimeoutRef.current);
      }
    };
  }, []);

  const handleButtonPress = useCallback((button: 'prev' | 'next') => {
    // Clear any existing timeout
    if (pressTimeoutRef.current) {
      clearTimeout(pressTimeoutRef.current);
    }
    setPressedButton(button);
    // Clear the pressed state after 150ms (matches transition duration)
    pressTimeoutRef.current = setTimeout(() => {
      setPressedButton(null);
    }, 150);
  }, []);

  const goToPrev = useCallback(() => {
    handleButtonPress('prev');
    setActiveIndex((prev) => (prev - 1 + 3) % 3);
  }, [handleButtonPress]);

  const goToNext = useCallback(() => {
    handleButtonPress('next');
    setActiveIndex((prev) => (prev + 1) % 3);
  }, [handleButtonPress]);

  // Swipe gesture handlers
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (e.touches.length === 1) {
      touchStartX.current = e.touches[0].clientX;
      touchStartY.current = e.touches[0].clientY;
    }
  }, []);

  const handleTouchEnd = useCallback((e: React.TouchEvent) => {
    if (touchStartX.current === null || touchStartY.current === null) return;

    const touchEndX = e.changedTouches[0].clientX;
    const touchEndY = e.changedTouches[0].clientY;
    const deltaX = touchEndX - touchStartX.current;
    const deltaY = touchEndY - touchStartY.current;

    // Only trigger swipe if horizontal movement is greater than vertical
    // (to avoid interfering with vertical scroll)
    if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > SWIPE_THRESHOLD) {
      if (deltaX > 0) {
        goToPrev(); // Swipe right = previous
      } else {
        goToNext(); // Swipe left = next
      }
    }

    touchStartX.current = null;
    touchStartY.current = null;
  }, [goToPrev, goToNext]);

  return (
    <div
      className="h-full flex flex-col"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      {/* Chart title */}
      <h3 className="text-center text-lg font-semibold text-gray-700 mb-2">
        {CHART_TITLES[activeIndex]}
      </h3>

      {/* Chart container with navigation */}
      <div className="flex-1 flex items-center gap-2 sm:gap-4 min-h-0">
        {/* Previous button - larger touch target */}
        <button
          onClick={goToPrev}
          className={`p-3 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0 touch-manipulation ${
            pressedButton === 'prev' ? 'bg-gray-200' : ''
          }`}
          aria-label="Previous chart"
        >
          <svg
            className="w-6 h-6 sm:w-8 sm:h-8 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>

        {/* Chart */}
        <div className="flex-1 h-full min-w-0">
          {activeIndex === 0 && <KiteableLineChart spotId={spotId} />}
          {activeIndex === 1 && <WindHistogram spotId={spotId} />}
          {activeIndex === 2 && <WindRose spotId={spotId} />}
        </div>

        {/* Next button - larger touch target */}
        <button
          onClick={goToNext}
          className={`p-3 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0 touch-manipulation ${
            pressedButton === 'next' ? 'bg-gray-200' : ''
          }`}
          aria-label="Next chart"
        >
          <svg
            className="w-6 h-6 sm:w-8 sm:h-8 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 5l7 7-7 7"
            />
          </svg>
        </button>
      </div>

      {/* Dot indicators - 44px touch targets with visual dot inside */}
      <div className="flex justify-center gap-1 pt-2 sm:pt-4">
        {[0, 1, 2].map((index) => (
          <button
            key={index}
            onClick={() => setActiveIndex(index)}
            className="w-11 h-11 flex items-center justify-center touch-manipulation"
            aria-label={`Go to ${CHART_TITLES[index]}`}
          >
            <span
              className={`w-3 h-3 rounded-full transition-colors ${
                index === activeIndex ? 'bg-kite-pink' : 'bg-gray-300'
              }`}
            />
          </button>
        ))}
      </div>
    </div>
  );
}

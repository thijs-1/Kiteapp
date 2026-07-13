import { useState, useRef, useCallback, useEffect, useMemo, memo } from 'react';
import type { NearestAirport, Spot } from '../../api/types';
import { KiteableLineChart } from './Charts/KiteableLineChart';
import { WindHistogram } from './Charts/WindHistogram';
import { WindRose } from './Charts/WindRose';
import { DailyWindChart } from './Charts/DailyWindChart';
import { TemperatureChart } from './Charts/TemperatureChart';
import { PrecipitationChart } from './Charts/PrecipitationChart';
import { AirportsCard } from './AirportsCard';

// Memoized chart components to prevent re-renders when only activeIndex changes
const MemoKiteableLineChart = memo(KiteableLineChart);
const MemoWindHistogram = memo(WindHistogram);
const MemoWindRose = memo(WindRose);
const MemoDailyWindChart = memo(DailyWindChart);
const MemoTemperatureChart = memo(TemperatureChart);
const MemoPrecipitationChart = memo(PrecipitationChart);
const MemoAirportsCard = memo(AirportsCard);

interface CarouselProps {
  spot: Spot;
  airports: NearestAirport[];
}

// Minimum swipe distance to trigger navigation (in pixels)
const SWIPE_THRESHOLD = 50;

export function Carousel({ spot, airports }: CarouselProps) {
  // Start with line chart (index 0)
  const [activeIndex, setActiveIndex] = useState(0);
  // Track which charts have been visited to enable lazy mounting
  const [mountedCharts, setMountedCharts] = useState(new Set([0]));
  const touchStartX = useRef<number | null>(null);
  const touchStartY = useRef<number | null>(null);

  // Track which button is pressed for mobile-friendly feedback
  const [pressedButton, setPressedButton] = useState<'prev' | 'next' | null>(null);
  const pressTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Memoize slides so invisible ones don't re-render on navigation
  const slides = useMemo(() => {
    const items = [
      { title: 'Kiteable Wind %', element: <MemoKiteableLineChart spotId={spot.spot_id} /> },
      { title: 'Wind Strength Distribution', element: <MemoWindHistogram spotId={spot.spot_id} /> },
      { title: 'Wind Rose', element: <MemoWindRose spotId={spot.spot_id} /> },
      { title: 'Daily Wind Profiles', element: <MemoDailyWindChart spotId={spot.spot_id} /> },
      { title: 'Daytime Temperature', element: <MemoTemperatureChart spotId={spot.spot_id} /> },
      { title: 'Rain', element: <MemoPrecipitationChart spotId={spot.spot_id} /> },
    ];
    if (airports.length > 0) {
      items.push({
        title: 'Nearest Airports',
        element: <MemoAirportsCard spot={spot} airports={airports} />,
      });
    }
    return items;
  }, [spot, airports]);

  // Airports load async, so the slide count can shrink between renders
  const safeIndex = Math.min(activeIndex, slides.length - 1);

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

  const navigateTo = useCallback((index: number) => {
    setActiveIndex(index);
    setMountedCharts((prev) => {
      if (prev.has(index)) return prev;
      const next = new Set(prev);
      next.add(index);
      return next;
    });
  }, []);

  const goToPrev = useCallback(() => {
    handleButtonPress('prev');
    navigateTo((safeIndex - 1 + slides.length) % slides.length);
  }, [handleButtonPress, navigateTo, safeIndex, slides.length]);

  const goToNext = useCallback(() => {
    handleButtonPress('next');
    navigateTo((safeIndex + 1) % slides.length);
  }, [handleButtonPress, navigateTo, safeIndex, slides.length]);

  // Keyboard navigation (Left/Right arrow keys)
  // Skip when focus is on interactive elements like sliders or inputs
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest('[role="slider"], input, textarea, select')) return;
      if (e.key === 'ArrowLeft') goToPrev();
      if (e.key === 'ArrowRight') goToNext();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [goToPrev, goToNext]);

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

  // Reset touch state if browser cancels the gesture (e.g. system gesture, incoming call)
  const handleTouchCancel = useCallback(() => {
    touchStartX.current = null;
    touchStartY.current = null;
  }, []);

  return (
    <div
      className="h-full flex flex-col"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={handleTouchCancel}
    >
      {/* Chart title with page indicator */}
      <div className="flex items-center justify-center gap-2 mb-2">
        <h3 className="text-lg font-semibold text-gray-700">
          {slides[safeIndex].title}
        </h3>
        <span className="text-sm text-gray-400">{safeIndex + 1}/{slides.length}</span>
      </div>

      {/* Chart container with navigation */}
      <div className="flex-1 flex items-center gap-2 sm:gap-4 min-h-0">
        {/* Previous button - hidden on mobile where swipe and dots handle navigation */}
        <button
          onClick={goToPrev}
          className={`hidden sm:block p-3 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0 touch-manipulation ${
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

        {/* Chart — only mount charts that have been visited, show only active one */}
        <div className="flex-1 h-full min-w-0 relative">
          {slides.map((slide, index) => (
            <div
              key={index}
              className={`absolute inset-0 transition-[opacity,visibility] duration-200 ${
                index === safeIndex
                  ? 'opacity-100 visible'
                  : 'opacity-0 invisible pointer-events-none'
              }`}
            >
              {mountedCharts.has(index) ? slide.element : null}
            </div>
          ))}
        </div>

        {/* Next button - hidden on mobile where swipe and dots handle navigation */}
        <button
          onClick={goToNext}
          className={`hidden sm:block p-3 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0 touch-manipulation ${
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
        {slides.map((slide, index) => (
          <button
            key={index}
            onClick={() => navigateTo(index)}
            className="w-11 h-11 flex items-center justify-center touch-manipulation"
            aria-label={`Go to ${slide.title}`}
          >
            <span
              className={`w-3 h-3 rounded-full transition-colors ${
                index === safeIndex ? 'bg-kite' : 'bg-gray-300'
              }`}
            />
          </button>
        ))}
      </div>
    </div>
  );
}

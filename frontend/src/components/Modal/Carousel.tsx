import { useState } from 'react';
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

export function Carousel({ spotId }: CarouselProps) {
  // Start with line chart (index 0)
  const [activeIndex, setActiveIndex] = useState(0);

  const goToPrev = () => {
    setActiveIndex((prev) => (prev - 1 + 3) % 3);
  };

  const goToNext = () => {
    setActiveIndex((prev) => (prev + 1) % 3);
  };

  return (
    <div className="h-full flex flex-col">
      {/* Chart title */}
      <h3 className="text-center text-lg font-semibold text-gray-700 mb-2">
        {CHART_TITLES[activeIndex]}
      </h3>

      {/* Chart container with navigation */}
      <div className="flex-1 flex items-center gap-4 min-h-0">
        {/* Previous button */}
        <button
          onClick={goToPrev}
          className="p-2 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0"
          aria-label="Previous chart"
        >
          <svg
            className="w-8 h-8 text-gray-400"
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

        {/* Next button */}
        <button
          onClick={goToNext}
          className="p-2 hover:bg-gray-100 rounded-full transition-colors flex-shrink-0"
          aria-label="Next chart"
        >
          <svg
            className="w-8 h-8 text-gray-400"
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

      {/* Dot indicators */}
      <div className="flex justify-center gap-2 pt-4">
        {[0, 1, 2].map((index) => (
          <button
            key={index}
            onClick={() => setActiveIndex(index)}
            className={`w-3 h-3 rounded-full transition-colors ${
              index === activeIndex ? 'bg-kite-pink' : 'bg-gray-300 hover:bg-gray-400'
            }`}
            aria-label={`Go to ${CHART_TITLES[index]}`}
          />
        ))}
      </div>
    </div>
  );
}

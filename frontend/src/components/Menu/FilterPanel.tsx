import { WindRangeSlider } from './WindRangeSlider';
import { SustainedWindSlider } from './SustainedWindSlider';
import { DateRangePicker } from './DateRangePicker';
import { CountrySelector } from './CountrySelector';
import { SpotSearch } from './SpotSearch';
import { PercentageSlider } from './PercentageSlider';
import { useFilterStore } from '../../store/filterStore';
import { useSpotStore } from '../../store/spotStore';

export function FilterPanel() {
  const resetFilters = useFilterStore((state) => state.resetFilters);
  const { spots, isLoading } = useSpotStore();

  return (
    <div className="space-y-6">
      <WindRangeSlider />
      <SustainedWindSlider />
      <PercentageSlider />
      <DateRangePicker />
      <CountrySelector />
      <SpotSearch />

      {/* Reset button */}
      <button
        onClick={resetFilters}
        className="w-full py-2 px-4 bg-gray-200 hover:bg-gray-300 rounded-lg text-gray-700 transition-colors"
      >
        Reset Filters
      </button>

      {/* Results count */}
      <div className="text-center text-sm text-gray-500">
        {isLoading ? (
          'Loading...'
        ) : (
          <>
            <span className="font-semibold text-kite-pink">{spots.length}</span> spots
            found
          </>
        )}
      </div>
    </div>
  );
}

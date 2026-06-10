import { SearchInput } from './SearchInput';
import { WindRangeSlider } from './WindRangeSlider';
import { DateRangePicker } from './DateRangePicker';
import { PercentageSlider } from './PercentageSlider';
import { AirportDistanceSlider } from './AirportDistanceSlider';
import { useSpotsMeta } from '../../hooks/useSpotsMeta';

export function FilterPanel() {
  // Hide the airport filter when the dataset carries no airport data;
  // the backend would silently ignore it and the slider would do nothing.
  const meta = useSpotsMeta();

  return (
    <div className="space-y-6">
      <SearchInput />

      <div className="border-t border-gray-100" />

      <WindRangeSlider />
      <PercentageSlider />
      {meta?.has_airport_data && <AirportDistanceSlider />}

      <div className="border-t border-gray-100" />

      <DateRangePicker />
    </div>
  );
}

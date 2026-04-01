import { SearchInput } from './SearchInput';
import { WindRangeSlider } from './WindRangeSlider';
import { DateRangePicker } from './DateRangePicker';
import { PercentageSlider } from './PercentageSlider';

export function FilterPanel() {
  return (
    <div className="space-y-6">
      <SearchInput />

      <div className="border-t border-gray-100" />

      <WindRangeSlider />
      <PercentageSlider />

      <div className="border-t border-gray-100" />

      <DateRangePicker />
    </div>
  );
}

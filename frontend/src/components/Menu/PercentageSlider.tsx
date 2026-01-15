import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { useFilterStore } from '../../store/filterStore';

const PERCENTAGE_MARKS: Record<number, string> = {
  0: '0%',
  25: '25%',
  50: '50%',
  75: '75%',
  100: '100%',
};

export function PercentageSlider() {
  const { minPercentage, setMinPercentage } = useFilterStore();

  const handleChange = (value: number | number[]) => {
    if (typeof value === 'number') {
      setMinPercentage(value);
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        Minimum Kiteable %
      </label>
      <div className="px-2 pb-6">
        <Slider
          min={0}
          max={100}
          step={5}
          value={minPercentage}
          onChange={handleChange}
          marks={PERCENTAGE_MARKS}
          trackStyle={{ backgroundColor: '#FF69B4' }}
          handleStyle={{ borderColor: '#FF69B4', backgroundColor: 'white' }}
          railStyle={{ backgroundColor: '#E5E7EB' }}
        />
      </div>
      <div className="text-xs text-gray-500 text-center">
        At least {minPercentage}% of time with good wind
      </div>
    </div>
  );
}

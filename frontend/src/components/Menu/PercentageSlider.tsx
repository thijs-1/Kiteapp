import { useState, useEffect } from 'react';
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
  const [localValue, setLocalValue] = useState(minPercentage);

  // Sync local state when store changes (e.g., reset filters)
  useEffect(() => {
    setLocalValue(minPercentage);
  }, [minPercentage]);

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
          value={localValue}
          onChange={(value) => setLocalValue(value as number)}
          onAfterChange={(value) => {
            if (typeof value === 'number') {
              setMinPercentage(value);
            }
          }}
          marks={PERCENTAGE_MARKS}
          trackStyle={{ backgroundColor: '#FF69B4' }}
          handleStyle={{ borderColor: '#FF69B4', backgroundColor: 'white' }}
          railStyle={{ backgroundColor: '#E5E7EB' }}
        />
      </div>
      <div className="text-xs text-gray-500 text-center">
        At least {localValue}% of time with good wind
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { useFilterStore } from '../../store/filterStore';

// Wind bins: 0, 2.5, 5, ..., 35
const SLIDER_MAX = 35;

const WIND_MARKS: Record<number, string> = {
  0: '0',
  10: '10',
  20: '20',
  30: '30',
  [SLIDER_MAX]: '35',
};

export function SustainedWindSlider() {
  const { sustainedWindMin, setSustainedWindMin } = useFilterStore();
  const [localValue, setLocalValue] = useState(sustainedWindMin);

  // Sync local state when store changes (e.g., reset filters)
  useEffect(() => {
    setLocalValue(sustainedWindMin);
  }, [sustainedWindMin]);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        Sustained Wind (knots)
      </label>
      <div className="px-2 pb-6">
        <Slider
          min={0}
          max={SLIDER_MAX}
          step={2.5}
          value={localValue}
          onChange={(value) => setLocalValue(value as number)}
          onAfterChange={(value) => {
            if (typeof value === 'number') {
              setSustainedWindMin(value);
            }
          }}
          marks={WIND_MARKS}
          trackStyle={{ backgroundColor: '#FF69B4' }}
          handleStyle={{ borderColor: '#FF69B4', backgroundColor: 'white' }}
          railStyle={{ backgroundColor: '#E5E7EB' }}
        />
      </div>
      <div className="text-xs text-gray-500 text-center">
        {localValue === 0 ? (
          'No sustained wind filter'
        ) : (
          <>Min {localValue} knots for 2+ hours</>
        )}
      </div>
    </div>
  );
}

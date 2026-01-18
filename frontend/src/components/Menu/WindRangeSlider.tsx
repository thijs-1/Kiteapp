import { useState, useEffect } from 'react';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { useFilterStore } from '../../store/filterStore';

// Wind bins: 0, 2.5, 5, ..., 35, 37.5 (infinity)
const SLIDER_MAX = 37.5;
const STORE_INFINITY = 100; // Backend treats 100 as infinity

const WIND_MARKS: Record<number, string> = {
  0: '0',
  10: '10',
  20: '20',
  30: '30',
  [SLIDER_MAX]: '35+',
};

export function WindRangeSlider() {
  const { windMin, windMax, setWindRange } = useFilterStore();
  // Clamp store values to slider range for display
  const [localValue, setLocalValue] = useState([
    windMin,
    Math.min(windMax, SLIDER_MAX),
  ]);

  // Sync local state when store changes (e.g., reset filters)
  useEffect(() => {
    setLocalValue([windMin, Math.min(windMax, SLIDER_MAX)]);
  }, [windMin, windMax]);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        Wind Range (knots)
      </label>
      <div className="px-2 pb-6">
        <Slider
          range
          min={0}
          max={SLIDER_MAX}
          step={2.5}
          value={localValue}
          onChange={(value) => setLocalValue(value as number[])}
          onAfterChange={(value) => {
            if (Array.isArray(value)) {
              // Convert slider max to store infinity value
              const max = value[1] >= SLIDER_MAX ? STORE_INFINITY : value[1];
              setWindRange(value[0], max);
            }
          }}
          marks={WIND_MARKS}
          trackStyle={[{ backgroundColor: '#FF69B4' }]}
          handleStyle={[
            { borderColor: '#FF69B4', backgroundColor: 'white' },
            { borderColor: '#FF69B4', backgroundColor: 'white' },
          ]}
          railStyle={{ backgroundColor: '#E5E7EB' }}
        />
      </div>
      <div className="text-xs text-gray-500 text-center">
        {localValue[0]} - {localValue[1] >= SLIDER_MAX ? '35+' : localValue[1]} knots
      </div>
    </div>
  );
}

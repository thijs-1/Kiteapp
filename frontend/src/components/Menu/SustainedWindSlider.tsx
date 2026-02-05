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

const PERCENTAGE_MARKS: Record<number, string> = {
  0: '0%',
  25: '25%',
  50: '50%',
  75: '75%',
  100: '100%',
};

export function SustainedWindSlider() {
  const {
    sustainedWindMin,
    setSustainedWindMin,
    sustainedWindDaysMin,
    setSustainedWindDaysMin,
  } = useFilterStore();
  const [localWindValue, setLocalWindValue] = useState(sustainedWindMin);
  const [localDaysValue, setLocalDaysValue] = useState(sustainedWindDaysMin);

  // Sync local state when store changes (e.g., reset filters)
  useEffect(() => {
    setLocalWindValue(sustainedWindMin);
  }, [sustainedWindMin]);

  useEffect(() => {
    setLocalDaysValue(sustainedWindDaysMin);
  }, [sustainedWindDaysMin]);

  return (
    <div className="space-y-4">
      <label className="block text-sm font-medium text-gray-700">
        Sustained Wind Filter
      </label>

      {/* Wind threshold slider */}
      <div className="space-y-1">
        <div className="text-xs text-gray-600">Wind threshold (knots)</div>
        <div className="px-2 pb-6">
          <Slider
            min={0}
            max={SLIDER_MAX}
            step={2.5}
            value={localWindValue}
            onChange={(value) => setLocalWindValue(value as number)}
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
      </div>

      {/* Days percentage slider - only show when wind threshold > 0 */}
      {localWindValue > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-gray-600">Minimum % of days</div>
          <div className="px-2 pb-6">
            <Slider
              min={0}
              max={100}
              step={5}
              value={localDaysValue}
              onChange={(value) => setLocalDaysValue(value as number)}
              onAfterChange={(value) => {
                if (typeof value === 'number') {
                  setSustainedWindDaysMin(value);
                }
              }}
              marks={PERCENTAGE_MARKS}
              trackStyle={{ backgroundColor: '#FF69B4' }}
              handleStyle={{ borderColor: '#FF69B4', backgroundColor: 'white' }}
              railStyle={{ backgroundColor: '#E5E7EB' }}
            />
          </div>
        </div>
      )}

      <div className="text-xs text-gray-500 text-center">
        {localWindValue === 0 ? (
          'No sustained wind filter'
        ) : (
          <>{localDaysValue}% of days with {localWindValue}+ knots for 2+ hours</>
        )}
      </div>
    </div>
  );
}

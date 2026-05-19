import { useState, useEffect } from 'react';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import {
  useFilterStore,
  AIRPORT_DISTANCE_NO_LIMIT,
} from '../../store/filterStore';

const DISTANCE_MARKS: Record<number, string> = {
  0: '0',
  100: '100',
  250: '250',
  [AIRPORT_DISTANCE_NO_LIMIT]: `${AIRPORT_DISTANCE_NO_LIMIT}+`,
};

export function AirportDistanceSlider() {
  const { maxAirportDistance, setMaxAirportDistance } = useFilterStore();
  const [localValue, setLocalValue] = useState(maxAirportDistance);

  useEffect(() => {
    setLocalValue(maxAirportDistance);
  }, [maxAirportDistance]);

  const isNoLimit = localValue >= AIRPORT_DISTANCE_NO_LIMIT;

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        Distance to airport
      </label>
      <div className="px-2 pb-6">
        <Slider
          min={0}
          max={AIRPORT_DISTANCE_NO_LIMIT}
          step={25}
          value={localValue}
          onChange={(value) => setLocalValue(value as number)}
          onAfterChange={(value) => {
            if (typeof value === 'number') {
              setMaxAirportDistance(value);
            }
          }}
          marks={DISTANCE_MARKS}
          trackStyle={{ backgroundColor: '#0891B2' }}
          handleStyle={{ borderColor: '#0891B2', backgroundColor: 'white' }}
          railStyle={{ backgroundColor: '#E5E7EB' }}
        />
      </div>
      <div className="text-xs text-gray-500 text-center">
        {isNoLimit ? 'No limit' : `Within ${localValue} km of an airport`}
      </div>
    </div>
  );
}

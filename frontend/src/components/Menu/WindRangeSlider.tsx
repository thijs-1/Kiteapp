import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { useFilterStore } from '../../store/filterStore';

// Wind bins: 0, 2.5, 5, ..., 35, 37.5 (infinity)
const WIND_MARKS: Record<number, string> = {
  0: '0',
  10: '10',
  20: '20',
  30: '30',
  37.5: '35+',
};

export function WindRangeSlider() {
  const { windMin, windMax, setWindRange } = useFilterStore();

  const handleChange = (value: number | number[]) => {
    if (Array.isArray(value)) {
      setWindRange(value[0], value[1]);
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        Wind Range (knots)
      </label>
      <div className="px-2 pb-6">
        <Slider
          range
          min={0}
          max={37.5}
          step={2.5}
          value={[windMin, windMax]}
          onChange={handleChange}
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
        {windMin} - {windMax >= 37.5 ? '35+' : windMax} knots
      </div>
    </div>
  );
}

import { useState, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ChartOptions,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { useKiteablePercentage } from '../../../hooks/useHistogram';
import { useFilterStore } from '../../../store/filterStore';
import { sortDatesForRange } from '../../../utils/dateUtils';
import { ChartDateRangeSelector } from './ChartDateRangeSelector';

const SLIDER_MAX = 37.5;
const STORE_INFINITY = 100;

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface Props {
  spotId: string;
}

export function KiteableLineChart({ spotId }: Props) {
  const { startDate, endDate, windMin, windMax, setWindRange } = useFilterStore();
  const { data, isLoading, error } = useKiteablePercentage(spotId);

  // Local state for slider (to avoid API calls on every drag)
  const [localWindRange, setLocalWindRange] = useState([
    windMin,
    Math.min(windMax, SLIDER_MAX),
  ]);

  // Sync local state when store changes
  useEffect(() => {
    setLocalWindRange([windMin, Math.min(windMax, SLIDER_MAX)]);
  }, [windMin, windMax]);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-kite-pink" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        No data available
      </div>
    );
  }

  // Sort dates chronologically (handles year-wrap ranges like Dec-Jan)
  const sortedDates = sortDatesForRange(Object.keys(data.daily_percentage), startDate, endDate);
  const percentages = sortedDates.map((date) => data.daily_percentage[date]);

  // Format dates for display (show every 15th day)
  const labels = sortedDates.map((date, idx) => {
    if (idx % 15 === 0) {
      const [month, day] = date.split('-');
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return `${monthNames[parseInt(month) - 1]} ${parseInt(day)}`;
    }
    return '';
  });

  const chartData = {
    labels,
    datasets: [
      {
        label: 'Kiteable %',
        data: percentages,
        borderColor: '#FF69B4',
        backgroundColor: 'rgba(255, 105, 180, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 4,
      },
    ],
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          title: (items) => {
            const date = sortedDates[items[0].dataIndex];
            const [month, day] = date.split('-');
            const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
            return `${monthNames[parseInt(month) - 1]} ${parseInt(day)}`;
          },
          label: (item) => {
            return `${(item.raw as number).toFixed(1)}% kiteable`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 100,
        title: {
          display: true,
          text: 'Kiteable %',
        },
      },
      x: {
        grid: {
          display: false,
        },
      },
    },
  };

  const formatWindRange = () => {
    const min = localWindRange[0];
    const max = localWindRange[1] >= SLIDER_MAX ? '35+' : localWindRange[1];
    return `${min}-${max} kts`;
  };

  return (
    <div className="h-full flex flex-col">
      {/* Wind range slider */}
      <div className="flex items-center gap-3 px-2 pb-2 flex-shrink-0">
        <span className="text-xs text-gray-500 whitespace-nowrap w-16">{formatWindRange()}</span>
        <div className="flex-1">
          <Slider
            range
            min={0}
            max={SLIDER_MAX}
            step={2.5}
            value={localWindRange}
            onChange={(value) => setLocalWindRange(value as number[])}
            onChangeComplete={(value) => {
              if (Array.isArray(value)) {
                const max = value[1] >= SLIDER_MAX ? STORE_INFINITY : value[1];
                setWindRange(value[0], max);
              }
            }}
            trackStyle={[{ backgroundColor: '#FF69B4', height: 4 }]}
            handleStyle={[
              { borderColor: '#FF69B4', backgroundColor: 'white', width: 12, height: 12, marginTop: -4 },
              { borderColor: '#FF69B4', backgroundColor: 'white', width: 12, height: 12, marginTop: -4 },
            ]}
            railStyle={{ backgroundColor: '#E5E7EB', height: 4 }}
          />
        </div>
      </div>

      {/* Chart */}
      <ChartDateRangeSelector dates={sortedDates}>
        <div className="h-full">
          <Line data={chartData} options={options} />
        </div>
      </ChartDateRangeSelector>
    </div>
  );
}

import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';
import { Radar } from 'react-chartjs-2';
import { useWindRoseData } from '../../../hooks/useHistogram';

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

// Direction labels for 36 sectors (10 degrees each)
// Bins are centered at 0°, 10°, 20°, ... so N=0, E=9, S=18, W=27
const DIRECTION_LABELS = [
  'N',   // 0 = 0°
  '',    // 1 = 10°
  'NNE', // 2 = 20° (NNE is 22.5°)
  '',    // 3 = 30°
  'NE',  // 4 = 40° (NE is 45°)
  '',    // 5 = 50°
  '',    // 6 = 60°
  'ENE', // 7 = 70° (ENE is 67.5°)
  '',    // 8 = 80°
  'E',   // 9 = 90°
  '',    // 10 = 100°
  'ESE', // 11 = 110° (ESE is 112.5°)
  '',    // 12 = 120°
  'SE',  // 13 = 130° (SE is 135°)
  '',    // 14 = 140°
  '',    // 15 = 150°
  'SSE', // 16 = 160° (SSE is 157.5°)
  '',    // 17 = 170°
  'S',   // 18 = 180°
  '',    // 19 = 190°
  'SSW', // 20 = 200° (SSW is 202.5°)
  '',    // 21 = 210°
  'SW',  // 22 = 220° (SW is 225°)
  '',    // 23 = 230°
  '',    // 24 = 240°
  'WSW', // 25 = 250° (WSW is 247.5°)
  '',    // 26 = 260°
  'W',   // 27 = 270°
  '',    // 28 = 280°
  'WNW', // 29 = 290° (WNW is 292.5°)
  '',    // 30 = 300°
  'NW',  // 31 = 310° (NW is 315°)
  '',    // 32 = 320°
  '',    // 33 = 330°
  'NNW', // 34 = 340° (NNW is 337.5°)
  '',    // 35 = 350°
];

// Same color scheme as WindHistogram
const WIND_COLORS = [
  '#E3F2FD', // 0-2.5: Very light blue
  '#BBDEFB', // 2.5-5
  '#90CAF9', // 5-7.5
  '#64B5F6', // 7.5-10
  '#42A5F5', // 10-12.5
  '#2196F3', // 12.5-15: Blue
  '#1E88E5', // 15-17.5
  '#1976D2', // 17.5-20
  '#1565C0', // 20-22.5
  '#0D47A1', // 22.5-25
  '#FFC107', // 25-27.5: Yellow/Orange
  '#FF9800', // 27.5-30
  '#FF5722', // 30-32.5
  '#F44336', // 32.5-35
  '#B71C1C', // 35+: Dark red
];

interface Props {
  spotId: string;
}

export function WindRose({ spotId }: Props) {
  const { data, isLoading, error } = useWindRoseData(spotId);

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

  const numStrengthBins = data.data.length;
  const numDirections = data.direction_bins.length - 1;

  // Create bin labels for legend
  const getBinLabel = (binIdx: number): string => {
    const low = data.strength_bins[binIdx];
    const high = data.strength_bins[binIdx + 1];
    if (high === undefined || high > 99) {
      return `${low}+ kts`;
    }
    return `${low}-${high} kts`;
  };

  // Build cumulative datasets for stacked radar effect
  // Each dataset contains cumulative values, fill: '-1' fills the gap
  const datasets: {
    label: string;
    data: number[];
    backgroundColor: string;
    borderColor: string;
    borderWidth: number;
    pointRadius: number;
    fill: string;
  }[] = [];
  let cumulativeData = new Array(numDirections).fill(0);

  for (let s = 0; s < numStrengthBins; s++) {
    // Add this bin's values to cumulative
    const newCumulative = cumulativeData.map((val, d) => val + (data.data[s][d] || 0));

    datasets.push({
      label: getBinLabel(s),
      data: newCumulative,
      backgroundColor: WIND_COLORS[s] || '#999',
      borderColor: 'rgba(255, 255, 255, 0.5)',
      borderWidth: 0.5,
      pointRadius: 0,
      fill: s === 0 ? 'origin' : '-1',
    });

    cumulativeData = newCumulative;
  }

  const chartData = {
    labels: DIRECTION_LABELS.slice(0, numDirections),
    datasets,
  };

  const options: ChartOptions<'radar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'right' as const,
        labels: {
          boxWidth: 12,
          font: { size: 9 },
        },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            // Show the actual bin value, not cumulative
            const binIdx = datasets.findIndex(d => d.label === item.dataset.label);
            const dirIdx = item.dataIndex;
            const actualValue = data.data[binIdx]?.[dirIdx] || 0;
            return `${item.dataset.label}: ${actualValue.toFixed(1)}%`;
          },
        },
      },
    },
    scales: {
      r: {
        beginAtZero: true,
        ticks: {
          display: false,
        },
        pointLabels: {
          font: {
            size: 10,
          },
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.1)',
        },
      },
    },
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0">
        <Radar data={chartData} options={options} />
      </div>
      <p className="text-xs text-gray-500 text-center mt-2">
        * Wind direction shows where wind is going TO (not from)
      </p>
    </div>
  );
}

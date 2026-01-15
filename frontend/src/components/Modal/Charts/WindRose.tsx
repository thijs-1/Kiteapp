import {
  Chart as ChartJS,
  RadialLinearScale,
  ArcElement,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';
import { PolarArea } from 'react-chartjs-2';
import { useWindRoseData } from '../../../hooks/useHistogram';

ChartJS.register(RadialLinearScale, ArcElement, Tooltip, Legend);

// Direction labels for 36 sectors (10 degrees each)
const DIRECTION_LABELS = [
  'N', '', 'NNE', '', 'NE', '', 'ENE', '', 'E', '',
  'ESE', '', 'SE', '', 'SSE', '', 'S', '', 'SSW', '',
  'SW', '', 'WSW', '', 'W', '', 'WNW', '', 'NW', '',
  'NNW', '', '', '', '', '',
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

  // Sum across all wind speeds for each direction
  // data.data is [strength_bins x direction_bins]
  const directionTotals: number[] = [];
  const numDirections = data.direction_bins.length - 1;

  for (let d = 0; d < numDirections; d++) {
    let total = 0;
    for (let s = 0; s < data.data.length; s++) {
      total += data.data[s][d] || 0;
    }
    directionTotals.push(total);
  }

  // Create colors for each direction (gradient from light to dark pink)
  const colors = directionTotals.map((_, idx) => {
    const hue = 330; // Pink
    const saturation = 70 + (idx % 4) * 5;
    const lightness = 60 - (idx % 3) * 10;
    return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
  });

  const chartData = {
    labels: DIRECTION_LABELS.slice(0, numDirections),
    datasets: [
      {
        data: directionTotals,
        backgroundColor: colors,
        borderColor: 'white',
        borderWidth: 1,
      },
    ],
  };

  const options: ChartOptions<'polarArea'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            return `${item.label || 'Direction'}: ${(item.raw as number).toFixed(1)}%`;
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
      },
    },
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0">
        <PolarArea data={chartData} options={options} />
      </div>
      <p className="text-xs text-gray-500 text-center mt-2">
        * Wind direction shows where wind is going TO (not from)
      </p>
    </div>
  );
}

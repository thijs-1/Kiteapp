import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  ChartOptions,
} from 'chart.js';
import { Scatter } from 'react-chartjs-2';
import { useDailyWindProfiles } from '../../../hooks/useHistogram';

ChartJS.register(
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip
);

interface Props {
  spotId: string;
}

function formatHour(h: number): string {
  const hours = Math.floor(h);
  const minutes = Math.round((h - hours) * 60);
  return `${hours}:${minutes.toString().padStart(2, '0')}`;
}

export function DailyWindChart({ spotId }: Props) {
  const { data, isLoading, error } = useDailyWindProfiles(spotId);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-kite" />
      </div>
    );
  }

  if (error || !data || data.profiles.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        No data available
      </div>
    );
  }

  const lineOpacity = Math.max(0.05, Math.min(0.25, 2.0 / Math.sqrt(data.profiles.length)));

  const datasets = data.profiles.map((profile) => ({
    label: profile.date,
    data: profile.hours.map((h, i) => ({ x: h, y: profile.strength[i] })),
    showLine: true,
    borderColor: `rgba(8, 145, 178, ${lineOpacity})`,
    borderWidth: 1.5,
    pointRadius: 0,
    pointHoverRadius: 0,
    tension: 0.3,
  }));

  // Find x-axis range from data
  let minHour = 24;
  let maxHour = 0;
  for (const profile of data.profiles) {
    for (const h of profile.hours) {
      if (h < minHour) minHour = h;
      if (h > maxHour) maxHour = h;
    }
  }
  minHour = Math.floor(minHour);
  maxHour = Math.ceil(maxHour);

  const options: ChartOptions<'scatter'> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        enabled: false,
      },
    },
    scales: {
      x: {
        type: 'linear',
        min: minHour,
        max: maxHour,
        title: {
          display: true,
          text: 'Local Time',
        },
        ticks: {
          stepSize: 2,
          callback: (value) => formatHour(value as number),
        },
        grid: {
          display: false,
        },
      },
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Wind (kts)',
        },
      },
    },
  };

  return (
    <div className="h-full flex flex-col">
      <div className="text-xs text-gray-500 text-center pb-1">
        {data.profiles.length} days overlaid
      </div>
      <div className="flex-1 min-h-0">
        <Scatter data={{ datasets }} options={options} />
      </div>
    </div>
  );
}

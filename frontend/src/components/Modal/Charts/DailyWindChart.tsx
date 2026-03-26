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
import { useIsMobile } from '../../../hooks/useIsMobile';

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

const SHORT_MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

function formatDateRange(first: string, last: string): string {
  // Dates are YYYY-MM-DD; display as "Jan 1 - Dec 31"
  const [, sm, sd] = first.split('-').map(Number);
  const [, em, ed] = last.split('-').map(Number);
  return `${SHORT_MONTHS[sm - 1]} ${sd} – ${SHORT_MONTHS[em - 1]} ${ed}`;
}

function formatHour(h: number): string {
  const hours = Math.floor(h);
  const minutes = Math.round((h - hours) * 60);
  return `${hours}:${minutes.toString().padStart(2, '0')}`;
}

export function DailyWindChart({ spotId }: Props) {
  const { data, isLoading, error } = useDailyWindProfiles(spotId);
  const isMobile = useIsMobile();

  if (isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-kite" />
        <span className="text-sm text-gray-400">Loading chart...</span>
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

  const lineOpacity = Math.max(0.07, Math.min(0.35, 3.0 / Math.sqrt(data.profiles.length)));

  // Merge all profiles into a single dataset with NaN separators for line breaks.
  // This avoids creating hundreds of Chart.js datasets (one per day) which is very slow.
  const mergedPoints: { x: number; y: number }[] = [];
  for (const profile of data.profiles) {
    for (let i = 0; i < profile.hours.length; i++) {
      mergedPoints.push({ x: profile.hours[i], y: profile.strength[i] });
    }
    mergedPoints.push({ x: NaN, y: NaN });
  }

  // Plugin: draw each profile separately with multiply compositing so overlapping
  // lines compound to darker values at high-density regions.
  // The merged dataset is kept invisible purely for y-axis auto-scaling.
  const renderPlugin = {
    id: 'dailyWindLines',
    beforeDatasetsDraw(chart: ChartJS) {
      const { ctx, chartArea, scales } = chart;
      if (!chartArea) return;

      const xScale = scales.x;
      const yScale = scales.y;

      ctx.save();
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(chartArea.left, chartArea.top, chartArea.width, chartArea.height);
      ctx.beginPath();
      ctx.rect(chartArea.left, chartArea.top, chartArea.width, chartArea.height);
      ctx.clip();
      ctx.globalCompositeOperation = 'multiply';
      ctx.strokeStyle = `rgba(8, 145, 178, ${lineOpacity})`;
      ctx.lineWidth = 1.5;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';

      for (const profile of data.profiles) {
        if (profile.hours.length === 0) continue;
        ctx.beginPath();
        ctx.moveTo(xScale.getPixelForValue(profile.hours[0]), yScale.getPixelForValue(profile.strength[0]));
        for (let i = 1; i < profile.hours.length; i++) {
          ctx.lineTo(xScale.getPixelForValue(profile.hours[i]), yScale.getPixelForValue(profile.strength[i]));
        }
        ctx.stroke();
      }

      ctx.restore();
    },
  };

  const datasets = [
    {
      label: '',
      data: mergedPoints,
      showLine: false,
      borderColor: 'transparent' as const,
      pointRadius: 0,
      pointHoverRadius: 0,
    },
  ];

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
          stepSize: isMobile ? 3 : 2,
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
        {formatDateRange(data.profiles[0].date, data.profiles[data.profiles.length - 1].date)}
      </div>
      <div className="flex-1 min-h-0">
        <Scatter data={{ datasets }} options={options} plugins={[renderPlugin]} />
      </div>
    </div>
  );
}

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { useWeatherHistogram } from '../../../hooks/useWeather';
import { useFilterStore } from '../../../store/filterStore';
import { useIsMobile } from '../../../hooks/useIsMobile';
import { aggregateDailyCounts } from '../../../utils/weatherStats';
import { ChartDateRangeSelector } from './ChartDateRangeSelector';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

// Fixed color map for the rainy 0.5 mm/h bins (the dry 0-0.5 bin is not
// plotted): light to dark blue with increasing rain intensity.
const RAIN_COLORS = [
  '#DBEAFE', // 0.5-1
  '#BFDBFE', // 1-1.5
  '#93C5FD', // 1.5-2
  '#60A5FA', // 2-2.5
  '#3B82F6', // 2.5-3
  '#2563EB', // 3-3.5
  '#1D4ED8', // 3.5-4
  '#1E40AF', // 4-4.5
  '#1E3A8A', // 4.5-5
  '#172554', // 5+
];

// The first bin (0-0.5 mm/h) holds the dry hours and is excluded from the stack
const FIRST_RAIN_BIN = 1;

interface Props {
  spotId: string;
}

export function PrecipitationChart({ spotId }: Props) {
  const { startDate, endDate } = useFilterStore();
  const { data, isLoading, error } = useWeatherHistogram(spotId, 'precipitation');
  const isMobile = useIsMobile();

  if (isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-kite" />
        <span className="text-sm text-gray-400">Loading chart...</span>
      </div>
    );
  }

  if (error || !data || Object.keys(data.daily_data).length === 0 || data.bins.length < 2) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        No data available
      </div>
    );
  }

  const { labels, counts, sortedDates, level } = aggregateDailyCounts(
    data.daily_data,
    startDate,
    endDate
  );

  // Rainy bin labels; the last bin's upper edge is the sanitized infinity, so show "5+"
  const binLabels = data.bins.slice(FIRST_RAIN_BIN, -1).map((bin, idx) => {
    const nextIdx = FIRST_RAIN_BIN + idx + 1;
    if (nextIdx === data.bins.length - 1) {
      return `${bin}+`;
    }
    return `${bin}-${data.bins[nextIdx]}`;
  });

  // All daytime hours (dry included) as the denominator, so segment heights
  // read as % of daytime hours with rain of that intensity
  const totals = counts.map((c) => c.reduce((sum, v) => sum + v, 0));

  // One stacked dataset per rainy bin; bar height totals % of hours with rain
  const datasets = binLabels.map((label, idx) => ({
    label: `${label} mm/h`,
    data: counts.map((c, keyIdx) => {
      const total = totals[keyIdx];
      return total > 0 ? ((c[FIRST_RAIN_BIN + idx] || 0) / total) * 100 : 0;
    }),
    backgroundColor: RAIN_COLORS[idx] || '#999',
  }));

  const chartData = {
    labels,
    datasets,
  };

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: isMobile ? 'bottom' as const : 'right' as const,
        labels: {
          boxWidth: isMobile ? 8 : 12,
          font: { size: isMobile ? 8 : 10 },
          padding: isMobile ? 4 : 10,
        },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            return `${item.dataset.label}: ${(item.raw as number).toFixed(1)}%`;
          },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        ticks: {
          maxRotation: level === 'daily' ? 45 : 0,
          autoSkip: true,
          maxTicksLimit: level === 'daily' ? (isMobile ? 7 : 15) : (isMobile ? 6 : 12),
          font: { size: level === 'daily' ? 9 : (isMobile ? 9 : 11) },
        },
        grid: {
          display: false,
        },
      },
      y: {
        stacked: true,
        beginAtZero: true,
        suggestedMax: 10,
        title: {
          display: true,
          text: '% of daytime hours with rain',
        },
      },
    },
  };

  return (
    <ChartDateRangeSelector dates={sortedDates}>
      <div className="h-full">
        <Bar data={chartData} options={options} />
      </div>
    </ChartDateRangeSelector>
  );
}

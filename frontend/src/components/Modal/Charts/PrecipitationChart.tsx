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
import { aggregateDailyCounts, percentAtOrAboveBin } from '../../../utils/weatherStats';
import { ChartDateRangeSelector } from './ChartDateRangeSelector';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const RAIN_COLOR = '#2563EB'; // Blue, distinct from the kite cyan

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

  // Share of daytime hours beyond the first bin. With 2.5 mm bins the first
  // bin (0-2.5 mm) contains the dry hours, so this counts hours with rain
  // heavier than the first bin edge.
  const rainThreshold = data.bins[1];
  const rainyPercent = counts.map((c) => percentAtOrAboveBin(c, 1));

  const chartData = {
    labels,
    datasets: [
      {
        label: `Hours with rain ≥ ${rainThreshold} mm/h`,
        data: rainyPercent,
        backgroundColor: RAIN_COLOR,
        borderRadius: 4,
        maxBarThickness: 32,
      },
    ],
  };

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false, // Single series: the axis title names it
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            const value = item.raw as number | null;
            if (value === null) return 'No data';
            return `${value.toFixed(1)}% of daytime hours with rain ≥ ${rainThreshold} mm/h`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        suggestedMax: 10,
        title: {
          display: true,
          text: `% of daytime hours with rain (≥ ${rainThreshold} mm/h)`,
        },
      },
      x: {
        grid: {
          display: false,
        },
        ticks: {
          maxRotation: level === 'daily' ? 45 : 0,
          autoSkip: true,
          maxTicksLimit: level === 'daily' ? (isMobile ? 7 : 15) : (isMobile ? 6 : 12),
          font: { size: level === 'daily' ? 9 : (isMobile ? 9 : 11) },
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

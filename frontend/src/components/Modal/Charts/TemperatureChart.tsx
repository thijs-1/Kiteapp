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
import { useWeatherHistogram } from '../../../hooks/useWeather';
import { useFilterStore } from '../../../store/filterStore';
import { useIsMobile } from '../../../hooks/useIsMobile';
import {
  aggregateDailyCounts,
  weightedMean,
  binnedPercentile,
} from '../../../utils/weatherStats';
import { ChartDateRangeSelector } from './ChartDateRangeSelector';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

const TEMP_COLOR = '#EA580C'; // Orange: warm, distinct from the kite cyan
const BAND_FILL = 'rgba(234, 88, 12, 0.12)';

interface Props {
  spotId: string;
}

export function TemperatureChart({ spotId }: Props) {
  const { startDate, endDate } = useFilterStore();
  const { data, isLoading, error } = useWeatherHistogram(spotId, 'temperature');
  const isMobile = useIsMobile();

  if (isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-kite" />
        <span className="text-sm text-gray-400">Loading chart...</span>
      </div>
    );
  }

  if (error || !data || Object.keys(data.daily_data).length === 0) {
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

  const mean = counts.map((c) => weightedMean(c, data.bins));
  const p25 = counts.map((c) => binnedPercentile(c, data.bins, 0.25));
  const p75 = counts.map((c) => binnedPercentile(c, data.bins, 0.75));

  const chartData = {
    labels,
    datasets: [
      {
        label: '25–75% range',
        data: p75,
        borderWidth: 0,
        pointRadius: 0,
        pointHoverRadius: 0,
        backgroundColor: BAND_FILL,
        fill: '+1', // Fill down to the 25th percentile dataset
        tension: 0.3,
      },
      {
        label: 'p25',
        data: p25,
        borderWidth: 0,
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false,
        tension: 0.3,
      },
      {
        label: 'Average',
        data: mean,
        borderColor: TEMP_COLOR,
        backgroundColor: TEMP_COLOR,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        fill: false,
        tension: 0.3,
      },
    ],
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: {
      legend: {
        display: true,
        position: 'bottom' as const,
        labels: {
          boxWidth: isMobile ? 8 : 12,
          font: { size: isMobile ? 9 : 11 },
          // Hide the helper dataset that only anchors the band fill
          filter: (item) => item.text !== 'p25',
        },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            if (item.datasetIndex === 2) {
              return `Average: ${(item.raw as number).toFixed(1)}°C`;
            }
            if (item.datasetIndex === 0) {
              const low = p25[item.dataIndex];
              const high = p75[item.dataIndex];
              if (low === null || high === null) return '';
              return `Typical: ${low.toFixed(1)} to ${high.toFixed(1)}°C`;
            }
            return '';
          },
        },
      },
    },
    scales: {
      y: {
        title: {
          display: true,
          text: 'Daytime temperature (°C)',
        },
        grace: '10%',
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
        <Line data={chartData} options={options} />
      </div>
    </ChartDateRangeSelector>
  );
}

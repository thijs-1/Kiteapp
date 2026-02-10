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
import { useHistogramData } from '../../../hooks/useHistogram';
import { useFilterStore } from '../../../store/filterStore';
import { useIsMobile } from '../../../hooks/useIsMobile';
import {
  sortDatesForRange,
  sortMonthsForRange,
  getAggregationLevel,
  groupDatesByWeek,
} from '../../../utils/dateUtils';
import { WIND_COLORS } from '../../../utils/windColors';
import { ChartDateRangeSelector } from './ChartDateRangeSelector';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

interface Props {
  spotId: string;
}

export function WindHistogram({ spotId }: Props) {
  const { startDate, endDate } = useFilterStore();
  const { data, isLoading, error } = useHistogramData(spotId);
  const isMobile = useIsMobile();

  if (isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-2">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-kite" />
        <span className="text-sm text-gray-400">Loading chart...</span>
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
  const sortedDates = sortDatesForRange(Object.keys(data.daily_data), startDate, endDate);
  const aggregationLevel = getAggregationLevel(startDate, endDate);

  // Helper to format date label (e.g., "Jan 14")
  const formatDateLabel = (mmdd: string) => {
    const [month, day] = mmdd.split('-').map(Number);
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${monthNames[month - 1]} ${day}`;
  };

  // Aggregate data based on the level
  let labels: string[];
  let groupedData: Record<string, number[][]>;
  let sortedKeys: string[];

  if (aggregationLevel === 'daily') {
    // Daily: show each day directly (data already has ±2 week moving average from backend)
    labels = sortedDates.map(formatDateLabel);
    groupedData = Object.fromEntries(sortedDates.map((d) => [d, [data.daily_data[d]]]));
    sortedKeys = sortedDates;
  } else if (aggregationLevel === 'weekly') {
    // Weekly: group by week number
    const { weekData, sortedWeeks } = groupDatesByWeek(sortedDates, startDate, endDate);
    groupedData = Object.fromEntries(
      sortedWeeks.map((week) => [week, weekData[week].map((d) => data.daily_data[d])])
    );
    sortedKeys = sortedWeeks;
    // Label weeks by mid-week date for clarity
    labels = sortedWeeks.map((week) => {
      const weekDates = weekData[week];
      const midDate = weekDates[Math.floor(weekDates.length / 2)];
      return formatDateLabel(midDate);
    });
  } else {
    // Monthly: group by month (original behavior)
    const monthlyData: Record<string, number[][]> = {};
    for (const date of sortedDates) {
      const month = date.split('-')[0];
      if (!monthlyData[month]) {
        monthlyData[month] = [];
      }
      monthlyData[month].push(data.daily_data[date]);
    }
    const months = sortMonthsForRange(Object.keys(monthlyData), startDate, endDate);
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    labels = months.map((m) => monthNames[parseInt(m) - 1]);
    groupedData = monthlyData;
    sortedKeys = months;
  }

  // Create bin labels
  const binLabels = data.bins.slice(0, -1).map((bin, idx) => {
    const next = data.bins[idx + 1];
    if (next === Infinity || next > 100) {
      return `${bin}+`;
    }
    return `${bin}-${next}`;
  });

  // Create datasets for each wind bin (stacked)
  const datasets = binLabels.map((label, binIdx) => ({
    label: `${label} kts`,
    data: sortedKeys.map((key) => {
      const histograms = groupedData[key];
      const avgCount = histograms.reduce((sum, h) => sum + (h[binIdx] || 0), 0) / histograms.length;
      return avgCount;
    }),
    backgroundColor: WIND_COLORS[binIdx] || '#999',
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
        display: !isMobile,
        position: 'right' as const,
        labels: {
          boxWidth: 12,
          font: { size: 10 },
        },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            return `${item.dataset.label}: ${(item.raw as number).toFixed(1)}`;
          },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        ticks: {
          maxRotation: aggregationLevel === 'daily' ? 45 : 0,
          autoSkip: true,
          maxTicksLimit: aggregationLevel === 'daily'
            ? (isMobile ? 7 : 15)
            : (aggregationLevel === 'weekly' ? (isMobile ? 6 : undefined) : undefined),
          font: { size: aggregationLevel === 'daily' ? 9 : (isMobile ? 9 : 11) },
        },
      },
      y: {
        stacked: true,
        title: {
          display: true,
          text: 'Observations',
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

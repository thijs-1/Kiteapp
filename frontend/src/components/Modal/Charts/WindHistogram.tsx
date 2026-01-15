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

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

// Fixed color map for wind strength bins
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

export function WindHistogram({ spotId }: Props) {
  const { data, isLoading, error } = useHistogramData(spotId);

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

  // Sort dates and aggregate monthly
  const sortedDates = Object.keys(data.daily_data).sort();

  // Group by month
  const monthlyData: Record<string, number[][]> = {};
  for (const date of sortedDates) {
    const month = date.split('-')[0];
    if (!monthlyData[month]) {
      monthlyData[month] = [];
    }
    monthlyData[month].push(data.daily_data[date]);
  }

  // Average each month
  const months = Object.keys(monthlyData).sort();
  const monthLabels = months.map((m) => {
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return monthNames[parseInt(m) - 1];
  });

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
    data: months.map((month) => {
      const histograms = monthlyData[month];
      const avgCount = histograms.reduce((sum, h) => sum + (h[binIdx] || 0), 0) / histograms.length;
      return avgCount;
    }),
    backgroundColor: WIND_COLORS[binIdx] || '#999',
  }));

  const chartData = {
    labels: monthLabels,
    datasets,
  };

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
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
    <div className="h-full">
      <Bar data={chartData} options={options} />
    </div>
  );
}

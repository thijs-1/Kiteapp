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
import { useKiteablePercentage } from '../../../hooks/useHistogram';

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
  const { data, isLoading, error } = useKiteablePercentage(spotId);

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

  // Sort dates and prepare data
  const sortedDates = Object.keys(data.daily_percentage).sort();
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

  return (
    <div className="h-full">
      <Line data={chartData} options={options} />
    </div>
  );
}

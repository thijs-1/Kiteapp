// Helpers to turn daily binned weather histograms into chart series.
import {
  sortDatesForRange,
  sortMonthsForRange,
  getAggregationLevel,
  groupDatesByWeek,
} from './dateUtils';

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatDateLabel(mmdd: string): string {
  const [month, day] = mmdd.split('-').map(Number);
  return `${MONTH_NAMES[month - 1]} ${day}`;
}

// Days within ±3 days are pooled at daily aggregation so 10 years of hourly
// samples per calendar day still yield a stable estimate (mirrors the ±2 week
// smoothing the wind charts get from the backend's moving-average endpoint).
const DAILY_SMOOTHING_RADIUS = 3;

export interface AggregatedCounts {
  labels: string[]; // X-axis labels per period
  counts: number[][]; // Summed histogram counts per period
  sortedDates: string[]; // Sorted MM-DD dates backing the date-range selector
  level: 'daily' | 'weekly' | 'monthly';
}

function sumCounts(rows: number[][]): number[] {
  if (rows.length === 0) return [];
  const total = new Array(rows[0].length).fill(0);
  for (const row of rows) {
    for (let i = 0; i < row.length; i++) {
      total[i] += row[i] || 0;
    }
  }
  return total;
}

/**
 * Aggregate per-day histogram counts into daily/weekly/monthly periods
 * depending on the length of the selected date range.
 */
export function aggregateDailyCounts(
  dailyData: Record<string, number[]>,
  startDate: string,
  endDate: string
): AggregatedCounts {
  const sortedDates = sortDatesForRange(Object.keys(dailyData), startDate, endDate);
  const level = getAggregationLevel(startDate, endDate);

  if (level === 'daily') {
    // Pool each day with its neighbours for a smoother line
    const counts = sortedDates.map((_, i) => {
      const windowRows = [];
      for (
        let j = Math.max(0, i - DAILY_SMOOTHING_RADIUS);
        j <= Math.min(sortedDates.length - 1, i + DAILY_SMOOTHING_RADIUS);
        j++
      ) {
        windowRows.push(dailyData[sortedDates[j]]);
      }
      return sumCounts(windowRows);
    });
    return {
      labels: sortedDates.map(formatDateLabel),
      counts,
      sortedDates,
      level,
    };
  }

  if (level === 'weekly') {
    const { weekData, sortedWeeks } = groupDatesByWeek(sortedDates, startDate, endDate);
    const counts = sortedWeeks.map((week) =>
      sumCounts(weekData[week].map((d) => dailyData[d]))
    );
    // Label weeks by mid-week date for clarity
    const labels = sortedWeeks.map((week) => {
      const weekDates = weekData[week];
      return formatDateLabel(weekDates[Math.floor(weekDates.length / 2)]);
    });
    return { labels, counts, sortedDates, level };
  }

  // Monthly
  const monthlyRows: Record<string, number[][]> = {};
  for (const date of sortedDates) {
    const month = date.split('-')[0];
    if (!monthlyRows[month]) monthlyRows[month] = [];
    monthlyRows[month].push(dailyData[date]);
  }
  const months = sortMonthsForRange(Object.keys(monthlyRows), startDate, endDate);
  return {
    labels: months.map((m) => MONTH_NAMES[parseInt(m) - 1]),
    counts: months.map((m) => sumCounts(monthlyRows[m])),
    sortedDates,
    level,
  };
}

/** Mean value of a histogram, using bin midpoints weighted by counts. */
export function weightedMean(counts: number[], bins: number[]): number | null {
  let total = 0;
  let sum = 0;
  for (let i = 0; i < counts.length; i++) {
    const midpoint = (bins[i] + bins[i + 1]) / 2;
    total += counts[i];
    sum += counts[i] * midpoint;
  }
  return total > 0 ? sum / total : null;
}

/**
 * Percentile (q in 0..1) of a histogram, linearly interpolated within the
 * bin where the cumulative count crosses the target.
 */
export function binnedPercentile(
  counts: number[],
  bins: number[],
  q: number
): number | null {
  const total = counts.reduce((sum, c) => sum + c, 0);
  if (total <= 0) return null;

  const target = q * total;
  let cumulative = 0;
  for (let i = 0; i < counts.length; i++) {
    if (cumulative + counts[i] >= target && counts[i] > 0) {
      const withinBin = (target - cumulative) / counts[i];
      return bins[i] + withinBin * (bins[i + 1] - bins[i]);
    }
    cumulative += counts[i];
  }
  return bins[bins.length - 1];
}

/** Percentage of observations in bins at or above the given bin index. */
export function percentAtOrAboveBin(counts: number[], fromBinIndex: number): number | null {
  const total = counts.reduce((sum, c) => sum + c, 0);
  if (total <= 0) return null;
  const above = counts.slice(fromBinIndex).reduce((sum, c) => sum + c, 0);
  return (above / total) * 100;
}

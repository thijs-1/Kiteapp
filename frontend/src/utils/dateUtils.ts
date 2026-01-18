/**
 * Sort dates (MM-DD format) chronologically for a given date range,
 * accounting for ranges that wrap around the year (e.g., Dec 15 - Jan 15).
 */
export function sortDatesForRange(
  dates: string[],
  startDate: string,
  endDate: string
): string[] {
  const isWrapping = startDate > endDate;

  if (!isWrapping) {
    return [...dates].sort();
  }

  // Year-wrapping range: dates >= startDate come first, then dates <= endDate
  return [...dates].sort((a, b) => {
    const aInFirstPart = a >= startDate;
    const bInFirstPart = b >= startDate;

    if (aInFirstPart && !bInFirstPart) return -1;
    if (!aInFirstPart && bInFirstPart) return 1;
    return a.localeCompare(b);
  });
}

/**
 * Sort month strings ("01"-"12") chronologically for a given date range,
 * accounting for ranges that wrap around the year.
 */
export function sortMonthsForRange(
  months: string[],
  startDate: string,
  endDate: string
): string[] {
  const startMonth = startDate.split('-')[0];
  const endMonth = endDate.split('-')[0];
  const isWrapping = startMonth > endMonth;

  if (!isWrapping) {
    return [...months].sort();
  }

  return [...months].sort((a, b) => {
    const aInFirstPart = a >= startMonth;
    const bInFirstPart = b >= startMonth;

    if (aInFirstPart && !bInFirstPart) return -1;
    if (!aInFirstPart && bInFirstPart) return 1;
    return a.localeCompare(b);
  });
}

/**
 * Calculate the duration of a date range in months.
 * Handles year-wrapping ranges (e.g., Dec 15 - Jan 15 = ~1 month).
 */
export function getDateRangeMonths(startDate: string, endDate: string): number {
  const [startMonth, startDay] = startDate.split('-').map(Number);
  const [endMonth, endDay] = endDate.split('-').map(Number);

  // Convert to day of year (approximate, treating all months as 30 days)
  const startDayOfYear = (startMonth - 1) * 30 + startDay;
  const endDayOfYear = (endMonth - 1) * 30 + endDay;

  let daysDiff: number;
  if (endDayOfYear >= startDayOfYear) {
    // Normal range (e.g., Jan - Mar)
    daysDiff = endDayOfYear - startDayOfYear + 1;
  } else {
    // Year-wrapping range (e.g., Nov - Feb)
    daysDiff = (360 - startDayOfYear) + endDayOfYear + 1;
  }

  return daysDiff / 30;
}

/**
 * Get the ISO week number for a date in MM-DD format.
 * Uses a reference year (2024, a leap year) for calculation.
 */
export function getWeekNumber(mmdd: string): number {
  const [month, day] = mmdd.split('-').map(Number);
  // Use 2024 as reference year (leap year to handle Feb 29)
  const date = new Date(2024, month - 1, day);
  const startOfYear = new Date(2024, 0, 1);
  const dayOfYear = Math.floor((date.getTime() - startOfYear.getTime()) / (24 * 60 * 60 * 1000));
  return Math.floor(dayOfYear / 7) + 1;
}

/**
 * Group dates by week and return sorted week labels.
 * Handles year-wrapping ranges.
 */
export function groupDatesByWeek(
  dates: string[],
  startDate: string,
  endDate: string
): { weekData: Record<string, string[]>; sortedWeeks: string[] } {
  const sortedDates = sortDatesForRange(dates, startDate, endDate);
  const weekData: Record<string, string[]> = {};

  for (const date of sortedDates) {
    const weekNum = getWeekNumber(date);
    const weekKey = `W${weekNum.toString().padStart(2, '0')}`;
    if (!weekData[weekKey]) {
      weekData[weekKey] = [];
    }
    weekData[weekKey].push(date);
  }

  // Sort weeks in order of first appearance (handles year-wrap)
  const sortedWeeks: string[] = [];
  const seenWeeks = new Set<string>();
  for (const date of sortedDates) {
    const weekNum = getWeekNumber(date);
    const weekKey = `W${weekNum.toString().padStart(2, '0')}`;
    if (!seenWeeks.has(weekKey)) {
      seenWeeks.add(weekKey);
      sortedWeeks.push(weekKey);
    }
  }

  return { weekData, sortedWeeks };
}

/**
 * Determine the aggregation level based on the date range.
 * - <= 3 months: daily
 * - > 3 months and <= 9 months: weekly
 * - > 9 months: monthly
 */
export function getAggregationLevel(startDate: string, endDate: string): 'daily' | 'weekly' | 'monthly' {
  const months = getDateRangeMonths(startDate, endDate);
  if (months <= 3) {
    return 'daily';
  } else if (months <= 9) {
    return 'weekly';
  } else {
    return 'monthly';
  }
}

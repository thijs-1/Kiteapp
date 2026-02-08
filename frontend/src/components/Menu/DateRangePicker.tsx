import { useFilterStore } from '../../store/filterStore';

const MONTHS = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' },
];

const MONTH_LAST_DAY = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

export function DateRangePicker() {
  const { startDate, endDate, setDateRange } = useFilterStore();

  // Extract month from MM-DD format
  const startMonth = parseInt(startDate.split('-')[0], 10);
  const endMonth = parseInt(endDate.split('-')[0], 10);

  const formatStart = (month: number) =>
    `${String(month).padStart(2, '0')}-01`;

  const formatEnd = (month: number) =>
    `${String(month).padStart(2, '0')}-${String(MONTH_LAST_DAY[month - 1]).padStart(2, '0')}`;

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        Season
      </label>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <span className="text-xs text-gray-500">From</span>
          <select
            value={startMonth}
            onChange={(e) =>
              setDateRange(formatStart(Number(e.target.value)), endDate)
            }
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-kite focus:border-transparent"
          >
            {MONTHS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-1">
          <span className="text-xs text-gray-500">To</span>
          <select
            value={endMonth}
            onChange={(e) =>
              setDateRange(startDate, formatEnd(Number(e.target.value)))
            }
            className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-kite focus:border-transparent"
          >
            {MONTHS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

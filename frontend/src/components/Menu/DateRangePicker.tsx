import { useFilterStore } from '../../store/filterStore';

// Month names for dropdown
const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

// Days 1-31
const DAYS = Array.from({ length: 31 }, (_, i) => i + 1);

export function DateRangePicker() {
  const { startDate, endDate, setDateRange } = useFilterStore();

  // Parse MM-DD format
  const parseDate = (date: string) => {
    const [month, day] = date.split('-').map(Number);
    return { month, day };
  };

  const start = parseDate(startDate);
  const end = parseDate(endDate);

  const formatDate = (month: number, day: number) => {
    return `${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        Date Range:
      </label>

      <div className="grid grid-cols-2 gap-4">
        {/* Start date */}
        <div className="space-y-1">
          <span className="text-xs text-gray-500">From</span>
          <div className="flex gap-1">
            <select
              value={start.month}
              onChange={(e) =>
                setDateRange(formatDate(Number(e.target.value), start.day), endDate)
              }
              className="flex-1 px-2 py-1 border rounded text-sm"
            >
              {MONTHS.map((name, idx) => (
                <option key={idx} value={idx + 1}>
                  {name}
                </option>
              ))}
            </select>
            <select
              value={start.day}
              onChange={(e) =>
                setDateRange(formatDate(start.month, Number(e.target.value)), endDate)
              }
              className="w-14 px-2 py-1 border rounded text-sm"
            >
              {DAYS.map((day) => (
                <option key={day} value={day}>
                  {day}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* End date */}
        <div className="space-y-1">
          <span className="text-xs text-gray-500">To</span>
          <div className="flex gap-1">
            <select
              value={end.month}
              onChange={(e) =>
                setDateRange(startDate, formatDate(Number(e.target.value), end.day))
              }
              className="flex-1 px-2 py-1 border rounded text-sm"
            >
              {MONTHS.map((name, idx) => (
                <option key={idx} value={idx + 1}>
                  {name}
                </option>
              ))}
            </select>
            <select
              value={end.day}
              onChange={(e) =>
                setDateRange(startDate, formatDate(end.month, Number(e.target.value)))
              }
              className="w-14 px-2 py-1 border rounded text-sm"
            >
              {DAYS.map((day) => (
                <option key={day} value={day}>
                  {day}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}

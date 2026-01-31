import { useRef, useState, useCallback, ReactNode } from 'react';
import { useFilterStore } from '../../../store/filterStore';

interface Props {
  children: ReactNode;
  dates: string[]; // Sorted array of MM-DD dates that map to chart x-axis
  disabled?: boolean;
}

const FULL_YEAR_START = '01-01';
const FULL_YEAR_END = '12-31';

export function ChartDateRangeSelector({ children, dates, disabled = false }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectionStart, setSelectionStart] = useState<number | null>(null);
  const [selectionEnd, setSelectionEnd] = useState<number | null>(null);
  const { startDate, endDate, setDateRange } = useFilterStore();

  const isZoomedIn = startDate !== FULL_YEAR_START || endDate !== FULL_YEAR_END;

  // Chart area margins (approximate - Chart.js default padding)
  const CHART_LEFT_MARGIN = 50;
  const CHART_RIGHT_MARGIN = 20;

  const getDateIndexFromX = useCallback(
    (clientX: number): number | null => {
      if (!containerRef.current || dates.length === 0) return null;

      const rect = containerRef.current.getBoundingClientRect();
      const chartWidth = rect.width - CHART_LEFT_MARGIN - CHART_RIGHT_MARGIN;
      const relativeX = clientX - rect.left - CHART_LEFT_MARGIN;

      if (relativeX < 0 || relativeX > chartWidth) return null;

      const index = Math.round((relativeX / chartWidth) * (dates.length - 1));
      return Math.max(0, Math.min(dates.length - 1, index));
    },
    [dates]
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (disabled) return;
      const index = getDateIndexFromX(e.clientX);
      if (index !== null) {
        setIsDragging(true);
        setSelectionStart(index);
        setSelectionEnd(index);
      }
    },
    [disabled, getDateIndexFromX]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging) return;
      const index = getDateIndexFromX(e.clientX);
      if (index !== null) {
        setSelectionEnd(index);
      }
    },
    [isDragging, getDateIndexFromX]
  );

  const handleMouseUp = useCallback(() => {
    if (!isDragging || selectionStart === null || selectionEnd === null) {
      setIsDragging(false);
      setSelectionStart(null);
      setSelectionEnd(null);
      return;
    }

    const startIdx = Math.min(selectionStart, selectionEnd);
    const endIdx = Math.max(selectionStart, selectionEnd);

    // Only update if selection spans at least a few days
    if (endIdx - startIdx >= 2) {
      const newStartDate = dates[startIdx];
      const newEndDate = dates[endIdx];
      setDateRange(newStartDate, newEndDate);
    }

    setIsDragging(false);
    setSelectionStart(null);
    setSelectionEnd(null);
  }, [isDragging, selectionStart, selectionEnd, dates, setDateRange]);

  const handleMouseLeave = useCallback(() => {
    if (isDragging) {
      handleMouseUp();
    }
  }, [isDragging, handleMouseUp]);

  const handleDoubleClick = useCallback(() => {
    if (disabled) return;
    // Reset to full year on double-click
    setDateRange(FULL_YEAR_START, FULL_YEAR_END);
  }, [disabled, setDateRange]);

  const handleReset = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setDateRange(FULL_YEAR_START, FULL_YEAR_END);
  }, [setDateRange]);

  // Touch event handlers for mobile support
  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      if (disabled || e.touches.length !== 1) return;
      const touch = e.touches[0];
      const index = getDateIndexFromX(touch.clientX);
      if (index !== null) {
        setIsDragging(true);
        setSelectionStart(index);
        setSelectionEnd(index);
      }
    },
    [disabled, getDateIndexFromX]
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (!isDragging || e.touches.length !== 1) return;
      // Prevent page scroll while dragging on chart
      e.preventDefault();
      const touch = e.touches[0];
      const index = getDateIndexFromX(touch.clientX);
      if (index !== null) {
        setSelectionEnd(index);
      }
    },
    [isDragging, getDateIndexFromX]
  );

  const handleTouchEnd = useCallback(() => {
    if (!isDragging || selectionStart === null || selectionEnd === null) {
      setIsDragging(false);
      setSelectionStart(null);
      setSelectionEnd(null);
      return;
    }

    const startIdx = Math.min(selectionStart, selectionEnd);
    const endIdx = Math.max(selectionStart, selectionEnd);

    // Only update if selection spans at least a few days
    if (endIdx - startIdx >= 2) {
      const newStartDate = dates[startIdx];
      const newEndDate = dates[endIdx];
      setDateRange(newStartDate, newEndDate);
    }

    setIsDragging(false);
    setSelectionStart(null);
    setSelectionEnd(null);
  }, [isDragging, selectionStart, selectionEnd, dates, setDateRange]);

  // Calculate selection overlay position
  const getSelectionStyle = (): React.CSSProperties | null => {
    if (!isDragging || selectionStart === null || selectionEnd === null || !containerRef.current) {
      return null;
    }

    const rect = containerRef.current.getBoundingClientRect();
    const chartWidth = rect.width - CHART_LEFT_MARGIN - CHART_RIGHT_MARGIN;

    const startIdx = Math.min(selectionStart, selectionEnd);
    const endIdx = Math.max(selectionStart, selectionEnd);

    const left = CHART_LEFT_MARGIN + (startIdx / (dates.length - 1)) * chartWidth;
    const right = CHART_LEFT_MARGIN + (endIdx / (dates.length - 1)) * chartWidth;

    return {
      left: `${left}px`,
      width: `${right - left}px`,
      top: '10px',
      bottom: '30px',
    };
  };

  const selectionStyle = getSelectionStyle();

  // Format selected range for display
  const getSelectionLabel = (): string | null => {
    if (selectionStart === null || selectionEnd === null) return null;

    const startIdx = Math.min(selectionStart, selectionEnd);
    const endIdx = Math.max(selectionStart, selectionEnd);
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    const formatDate = (mmdd: string) => {
      const [month, day] = mmdd.split('-').map(Number);
      return `${monthNames[month - 1]} ${day}`;
    };

    return `${formatDate(dates[startIdx])} - ${formatDate(dates[endIdx])}`;
  };

  // Format current date range for display
  const getCurrentRangeLabel = (): string => {
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const formatDate = (mmdd: string) => {
      const [month, day] = mmdd.split('-').map(Number);
      return `${monthNames[month - 1]} ${day}`;
    };
    return `${formatDate(startDate)} - ${formatDate(endDate)}`;
  };

  return (
    <div
      ref={containerRef}
      className="relative h-full select-none touch-none"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
      onDoubleClick={handleDoubleClick}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      style={{ cursor: disabled ? 'default' : 'crosshair' }}
    >
      {children}

      {/* Selection overlay */}
      {selectionStyle && (
        <div
          className="absolute bg-kite-pink/30 border-l-2 border-r-2 border-kite-pink pointer-events-none"
          style={selectionStyle}
        >
          {/* Selection label */}
          <div className="absolute top-1 left-1/2 -translate-x-1/2 bg-kite-pink text-white text-xs px-2 py-0.5 rounded whitespace-nowrap">
            {getSelectionLabel()}
          </div>
        </div>
      )}

      {/* Current range indicator and reset button when zoomed in */}
      {!disabled && !isDragging && isZoomedIn && (
        <div className="absolute top-1 left-14 flex items-center gap-2">
          <span className="text-xs text-gray-600 bg-white/80 px-1.5 py-0.5 rounded">
            {getCurrentRangeLabel()}
          </span>
          <button
            onClick={handleReset}
            className="text-xs text-kite-pink hover:text-kite-pink/80 bg-white/80 px-1.5 py-0.5 rounded hover:bg-white transition-colors"
            title="Reset to full year (or double-click)"
          >
            Reset
          </button>
        </div>
      )}

      {/* Drag hint */}
      {!disabled && !isDragging && (
        <div className="absolute -bottom-5 right-2 text-xs text-gray-400 pointer-events-none">
          {isZoomedIn ? 'Drag to zoom, double-click to reset' : 'Drag to select date range'}
        </div>
      )}
    </div>
  );
}

import { useRef, useState, useCallback, useEffect, ReactNode } from 'react';
import { Chart as ChartJS } from 'chart.js';
import { useFilterStore } from '../../../store/filterStore';
import { useIsMobile } from '../../../hooks/useIsMobile';

interface Props {
  children: ReactNode;
  dates: string[]; // Sorted array of MM-DD dates that map to chart x-axis
  disabled?: boolean;
}

const FULL_YEAR_START = '01-01';
const FULL_YEAR_END = '12-31';

export function ChartDateRangeSelector({ children, dates, disabled = false }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectionStart, setSelectionStart] = useState<number | null>(null);
  const [selectionEnd, setSelectionEnd] = useState<number | null>(null);
  const { startDate, endDate, setDateRange } = useFilterStore();
  const isMobile = useIsMobile();
  const [zoomMode, setZoomMode] = useState(false);

  // Use refs to track touch state for native event handlers
  const isDraggingRef = useRef(false);
  const selectionStartRef = useRef<number | null>(null);
  const selectionEndRef = useRef<number | null>(null);

  const isZoomedIn = startDate !== FULL_YEAR_START || endDate !== FULL_YEAR_END;

  // Track chart area bounds for overlay positioning
  const [overlayBounds, setOverlayBounds] = useState<{ left: number; right: number; top: number; bottom: number } | null>(null);

  // Get the actual chart area from the Chart.js instance
  const getChartArea = useCallback(() => {
    if (!containerRef.current) return null;
    const canvas = containerRef.current.querySelector('canvas');
    if (!canvas) return null;
    const chart = ChartJS.getChart(canvas);
    if (!chart || !chart.chartArea) return null;
    return chart.chartArea;
  }, []);

  // Update overlay bounds when chart renders or resizes
  useEffect(() => {
    const updateBounds = () => {
      const area = getChartArea();
      if (!area || !containerRef.current) return;
      const containerHeight = containerRef.current.getBoundingClientRect().height;
      setOverlayBounds({
        left: area.left,
        right: area.right,
        top: area.top,
        bottom: containerHeight - area.bottom,
      });
    };

    // Initial update after chart renders
    const timer = setTimeout(updateBounds, 100);

    // Update on resize
    const observer = new ResizeObserver(updateBounds);
    if (containerRef.current) observer.observe(containerRef.current);

    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [getChartArea, dates, startDate, endDate]);

  const getDateIndexFromX = useCallback(
    (clientX: number): number | null => {
      if (!containerRef.current || dates.length === 0) return null;

      const chartArea = getChartArea();
      if (!chartArea) return null;

      const rect = containerRef.current.getBoundingClientRect();
      const relativeX = clientX - rect.left - chartArea.left;
      const chartWidth = chartArea.right - chartArea.left;

      if (relativeX < 0 || relativeX > chartWidth) return null;

      const index = Math.round((relativeX / chartWidth) * (dates.length - 1));
      return Math.max(0, Math.min(dates.length - 1, index));
    },
    [dates, getChartArea]
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
      setZoomMode(false);
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

  // Native touch event handlers for mobile support
  // Using native events with { passive: false } to allow preventDefault()
  // Attached to overlay element which sits above the Chart.js canvas
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;

    const handleTouchStart = (e: TouchEvent) => {
      if (disabled || e.touches.length !== 1) return;
      const touch = e.touches[0];
      const index = getDateIndexFromX(touch.clientX);
      if (index !== null) {
        // Stop propagation to prevent Carousel swipe from interfering
        e.stopPropagation();
        isDraggingRef.current = true;
        selectionStartRef.current = index;
        selectionEndRef.current = index;
        setIsDragging(true);
        setSelectionStart(index);
        setSelectionEnd(index);
      }
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!isDraggingRef.current || e.touches.length !== 1) return;
      // Prevent page scroll while dragging on chart
      e.preventDefault();
      const touch = e.touches[0];
      const index = getDateIndexFromX(touch.clientX);
      if (index !== null) {
        selectionEndRef.current = index;
        setSelectionEnd(index);
      }
    };

    const handleTouchEnd = (e: TouchEvent) => {
      // Stop propagation to prevent Carousel swipe from interfering
      e.stopPropagation();

      if (!isDraggingRef.current || selectionStartRef.current === null || selectionEndRef.current === null) {
        isDraggingRef.current = false;
        selectionStartRef.current = null;
        selectionEndRef.current = null;
        setIsDragging(false);
        setSelectionStart(null);
        setSelectionEnd(null);
        return;
      }

      const startIdx = Math.min(selectionStartRef.current, selectionEndRef.current);
      const endIdx = Math.max(selectionStartRef.current, selectionEndRef.current);

      // Only update if selection spans at least a few days
      if (endIdx - startIdx >= 2) {
        const newStartDate = dates[startIdx];
        const newEndDate = dates[endIdx];
        setDateRange(newStartDate, newEndDate);
        setZoomMode(false);
      }

      isDraggingRef.current = false;
      selectionStartRef.current = null;
      selectionEndRef.current = null;
      setIsDragging(false);
      setSelectionStart(null);
      setSelectionEnd(null);
    };

    // Attach with { passive: false } to allow preventDefault() in touchmove
    overlay.addEventListener('touchstart', handleTouchStart, { passive: true });
    overlay.addEventListener('touchmove', handleTouchMove, { passive: false });
    overlay.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      overlay.removeEventListener('touchstart', handleTouchStart);
      overlay.removeEventListener('touchmove', handleTouchMove);
      overlay.removeEventListener('touchend', handleTouchEnd);
    };
  }, [disabled, dates, getDateIndexFromX, setDateRange]);

  // Calculate selection overlay position
  const getSelectionStyle = (): React.CSSProperties | null => {
    if (!isDragging || selectionStart === null || selectionEnd === null || !containerRef.current) {
      return null;
    }

    const chartArea = getChartArea();
    if (!chartArea) return null;

    const chartWidth = chartArea.right - chartArea.left;

    const startIdx = Math.min(selectionStart, selectionEnd);
    const endIdx = Math.max(selectionStart, selectionEnd);

    const left = chartArea.left + (startIdx / (dates.length - 1)) * chartWidth;
    const right = chartArea.left + (endIdx / (dates.length - 1)) * chartWidth;

    return {
      left: `${left}px`,
      width: `${right - left}px`,
      top: `${chartArea.top}px`,
      bottom: `${containerRef.current.getBoundingClientRect().height - chartArea.bottom}px`,
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
      className="relative h-full select-none"
      style={{ touchAction: 'none' }}
    >
      {children}

      {/* Transparent overlay to capture touch/mouse events above the chart area only */}
      <div
        ref={overlayRef}
        className="absolute"
        style={{
          left: overlayBounds ? `${overlayBounds.left}px` : 0,
          top: overlayBounds ? `${overlayBounds.top}px` : 0,
          bottom: overlayBounds ? `${overlayBounds.bottom}px` : 0,
          width: overlayBounds ? `${overlayBounds.right - overlayBounds.left}px` : '100%',
          cursor: disabled ? 'default' : 'crosshair',
          touchAction: 'none',
          pointerEvents: (!isMobile || zoomMode) ? 'auto' : 'none',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onDoubleClick={handleDoubleClick}
      />

      {/* Selection overlay */}
      {selectionStyle && (
        <div
          className="absolute bg-kite/30 border-l-2 border-r-2 border-kite pointer-events-none"
          style={selectionStyle}
        >
          {/* Selection label */}
          <div className="absolute top-1 left-1/2 -translate-x-1/2 bg-kite text-white text-xs px-2 py-0.5 rounded whitespace-nowrap">
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
            className="text-xs text-kite hover:text-kite/80 bg-white/80 px-1.5 py-0.5 rounded hover:bg-white transition-colors"
            title="Reset to full year (or double-click)"
          >
            Reset
          </button>
        </div>
      )}

      {/* Zoom toggle button (mobile only) */}
      {!disabled && isMobile && (
        <button
          onClick={(e) => { e.stopPropagation(); setZoomMode((v) => !v); }}
          className={`absolute top-1 right-1 z-10 w-8 h-8 flex items-center justify-center rounded-full transition-colors ${
            zoomMode ? 'bg-kite text-white' : 'bg-white/80 text-gray-400 border border-gray-200'
          }`}
          aria-label={zoomMode ? 'Disable date zoom' : 'Enable date zoom'}
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
          </svg>
        </button>
      )}

      {/* Drag hint */}
      {!disabled && !isDragging && (
        <div className={`absolute left-1/2 -translate-x-1/2 text-xs text-gray-400 bg-white/90 px-2 py-0.5 rounded pointer-events-none whitespace-nowrap ${isMobile ? '-bottom-2' : 'bottom-1'}`}>
          {isMobile
            ? (isZoomedIn ? 'Tap 🔍 to zoom, double-tap to reset' : 'Tap 🔍 to select date range')
            : (isZoomedIn ? 'Drag to zoom, double-click to reset' : 'Drag to select date range')
          }
        </div>
      )}
    </div>
  );
}

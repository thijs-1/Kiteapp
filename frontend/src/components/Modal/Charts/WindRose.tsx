import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  SubTitle,
  ChartOptions,
} from 'chart.js';
import { Radar } from 'react-chartjs-2';
import { useWindRoseData } from '../../../hooks/useHistogram';
import { useSpotStore } from '../../../store/spotStore';
import { WIND_COLORS } from '../../../utils/windColors';
import { useIsMobile } from '../../../hooks/useIsMobile';

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend, SubTitle);

// Direction labels for 36 sectors (10 degrees each)
// Only label the 4 cardinal directions: N=0, E=9, S=18, W=27
const DIRECTION_LABELS = [
  'N',  '', '', '', '', '', '', '', '',
  'E',  '', '', '', '', '', '', '', '',
  'S',  '', '', '', '', '', '', '', '',
  'W',  '', '', '', '', '', '', '', '',
];

// Half-width of the map box around the spot, in meters
const MAP_HALF_BOX_M = 500;
const METERS_PER_DEGREE_LAT = 111320;
// Fixed export resolution so the image URL (and browser cache entry) is
// stable across container resizes; ~1 m/px for the ±500m box
const MAP_IMAGE_PX = 1024;

const hexToRgba = (hex: string, alpha: number): string => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

interface Props {
  spotId: string;
}

export function WindRose({ spotId }: Props) {
  const { data, isLoading, error } = useWindRoseData(spotId);
  const isMobile = useIsMobile();
  const selectedSpot = useSpotStore((s) => s.selectedSpot);
  const [showMap, setShowMap] = useState(false);

  // Square overlay size: largest square that fits the chart container
  const containerRef = useRef<HTMLDivElement>(null);
  const [side, setSide] = useState(0);
  useEffect(() => {
    const el = containerRef.current;
    if (!showMap || !el) return;
    const update = () => setSide(Math.floor(Math.min(el.clientWidth, el.clientHeight)));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, [showMap]);

  const spot = selectedSpot && selectedSpot.spot_id === spotId ? selectedSpot : null;

  // Single static satellite image of the ±500m box instead of an interactive
  // map: one cacheable request, no tile churn. The spot sits at the center.
  const mapImageUrl = useMemo(() => {
    if (!spot) return null;
    const latDelta = MAP_HALF_BOX_M / METERS_PER_DEGREE_LAT;
    const lngDelta =
      MAP_HALF_BOX_M / (METERS_PER_DEGREE_LAT * Math.cos((spot.latitude * Math.PI) / 180));
    const bbox = [
      spot.longitude - lngDelta,
      spot.latitude - latDelta,
      spot.longitude + lngDelta,
      spot.latitude + latDelta,
    ].join(',');
    return (
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export' +
      `?bbox=${bbox}&bboxSR=4326&imageSR=3857&size=${MAP_IMAGE_PX},${MAP_IMAGE_PX}` +
      '&format=jpg&f=image'
    );
  }, [spot]);

  // Only show the spinner on first load; during refetches the stale rose (and
  // the map, which doesn't depend on histogram data) stays mounted
  if (isLoading && !data) {
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

  const numStrengthBins = data.data.length;
  const numDirections = data.direction_bins.length - 1;
  const mapMode = showMap && spot !== null && mapImageUrl !== null;

  // Create bin labels for legend
  const getBinLabel = (binIdx: number): string => {
    const low = data.strength_bins[binIdx];
    const high = data.strength_bins[binIdx + 1];
    if (high === undefined || high > 99) {
      return `${low}+ kts`;
    }
    return `${low}-${high} kts`;
  };

  // Build cumulative datasets for stacked radar effect
  // Each dataset contains cumulative values, fill: '-1' fills the gap
  const datasets: {
    label: string;
    data: number[];
    backgroundColor: string;
    borderColor: string;
    borderWidth: number;
    pointRadius: number;
    fill: string;
  }[] = [];
  let cumulativeData = new Array(numDirections).fill(0);

  for (let s = 0; s < numStrengthBins; s++) {
    // Add this bin's values to cumulative
    const newCumulative = cumulativeData.map((val, d) => val + (data.data[s][d] || 0));

    datasets.push({
      label: getBinLabel(s),
      // Semi-transparent fills in map mode so the shoreline stays visible
      data: newCumulative,
      backgroundColor: mapMode
        ? hexToRgba(WIND_COLORS[s] || '#999999', 0.55)
        : WIND_COLORS[s] || '#999',
      borderColor: 'rgba(255, 255, 255, 0.5)',
      borderWidth: 0.5,
      pointRadius: 0,
      fill: s === 0 ? 'origin' : '-1',
    });

    cumulativeData = newCumulative;
  }

  const chartData = {
    labels: DIRECTION_LABELS.slice(0, numDirections),
    datasets,
  };

  // Plugin to balance the right legend by adding equal left padding
  const balanceLegendPlugin = {
    id: 'balanceLegend',
    afterLayout(chart: ChartJS) {
      if (isMobile) return;
      const legendWidth = chart.legend?.width || 0;
      if (legendWidth > 0 && chart.options.layout?.padding !== undefined) {
        const padding = chart.options.layout.padding as { left: number };
        if (padding.left !== legendWidth) {
          padding.left = legendWidth;
          chart.update('none');
        }
      }
    },
  };

  const options: ChartOptions<'radar'> = {
    responsive: true,
    maintainAspectRatio: false,
    layout: {
      padding: { left: 0 },
    },
    plugins: {
      subtitle: {
        // Hidden in map mode so the rose stays centered on the spot
        display: !mapMode,
        text: '* Wind direction shows where wind is going TO (not from)',
        position: 'bottom' as const,
        font: { size: 11 },
        color: '#6b7280',
        padding: { top: 4 },
      },
      legend: {
        display: !mapMode,
        position: isMobile ? 'bottom' as const : 'right' as const,
        labels: {
          boxWidth: isMobile ? 8 : 12,
          font: { size: isMobile ? 8 : 9 },
          padding: isMobile ? 4 : 10,
        },
      },
      tooltip: {
        callbacks: {
          label: (item) => {
            // Show the actual bin value, not cumulative
            const binIdx = datasets.findIndex(d => d.label === item.dataset.label);
            const dirIdx = item.dataIndex;
            const actualValue = data.data[binIdx]?.[dirIdx] || 0;
            return `${item.dataset.label}: ${actualValue.toFixed(1)}%`;
          },
        },
      },
    },
    scales: {
      r: {
        beginAtZero: true,
        ticks: {
          display: false,
        },
        pointLabels: mapMode
          ? {
              color: '#ffffff',
              font: { size: 12, weight: 'bold' as const },
              // Only the labeled cardinal directions get a backdrop;
              // empty labels would otherwise draw small dark boxes
              backdropColor: (ctx: { label?: string }) =>
                ctx.label ? 'rgba(0, 0, 0, 0.45)' : 'transparent',
              backdropPadding: 3,
            }
          : {
              font: {
                size: 10,
              },
            },
        grid: {
          color: mapMode ? 'rgba(255, 255, 255, 0.45)' : 'rgba(0, 0, 0, 0.2)',
          lineWidth: mapMode ? 1 : 2,
        },
        angleLines: {
          color: mapMode ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.15)',
          lineWidth: 1,
        },
      },
    },
  };

  return (
    <div ref={containerRef} className="relative h-full w-full">
      {spot && (
        <button
          onClick={() => setShowMap((v) => !v)}
          className={`absolute top-1 right-1 z-[700] w-8 h-8 flex items-center justify-center rounded-full transition-colors touch-manipulation ${
            showMap
              ? 'bg-kite text-white'
              : 'bg-white/80 text-gray-400 border border-gray-200'
          }`}
          aria-label="Toggle spot map background"
          aria-pressed={showMap}
          title="Show the spot on a map (±500 m) to judge onshore/offshore wind"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
            />
          </svg>
        </button>
      )}

      {mapMode ? (
        <div className="absolute inset-0 flex items-center justify-center">
          {side > 0 && (
            <div
              className="relative rounded-lg overflow-hidden border border-gray-200 bg-gray-300"
              style={{ width: side, height: side }}
            >
              <img
                src={mapImageUrl}
                alt={`Satellite view of ${spot.name}`}
                className="absolute inset-0 h-full w-full object-cover"
                draggable={false}
                onError={(e) => (e.currentTarget.style.visibility = 'hidden')}
                onLoad={(e) => (e.currentTarget.style.visibility = 'visible')}
              />

              {/* Spot marker: the spot is the center of the bbox by construction */}
              <div
                className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full pointer-events-none"
                style={{ backgroundColor: '#F97316', border: '2px solid #EA580C' }}
              />

              {/* Wind rose superimposed, its center on the spot */}
              <div className="absolute inset-0">
                <Radar data={chartData} options={options} />
              </div>

              <div className="absolute top-1 left-1 bg-black/50 text-white text-[10px] px-1.5 py-0.5 rounded pointer-events-none">
                box ±500 m · wind blows toward
              </div>

              <div className="absolute bottom-0 right-0 bg-white/70 text-gray-700 text-[9px] px-1 rounded-tl pointer-events-none">
                Imagery &copy; Esri
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="h-full">
          <Radar data={chartData} options={options} plugins={[balanceLegendPlugin]} />
        </div>
      )}
    </div>
  );
}

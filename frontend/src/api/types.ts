// API types matching backend schemas

export interface Spot {
  spot_id: string;
  name: string;
  latitude: number;
  longitude: number;
  country: string | null;
}

export interface SpotWithStats extends Spot {
  kiteable_percentage: number;
}

export interface SpotFilters {
  wind_min: number;
  wind_max: number;
  start_date: string;
  end_date: string;
  country?: string;
  name?: string;
  min_percentage: number;
}

export interface HistogramData {
  spot_id: string;
  bins: number[];
  daily_data: Record<string, number[]>;
}

export interface KiteablePercentageData {
  spot_id: string;
  wind_min: number;
  wind_max: number;
  daily_percentage: Record<string, number>;
}

export interface WindRoseData {
  spot_id: string;
  strength_bins: number[];
  direction_bins: number[];
  data: number[][];
}

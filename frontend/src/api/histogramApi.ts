import { api } from './index';
import type { HistogramData, KiteablePercentageData, WindRoseData, DailyWindProfileData } from './types';

export interface DateRangeParams {
  start_date?: string;
  end_date?: string;
}

export interface KiteableParams extends DateRangeParams {
  wind_min?: number;
  wind_max?: number;
  moving_average?: boolean;
  window_weeks?: number;
}

export const histogramApi = {
  /**
   * Get daily histograms for a spot
   */
  getDailyHistograms: async (
    spotId: string,
    params: DateRangeParams = {}
  ): Promise<HistogramData> => {
    const { data } = await api.get<HistogramData>(
      `/spots/${spotId}/histograms/daily`,
      { params }
    );
    return data;
  },

  /**
   * Get moving average histograms for a spot
   */
  getMovingAverageHistograms: async (
    spotId: string,
    params: DateRangeParams & { window_weeks?: number } = {}
  ): Promise<HistogramData> => {
    const { data } = await api.get<HistogramData>(
      `/spots/${spotId}/histograms/moving-average`,
      { params }
    );
    return data;
  },

  /**
   * Get kiteable percentage for a spot
   */
  getKiteablePercentage: async (
    spotId: string,
    params: KiteableParams = {}
  ): Promise<KiteablePercentageData> => {
    const { data } = await api.get<KiteablePercentageData>(
      `/spots/${spotId}/histograms/kiteable-percentage`,
      { params }
    );
    return data;
  },

  /**
   * Get wind rose data for a spot
   */
  getWindRose: async (
    spotId: string,
    params: DateRangeParams = {}
  ): Promise<WindRoseData> => {
    const { data } = await api.get<WindRoseData>(
      `/spots/${spotId}/windrose`,
      { params }
    );
    return data;
  },

  /**
   * Get daily wind profiles (dawn-to-dusk) for a spot
   */
  getDailyWindProfiles: async (
    spotId: string,
    params: DateRangeParams = {}
  ): Promise<DailyWindProfileData> => {
    const { data } = await api.get<DailyWindProfileData>(
      `/spots/${spotId}/daily-wind-profiles`,
      { params }
    );
    return data;
  },
};

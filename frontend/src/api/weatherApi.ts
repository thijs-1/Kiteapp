import { api } from './index';
import type { WeatherHistogramData, WeatherVariable } from './types';
import type { DateRangeParams } from './histogramApi';

export const weatherApi = {
  /**
   * Get daily daytime weather histograms (temperature or precipitation) for a spot
   */
  getWeatherHistograms: async (
    spotId: string,
    variable: WeatherVariable,
    params: DateRangeParams = {}
  ): Promise<WeatherHistogramData> => {
    const { data } = await api.get<WeatherHistogramData>(
      `/spots/${spotId}/weather/${variable}/daily`,
      { params }
    );
    return data;
  },
};

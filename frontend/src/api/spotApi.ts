import { api } from './index';
import type { Spot, SpotDetail, SpotsMeta, SpotWithStats, SpotFilters } from './types';

export const spotApi = {
  /**
   * Get filtered spots based on wind conditions
   */
  getFilteredSpots: async (filters: Partial<SpotFilters>, signal?: AbortSignal): Promise<SpotWithStats[]> => {
    const params = {
      wind_min: filters.wind_min ?? 0,
      wind_max: filters.wind_max ?? 100,
      start_date: filters.start_date ?? '01-01',
      end_date: filters.end_date ?? '12-31',
      min_percentage: filters.min_percentage ?? 75,
      ...(filters.country && { country: filters.country }),
      ...(filters.name && { name: filters.name }),
      ...(filters.max_airport_distance_km !== undefined && {
        max_airport_distance_km: filters.max_airport_distance_km,
      }),
    };
    const { data } = await api.get<SpotWithStats[]>('/spots', { params, signal });
    return data;
  },

  /**
   * Get all spots without filtering
   */
  getAllSpots: async (): Promise<Spot[]> => {
    const { data } = await api.get<Spot[]>('/spots/all');
    return data;
  },

  /**
   * Get a single spot by ID, including its nearest airports
   */
  getSpot: async (spotId: string): Promise<SpotDetail> => {
    const { data } = await api.get<SpotDetail>(`/spots/${spotId}`);
    return data;
  },

  /**
   * Get list of all countries
   */
  getCountries: async (): Promise<string[]> => {
    const { data } = await api.get<string[]>('/spots/countries');
    return data;
  },

  /**
   * Get dataset-level metadata (e.g. whether airport data is available)
   */
  getMeta: async (): Promise<SpotsMeta> => {
    const { data } = await api.get<SpotsMeta>('/spots/meta');
    return data;
  },
};

import { api } from './index';
import type { Spot, SpotWithStats, SpotFilters } from './types';

export const spotApi = {
  /**
   * Get filtered spots based on wind conditions
   */
  getFilteredSpots: async (filters: Partial<SpotFilters>): Promise<SpotWithStats[]> => {
    const params = {
      wind_min: filters.wind_min ?? 0,
      wind_max: filters.wind_max ?? 100,
      start_date: filters.start_date ?? '01-01',
      end_date: filters.end_date ?? '12-31',
      min_percentage: filters.min_percentage ?? 75,
      sustained_wind_min: filters.sustained_wind_min ?? 0,
      ...(filters.country && { country: filters.country }),
      ...(filters.name && { name: filters.name }),
    };
    const { data } = await api.get<SpotWithStats[]>('/spots', { params });
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
   * Get a single spot by ID
   */
  getSpot: async (spotId: string): Promise<Spot> => {
    const { data } = await api.get<Spot>(`/spots/${spotId}`);
    return data;
  },

  /**
   * Get list of all countries
   */
  getCountries: async (): Promise<string[]> => {
    const { data } = await api.get<string[]>('/spots/countries');
    return data;
  },
};

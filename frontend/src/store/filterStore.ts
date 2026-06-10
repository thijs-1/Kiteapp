import { create } from 'zustand';

interface FilterState {
  // Filter values
  windMin: number;
  windMax: number;
  startDate: string;
  endDate: string;
  minPercentage: number;
  searchName: string;
  maxAirportDistance: number; // km; AIRPORT_DISTANCE_NO_LIMIT means "no filter"

  // Actions
  setWindRange: (min: number, max: number) => void;
  setDateRange: (start: string, end: string) => void;
  setMinPercentage: (percentage: number) => void;
  setSearchName: (name: string) => void;
  setMaxAirportDistance: (km: number) => void;
  resetFilters: () => void;
}

export const AIRPORT_DISTANCE_NO_LIMIT = 500;

export const defaultFilters = {
  windMin: 15,
  windMax: 100, // 100 represents infinity
  startDate: '01-01',
  endDate: '12-31',
  minPercentage: 50,
  searchName: '',
  maxAirportDistance: AIRPORT_DISTANCE_NO_LIMIT,
};

export const useFilterStore = create<FilterState>((set) => ({
  ...defaultFilters,

  setWindRange: (min, max) => set({ windMin: min, windMax: max }),

  setDateRange: (start, end) => set({ startDate: start, endDate: end }),

  setMinPercentage: (percentage) => set({ minPercentage: percentage }),

  setSearchName: (name) => set({ searchName: name }),

  setMaxAirportDistance: (km) => set({ maxAirportDistance: km }),

  resetFilters: () => set(defaultFilters),
}));

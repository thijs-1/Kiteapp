import { create } from 'zustand';

interface FilterState {
  // Filter values
  windMin: number;
  windMax: number;
  startDate: string;
  endDate: string;
  minPercentage: number;
  searchName: string;

  // Actions
  setWindRange: (min: number, max: number) => void;
  setDateRange: (start: string, end: string) => void;
  setMinPercentage: (percentage: number) => void;
  setSearchName: (name: string) => void;
  resetFilters: () => void;
}

export const defaultFilters = {
  windMin: 15,
  windMax: 100, // 100 represents infinity
  startDate: '01-01',
  endDate: '12-31',
  minPercentage: 50,
  searchName: '',
};

export const useFilterStore = create<FilterState>((set) => ({
  ...defaultFilters,

  setWindRange: (min, max) => set({ windMin: min, windMax: max }),

  setDateRange: (start, end) => set({ startDate: start, endDate: end }),

  setMinPercentage: (percentage) => set({ minPercentage: percentage }),

  setSearchName: (name) => set({ searchName: name }),

  resetFilters: () => set(defaultFilters),
}));

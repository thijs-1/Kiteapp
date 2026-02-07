import { create } from 'zustand';

export type WindMode = 'hourly' | 'sustained';

interface FilterState {
  // Filter values
  windMin: number;
  windMax: number;
  startDate: string;
  endDate: string;
  country: string | null;
  spotName: string;
  minPercentage: number;
  sustainedWindMin: number;
  sustainedWindDaysMin: number;
  windMode: WindMode;

  // Actions
  setWindRange: (min: number, max: number) => void;
  setDateRange: (start: string, end: string) => void;
  setCountry: (country: string | null) => void;
  setSpotName: (name: string) => void;
  setMinPercentage: (percentage: number) => void;
  setSustainedWindMin: (threshold: number) => void;
  setSustainedWindDaysMin: (percentage: number) => void;
  setWindMode: (mode: WindMode) => void;
  resetFilters: () => void;
}

const defaultFilters = {
  windMin: 0,
  windMax: 100, // 100 represents infinity
  startDate: '01-01',
  endDate: '12-31',
  country: null as string | null,
  spotName: '',
  minPercentage: 75,
  sustainedWindMin: 0,
  sustainedWindDaysMin: 50,
  windMode: 'hourly' as WindMode,
};

export const useFilterStore = create<FilterState>((set) => ({
  ...defaultFilters,

  setWindRange: (min, max) => set({ windMin: min, windMax: max }),

  setDateRange: (start, end) => set({ startDate: start, endDate: end }),

  setCountry: (country) => set({ country }),

  setSpotName: (name) => set({ spotName: name }),

  setMinPercentage: (percentage) => set({ minPercentage: percentage }),

  setSustainedWindMin: (threshold) => set({ sustainedWindMin: threshold }),

  setSustainedWindDaysMin: (percentage) => set({ sustainedWindDaysMin: percentage }),

  setWindMode: (mode) =>
    set(
      mode === 'hourly'
        ? { windMode: mode, sustainedWindMin: 0, sustainedWindDaysMin: 50 }
        : { windMode: mode, minPercentage: 0 }
    ),

  resetFilters: () => set(defaultFilters),
}));

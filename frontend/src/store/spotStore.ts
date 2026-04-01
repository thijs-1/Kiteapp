import { create } from 'zustand';
import type { SpotWithStats } from '../api/types';
import { setSpotIdInUrl } from '../hooks/useSpotUrl';

interface SpotState {
  // Spots data
  spots: SpotWithStats[];
  selectedSpot: SpotWithStats | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  setSpots: (spots: SpotWithStats[]) => void;
  selectSpot: (spot: SpotWithStats | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useSpotStore = create<SpotState>((set) => ({
  spots: [],
  selectedSpot: null,
  isLoading: false,
  error: null,

  setSpots: (spots) => set({ spots, error: null }),

  selectSpot: (spot) => {
    set({ selectedSpot: spot });
    setSpotIdInUrl(spot?.spot_id ?? null);
  },

  setLoading: (isLoading) => set({ isLoading }),

  setError: (error) => set({ error, isLoading: false }),
}));

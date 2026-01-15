import { useEffect, useCallback } from 'react';
import { useFilterStore } from '../store/filterStore';
import { useSpotStore } from '../store/spotStore';
import { spotApi } from '../api/spotApi';

export function useFilteredSpots() {
  const filters = useFilterStore();
  const { spots, isLoading, error, setSpots, setLoading, setError } = useSpotStore();

  const fetchSpots = useCallback(async () => {
    setLoading(true);
    try {
      const data = await spotApi.getFilteredSpots({
        wind_min: filters.windMin,
        wind_max: filters.windMax,
        start_date: filters.startDate,
        end_date: filters.endDate,
        country: filters.country || undefined,
        name: filters.spotName || undefined,
        min_percentage: filters.minPercentage,
      });
      setSpots(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch spots');
    }
  }, [
    filters.windMin,
    filters.windMax,
    filters.startDate,
    filters.endDate,
    filters.country,
    filters.spotName,
    filters.minPercentage,
    setSpots,
    setLoading,
    setError,
  ]);

  useEffect(() => {
    fetchSpots();
  }, [fetchSpots]);

  return { spots, isLoading, error, refetch: fetchSpots };
}

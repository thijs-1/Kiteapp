import { useEffect, useRef, useCallback } from 'react';
import { useFilterStore } from '../store/filterStore';
import { useSpotStore } from '../store/spotStore';
import { spotApi } from '../api/spotApi';

const DEBOUNCE_MS = 250;

export function useFilteredSpots() {
  const filters = useFilterStore();
  const { spots, isLoading, error, setSpots, setLoading, setError } = useSpotStore();
  const abortControllerRef = useRef<AbortController | null>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchSpots = useCallback(async (signal: AbortSignal) => {
    setLoading(true);
    try {
      const data = await spotApi.getFilteredSpots(
        {
          wind_min: filters.windMin,
          wind_max: filters.windMax,
          start_date: filters.startDate,
          end_date: filters.endDate,
          min_percentage: filters.minPercentage,
        },
        signal,
      );
      if (!signal.aborted) {
        setSpots(data);
        setLoading(false);
      }
    } catch (err) {
      if (signal.aborted) return;
      setError(err instanceof Error ? err.message : 'Failed to fetch spots');
    }
  }, [
    filters.windMin,
    filters.windMax,
    filters.startDate,
    filters.endDate,
    filters.minPercentage,
    setSpots,
    setLoading,
    setError,
  ]);

  useEffect(() => {
    // Clear any pending debounce timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      // Abort any in-flight request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;
      fetchSpots(controller.signal);
    }, DEBOUNCE_MS);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [fetchSpots]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const refetch = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;
    fetchSpots(controller.signal);
  }, [fetchSpots]);

  return { spots, isLoading, error, refetch };
}

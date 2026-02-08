import { useState, useEffect } from 'react';
import { useFilterStore } from '../store/filterStore';
import { histogramApi } from '../api/histogramApi';
import type { KiteablePercentageData, HistogramData, WindRoseData, DailyWindProfileData } from '../api/types';

export function useKiteablePercentage(spotId: string | null) {
  const { windMin, windMax, startDate, endDate } = useFilterStore();
  const [data, setData] = useState<KiteablePercentageData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!spotId) {
      setData(null);
      return;
    }

    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await histogramApi.getKiteablePercentage(spotId, {
          wind_min: windMin,
          wind_max: windMax,
          start_date: startDate,
          end_date: endDate,
          moving_average: true,
          window_weeks: 2,
        });
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [spotId, windMin, windMax, startDate, endDate]);

  return { data, isLoading, error };
}

export function useHistogramData(spotId: string | null) {
  const { startDate, endDate } = useFilterStore();
  const [data, setData] = useState<HistogramData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!spotId) {
      setData(null);
      return;
    }

    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await histogramApi.getMovingAverageHistograms(spotId, {
          start_date: startDate,
          end_date: endDate,
          window_weeks: 2,
        });
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [spotId, startDate, endDate]);

  return { data, isLoading, error };
}

export function useWindRoseData(spotId: string | null) {
  const { startDate, endDate } = useFilterStore();
  const [data, setData] = useState<WindRoseData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!spotId) {
      setData(null);
      return;
    }

    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await histogramApi.getWindRose(spotId, {
          start_date: startDate,
          end_date: endDate,
        });
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [spotId, startDate, endDate]);

  return { data, isLoading, error };
}

export function useDailyWindProfiles(spotId: string | null) {
  const { startDate, endDate } = useFilterStore();
  const [data, setData] = useState<DailyWindProfileData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!spotId) {
      setData(null);
      return;
    }

    const fetchData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const result = await histogramApi.getDailyWindProfiles(spotId, {
          start_date: startDate,
          end_date: endDate,
        });
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [spotId, startDate, endDate]);

  return { data, isLoading, error };
}

import { useState, useEffect } from 'react';
import { useFilterStore } from '../store/filterStore';
import { weatherApi } from '../api/weatherApi';
import type { WeatherHistogramData, WeatherVariable } from '../api/types';

export function useWeatherHistogram(
  spotId: string | null,
  variable: WeatherVariable
) {
  const { startDate, endDate } = useFilterStore();
  const [data, setData] = useState<WeatherHistogramData | null>(null);
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
        const result = await weatherApi.getWeatherHistograms(spotId, variable, {
          start_date: startDate,
          end_date: endDate,
        });
        setData(result);
      } catch (err) {
        // A 404 means the weather data files haven't been generated yet;
        // charts render this as the regular "No data available" state.
        setData(null);
        setError(err instanceof Error ? err.message : 'Failed to fetch data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [spotId, variable, startDate, endDate]);

  return { data, isLoading, error };
}

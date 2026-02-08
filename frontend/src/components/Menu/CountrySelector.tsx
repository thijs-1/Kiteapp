import { useState, useEffect } from 'react';
import { useFilterStore } from '../../store/filterStore';
import { spotApi } from '../../api/spotApi';

export function CountrySelector() {
  const { country, setCountry } = useFilterStore();
  const [countries, setCountries] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchCountries = async () => {
      try {
        const data = await spotApi.getCountries();
        setCountries(data);
      } catch (error) {
        console.error('Failed to fetch countries:', error);
      } finally {
        setIsLoading(false);
      }
    };
    fetchCountries();
  }, []);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">Country</label>
      <select
        value={country || ''}
        onChange={(e) => setCountry(e.target.value || null)}
        className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-kite focus:border-transparent"
        disabled={isLoading}
      >
        <option value="">All Countries</option>
        {countries.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
    </div>
  );
}

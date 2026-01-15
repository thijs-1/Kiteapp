import { useState, useEffect } from 'react';
import { useFilterStore } from '../../store/filterStore';

export function SpotSearch() {
  const { spotName, setSpotName } = useFilterStore();
  const [inputValue, setInputValue] = useState(spotName);

  // Debounce the search
  useEffect(() => {
    const timer = setTimeout(() => {
      setSpotName(inputValue);
    }, 300);

    return () => clearTimeout(timer);
  }, [inputValue, setSpotName]);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">Spot Name</label>
      <div className="relative">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Search spots..."
          className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-kite-pink focus:border-transparent"
        />
        {inputValue && (
          <button
            onClick={() => setInputValue('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

import { useEffect } from 'react';
import { useSpotStore } from '../store/spotStore';
import { spotApi } from '../api/spotApi';
import { getSpotIdFromUrl, setSpotIdInUrl } from './useSpotUrl';

export function useSpotFromUrl() {
  useEffect(() => {
    const spotId = getSpotIdFromUrl();
    if (!spotId) return;

    spotApi
      .getSpot(spotId)
      .then((spot) => {
        useSpotStore.getState().selectSpot({
          ...spot,
          kiteable_percentage: 0,
        });
      })
      .catch(() => {
        setSpotIdInUrl(null);
      });
  }, []);
}

import { useEffect, useState } from 'react';
import { spotApi } from '../api/spotApi';
import type { SpotsMeta } from '../api/types';

let cachedMeta: SpotsMeta | null = null;
let pendingFetch: Promise<SpotsMeta> | null = null;

/**
 * Dataset-level metadata, fetched once per page load and shared across
 * consumers. Returns null until loaded; on fetch failure it stays null
 * (consumers should degrade gracefully).
 */
export function useSpotsMeta(): SpotsMeta | null {
  const [meta, setMeta] = useState<SpotsMeta | null>(cachedMeta);

  useEffect(() => {
    if (cachedMeta) return;
    let cancelled = false;
    pendingFetch ??= spotApi.getMeta();
    pendingFetch
      .then((data) => {
        cachedMeta = data;
        if (!cancelled) setMeta(data);
      })
      .catch(() => {
        pendingFetch = null;
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return meta;
}

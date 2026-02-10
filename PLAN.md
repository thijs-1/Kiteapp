# Performance Plan: Boost Spot Filtering Speed

## Current Architecture Summary

The `/spots` endpoint flow:
1. **NumPy vectorized calc** — `_calculate_all_percentages_vectorized()` slices a 3D array `(~200 spots × 366 days × 16 bins)`, sums across days+bins → per-spot percentages
2. **Optional sustained wind** — same pattern on a second 3D array
3. **DataFrame assembly** — copies full spot DataFrame, maps percentages via dict, filters by threshold, sorts, rounds
4. **Pydantic serialization** — builds `SpotWithStats` per row via `itertuples()`, FastAPI JSON-encodes the list

## Identified Bottlenecks (profiled by code inspection)

| # | Bottleneck | Location | Why It's Slow |
|---|-----------|----------|---------------|
| B1 | Recalculation on every request | `spot_service.py:95-134` | Identical filter params repeat the full NumPy pipeline |
| B2 | Two-pass fancy indexing | `spot_service.py:121-127` | `data[:, day_mask, :]` then `[:, :, bin_mask]` creates 2 intermediate arrays |
| B3 | Python dict round-trip | `spot_service.py:134` | Builds `{spot_id: pct}` dict, then `.map()` back onto DataFrame |
| B4 | DataFrame copy per request | `spot_repository.py:45` | `get_all_spots()` returns `df.copy()` every call |
| B5 | Pydantic model construction | `spot_service.py:257-267` | Loop constructing ~200 Pydantic objects, then JSON-serialized by FastAPI |
| B6 | Mask recomputation | `histogram_repository.py:117-156` | `get_1d_day_indices()` and `get_1d_bin_mask()` rebuild arrays each call |
| B7 | Service re-instantiation | `dependencies.py:25-30` | `SpotService` created per request (not cached) |
| B8 | No frontend debouncing | `useSpots.ts` | Date selector fires API call on every change, no cancellation of stale requests |
| B9 | float64 arrays | `histogram_repository.py` | Double-precision wastes memory bandwidth; data fits in float32 |
| B10 | Default JSON serializer | `main.py` | stdlib `json` is slow for large lists |

---

## Optimization Plan

### Phase 1: Backend — Eliminate Redundant Work (target: 5–10x)

#### 1.1 Add result-level LRU cache on `filter_spots()` ← highest ROI
**File:** `backend/services/spot_service.py`

- Cache the *serialized JSON bytes* (or the list of dicts) keyed by `(wind_min, wind_max, start_date, end_date, country, name, min_percentage, sustained_wind_min, sustained_wind_days_min)`.
- The parameter space is small and data is static at runtime — no invalidation needed.
- Use `functools.lru_cache` (with hashable args) or a simple dict cache on the service singleton.
- Repeated identical requests (common when multiple users have default filters, or same user re-opens app) become O(1).

**Expected impact:** Repeated queries go from ~5-15ms to <0.1ms. First-time queries unchanged.

#### 1.2 Cache mask computations
**File:** `backend/data/histogram_repository.py`

- `get_1d_day_indices(start_date, end_date)` — only 366×366 ≈ ~134K possible inputs; cache with `@lru_cache(maxsize=512)`.
- `get_1d_bin_mask(wind_min, wind_max)` — only ~14×14 ≈ 196 valid bin combos; cache with `@lru_cache(maxsize=256)`.
- Convert the methods to accept hashable args (they already do: floats and strings).

**Expected impact:** Saves ~0.1–0.3ms per mask creation on repeated calls.

#### 1.3 Cache the SpotService singleton
**File:** `backend/api/dependencies.py`

- Add `@lru_cache()` to `get_spot_service()` so the same instance (with its cache) persists across requests.

---

### Phase 2: Backend — Optimize the Hot Path (target: 2–3x on cache miss)

#### 2.1 Precompute cumulative sums for O(1) date-range queries
**File:** `backend/data/histogram_repository.py` + `backend/services/spot_service.py`

After loading the 1D array `(num_spots, 366, num_bins)`:
- Compute `cumsum_total[s, d] = Σ_{d'=0}^{d} Σ_b data[s, d', b]` — cumulative total per spot along days.
- For each valid bin mask `m`, compute `cumsum_inrange[m][s, d] = Σ_{d'=0}^{d} Σ_{b∈m} data[s, d', b]`.

On query: `total = cumsum_total[:, end] - cumsum_total[:, start-1]` (vectorized across spots, O(num_spots)).

Since there are only ~196 bin mask combinations (14 wind_min × 14 wind_max values), precomputing all is feasible: `196 × 200 × 366 × 4 bytes ≈ 57 MB` in float32. If memory is a concern, compute lazily per bin combo and cache.

**Expected impact:** Reduces per-query NumPy work from O(spots × days × bins) to O(spots). ~2-3x faster on cache miss.

#### 2.2 Eliminate DataFrame intermediary — use parallel arrays
**File:** `backend/services/spot_service.py`

Replace the current flow:
```python
df = self.spot_repo.get_all_spots()     # DataFrame copy
df["kiteable_percentage"] = df["spot_id"].map(all_percentages)
df = df[df["kiteable_percentage"] >= min_percentage]
df = df.sort_values(...)
```
With pre-built NumPy arrays in the repository:
```python
# Arrays built once at load time (parallel to histogram spot_ids):
spot_ids: np.ndarray      # (num_spots,) string array
names: np.ndarray          # (num_spots,)
latitudes: np.ndarray      # (num_spots,) float32
longitudes: np.ndarray     # (num_spots,) float32
countries: np.ndarray      # (num_spots,)

# Filtering becomes pure NumPy:
pct = percentages_array     # already (num_spots,) from vectorized calc
mask = pct >= min_percentage
if country:
    mask &= (countries == country)
# argsort only the passing spots
passing_idx = np.where(mask)[0]
order = np.argsort(-pct[passing_idx])
result_idx = passing_idx[order]
```

This eliminates DataFrame copy, `.map()`, and pandas filtering overhead.

**Expected impact:** ~2x faster for the metadata join + filter + sort stage.

#### 2.3 Downcast histogram arrays to float32
**File:** `backend/data/histogram_repository.py`

On load, cast: `self._1d_data = data["data"].astype(np.float32)`. Halves memory bandwidth for all vectorized operations.

**Expected impact:** ~1.3-1.5x faster NumPy operations due to better cache utilization.

---

### Phase 3: Serialization (target: 2–5x on serialization)

#### 3.1 Use `orjson` for response serialization
**Files:** `backend/main.py`, `backend/api/routes/spots.py`

- Install `orjson` and configure a custom `ORJSONResponse` class.
- `orjson` is 5–10x faster than stdlib `json` for serializing lists of dicts/models.

#### 3.2 Return dicts instead of Pydantic models from filter_spots()
**File:** `backend/services/spot_service.py`

Skip Pydantic model construction in the hot path. Build a list of plain dicts directly from the NumPy arrays:
```python
return [
    {
        "spot_id": spot_ids[i],
        "name": names[i],
        "latitude": float(latitudes[i]),
        "longitude": float(longitudes[i]),
        "country": countries[i],
        "kiteable_percentage": round(float(pct[i]), 1),
    }
    for i in result_idx
]
```

Use FastAPI's `response_model` for documentation only; mark the route to skip validation with `response_model=None` and return a `JSONResponse`/`ORJSONResponse` directly.

**Expected impact:** Eliminates ~200 Pydantic object constructions and the default serializer. ~2-3x faster for the serialization phase.

---

### Phase 4: Frontend — Reduce Unnecessary Requests

#### 4.1 Debounce filter changes
**File:** `frontend/src/hooks/useSpots.ts`

Add a 250ms debounce to the `useEffect` that triggers `fetchSpots()`. This prevents rapid-fire API calls when the user adjusts the date range (which currently fires on every dropdown change).

#### 4.2 Cancel stale requests with AbortController
**File:** `frontend/src/hooks/useSpots.ts`, `frontend/src/api/spotApi.ts`

Pass an `AbortSignal` to the Axios request. In the `useEffect` cleanup, abort the previous request. This prevents:
- Wasted server CPU on abandoned requests
- Race conditions where an older response arrives after a newer one

#### 4.3 Cache recent results client-side
**File:** `frontend/src/hooks/useSpots.ts`

Maintain a small Map of recent filter→result pairs. If the user reverts to a previous filter combo (common when exploring), return the cached result instantly while optionally revalidating in the background.

---

## Expected Combined Impact

| Phase | Scenario | Speedup |
|-------|----------|---------|
| Phase 1 (caching) | Repeated identical queries | **50–100x** (cache hit) |
| Phase 1 + 2 | First-time query | **3–5x** |
| Phase 3 | Response serialization | **2–5x** |
| Phase 4 | Perceived UI responsiveness | **2–3x** (fewer requests, instant cache hits) |
| **All phases combined** | Typical user session | **5–10x+ effective speedup** |

## Implementation Order (recommended)

1. **Phase 1.1 + 1.3** — Result cache + singleton service (highest ROI, smallest change)
2. **Phase 1.2** — Mask caching (trivial to add)
3. **Phase 4.1 + 4.2** — Frontend debounce + cancellation (reduces server load)
4. **Phase 2.2** — Replace DataFrame with NumPy arrays (moderate refactor)
5. **Phase 2.3** — float32 downcast (one-liner)
6. **Phase 3.1 + 3.2** — orjson + dict responses (moderate)
7. **Phase 2.1** — Cumulative sums (most complex, do last)

## Files Modified

| File | Changes |
|------|---------|
| `backend/services/spot_service.py` | Result cache, NumPy-based filtering, dict returns |
| `backend/data/histogram_repository.py` | Mask caching, float32 cast, cumulative sums |
| `backend/data/spot_repository.py` | Expose parallel arrays instead of DataFrame |
| `backend/api/dependencies.py` | Cache SpotService singleton |
| `backend/api/routes/spots.py` | ORJSONResponse for filtered spots |
| `backend/main.py` | orjson response class |
| `frontend/src/hooks/useSpots.ts` | Debounce, AbortController, client cache |
| `frontend/src/api/spotApi.ts` | Accept AbortSignal |
| `requirements.txt` | Add `orjson` |

export function getSpotIdFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  return params.get('spot');
}

export function setSpotIdInUrl(spotId: string | null): void {
  const url = new URL(window.location.href);
  if (spotId) {
    url.searchParams.set('spot', spotId);
  } else {
    url.searchParams.delete('spot');
  }
  window.history.replaceState({}, '', url.toString());
}

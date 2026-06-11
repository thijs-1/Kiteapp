import type { Spot } from '../api/types';

const SITE_NAME = 'WhereToKite';
const BASE_URL = 'https://wheretokite.com';
const DEFAULT_TITLE = `${SITE_NAME} - Find the Best Kitesurfing Spots Worldwide`;
const DEFAULT_DESCRIPTION =
  'Discover the best kitesurfing spots worldwide using 10 years of wind data. Filter by wind strength, direction, season, and country to find your ideal kite spot.';

const SPOT_JSONLD_ID = 'spot-jsonld';

function setMeta(selector: string, content: string): void {
  document.querySelector(selector)?.setAttribute('content', content);
}

function applyMeta(title: string, description: string, url: string): void {
  document.title = title;
  setMeta('meta[name="title"]', title);
  setMeta('meta[name="description"]', description);
  setMeta('meta[property="og:title"]', title);
  setMeta('meta[property="og:description"]', description);
  setMeta('meta[property="og:url"]', url);
  setMeta('meta[name="twitter:title"]', title);
  setMeta('meta[name="twitter:description"]', description);
  setMeta('meta[name="twitter:url"]', url);
  document.querySelector('link[rel="canonical"]')?.setAttribute('href', url);
}

function removeSpotJsonLd(): void {
  document.getElementById(SPOT_JSONLD_ID)?.remove();
}

function injectSpotJsonLd(spot: Spot, url: string): void {
  removeSpotJsonLd();
  const script = document.createElement('script');
  script.type = 'application/ld+json';
  script.id = SPOT_JSONLD_ID;
  script.textContent = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Place',
    name: spot.name,
    url,
    description: `Kitesurfing spot${spot.country ? ` in ${spot.country}` : ''} with 10 years of historical wind statistics.`,
    geo: {
      '@type': 'GeoCoordinates',
      latitude: spot.latitude,
      longitude: spot.longitude,
    },
    ...(spot.country && {
      address: { '@type': 'PostalAddress', addressCountry: spot.country },
    }),
  });
  document.head.appendChild(script);
}

/** Update title, meta tags, canonical URL and structured data for the
 *  selected spot, or restore the defaults when no spot is selected. */
export function updateSpotMeta(spot: Spot | null): void {
  if (!spot) {
    applyMeta(DEFAULT_TITLE, DEFAULT_DESCRIPTION, `${BASE_URL}/`);
    removeSpotJsonLd();
    return;
  }

  const url = `${BASE_URL}/?spot=${encodeURIComponent(spot.spot_id)}`;
  const where = spot.country ? `${spot.name}, ${spot.country}` : spot.name;
  const title = `Kitesurfing at ${spot.name} | ${SITE_NAME}`;
  const description = `Wind statistics for kitesurfing at ${where}: 10 years of wind strength and direction data, kiteable days per season, and wind rose charts.`;

  applyMeta(title, description, url);
  injectSpotJsonLd(spot, url);
}

"""Generate frontend/public/sitemap.xml.

By default only the homepage is listed. Per-spot URLs
(https://wheretokite.com/?spot=<spot_id>) can be included with --spots,
but hold off on that until spot pages serve unique prerendered content:
the static HTML shell canonicalizes every URL to the homepage, so mass
submission currently just creates thin-content and crawl-waste signals.

Usage:
    python -m scripts.generate_sitemap            # homepage only
    python -m scripts.generate_sitemap --spots    # include all spot URLs
"""

import argparse
import pickle
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

BASE_URL = "https://wheretokite.com"
SPOTS_PKL = Path("data/processed/spots.pkl")
SITEMAP_PATH = Path("frontend/public/sitemap.xml")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spots",
        action="store_true",
        help="Include a URL for every spot in data/processed/spots.pkl",
    )
    args = parser.parse_args()

    lastmod = date.today().isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        "  <url>",
        f"    <loc>{BASE_URL}/</loc>",
        f"    <lastmod>{lastmod}</lastmod>",
        "    <changefreq>weekly</changefreq>",
        "    <priority>1.0</priority>",
        "  </url>",
    ]
    url_count = 1

    if args.spots:
        with open(SPOTS_PKL, "rb") as f:
            spots = pickle.load(f)
        for spot_id in spots["spot_id"]:
            loc = escape(f"{BASE_URL}/?spot={spot_id}")
            lines += [
                "  <url>",
                f"    <loc>{loc}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                "    <changefreq>monthly</changefreq>",
                "    <priority>0.7</priority>",
                "  </url>",
            ]
        url_count += len(spots)

    lines.append("</urlset>")
    SITEMAP_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {url_count} URLs to {SITEMAP_PATH}")


if __name__ == "__main__":
    main()

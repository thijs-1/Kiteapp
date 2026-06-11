"""Generate frontend/public/sitemap.xml from the processed spots data.

Each spot is deep-linkable via https://wheretokite.com/?spot=<spot_id>,
so we publish one sitemap entry per spot plus the homepage.

Usage:
    python -m scripts.generate_sitemap
"""

import pickle
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

BASE_URL = "https://wheretokite.com"
SPOTS_PKL = Path("data/processed/spots.pkl")
SITEMAP_PATH = Path("frontend/public/sitemap.xml")


def main() -> None:
    with open(SPOTS_PKL, "rb") as f:
        spots = pickle.load(f)

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

    lines.append("</urlset>")
    SITEMAP_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(spots) + 1} URLs to {SITEMAP_PATH}")


if __name__ == "__main__":
    main()

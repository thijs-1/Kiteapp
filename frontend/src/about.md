# About Kiteapp

Kiteapp is a kitesurfing spot finder that helps you discover the best locations for your next session.

## How It Works

We analyze **10 years of ERA5 wind data** from the Copernicus Climate Data Store to identify optimal kitesurfing locations around the world. This historical data allows us to show you:

- **Daily wind patterns** throughout the year
- **Wind strength distributions** for each spot
- **Wind direction frequencies** via interactive wind roses
- **Kiteable percentage** based on your preferred wind range

## Using the Filters

Use the menu to customize your search:

- **Wind Range**: Set your preferred wind speed (in knots)
- **Date Range**: Focus on specific months or seasons
- **Country**: Filter spots by location
- **Min Kiteable %**: Only show spots above a threshold

## Understanding the Charts

When you click on a spot, you'll see three charts:

1. **Line Chart**: Daily kiteable percentage over the year
2. **Histogram**: Wind strength distribution for your selected dates
3. **Wind Rose**: Directional wind patterns showing where the wind comes from

## Data Source

Wind data is sourced from [ERA5](https://cds.climate.copernicus.eu/), the fifth generation ECMWF atmospheric reanalysis of global climate. ERA5 provides hourly estimates of atmospheric variables from 1940 to present.

---

Built with React, Leaflet, and Chart.js

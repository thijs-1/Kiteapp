# About

WhereToKite is the culmination of a passion project. Over the years I've gotten frustrated from kitesurfing vacations in which I spent 80% of my time waiting on weather. I didn't get it, I would do my research in advance, read up about the spots, check the pictures etc. Each spot would have gushing reviews, proclaiming the reliability of the levante or maestral boosted by thermals. Most likely written by the local kitesurf teacher in the hopes of attracting more custom.

Having a background in work prep for offshore construction work, I knew there was a better way. A data-driven way. A way that would ensure I spent my vacation getting thoroughly bruised and battered by wind and waves, my own ineptness and enthusiasm.

This website is that way.

## How It Works

Turns out weather forecasting agencies and climate modelling agencies open-source their data! To determine the kitability of a spot I downloaded 10 years of hindcast weather analysis. The best weather and climate models fitted to actual observations to generate the most complete and accurate weather data possible across the globe. To be precise, I downloaded **10 years of ERA5 wind data** from the Copernicus Climate Data Store to identify optimal kitesurfing locations around the world.

Wind data (at 10m above earth surface) is sourced from [ERA5](https://cds.climate.copernicus.eu/), the fifth generation ECMWF atmospheric reanalysis of global climate. ERA5 provides hourly estimates of atmospheric variables from 1940 to present.

## How It Is Processed
For each kitesurfing location scraped from the web, a 10-year hourly timeseries is extracted. This requires interpolating between the 4 nearest grid points provided by the ERA5 model.

That data is then aggregated into direction and wind strength in 2.5 knot steps and 10 degree bins. The wind direction is important because I'm not great at kiting and enjoy the safety of knowing I'll be blown back to shore when I inevitably crash.

This 2D histogram is compiled for each day of the year aggregating the last 10 years. Nighttime hours are excluded from the data set.

For the charts you see, the wind strength is further taken as the average for each date +/- 1 week. In an earlier version I did not take these averaged values and wound up in Naxos, Greece during a week that the data predicted 90% of great wind; I spent half the vacation waiting on wind. I inspected the data and found that the week prior and after were somewhat disappointing, and in general the area had a cyclical wind nature, 1 week on, 1 week off. The 90% prediction was a fluke.

Lesson learned: in this iteration you get the expected wind averaged out for a period of time plus or minus 1 week.

## Limitations
The data is extracted from a grid that is 0.25 degrees, or roughly 3 km at the equator. This means that any geographical features and their effects on the wind which are smaller than that are not well represented. Small peninsula covered in trees upwind of you? That is not captured.

The smallest time unit I'm representing is a day. So you will still have to ask a local to see if the wind tends to be stronger in the morning or the afternoon.

I only use hindcast data, so if you want to know the wind tomorrow, check windy.com :)

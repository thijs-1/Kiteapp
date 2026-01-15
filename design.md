# Kiteapp
This is the high level functional design spec for a kitesurfing application used to identify optimal surfing locations.

the app will have three main components
- backend
- frontend
- datapipelines

## Starting with the datapipelines:
inputs:
- pthon pkl file with kitespot names and coordinates
- copernicus climate data store (CDS)

outputs:
1. pkl file with spot specific a daily histograms of windstrength in knots with bins [0:2.5:35, 35-inf]. to calculate windstrength we need to convert from m/s to knots and combine the u and v components. strength = (u^2 + v^2)^0.5. we are expecting about 9000 pots
2. spot specific pkl files with a 3d array containing a daily 2D histogram with knots and windirecton. wind direction is "going to" and compass direction. so 90 degrees wind would be a wind coming from the west and going east. same windstrenght bins. and direction bins defaulting to [-5:10:355]. this will be used to create a windrose.
3. the files downloaded from copernicus

overall flow:
1. divide the globe into a 30 by 30 grid. 
2. for each square in that grid idenfity which spots occur in that grid
    - increase the grid size by 5 km in all directions. and download the last 10 years of winddata, using the ERA5 model, from the CDS. skip this step if there are no spots within the square and move on to the next square
    - extract the relevant information for the spots identified in step 2. and save  the data.

## backend
the backend will have the following features:
- filter and return spots based on:
        - percentage of time wind is within a range e.g. 15 & 20 knots AND a specific date frame e.g. 15th of may till 30 august. default to the entire year and the full windrange 0-inf
        - country | none would be equivalent of all countries
        - spotname
- for a specific spot serve 
    - the daily histograms for a specified date range
    - serve the windrose aggregated to a specified date frame
    - the daily histograms for a specified date range, but the histograms are a moving average i.e. the average of that date plus minus x weeks. where x defaults to 2
    - the percentage of time the wind falls within a configurable range per day within a specified date range
    - the moving average percentage of time the wind falls within a configurable range per day within a specified date range. again default the window to +- 2 weeks.

backend should use fastapi.
good separation between bussiness logic, data and endpoints

## frontend
should be a world map: countries, cities, streetmap, airports. using roman alphabet preferably.

the map should display pink dots for all of the kite spots.
a hamburger menu should contain the filter options for:
- wind range in discrete steps of 2.5 knots (a slider with two vertical bars would be great). defaults to full range 0 - inf
- the desired kiteable percentage default to 75%
- a date range picker. should be year agnostic. defaults to 1-jan to 31- dec
- country | defaut none
- spotname

when the user clicks on a dot a chart modals should pop up. showing for the specified date range:
- a line graph with percentage of kiteable wind
- a stacked barplot showing the histogram of windstrengths
    - with a fixed heatmap to windstrength
- a windrose aggregated across the date range range
    - mouseover text that it shows the wind in a going-to direction
the modals should be mounted on some type of carrousel. starting with the line plot being centered.

I want clear separation between:
- the service calls from front-end to backend
- front end components


    




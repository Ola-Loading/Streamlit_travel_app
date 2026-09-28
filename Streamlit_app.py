import logging

import pandas as pd
import numpy as np
import streamlit as st
import openmeteo_requests
import requests_cache
from retry_requests import retry
from datetime import datetime
import pydeck as pdk
import os
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


st.set_page_config(page_title="Japa", page_icon=":material/waving_hand:")
st.title("No-one wants to be stuck in the cold (cough cough the UK) come make we JAPA!")

st.write(
    """
    This is a simple webpage that utilises streamlit and various API's to
    produce a weather forecast for your location and allow you to customise what temperature you would love to be in at the moment 
    and it will recommend places (preferably outside of the country) that 
    you might consider booking a trip to. 
    
    Recommendations are based on both user inputted temperature thresholds and distance from you. Happy holidaying!
    """
)

@st.cache_data
def load_csv(path):
    a = pd.read_csv(path)
    return a 


# Function to calculate the distance using latitude and longitude values in decimal degrees. it is haversine formula that determines the great-circle distance between two points on a sphere given their longitudes and latitudes
def haversine(lat1, lon1, lat2, lon2):
    # Earth radius in kilometers
    R = 6371.0  
    phi1 = np.radians(lat1)   # Convert degrees to radians (degrees * pi/180)
    phi2 = np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)

    a = np.sin(delta_phi / 2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2)**2    
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    
    return R * c

@st.cache_resource
def get_openmeteo_client():
     # Setup the Open-Meteo API client with cache and retry on error
     cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
     retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
     openmeteo = openmeteo_requests.Client(session = retry_session)
     return openmeteo



def weather_chart(location):
	

	openmeteo = get_openmeteo_client()

	# Make sure all required weather variables are listed here
	# The order of variables in hourly or daily is important to assign them correctly below
	url = "https://api.open-meteo.com/v1/forecast"
	params = {
		"latitude": location[0],
		"longitude": location[1],
		"hourly": ["temperature_2m","apparent_temperature"]
	}
	responses = openmeteo.weather_api(url, params=params)

	response = responses[0]
     
	# Process hourly data. The order of variables needs to be the same as requested.
	hourly = response.Hourly()
	hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
	feel_temperature_2m = hourly.Variables(1).ValuesAsNumpy()

	hourly_data = {"date": pd.date_range(
		start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
		end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
		freq = pd.Timedelta(seconds = hourly.Interval()),
		inclusive = "left"
	)}

	hourly_data["temperature_2m"] = hourly_temperature_2m
	hourly_data["feels_like"] = feel_temperature_2m

	hourly_dataframe = pd.DataFrame(data = hourly_data)
	filtered_df = hourly_dataframe[hourly_dataframe['date'].dt.strftime('%Y-%m-%d %H') == str(datetime.now())[0:13]]    # To extract the current daily temperature at user inputted location, in use for the slider later
	
	return (filtered_df,hourly_dataframe)


@st.cache_data
def compute_threshold_countries(threshold, location, min_distance_km, max_distance_km):
    df = cities.copy()   # earlier dataset with city information
    # threshold is the value from the slider that the user inputs
    latitude = location[0]
    longitude = location[1]

    # in order to calculate the distances from the user's input location. API call limits necessitate that a sample from the overall dataset is passed as opposed to the whole dataset
    df['distance'] = df.apply(lambda row: haversine(latitude, longitude, row['lat'], row['lng']),axis=1)
    df.sort_values(by=['distance'], inplace=True)


    # Filter cities within the user-chosen distance range
    df = df[(df['distance'] > min_distance_km) & (df['distance'] < max_distance_km)]

    # Limit to top N cities within that range (e.g., 130)
    df = df.head(130)
    # df = df.head()            #for testing purposes
    df.rename(columns={"lat": "latitude", "lng": "longitude"},inplace=True)


    openmeteo = get_openmeteo_client()

    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": [i[2] for i in df.values],
        "longitude": [i[3] for i in df.values],
        "daily": ["temperature_2m_min"] * len(df)
    }


    responses = openmeteo.weather_api(url, params=params)

    if len(responses) != len(df):
        logger.warning(
            "Open-Meteo returned %d responses for %d requested cities; truncating to the shorter length",
            len(responses), len(df),
        )

    daily_data = {"date":[],
                "current_day_temp":[],
                "latitude":[],
                "longitude":[]}

    for i in range(min(len(responses), len(df))):
        response = responses[i]
        daily = response.Daily()
        daily_temperature_2m = daily.Variables(0).ValuesAsNumpy()

        daily_data["date"].append(pd.to_datetime(daily.Time(), unit = "s", utc = True))

        if daily_temperature_2m[0] >= threshold:
            daily_data["current_day_temp"].append(daily_temperature_2m[0])
        else:
            daily_data["current_day_temp"].append(None)

        daily_data["latitude"].append(params["latitude"][i])

        daily_data["longitude"].append(params["longitude"][i])




    daily_dataframe = pd.DataFrame(data = daily_data)
    daily_dataframe = daily_dataframe.join(df.set_index(['latitude','longitude']),on=['latitude','longitude'])
    daily_dataframe = daily_dataframe[daily_dataframe["current_day_temp"].isnull() == False]

    return daily_dataframe


def top_threshold_countries(threshold, location, min_distance_km, max_distance_km):
    latitude, longitude = location[0], location[1]
    daily_dataframe = compute_threshold_countries(threshold, location, min_distance_km, max_distance_km)

    if len(daily_dataframe) > 0:
        # Create Pydeck map
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=daily_dataframe,
            get_position='[longitude, latitude]',
            get_fill_color='[255, 0, 0, 160]',
            get_radius=8000,
            pickable=True)

        tooltip = {
            "html": "<b>City:</b> {city}<br/>"
                    "<b>Country:</b> {country}<br/>"
                    "<b>Temp (°C):</b> {current_day_temp}",
            "style": {
                "backgroundColor": "steelblue",
                "color": "white"
            }}

        view_state = pdk.ViewState(
            latitude=latitude,
            longitude=longitude,
            zoom=3,
            pitch=0,
        )

        st.pydeck_chart(pdk.Deck(
            map_style='light',
            initial_view_state=view_state,
            layers=[layer],
            tooltip=tooltip
        ))

    else:
        st.write('No Cities near your location that meet this requirement :((' )

    return daily_dataframe

def airport_selector(location, desired_location):
    
    latitude = location[0]             #User input location
    latitude_2 = desired_location[0]   #User selected travel location
    longitude = location[1] 
    longitude_2 = desired_location[1]
    airports = pd.read_csv("data/airports.csv")
    airports = airports[airports['IATA Code'].isnull()==False]    #removing entries without an IATA code which is necessary for the AviationStack API

    # in order to calculate the airports closest to the user's location for selection by user
    airports['distance'] = airports.apply(lambda row: haversine(latitude, longitude, row['latitude'], row['longitude']),
    axis=1)  
   
    # in order to calculate the airports closest to the user's desired location
    airports['distance_2'] = airports.apply(lambda row: haversine(latitude_2, longitude_2, row['latitude'], row['longitude']),
    axis=1)
    
    if airports.empty:
        return airports, airports

    airports.sort_values(by=['distance'], inplace=True)
    airports_2 = airports.sort_values(by=['distance_2'])


    airports = airports[0:10]
    airports_2 = airports_2[0:10]

    return (airports,airports_2)


def flights_to(api_key,origin,destination):
    url = f"https://api.aviationstack.com/v1/timetable?access_key={api_key}"
    params = {"iataCode":origin,"type":"departure","status":"scheduled"}
    response = requests.get(url, params=params)
    response_json = response.json()

    # When you convert from Python to JSON, Python objects are converted into the JSON (JavaScript) equivalent

    if not response_json.get("success", True) or 'data' not in response_json:
        print("Error or no data in response:", response_json)
        return pd.DataFrame()


    data = response_json.get('data')

    # Fix: Check if it's a valid list of flights
    if not isinstance(data, list) or not data:
        print(f"No scheduled flights from {origin} to {destination}. Response was:")
        print(response_json)
        return pd.DataFrame()

    df = pd.DataFrame(data=data)

    if 'arrival' not in df.columns:
        print("Arrival column missing in DataFrame.")
        return pd.DataFrame()

    # Extract arrival airport IATA code from the nested dict
    df['arrival_iata'] = df['arrival'].apply(lambda x: x.get('iataCode') if isinstance(x, dict) else None)

    # Filter for rows where arrival IATA code matches the destination
    df_filtered = df[df['arrival_iata'] == destination]

    # Inner function to simplify the unpacking of objects in dataframe columns
    def extract_field(df, column, field, new_column):
        df[new_column] = df[column].apply(lambda x: x.get(field) if isinstance(x, dict) else None)

    extract_field(df_filtered, 'airline', 'name', 'Airline_Name')
    extract_field(df_filtered, 'arrival', 'delay', 'Arrival_Delay')
    extract_field(df_filtered, 'arrival', 'gate', 'Arrival_Gate')
    extract_field(df_filtered, 'arrival', 'terminal', 'Arrival_Terminal')
    extract_field(df_filtered, 'arrival', 'scheduledTime', 'Scheduled Time')
    extract_field(df_filtered, 'flight', 'number', 'Flight_Number')
    extract_field(df_filtered, 'departure', 'delay', 'Departure_Delay')
    extract_field(df_filtered, 'departure', 'gate', 'Departure_Gate')
    extract_field(df_filtered, 'departure', 'terminal', 'Departure_Terminal')
    extract_field(df_filtered, 'departure', 'scheduledTime', 'Departure_Scheduled Time')
    extract_field(df_filtered, 'departure', 'estimatedTime', 'Departure_Estimated Time')

    # Convert to datetime
    df_filtered['Departure_Estimated Time'] = pd.to_datetime(df_filtered['Departure_Estimated Time'])
    df_filtered['Departure_Scheduled Time'] = pd.to_datetime(df_filtered['Departure_Scheduled Time'])
    df_filtered['Scheduled Time'] = pd.to_datetime(df_filtered['Scheduled Time'])

    # Format to a readable string, e.g., '2025-07-07 12:29'
    df_filtered['Departure_Estimated Time'] = df_filtered['Departure_Estimated Time'].dt.strftime('%Y-%m-%d %H:%M')
    df_filtered['Departure_Scheduled Time'] = df_filtered['Departure_Scheduled Time'].dt.strftime('%Y-%m-%d %H:%M')
    df_filtered['Scheduled Time'] = df_filtered['Scheduled Time'].dt.strftime('%Y-%m-%d %H:%M')


    return df_filtered[['Airline_Name','Arrival_Delay','Arrival_Gate', 'Arrival_Terminal', 'Scheduled Time', 'Flight_Number', 'Departure_Delay',
                        'Departure_Gate', 'Departure_Terminal', 'Departure_Scheduled Time' ,'Departure_Estimated Time']]  



load_dotenv()  # Loads variables from .env (used for local development)
api_key = os.getenv("AVIATION_API_KEY")
if not api_key:
    # On Streamlit Cloud there is no .env file; the key is read from Secrets
    # instead. st.secrets raises if no secrets.toml exists at all, so guard it.
    try:
        api_key = st.secrets.get("AVIATION_API_KEY")
    except Exception:
        api_key = None


# Datset that provides a comprehensive list of cities and their latitude/longitude, country alongside other details

cities = load_csv("data/worldcities.csv")
cities['city'] = cities['city'].str.lower()
location  =  st.text_input(label = 'your current location', placeholder = 'enter your current city')
location = location.lower()
longitude = None
latitude = None

#Checks user input to ensure it is present in the aformentioned Cities dataset. If it is it will extract the latitude and longitude. Further loops are used in order to extract the specific city intended as some countries have the same cityname. Establishes the longitude latitude variables used in later functions

if location:
    if location in cities['city'].values:
        filtered_cities = cities[cities['city'] == location]
        if len(filtered_cities) > 1:
            country_list = list(filtered_cities['country'])
            country = st.selectbox(label = 'Choose Which Country', options = country_list)
            if country:
                filtered_cities = filtered_cities[filtered_cities['country'] == country]
                
                if len(filtered_cities) > 1:
                    selection_list = list(filtered_cities['admin_name'])
                    selection = st.selectbox(label = 'Choose one', options = selection_list)
                    if selection:
                        # for when there are more than one entry for the same cityname and countryname
                        latitude = [filtered_cities[filtered_cities['admin_name']== selection]['lat'].values[0]] 
                        longitude = [filtered_cities[filtered_cities['admin_name']== selection]['lng'].values[0]]
                        st.write(f'your location is: {selection}, {country} at latitude {latitude[0]} and longitude {longitude[0]}')
                        city = selection
                else:
                    latitude = filtered_cities['lat'].values
                    longitude = filtered_cities['lng'].values
                    st.write(f'your location is: {location}, {country} at latitude {latitude[0]} and longitude {longitude[0]}')
                    city = location
        else:
            latitude = filtered_cities['lat'].values
            longitude = filtered_cities['lng'].values
            st.write(f'your location is: {location} at latitude {latitude[0]} and longitude {longitude[0]}')
            city = location
    else:
        st.write('Try again, I do not recognise that city name or country sorry!')



if location:
    if longitude != None and latitude != None:

        rough_location = (*latitude,*longitude)    #Unpack the values as it is a list object with one element

        try:
            dfs = weather_chart(rough_location)    #Retrieve weather forecast where the user is
        except Exception:
            logger.exception("Failed to fetch weather for location %s", rough_location)
            st.error("Sorry, I couldn't fetch the weather forecast for your location right now. Please try again shortly.")
        else:
            min_value = int(dfs[0]['temperature_2m'].min())  #Current daily temperature for user location

            st.subheader(f"Weather forecast (where you are) ")
            st.line_chart(dfs[1].set_index("date")["temperature_2m"], x_label='Date/time', y_label='Temperature °C') # Weather forecast Plot

            a = st.slider(label='Pick a temperature any temperature in °C',min_value=0 , max_value=50, help="Your ideal minimum temperature")

            min_distance, max_distance = st.slider(
                label='How far are you willing to fly? (km)',
                min_value=0, max_value=15000, value=(300, 3000),
                help="Destinations closer than the minimum or further than the maximum won't be suggested",
            )

            if a :
                st.subheader("Below are the locations of some cities not too far not too close that achieve the minimum temperature required")

                try:
                    data = top_threshold_countries(threshold = a,location = rough_location, min_distance_km = min_distance, max_distance_km = max_distance)
                except Exception:
                    logger.exception("Failed to fetch candidate destinations for location %s, threshold %s, distance range %s-%s", rough_location, a, min_distance, max_distance)
                    st.error("Sorry, I couldn't fetch destination weather data right now. Please try again shortly.")
                    data = None

                if data is not None:
                    st.write(data[['date','current_day_temp','city','country']])

                    desired_city = st.selectbox(label = 'Pick a city to travel to', options = data[data['city']!=city]['city'])

                    if desired_city:
                        desired_city_location = data[data['city']== desired_city]
                        desired_city_location = (*desired_city_location['latitude'],*desired_city_location['longitude']) #Unpack the pandas series object

                        airports_available =  airport_selector(rough_location,desired_city_location)
                        origins = airports_available[0]['Airport Name']
                        destinations =  airports_available[1]['Airport Name']

                        if origins.empty or destinations.empty:
                            st.write('No nearby airports found for one of these locations, try another city.')
                        else:
                            desired_airport = st.selectbox(label = 'Pick an airport to fly from', options = origins)
                            desired_destination_airport = st.selectbox(label = 'Pick an airport to arrive at', options = destinations)
                            if desired_airport and desired_destination_airport:
                                origin = airports_available[0][airports_available[0]['Airport Name'] == desired_airport]['IATA Code'].values[0]
                                destination = airports_available[1][airports_available[1]['Airport Name'] == desired_destination_airport]['IATA Code'].values[0]

                                try:
                                    final_flights = flights_to(api_key,origin=origin,destination=destination)
                                except Exception:
                                    logger.exception("Failed to fetch flights from %s to %s", origin, destination)
                                    st.error("Sorry, I couldn't fetch flight data right now. Please try again shortly.")
                                else:
                                    if len(final_flights) < 1:
                                        st.write('Unfortunately there are no scheduled flights between these two airports today :( try another combination')
                                    else:
                                        st.subheader("Voila! some flights for ya")
                                        st.write(final_flights)

            else:
                st.write('Waiting for your temperature selection')





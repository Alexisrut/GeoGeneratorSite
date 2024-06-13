from ctypes.wintypes import POINT
from flask import Flask, request, render_template, redirect, url_for
import geopandas as gpd
import pandas as pd
import numpy as np
import json
import h3
import folium
import osmnx as ox
from shapely import wkt
from folium.plugins import HeatMap
from shapely.geometry import Polygon, LineString
import requests
import csv
import matplotlib.pyplot as plt
from shapely.geometry import Point

app = Flask(__name__)
def take_places(city_name, organization_name):
    access_token = 'afb4ed0b-adcd-489e-8afe-bd5e8ae0ef80'
    file = open("all_info.csv","w")

    def getjson(url, data=None):
        response = requests.get(url, params=data)
        response = response.json()
        return response
    #51.321540, 128.028595 left
    #51.415088, 128.167131 right

    wall = getjson(f'https://search-maps.yandex.ru/v1/?apikey=afb4ed0b-adcd-489e-8afe-bd5e8ae0ef80&text={city_name},{organization_name}&lang=ru_RU&rspn=1&results=50')
    result = []
    busines_array = []
    for i in wall['features']:
        geometry = i['geometry']
        coordinates = i['geometry']['coordinates']
        name = i['properties']['name']
        adress = i['properties']['description']
        try:
            site = i['properties']['CompanyMetaData']['url']
        except:
            site = 'None'
        try:
            phone = i['properties']['CompanyMetaData']['Phones'][0]['formatted']
        except:
            phone = 'None'
        result.append({'city': f'{city_name}', 'object': 'building', 'Название организации': name, 'Адрес': adress, 'Сайт': site, 'Телефон': phone, 'geometry': geometry, 'coordinates': coordinates})
        busines_array.append({'city': f'{city_name}', 'object': 'building', 'geometry': geometry, 'coordinates': coordinates})
    busines_df = pd.DataFrame(busines_array)
    result_coord = []
    for i in result:
        result_coord.append({'lat': i['coordinates'][0], 'lon': i['coordinates'][1]})
    return result_coord, busines_df

def visualize_hexagons(hexagons, color="red", folium_map=None):
    polylines = []
    lat = []
    lng = []
    for hex in hexagons:
        polygons = h3.h3_set_to_multi_polygon([hex], geo_json=False)
        outlines = [loop for polygon in polygons for loop in polygon]
        polyline = [outline + [outline[0]] for outline in outlines][0]
        lat.extend(map(lambda v:v[0],polyline))
        lng.extend(map(lambda v:v[1],polyline))
        polylines.append(polyline)
    
    if folium_map is None:
        m = folium.Map(location=[sum(lat)/len(lat), sum(lng)/len(lng)], zoom_start = 20, tiles='cartodbpositron')
    else:
        m = folium_map
        
    for polyline in polylines:
        my_PolyLine=folium.PolyLine(locations=polyline,weight=1,color=color)
        m.add_child(my_PolyLine)
    return m
    """h3_address = []
    building_coord = pd.DataFrame(result_coord)
    for i in result_coord:
        h3_address.append(h3.geo_to_h3(i["lon"], i["lat"],  10))"""

def visualize_polygons(geometry):
    
    lats, lons = get_lat_lon(geometry)
    
    m = folium.Map(location=[sum(lats)/len(lats), sum(lons)/len(lons)], zoom_start=13, tiles='cartodbpositron')
    
    overlay = gpd.GeoSeries(geometry).to_json()
    folium.GeoJson(overlay, name = 'boundary').add_to(m)
    
    return m

def get_lat_lon(geometry):
    lon = geometry.apply(lambda x: x.x if x.type == 'Point' else x.centroid.x)
    lat = geometry.apply(lambda x: x.y if x.type == 'Point' else x.centroid.y)
    return lat, lon

def create_hexagons(geoJson):
    
    polyline = geoJson['coordinates'][0]

    polyline.append(polyline[0])
    lat = [p[0] for p in polyline]
    lng = [p[1] for p in polyline]
    m = folium.Map(location=[sum(lat)/len(lat), sum(lng)/len(lng)], zoom_start=13, tiles='cartodbpositron')
    my_PolyLine=folium.PolyLine(locations=polyline,weight=8,color="green")
    m.add_child(my_PolyLine)

    hexagons = list(h3.polyfill(geoJson, 10))
    polylines = []
    lat = []
    lng = []
    for hex in hexagons:
        polygons = h3.h3_set_to_multi_polygon([hex], geo_json=False)
        # flatten polygons into loops.
        outlines = [loop for polygon in polygons for loop in polygon]
        polyline = [outline + [outline[0]] for outline in outlines][0]
        lat.extend(map(lambda v:v[0],polyline))
        lng.extend(map(lambda v:v[1],polyline))
        polylines.append(polyline)
    for polyline in polylines:
        my_PolyLine=folium.PolyLine(locations=polyline,weight=2,color='blue')
        m.add_child(my_PolyLine)
        
    polylines_x = []
    for j in range(len(polylines)):
        a = np.column_stack((np.array(polylines[j])[:,1],np.array(polylines[j])[:,0])).tolist()
        polylines_x.append([(a[i][0], a[i][1]) for i in range(len(a))])
        
    polygons_hex = pd.Series(polylines_x).apply(lambda x: Polygon(x))
        
    return m, polygons_hex, polylines

def osm_query(tag, city):
    gdf = ox.geometries_from_place(city, tag).reset_index()
    gdf['city'] = np.full(len(gdf), city.split(',')[0])
    gdf['object'] = np.full(len(gdf), list(tag.keys())[0])
    gdf['type'] = np.full(len(gdf), tag[list(tag.keys())[0]])
    gdf = gdf[['city', 'object', 'type', 'geometry']]
    return gdf

def calculate_travel_time(start_lat, start_lon, end_lat, end_lon):
    # Construct the request URL for OSRM API
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=false"

    # Send the request to OSRM API
    response = requests.get(url)

    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        # Extract travel time in seconds from the response
        travel_time_seconds = data["routes"][0]["duration"]
        # Convert travel time to minutes
        return travel_time_seconds
    else:
        print("Error:", response.status_code)
        return None

def create_choropleth(data, json, columns, legend_name, bins, polygon_krd):
    lat, lon = get_lat_lon(data['polygon'])

    m = folium.Map(location=[sum(lat)/len(lat), sum(lon)/len(lon)], zoom_start=13, tiles='cartodbpositron')
    
    folium.Choropleth(
        geo_data=json,
        name="choropleth",
        data=data,
        columns=columns,
        key_on="feature.id",
        fill_color="YlGn",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=legend_name,
        nan_fill_color = 'black',
        bins = bins
    ).add_to(m)
    folium.LayerControl().add_to(m)
    visualize_polygons(polygon_krd['geometry']).add_to(m)
    return m

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        global city
        city = request.form['city']
        organization = request.form['organization']
        global busines_df
        global result_coord
        result_coord, busines_df = take_places(city, organization)

        busines_df.to_csv('dataframe.csv', index=False)
        h3_address = []
        for i in result_coord:
            h3_address.append(h3.geo_to_h3(i["lon"], i["lat"],  10))
        cities = [f'{city}']
        polygon_krd = ox.geometries_from_place(cities, {'boundary':'administrative'}).reset_index()
        # посмотрим что получилось
        geoJson = json.loads(gpd.GeoSeries(polygon_krd['geometry']).to_json())
        geoJson = geoJson['features'][0]['geometry']
        try:
            geoJson = {'type':'Polygon','coordinates': [np.column_stack((np.array(geoJson['coordinates'][0])[:, 1], np.array(geoJson['coordinates'][0])[:, 0])).tolist()]}
        except:
            line = LineString(geoJson['coordinates'])
            polygon = line.buffer(0.001)  # Buffer to create a polygon around the line
            coordinates = np.array(polygon.exterior.coords)
            geoJson = {
                'type': "Polygon",
                'coordinates': [np.column_stack((coordinates[:, 1], coordinates[:, 0])).tolist()]
            }
        

        m, polygons_city, polylines = create_hexagons(geoJson)
        """cities = [f'Россия, {city}']
        polygon_krd = ox.geometries_from_place(cities, {'boundary': 'administrative'}).reset_index()
    
        # Ensure that the GeoSeries to JSON conversion is correct
        geoJson = json.loads(gpd.GeoSeries(polygon_krd['geometry']).to_json())
        
        if not geoJson['features']:
            raise ValueError("No geometry found for the specified city.")
        
        geoJson = geoJson['features'][0]['geometry']
        
        # Handle different geometry types
        coordinates = np.array(geoJson['coordinates'])
        print(coordinates)
        geoJson = {
            'type': 'Polygon',
            'coordinates': [np.column_stack((coordinates[:, 1], coordinates[:, 0])).tolist()]
        }
        
        m, polygons_city, polylines = create_hexagons(geoJson)"""
        # посмотрим что получилось


        def get_lat_lon_mine(geometry):
            lon = geometry.apply(lambda x: x.x)
            lat = geometry.apply(lambda x: x.y)
            return lat, lon
        # добавим координаты/центроиды
        geometry_objects = [Point(xy[0], xy[1]) for xy in busines_df['coordinates']]
        gdf1 = gpd.GeoDataFrame(geometry=geometry_objects)
        busines_df = busines_df.drop('coordinates', axis = 1)

        help = pd.DataFrame()
        data_poi = pd.concat([busines_df, help])

        lat, lon = get_lat_lon_mine(gdf1['geometry'])
        data_poi['lat'] = lat
        data_poi['lon'] = lon
        gdf_1 = gpd.GeoDataFrame(data_poi, geometry=gpd.points_from_xy(data_poi.lon, data_poi.lat))
        gdf_1.set_crs(epsg=4326, inplace=True)

        gdf_2 = pd.DataFrame(polygons_city, columns = ['geometry'])
        gdf_2['polylines'] = polylines
        gdf_2['geometry'] = gdf_2['geometry'].astype(str)

        geometry_uniq = pd.DataFrame(gdf_2['geometry'].drop_duplicates())
        geometry_uniq['id'] = np.arange(len(geometry_uniq)).astype(str)
        gdf_2 = gdf_2.merge(geometry_uniq, on = 'geometry')
        gdf_2['geometry'] = gdf_2['geometry'].apply(wkt.loads)

        gdf_2 = gpd.GeoDataFrame(gdf_2, geometry='geometry')
        gdf_2.set_crs(epsg=4326, inplace=True)

        gdf_1['geometry'] = gdf_1['geometry'].apply(lambda geom: geom if geom.is_valid else geom.buffer(0))
        gdf_2['geometry'] = gdf_2['geometry'].apply(lambda geom: geom if geom.is_valid else geom.buffer(0))

        itog_table = gpd.sjoin(gdf_2, gdf_1, how='left', op='intersects')
        itog_table = itog_table.dropna()
        data = {
            'polygon': [],
            'time': []
        }
        df = pd.DataFrame(data)
        travel_time_seconds = []
        coord = [(row['lat'], row['lon']) for index, row in itog_table.iterrows()]
        resolution = 10
        hexagons = [h3.geo_to_h3(lat, lon, resolution) for lat, lon in coord]
        for hex in hexagons:
            hexagons_ring = h3.k_ring(hex,1)
            center_coord = list(h3.h3_to_geo(hex))
            for i, h3_hexagoninring in enumerate(hexagons_ring):
                target_coord = list(h3.h3_to_geo(h3_hexagoninring))
                travel_time = calculate_travel_time(center_coord[0], center_coord[1], target_coord[0], target_coord[1])
                #index = itog_table[itog_table['lat'] == ].index[0]
                travel_time_seconds.append(travel_time)
                point = Point(target_coord[1], target_coord[0])
                for i in polygons_city:
                    if i.contains(point):
                        new_row = {'polygon': i, 'time': travel_time}
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)


        df_copy = df.copy(deep=True)
        df = df.sort_values(by = 'time', ascending=True)
        zero_polygons = []
        for i in df['polygon']:
            index = df[df['polygon'] == i].index[0]
            if(df.loc[index, 'time'] == 0):
                zero_polygons.append(i)

        df = df.drop_duplicates(subset=['polygon'])
        df['id'] = range(1, len(df) + 1)
        df['time'] = df['time'].astype(int)

        df['polygon'] = df['polygon'].astype(str) #для groupby
        df['id'] = df['id'].astype(str) #для Choropleth
        df['polygon'] = df['polygon'].apply(wkt.loads) #возвращаем формат геометрий

        data_geo_1 = gpd.GeoSeries(df.set_index('id')["polygon"]).to_json()
        m = create_choropleth(df, data_geo_1, ["id", "time"], 'Время передвижения от центра', 30, polygon_krd)
        
        # Save the map to an HTML file
        map_divs = [m._repr_html_()]
        return render_template('map.html', map_divs=map_divs)
    return render_template('index.html')

@app.route('/process_coordinates', methods=['POST'])
def process_coordinates():
        if request.method == 'POST':
            latitude = request.form.get('latitude')
            longitude = request.form.get('longitude')
            # Здесь вы можете обработать координаты, например, сохранить их в базу данных или использовать в бизнес-логике
            busines_df = pd.read_csv('dataframe.csv')
            busines_df.loc[len(busines_df)] = [pd.NA] * len(busines_df.columns)
            longitude = round(float(longitude), 6)
            latitude = round(float(latitude), 6)
            busines_df.at[len(busines_df)-1, 'coordinates'] = f"[{float(longitude)}, {float(latitude)}]" # [longitude, latitude]
            busines_df.at[len(busines_df)-1, 'geometry'] = {'type': 'Point', 'coordinates': [float(longitude), float(latitude)]} # [longitude, latitude]
            busines_df.at[len(busines_df)-1, 'city'] = 'Свободный'
            busines_df.at[len(busines_df)-1, 'object'] = 'building'
            data = {
                'lat': float(longitude),
                'lon': float(latitude)
            }
            result_coord.append(data)
            h3_address = []
            for i in result_coord:
                h3_address.append(h3.geo_to_h3(i["lon"], i["lat"],  10))
            cities = [f'{city}']
            polygon_krd = ox.geometries_from_place(cities, {'boundary':'administrative'}).reset_index()
            # посмотрим что получилось
            geoJson = json.loads(gpd.GeoSeries(polygon_krd['geometry']).to_json())
            geoJson = geoJson['features'][0]['geometry']
            try:
                geoJson = {'type':'Polygon','coordinates': [np.column_stack((np.array(geoJson['coordinates'][0])[:, 1], np.array(geoJson['coordinates'][0])[:, 0])).tolist()]}
            except:
                line = LineString(geoJson['coordinates'])
                polygon = line.buffer(0.001)  # Buffer to create a polygon around the line
                coordinates = np.array(polygon.exterior.coords)
                geoJson = {
                    'type': "Polygon",
                    'coordinates': [np.column_stack((coordinates[:, 1], coordinates[:, 0])).tolist()]
                }
            m, polygons_city, polylines = create_hexagons(geoJson)
            # посмотрим что получилось


            def get_lat_lon_mine(geometry):
                lon = geometry.apply(lambda x: x.x)
                lat = geometry.apply(lambda x: x.y)
                return lat, lon
            # добавим координаты/центроиды
            def parse_coordinates(coord_str):
                coord_str = coord_str.strip('[]')
                lat, lon = map(float, coord_str.split(','))
                return lat, lon

        # Преобразование координат в DataFrame
            busines_df['coordinates'] = busines_df['coordinates'].apply(parse_coordinates)
            geometry_objects = [Point(xy[0], xy[1]) for xy in busines_df['coordinates']]
            gdf1 = gpd.GeoDataFrame(geometry=geometry_objects)
            busines_df = busines_df.drop('coordinates', axis = 1)


            help = pd.DataFrame()
            data_poi = pd.concat([busines_df, help])

            lat, lon = get_lat_lon_mine(gdf1['geometry'])
            data_poi['lat'] = lat
            data_poi['lon'] = lon
            gdf_1 = gpd.GeoDataFrame(data_poi, geometry=gpd.points_from_xy(data_poi.lon, data_poi.lat))
            gdf_1.set_crs(epsg=4326, inplace=True)

            gdf_2 = pd.DataFrame(polygons_city, columns = ['geometry'])
            gdf_2['polylines'] = polylines
            gdf_2['geometry'] = gdf_2['geometry'].astype(str)

            geometry_uniq = pd.DataFrame(gdf_2['geometry'].drop_duplicates())
            geometry_uniq['id'] = np.arange(len(geometry_uniq)).astype(str)
            gdf_2 = gdf_2.merge(geometry_uniq, on = 'geometry')
            gdf_2['geometry'] = gdf_2['geometry'].apply(wkt.loads)

            gdf_2 = gpd.GeoDataFrame(gdf_2, geometry='geometry')
            gdf_2.set_crs(epsg=4326, inplace=True)

            gdf_1['geometry'] = gdf_1['geometry'].apply(lambda geom: geom if geom.is_valid else geom.buffer(0))
            gdf_2['geometry'] = gdf_2['geometry'].apply(lambda geom: geom if geom.is_valid else geom.buffer(0))

            itog_table = gpd.sjoin(gdf_2, gdf_1, how='left', op='intersects')
            itog_table = itog_table.dropna()
            data = {
                'polygon': [],
                'time': []
            }
            df = pd.DataFrame(data)
            travel_time_seconds = []
            coord = [(row['lat'], row['lon']) for index, row in itog_table.iterrows()]
            resolution = 10
            hexagons = [h3.geo_to_h3(lat, lon, resolution) for lat, lon in coord]
            for hex in hexagons:
                hexagons_ring = h3.k_ring(hex,1)
                center_coord = list(h3.h3_to_geo(hex))
                for i, h3_hexagoninring in enumerate(hexagons_ring):
                    target_coord = list(h3.h3_to_geo(h3_hexagoninring))
                    travel_time = calculate_travel_time(center_coord[0], center_coord[1], target_coord[0], target_coord[1])
                    #index = itog_table[itog_table['lat'] == ].index[0]
                    travel_time_seconds.append(travel_time)
                    point = Point(target_coord[1], target_coord[0])
                    for i in polygons_city:
                        if i.contains(point):
                            new_row = {'polygon': i, 'time': travel_time}
                            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)


            df_copy = df.copy(deep=True)
            df = df.sort_values(by = 'time', ascending=True)
            zero_polygons = []
            for i in df['polygon']:
                index = df[df['polygon'] == i].index[0]
                if(df.loc[index, 'time'] == 0):
                    zero_polygons.append(i)

            df = df.drop_duplicates(subset=['polygon'])
            df['id'] = range(1, len(df) + 1)
            df['time'] = df['time'].astype(int)

            df['polygon'] = df['polygon'].astype(str) #для groupby
            df['id'] = df['id'].astype(str) #для Choropleth
            df['polygon'] = df['polygon'].apply(wkt.loads) #возвращаем формат геометрий

            data_geo_1 = gpd.GeoSeries(df.set_index('id')["polygon"]).to_json()
            m = create_choropleth(df, data_geo_1, ["id", "time"], 'Время передвижения от центра', 30, polygon_krd)
            # Save the map to an HTML file
            map_divss = [m._repr_html_()]
            return render_template('fresh_map.html', map_divss=map_divss)

if __name__ == '__main__':
    app.run(debug=True)

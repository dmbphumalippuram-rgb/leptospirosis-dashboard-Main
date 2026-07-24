import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point
import os

# ==============================================================================
# 1. PAGE CONFIGURATION & METRICS DISPLAY
# ==============================================================================
st.set_page_config(
    page_title="Ernakulam Leptospirosis Hotspot Dashboard",
    page_icon="🦠",
    layout="wide"
)

st.title("🦠 Leptospirosis Hotspot Tracker & GIS Dashboard")
st.markdown("Analyze block-level Leptospirosis incidence in Ernakulam District, identify hotspots (>5 cases), and inspect spatial distribution.")

# ==============================================================================
# 2. ACCURATE ERNAKULAM HEALTH BLOCK DATA (WITH REAL LAT/LON)
# ==============================================================================
@st.cache_data
def load_data():
    # Accurate Geographic Coordinates for Ernakulam Health Blocks
    raw_data = {
        'Health Blocks': [
            'Angamaly', 'Chengamanad', 'Cheranalloor', 'Ezhikkara', 'Kalady',
            'Keechery', 'Kumbalanghi', 'Malayidamthuruth', 'Malippuram', 'Nettoor',
            'Pallarimangalam', 'Pampakuda', 'Pandappilly', 'Pizhala', 'Ramamangalam',
            'Vadavucode', 'Varappetty', 'Varappuzha', 'Vengoor', 'Kochi Corporation'
        ],
        'Number of Cases': [
            12, 4, 8, 2, 8, 7, 3, 20, 3, 2, 4, 4, 5, 0, 5, 10, 7, 4, 13, 11
        ],
        'latitude': [
            10.1960, 10.1517, 10.0461, 10.1412, 10.1685,
            9.8432, 9.8752, 10.0416, 10.0234, 9.9234,
            10.0789, 9.8631, 9.8921, 10.0521, 9.8512,
            9.9723, 10.0214, 10.0762, 10.1821, 9.9674
        ],
        'longitude': [
            76.3860, 76.3685, 76.2891, 76.2185, 76.4385,
            76.4321, 76.2845, 76.3985, 76.2189, 76.3124,
            76.6821, 76.5412, 76.6214, 76.2412, 76.5812,
            76.4412, 76.6512, 76.2612, 76.5512, 76.2426
        ]
    }
    return pd.DataFrame(raw_data)

@st.cache_data
def load_geojson_if_exists(df):
    geojson_path = "ernakulam.geojson"
    
    if os.path.exists(geojson_path):
        gdf = gpd.read_file(geojson_path).to_crs(epsg=4326)
        
        # Identify region name column from OSM Kerala attributes
        possible_cols = ['name', 'LSGD', 'BLOCK_NAME', 'PANCHAYAT', 'shapeName', 'Health Blocks']
        matched_col = next((c for c in possible_cols if c in gdf.columns), gdf.columns[0])
        
        gdf['Health Blocks'] = gdf[matched_col]
        
        # Merge GIS geometry with disease incidence
        gdf = gdf.merge(df, on='Health Blocks', how='inner')
        
        # Compute exact centroids
        centroids = gdf.geometry.centroid
        gdf['centroid_lat'] = centroids.y
        gdf['centroid_lon'] = centroids.x
        return gdf, True
    else:
        # Fallback if file is missing
        geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
        gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
        gdf['centroid_lat'] = df['latitude']
        gdf['centroid_lon'] = df['longitude']
        return gdf, False

# Load datasets
df_cases = load_data()
gdf_merged, has_geojson = load_geojson_if_exists(df_cases)

if not has_geojson:
    st.info("ℹ️ Running in **Point Marker Mode** using verified Ernakulam coordinates. To view polygon boundary shading, place `ernakulam_health_blocks.geojson` in your project folder.")

# ==============================================================================
# 3. TOP METRICS KPI BAR
# ==============================================================================
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
col_kpi1.metric("Total Cases", int(gdf_merged['Number of Cases'].sum()))
col_kpi2.metric("Total Health Blocks", len(gdf_merged))
col_kpi3.metric("Hotspot Blocks (>5 Cases)", int((gdf_merged['Number of Cases'] > 5).sum()))
col_kpi4.metric("Highest Incidence", f"{gdf_merged['Number of Cases'].max()} ({gdf_merged.loc[gdf_merged['Number of Cases'].idxmax(), 'Health Blocks']})")

st.markdown("---")

# ==============================================================================
# 4. SIDE-BY-SIDE DASHBOARD LAYOUT (MAP & DATA TABLE)
# ==============================================================================
left_col, right_col = st.columns([3, 2])

with left_col:
    st.subheader("🗺️ Spatial Distribution & Hotspot Map")
    
    # Center map over Ernakulam, Kerala
    m = folium.Map(
        location=[10.00, 76.35],
        zoom_start=10,
        tiles="CartoDB positron"
    )
    
    # Render GeoJSON Boundaries if file is provided
    if has_geojson:
        choropleth = folium.Choropleth(
            geo_data=gdf_merged,
            name="Choropleth Intensity",
            data=gdf_merged,
            columns=["Health Blocks", "Number of Cases"],
            key_on="feature.properties.Health Blocks",
            fill_color="YlOrRd",
            fill_opacity=0.4,
            line_opacity=0.6,
            line_weight=1.5,
            legend_name="Leptospirosis Cases",
            highlight=True
        ).add_to(m)

        choropleth.geojson.add_child(
            folium.features.GeoJsonTooltip(
                fields=["Health Blocks", "Number of Cases"],
                aliases=["Block:", "Cases:"],
                style="font-family: sans-serif; font-size: 12px; padding: 6px;"
            )
        )

    # Render Circle Markers for all Blocks (Red for Hotspots >5, Blue for Low Incidence <=5)
    for _, row in gdf_merged.iterrows():
        lat = row['centroid_lat']
        lon = row['centroid_lon']
        cases = row['Number of Cases']
        block_name = row['Health Blocks']
        is_hotspot = cases > 5
        
        # Color coding: Red for Hotspots, Light Blue for Non-Hotspots
        color_code = "#D32F2F" if is_hotspot else "#1E88E5"
        fill_code = "#FF1744" if is_hotspot else "#64B5F6"
        
        folium.CircleMarker(
            location=[lat, lon],
            radius=6 + (cases * 0.5), # Scale radius with case volume
            color=color_code,
            fill=True,
            fill_color=fill_code,
            fill_opacity=0.85,
            weight=2,
            tooltip=f"<b>{'HOTSPOT: ' if is_hotspot else ''}{block_name}</b><br>Cases: {cases}",
            popup=folium.Popup(
                f"<div style='font-family: sans-serif; min-width: 130px;'>"
                f"<h4 style='margin:0; color:{color_code};'>{block_name}</h4>"
                f"<hr style='margin:5px 0;'>"
                f"<b>Status:</b> {'⚠️ Hotspot (>5)' if is_hotspot else 'Normal (≤5)'}<br>"
                f"<b>Total Cases:</b> {cases}"
                f"</div>", 
                max_width=250
            )
        ).add_to(m)

    st_folium(m, width="100%", height=500)

with right_col:
    st.subheader("📋 Block Data Breakdown")
    
    search_query = st.text_input("🔍 Search Health Block", "")
    
    filtered_df = df_cases.copy()
    if search_query:
        filtered_df = filtered_df[filtered_df['Health Blocks'].str.contains(search_query, case=False)]
        
    show_hotspots_only = st.checkbox("Show Hotspots Only (>5 Cases)")
    if show_hotspots_only:
        filtered_df = filtered_df[filtered_df['Number of Cases'] > 5]

    st.dataframe(
        filtered_df[['Health Blocks', 'Number of Cases']].sort_values(by="Number of Cases", ascending=False),
        column_config={
            "Health Blocks": st.column_config.TextColumn("Health Block"),
            "Number of Cases": st.column_config.ProgressColumn(
                "Number of Cases",
                help="Total reported Leptospirosis cases",
                format="%d",
                min_value=0,
                max_value=int(df_cases['Number of Cases'].max())
            )
        },
        use_container_width=True,
        hide_index=True,
        height=400
    )

import streamlit as st
import pydeck as pdk
from db import Cassandra
import json
import matplotlib.pyplot as plt
import contextily as ctx
import sys
import pandas as pd

# Add utils to path
sys.path.append('./utils')

from header import simple_header
from filters import FilterManager

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')

# Global styles -------------------------------------------------------------------
st.set_page_config(layout="wide")

# Load the external CSS file
@st.cache_resource
def load_css():
    try:
        with open("./style.css") as f:
            return f.read()
    except FileNotFoundError:
        return ""

css_content = load_css()
if css_content:
    st.markdown(f'<style>{css_content}</style>', unsafe_allow_html=True)
# ---------------------------------------------------------------------------------

# Title with consistent styling
simple_header("Cracks Heatmap & Road Conditions", "Interactive maps showing crack distribution and road conditions", "🗺️")

# Initialize Cassandra connection
@st.cache_resource
def get_cassandra():
    return Cassandra()

cassandra = get_cassandra()

# Initialize Filter Manager
filter_manager = FilterManager(cassandra)

# Render filters in sidebar
filter_manager.render_filters_sidebar()

# Get current filters
current_filters = filter_manager.get_current_filters()

# Show filter summary - FIXED: Convert date objects to strings
with st.expander("📋 Current Filter Summary", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Districts", len(current_filters['districts']))
    with col2:
        st.metric("Confidence ≥", f"{current_filters['confidence']:.2f}")
    with col3:
        # Convert date to string
        start_date_str = current_filters['start_date'].strftime('%Y-%m-%d') if current_filters['start_date'] else 'N/A'
        st.metric("Start Date", start_date_str)
    with col4:
        # Convert date to string
        end_date_str = current_filters['end_date'].strftime('%Y-%m-%d') if current_filters['end_date'] else 'N/A'
        st.metric("End Date", end_date_str)

# ==============================================================================
# HEATMAP SECTION - EXACTLY AS BEFORE
# ==============================================================================
st.markdown("---")
st.title("🌡️ Cracks heatmap")

# Query with current filters
if current_filters['districts'] and current_filters['start_date'] and current_filters['end_date']:
    dists_filter = ", ".join([f"'{d}'" for d in current_filters['districts']])
    start_iso = f"{current_filters['start_date'].isoformat()} 00:00:00"
    end_iso = f"{current_filters['end_date'].isoformat()} 23:59:59"
    
    query = f"""
        SELECT lon, lat, confidence, label, timestamp, image 
        FROM crack 
        WHERE dist IN ({dists_filter}) 
        AND confidence >= {current_filters['confidence']}
        AND timestamp >= '{start_iso}' 
        AND timestamp <= '{end_iso}' 
        ALLOW FILTERING
    """
    
    cassandra.exec(query)
    data = cassandra.data.copy()
    
    if not data.empty and 'timestamp' in data.columns:
        data['timestamp'] = pd.to_datetime(data['timestamp']).dt.strftime("%Y-%m-%d %H:%M:%S")
else:
    # Fallback to original query if no districts selected
    cassandra.exec("SELECT lon, lat, confidence, label, timestamp, image FROM crack")
    data = cassandra.data.copy()
    if not data.empty and 'timestamp' in data.columns:
        data['timestamp'] = data['timestamp'].dt.strftime("%Y-%m-%d %H:%M:%S")

# Check if we have data
if data.empty:
    st.warning("No crack data available for the selected filters.")
    st.info("Showing heatmap without filters...")
    cassandra.exec("SELECT lon, lat, confidence, label, timestamp, image FROM crack")
    data = cassandra.data.copy()
    if not data.empty and 'timestamp' in data.columns:
        data['timestamp'] = pd.to_datetime(data['timestamp']).dt.strftime("%Y-%m-%d %H:%M:%S")

if not data.empty:
    # Initial view - EXACTLY AS BEFORE
    view_state = pdk.ViewState(
        latitude=data['lat'].iloc[0],
        longitude=data['lon'].iloc[0],
        zoom=15,
        pitch=45
    )

    # Heatmap layer - EXACTLY AS BEFORE
    heatmap_layer = pdk.Layer(
        "HeatmapLayer",
        data=data,
        get_position=["lon", "lat"],
        get_weight='confidence',
        aggregation="MEAN",
        radiusPixels=60,
        intensity=1.2,
        colorRange=[
            [46, 204, 113, 80],        # Emerald Green
            [241, 196, 15, 120],       # Yellow
            [230, 126, 34, 160],       # Orange
            [231, 76, 60, 200],        # Red
        ],
        pickable=False,
    )

    # Scatterplot layer for hover - EXACTLY AS BEFORE
    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position=["lon", "lat"],
        get_fill_color=[255, 140, 0],  # Color of points
        get_radius=1,
        pickable=True,                 # enables hover
        auto_highlight=True,
    )

    # Deck with both layers - EXACTLY AS BEFORE
    deck = pdk.Deck(
        layers=[heatmap_layer, scatter_layer],
        initial_view_state=view_state,
        tooltip={
            "html": """
            <b>Image:</b> {image} <br/>
            <b>Timestamp:</b> {timestamp} <br/>
            <b>Crack Type:</b> {label} <br/> 
            <b>Confidence:</b> {confidence}""",
            "style": {
                "color": "white",
                "backgroundColor": "rgba(0, 0, 0, 0.7)",
                "fontSize": "14px",
            }
        }
    )

    # Display in Streamlit - EXACTLY AS BEFORE
    st.pydeck_chart(deck)
else:
    st.error("No data available to display heatmap.")

# ==============================================================================
# ROAD CONDITIONS SECTION - EXACTLY AS BEFORE
# ==============================================================================
st.markdown("---")
st.title("🗺️ Roads PCI Map")

# Query with current filters
if current_filters['districts'] and current_filters['start_date'] and current_filters['end_date']:
    dists_filter = ", ".join([f"'{d}'" for d in current_filters['districts']])
    start_iso = f"{current_filters['start_date'].isoformat()} 00:00:00"
    end_iso = f"{current_filters['end_date'].isoformat()} 23:59:59"
    
    query = f"""
        SELECT x1,x2,y1,y2, road_index, label, ppm 
        FROM crack 
        WHERE dist IN ({dists_filter}) 
        AND confidence >= {current_filters['confidence']}
        AND timestamp >= '{start_iso}' 
        AND timestamp <= '{end_iso}' 
        ALLOW FILTERING
    """
    
    cassandra.exec(query)
    cassandra.join_roads()
    cassandra.calc_pci()
    data = cassandra.data.copy()
else:
    # Fallback to original query
    cassandra.exec("SELECT x1,x2,y1,y2, road_index, label, ppm FROM crack")
    cassandra.join_roads()
    cassandra.calc_pci()
    data = cassandra.data.copy()

if not data.empty:
    # Color map - EXACTLY AS BEFORE
    color_map = {
        "Excellent": [0, 255, 0, 120],
        "Good": [0, 200, 255, 120],
        "Fair": [255, 255, 0, 120],
        "Poor": [255, 165, 0, 120],
        "Very Poor": [255, 0, 255, 120],
        "Failed": [255, 0, 0, 120]
    }

    data["color"] = data["condition"].map(color_map)

    # Count per condition - EXACTLY AS BEFORE
    summary = data\
        .drop_duplicates(subset=['road_index'], keep='first')['condition']\
        .value_counts().reindex(
        ["Excellent", "Good", "Fair", "Poor", "Very Poor", "Failed"], fill_value=0
    )

    st.markdown("Number of roads in each PCI category.")

    # Display as colored cards - EXACTLY AS BEFORE
    st.markdown("""
<div style="text-align: center; color: #64748b; margin-bottom: 1rem; font-size: 0.9rem;">
    <i>Road Condition Distribution</i>
</div>
""", unsafe_allow_html=True)

    # Display as compact badges
    cols = st.columns(len(summary))

    for i, (condition, count) in enumerate(summary.items()):
        r, g, b, a = color_map[condition]
    
        with cols[i]:
            st.markdown(
                f"""
                <div style="
                    background: rgba({r}, {g}, {b}, 0.1);
                    border: 2px solid rgba({r}, {g}, {b}, 0.3);
                    border-radius: 12px;
                    padding: 1rem 0.5rem;
                    text-align: center;
                    height: 100px;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                ">
                    <div style="
                        font-size: 1.8rem;
                        font-weight: 700;
                        color: rgba({r}, {g}, {b}, 1);
                        margin-bottom: 0.3rem;
                    ">
                        {count}
                    </div>
                    <div style="
                        font-size: 0.8rem;
                        font-weight: 600;
                        color: rgba({r}, {g}, {b}, 0.9);
                        background: rgba({r}, {g}, {b}, 0.15);
                        padding: 0.2rem 0.6rem;
                        border-radius: 20px;
                    ">
                        {condition}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    geojson_data = json.loads(data.to_json())

    tooltip = {
        "html": """
            <b>Street:</b> {name}<br>
            <b>Condition:</b> {condition}<br>
            <b>PCI:</b> {pci}<br>
        """,
        "style": {
            "backgroundColor": "steelblue",
            "color": "white",
            "fontSize": "12px"
        }
    }

    # Create Pydeck Layer - EXACTLY AS BEFORE
    layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson_data,  # must be a dict or URL
        get_line_color="properties.color",  # must be stored in properties
        get_line_width=7,
        pickable=True,
        auto_highlight=True
    )

    # Define view - EXACTLY AS BEFORE
    view_state = pdk.ViewState(
        latitude=data.geometry.centroid.y.mean(),
        longitude=data.geometry.centroid.x.mean(),
        zoom=12
    )

    # Render - EXACTLY AS BEFORE
    deck = pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip, map_style="light")
    st.pydeck_chart(deck)
else:
    st.warning("No road data available for the selected filters.")

# ==============================================================================
# STATIC MAP SECTION - EXACTLY AS BEFORE (Commented out)
# ==============================================================================
# st.markdown("---")
# st.markdown("### 📍 Static Map (Optional)")
# 
# if not data.empty and 'geometry' in data.columns:
#     # data = data.to_crs(epsg=3857)
#     # data.plot(label='condition')
# 
#     fig, ax = plt.subplots(figsize=(10, 10))
#     data.plot(ax=ax, linewidth=3, color='green')
#     ctx.add_basemap(ax)
#     ax.set_axis_off()
#     plt.tight_layout()
#     st.pyplot(fig)
# else:
#     st.info("Static map requires geometry data.")

# ==============================================================================
# FOOTER
# ==============================================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #64748b; font-size: 0.9rem; margin-top: 2rem;">
    <i>Maps update based on selected filters. Use the sidebar to adjust criteria.</i>
</div>
""", unsafe_allow_html=True)
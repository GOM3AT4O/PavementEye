import streamlit as st
from db import Cassandra
import plotly.express as px
import numpy as np
from azure.storage.blob import BlobServiceClient
import cv2
from dotenv import load_dotenv
import os
from colors import DASHBOARD_PALETTE
import pandas as pd
from datetime import datetime
import warnings
import sys

# Import libs ----------------------
sys.path.append('./utils')

from header import title_page1
from filters import FilterManager

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

# Global styles and config -------------------------------------------------------------------
st.set_page_config(layout="wide")

# Load external CSS file efficiently
@st.cache_resource
def load_css():
    try:
        with open("style.css") as f:
            return f.read()
    except FileNotFoundError:
        return ""

css_content = load_css()
if css_content:
    st.markdown(f'<style>{css_content}</style>', unsafe_allow_html=True)
# ---------------------------------------------------------------------------------

# Title with custom styling
title_page1()

# Initialize Cassandra connection with caching
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

# Get filtered data
filtered_data = filter_manager.get_filtered_data()

if filtered_data is None:
    st.warning("Please configure filters in the sidebar")
    st.stop()

# Get data for road length calculation
@st.cache_data(ttl=300)
def get_road_data():
    cassandra.exec("SELECT road_index, label FROM crack")
    data2 = cassandra.join_roads()
    
    # Check if geometry column exists
    if 'geometry' in data2.columns and hasattr(data2, 'to_crs'):
        data2 = data2.to_crs("EPSG:3857")
        data2['length_km'] = data2.geometry.length / 1000
    else:
        data2['length_km'] = 0
    
    return data2

try:
    road_data = get_road_data()
    
    # Filter road data based on current filters
    road_data_columns = road_data.columns
    filter_conditions = []
    
    # Check if 'timestamp' column exists and filter by date
    if 'timestamp' in road_data_columns:
        try:
            road_data['date'] = pd.to_datetime(road_data['timestamp']).dt.date
            filter_conditions.append(road_data['date'] >= current_filters['start_date'])
            filter_conditions.append(road_data['date'] <= current_filters['end_date'])
        except:
            pass
    
    # Check if 'dist' column exists
    if 'dist' in road_data_columns:
        filter_conditions.append(road_data['dist'].isin(current_filters['districts']))
    elif 'district' in road_data_columns:
        filter_conditions.append(road_data['district'].isin(current_filters['districts']))
    
    # Check if 'confidence' column exists
    if 'confidence' in road_data_columns:
        filter_conditions.append(road_data['confidence'] >= current_filters['confidence'])
    
    # Apply filters
    if filter_conditions:
        mask = filter_conditions[0]
        for condition in filter_conditions[1:]:
            mask = mask & condition
        filtered_road_data = road_data[mask].copy()
    else:
        filtered_road_data = road_data.copy()
        
except Exception as e:
    st.error(f"Error loading data: {str(e)}")
    st.stop()

# Metrics ----------------------------------------------------------------------------------
with st.container():
    st.markdown("### 📈 Key Metrics")
    
    col1, col2, col3 = st.columns(3)
    
    # Calculate total length
    if 'length_km' in filtered_road_data.columns:
        total_len_km = filtered_road_data['length_km'].sum()
    else:
        total_len_km = 0
    
    # Calculate unique roads
    if 'road_index' in filtered_road_data.columns:
        unique_roads = filtered_road_data['road_index'].nunique()
    else:
        unique_roads = 0
    
    # Card 1: Total Cracks
    with col1:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 1.5rem;
            color: white;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        ">
            <div style="font-size: 0.9rem; opacity: 0.9; margin-bottom: 0.5rem;">
                🧱 Total Cracks
            </div>
            <div style="font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;">
                {:,}
            </div>
            <div style="font-size: 0.8rem; opacity: 0.8;">
                Across all selected districts
            </div>
        </div>
        """.format(len(filtered_road_data)), unsafe_allow_html=True)
    
    # Card 2: Total Length
    with col2:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            border-radius: 15px;
            padding: 1.5rem;
            color: white;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        ">
            <div style="font-size: 0.9rem; opacity: 0.9; margin-bottom: 0.5rem;">
                🛣️ Total Length
            </div>
            <div style="font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;">
                {:.2f} Km
            </div>
            <div style="font-size: 0.8rem; opacity: 0.8;">
                Combined road length
            </div>
        </div>
        """.format(total_len_km), unsafe_allow_html=True)
    
    # Card 3: Unique Roads
    with col3:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            border-radius: 15px;
            padding: 1.5rem;
            color: white;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            height: 140px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        ">
            <div style="font-size: 0.9rem; opacity: 0.9; margin-bottom: 0.5rem;">
                🗺️ Unique Roads
            </div>
            <div style="font-size: 2.5rem; font-weight: 700; margin-bottom: 0.5rem;">
                {:,}
            </div>
            <div style="font-size: 0.8rem; opacity: 0.8;">
                Distinct road segments
            </div>
        </div>
        """.format(unique_roads), unsafe_allow_html=True)

# Optional: Add some spacing
st.markdown("<br>", unsafe_allow_html=True)

# Recent cracks table ------------------------------------------------------------------
with st.container():
    st.markdown("### 📋 Recent Cracks")
    if not filtered_data.empty:
        display_data = filtered_data.head(50)
        st.dataframe(
            display_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "image": st.column_config.TextColumn("Image", width="medium"),
                "label": st.column_config.TextColumn("Label", width="small"),
                "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
                "timestamp": st.column_config.DatetimeColumn("Timestamp"),
            }
        )
    else:
        st.info("No cracks found for the selected filters")

# Image detection section ------------------------------------------------------------------
@st.cache_resource
def get_blob_service():
    load_dotenv()
    account_name = os.getenv("account_name")
    account_key = os.getenv("account_key")
    connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
    return BlobServiceClient.from_connection_string(connection_string)

with st.container():
    st.markdown("### 🎯 Detection Results")
    
    image_name = st.text_input(
        "🔍 Enter image name (with extension):",
        placeholder="e.g., image_12345.jpg",
        help="You can get image names from the table above"
    )
    
    if image_name:
        with st.spinner("Loading image and detections..."):
            try:
                blob_service_client = get_blob_service()
                file_system_name = os.getenv("file_system_name")
                blob_client = blob_service_client.get_blob_client(
                    container=file_system_name, 
                    blob=f"raw/{image_name}"
                )
                
                image_data = blob_client.download_blob().readall()
                nparr = np.frombuffer(image_data, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if image is None:
                    st.error("Could not decode image. Please check the file name and format.")
                else:
                    # Get detections for this image
                    image_column = None
                    for col in ['image', 'filename', 'img_name', 'image_name']:
                        if col in filtered_data.columns:
                            image_column = col
                            break
                    
                    if image_column:
                        detections = filtered_data[filtered_data[image_column] == image_name]
                    else:
                        detections = filtered_data[filtered_data.astype(str).apply(
                            lambda row: image_name in row.values, axis=1
                        )]
                    
                    if not detections.empty:
                        img_annotated = image.copy()
                        for _, row in detections.iterrows():
                            # Get coordinates
                            coord_mapping = {
                                'x1': ['x1', 'xmin', 'x_min'],
                                'x2': ['x2', 'xmax', 'x_max'],
                                'y1': ['y1', 'ymin', 'y_min'],
                                'y2': ['y2', 'ymax', 'y_max']
                            }
                            
                            coords = {}
                            for coord_key, possible_names in coord_mapping.items():
                                for name in possible_names:
                                    if name in row:
                                        coords[coord_key] = int(row[name])
                                        break
                            
                            if len(coords) == 4:
                                x1, x2, y1, y2 = coords['x1'], coords['x2'], coords['y1'], coords['y2']
                                
                                # Get label
                                label_col = None
                                for col in ['label', 'class', 'type', 'crack_type']:
                                    if col in row:
                                        label_col = col
                                        break
                                label = row[label_col] if label_col else "unknown"
                                
                                conf = row.get('confidence')
                                
                                # Draw rectangle
                                cv2.rectangle(img_annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                                
                                # Add label
                                text = f"{label}"
                                if pd.notna(conf):
                                    text += f" ({conf:.2f})"
                                
                                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                                cv2.rectangle(img_annotated, (x1, y1 - th - 4), (x1 + tw, y1), (0, 255, 0), -1)
                                cv2.putText(img_annotated, text, (x1, y1 - 4), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                        
                        img_rgb = cv2.cvtColor(img_annotated, cv2.COLOR_BGR2RGB)
                        st.image(img_rgb, caption=f"Detections for {image_name}", use_container_width=True)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**Total detections:** {len(detections)}")
                        with col2:
                            label_col = None
                            for col in ['label', 'class', 'type']:
                                if col in detections.columns:
                                    label_col = col
                                    break
                            if label_col:
                                unique_labels = detections[label_col].unique()
                                st.info(f"**Crack types:** {', '.join(map(str, unique_labels))}")
                    else:
                        st.warning(f"No detections found for image: {image_name}")
                        
            except Exception as e:
                st.error(f"Error loading image: {str(e)}")

# Charts section ---------------------------------------------------------------------------
with st.container():
    st.markdown("### 📊 Analysis Charts")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if not filtered_data.empty:
            st.markdown("##### Crack Type Distribution")
            
            label_col = None
            for col in ['label', 'class', 'type', 'crack_type']:
                if col in filtered_data.columns:
                    label_col = col
                    break
            
            if label_col:
                crack_counts = filtered_data[label_col].value_counts().sort_values()
                
                fig = px.bar(
                    x=crack_counts.values,
                    y=crack_counts.index,
                    orientation='h',
                    labels={'x': 'Count', 'y': 'Crack Type'},
                    color=crack_counts.index,
                    color_discrete_sequence=DASHBOARD_PALETTE,
                    title=None
                )
                
                fig.update_layout(
                    yaxis=dict(categoryorder='total ascending'),
                    template='plotly_white',
                    showlegend=False,
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No label column found for chart")
        else:
            st.info("No data available for chart")
    
    with col2:
        if not filtered_road_data.empty:
            st.markdown("##### Crack Type by Road Type")
            
            fclass_col = None
            label_col = None
            
            for col in ['fclass', 'road_type', 'class', 'type']:
                if col in filtered_road_data.columns:
                    fclass_col = col
                    break
            
            for col in ['label', 'class', 'type', 'crack_type']:
                if col in filtered_road_data.columns:
                    label_col = col
                    break
            
            if fclass_col and label_col:
                grouped_df = filtered_road_data.groupby([fclass_col, label_col]).size().reset_index(name='count')
                
                fig = px.treemap(
                    grouped_df,
                    path=[fclass_col, label_col],
                    values="count",
                    color=fclass_col,
                    color_discrete_sequence=DASHBOARD_PALETTE,
                    title=None
                )
                
                fig.update_layout(
                    height=400,
                    margin=dict(t=0, l=0, r=0, b=0)
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Cannot create treemap. Missing required columns.")
        else:
            st.info("No data available for treemap")
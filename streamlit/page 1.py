import streamlit as st
from db import Cassandra
import matplotlib.pyplot as plt
import plotly.express as px
import numpy as np
from azure.storage.blob import BlobServiceClient
import cv2
from dotenv import load_dotenv
import os
from ultralytics import YOLO

# Global styles -------------------------------------------------------------------
st.set_page_config(layout="wide")

# Load the external CSS file
def local_css(file_name):
  with open(file_name) as f:
      st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("style.css")
# ---------------------------------------------------------------------------------

cassandra = Cassandra()
cassandra.exec("SELECT * FROM crack")
data = cassandra.join_roads()
data = data.drop(['geometry', 'index', 'road_index', 'id'], axis=1)

st.title("🛣️ Pavement eye")

# ------------------------------------------------------------------------------
cassandra.exec("SELECT road_index, label FROM crack")
data2 = cassandra.join_roads()

col1, col2, col3 = st.columns(3)

data2 = data2.to_crs("EPSG:3857")
data2['length_km'] = data2.geometry.length / 1000
total_len_km = data2['length_km'].sum()

col1.metric("Total Number of cracks", len(data2))
col2.metric("Total length in Km", round(total_len_km, 2))
# ----------------------------------------------------------------------------------


st.markdown("###### Last cracks")
st.dataframe(data)


# ----------------------------------------------------------------------------------
st.markdown("### 🎯 Detection Results")
image_name = st.text_input("🔍 Enter image name (with extension):")
st.markdown("You can get image name form the table above.")

load_dotenv() # load vars from .env

# Your Azure Data Lake Storage credentials
# Replace with your actual values
account_name = os.getenv("account_name")
account_key = os.getenv("account_key")
connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
file_system_name = os.getenv("file_system_name")

model = YOLO("../models/fine_tunning/runs/main_trainging/yolov8s/weights/best.pt")

if image_name:
    try:
        # Connect to Azure Blob
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=file_system_name, blob=f"raw/{image_name}")

        # Download image
        image_data = blob_client.download_blob().readall()
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)  # BGR format

        # Run YOLO inference (exactly the same weights in backend)
        results = model.predict(source=image, conf=0.25, save=False)

        # Annotate image
        annotated_image = results[0].plot()  # results[0] is the first image in results

        # Convert BGR to RGB for Streamlit
        annotated_image = cv2.cvtColor(annotated_image, cv2.COLOR_BGR2RGB)

        cols = st.columns([1, 2, 1])  # Left, center, right columns
        with cols[1]:  # Put image in the middle column
          st.image(annotated_image, caption=f"YOLO Predictions: {image_name}", width=400)

    except Exception as e:
        st.error(f"Could not load image: {e}")

# ----------------------------------------------------------------------------------
col1, col2 = st.columns([1, 2])

with col1:
  st.markdown("###### Percentage of each crack type")
  data1 = cassandra.exec("SELECT label FROM crack")

  cmap = plt.get_cmap('Dark2')

  # Get a list of 8 colors from the colormap

  fig, ax = plt.subplots(1, 1)

  plot = data1.groupby('label')['label'].count().sort_values()

  colors = cmap(np.linspace(0, 1, len(plot.index)))
  ax.pie(plot, labels=plot.index, autopct='%.2f%%', colors=colors)
  st.pyplot(fig)
# -----------------------------------------------------------------------------------

grouped_df = data2.groupby(["fclass", "label"]).size().reset_index(name='count')

with col2:
  # Title
  st.markdown("###### Crack Type by Road Type")

  # Treemap plot
  fig = px.treemap(
    grouped_df,
    path=["fclass", "label"],
    values="count",
    color="fclass",
    title="Distribution of Crack Types Across Road Types",
    color_discrete_sequence=px.colors.qualitative.Dark24
  )

  st.plotly_chart(fig, use_container_width=True)
# ----------------------------------------------------------------------------------

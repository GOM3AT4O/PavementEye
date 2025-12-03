import streamlit as st
from db import Cassandra
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
from colors import DASHBOARD_PALETTE
import sys

# Add utils to path
sys.path.append('./utils')

from header import simple_header
from filters import FilterManager

# Global styles -------------------------------------------------------------------
st.set_page_config(layout="wide")

# Load the external CSS file
def local_css(file_name):
  with open(file_name) as f:
      st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("./style.css")

cmap = plt.get_cmap('Dark2')
# ---------------------------------------------------------------------------------

# Title with consistent styling
simple_header("Road Characteristics Analysis", "Crack distribution by road speed limits and one-way vs both directions", "🚦")

# Initialize Cassandra connection
cassandra = Cassandra()

# Initialize Filter Manager
filter_manager = FilterManager(cassandra)

# Render filters in sidebar
filter_manager.render_filters_sidebar()

# Get current filters
current_filters = filter_manager.get_current_filters()

# Show filter summary
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
# FIRST SECTION - Maxspeed Analysis (EXACTLY AS BEFORE)
# ==============================================================================

st.markdown("---")
st.markdown("##### 🚦 Comparison between different road speeds")

# Query with current filters
if current_filters['districts'] and current_filters['start_date'] and current_filters['end_date']:
    dists_filter = ", ".join([f"'{d}'" for d in current_filters['districts']])
    start_iso = f"{current_filters['start_date'].isoformat()} 00:00:00"
    end_iso = f"{current_filters['end_date'].isoformat()} 23:59:59"
    
    query = f"""
        SELECT label, road_index 
        FROM crack 
        WHERE dist IN ({dists_filter}) 
        AND confidence >= {current_filters['confidence']}
        AND timestamp >= '{start_iso}' 
        AND timestamp <= '{end_iso}' 
        ALLOW FILTERING
    """
    
    cassandra.exec(query)
    cassandra.join_roads()
    cracks_df = cassandra.data
else:
    # Fallback to original query
    cassandra.exec("SELECT label, road_index FROM crack")
    cassandra.join_roads()
    cracks_df = cassandra.data

# Filter valid speeds - EXACTLY AS BEFORE
cracks_df = cracks_df[cracks_df['maxspeed'] > 0]

# Group by maxspeed and crack type - EXACTLY AS BEFORE
speed_cracks = (
    cracks_df.groupby(["maxspeed", "label"])
    .size()
    .reset_index(name="count")
)

# Pivot to have crack types as columns (actual counts) - EXACTLY AS BEFORE
pivot_speed = speed_cracks.pivot(
    index="maxspeed", columns="label", values="count"
).fillna(0)

# Melt to long-form for Plotly - EXACTLY AS BEFORE
pivot_long = pivot_speed.reset_index().melt(
    id_vars='maxspeed',
    var_name='Crack Type',
    value_name='Count'
)

# Total counts for annotation - EXACTLY AS BEFORE
total_counts = cracks_df.groupby('maxspeed').size().sort_index()

# Map colors to your professional palette - EXACTLY AS BEFORE
color_map = {k: v for k, v in zip(pivot_long['Crack Type'].unique(), DASHBOARD_PALETTE)}

# Plotly stacked horizontal bar chart - EXACTLY AS BEFORE
fig = px.bar(
    pivot_long,
    x='maxspeed',
    y='Count',
    color='Crack Type',
    color_discrete_map=color_map,
    text='Count',
    labels={'maxspeed': 'Maxspeed (KM/H)', 'Count': 'Number of Cracks'},
    title="Number of Crack Types per Maxspeed",
    template='plotly_white'
)

# Make bars stacked - EXACTLY AS BEFORE
fig.update_layout(
    barmode='stack',
    xaxis=dict(type='category', categoryorder='category ascending'),
    bargap=0,  
    width=1200,
    height=600
)

# Add total count annotations above each stack - EXACTLY AS BEFORE
for speed in total_counts.index:
    fig.add_annotation(
        x=speed,
        y=total_counts.loc[speed] + 2,  # slightly above total
        text=f"{total_counts.loc[speed]} cracks",
        showarrow=False,
        font=dict(size=12)
    )

fig.update_layout(width=1200, height=600)

# Display in Streamlit - EXACTLY AS BEFORE
st.plotly_chart(fig, use_container_width=True)
# ------------------------------------------------------------------------------------------


st.markdown("##### 🔄 One way roads vs both")
df = cassandra.data

oneway_B = df[df['oneway'] == 'B'].groupby('label').size()
oneway_F = df[df['oneway'] == 'F'].groupby('label').size()


categories_B = oneway_B.index
categories_F = oneway_F.index

fig = go.Figure()

fig.add_trace(go.Scatterpolar(
    r=oneway_B.values,
    theta=categories_B,
    fill='toself',
    name='Both',
))
fig.add_trace(go.Scatterpolar(
    r=oneway_F.values,
    theta=categories_F,
    fill='toself',
    name='False'
))

fig.update_layout(
    polar=dict(
        radialaxis=dict(
            visible=True,
            range=[0, max(max(oneway_B.values), max(oneway_F.values)) + 1]
        )
    ),
    showlegend=True
)

st.plotly_chart(fig, use_container_width=True)
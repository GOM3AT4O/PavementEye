import streamlit as st
import matplotlib.pyplot as plt
from db import Cassandra
import plotly.express as px
import pandas as pd
import numpy as np
from colors import DASHBOARD_PALETTE, color_scale
import sys

# Add utils to path
sys.path.append('./utils')

from header import simple_header
from filters import FilterManager

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

cmap = plt.get_cmap('Dark2')
# ---------------------------------------------------------------------------------

# Title with consistent styling
simple_header("Road Infrastructure Analysis", "Crack distribution across bridges, tunnels, and normal roads", "🌉")

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

st.markdown("""
<div style="text-align: center; color: #64748b; margin: 1rem 0; font-size: 0.95rem;">
    <i>Normal road means road that is not tunnel or bridge.</i>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# FIRST SECTION - Crack Types by Infrastructure 
# ==============================================================================

# Query with current filters
if current_filters['districts'] and current_filters['start_date'] and current_filters['end_date']:
    dists_filter = ", ".join([f"'{d}'" for d in current_filters['districts']])
    start_iso = f"{current_filters['start_date'].isoformat()} 00:00:00"
    end_iso = f"{current_filters['end_date'].isoformat()} 23:59:59"
    
    # First, let's see what columns we have in the crack table
    cassandra.exec(f"""
        SELECT column_name 
        FROM system_schema.columns 
        WHERE keyspace_name = 'default' AND table_name = 'crack'
    """)
    crack_columns = cassandra.data['column_name'].tolist() if not cassandra.data.empty else []
    
    # Now get the data with all available columns
    query = f"""
        SELECT * 
        FROM crack 
        WHERE dist IN ({dists_filter}) 
        AND confidence >= {current_filters['confidence']}
        AND timestamp >= '{start_iso}' 
        AND timestamp <= '{end_iso}' 
        ALLOW FILTERING
    """
    
    cassandra.exec(query)
    df = cassandra.join_roads()
else:
    # Fallback to original query
    cassandra.exec("SELECT road_index, label FROM crack")
    df = cassandra.join_roads()

# Check if bridge/tunnel columns exist
if 'bridge' not in df.columns or 'tunnel' not in df.columns:
    st.warning("⚠️ 'bridge' or 'tunnel' columns not found in the data. Showing alternative analysis.")
    
    # Show what columns we do have
    st.info(f"Available columns: {', '.join(df.columns)}")
    
    # Try alternative analysis based on what we have
    if 'fclass' in df.columns:
        st.markdown("### Alternative: Crack Types by Road Class")
        
        # Group by road class (fclass) instead
        if not df.empty:
            # Get top road classes
            road_classes = df['fclass'].unique()[:3] if len(df['fclass'].unique()) >= 3 else df['fclass'].unique()
            
            col1, col2, col3 = st.columns(3)
            
            for i, road_class in enumerate(road_classes):
                if i < 3:  # Show up to 3 columns
                    class_data = df[df['fclass'] == road_class].groupby('label').size().rename('count').sort_values(ascending=False)
                    
                    with [col1, col2, col3][i]:
                        if not class_data.empty:
                            df_plot = class_data.reset_index()
                            df_plot.columns = ['Crack Type', 'Count']
                            
                            color_map = {k: v for k, v in zip(df_plot['Crack Type'], DASHBOARD_PALETTE[:len(df_plot)])}
                            
                            fig = px.bar(
                                df_plot,
                                x='Count',
                                y='Crack Type',
                                orientation='h',
                                text='Count',
                                color='Crack Type',
                                color_discrete_map=color_map,
                                labels={'Count': 'Number of Cracks', 'Crack Type': 'Crack Type'},
                                title=f"{road_class} Roads",
                                template='plotly_white',
                                hover_data={'Count': True, 'Crack Type': True}
                            )
                            fig.update_layout(showlegend=False, height=400)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info(f"No data for {road_class} roads")
    else:
        # Just show overall crack distribution
        st.markdown("### Overall Crack Distribution")
        if not df.empty and 'label' in df.columns:
            overall = df.groupby('label').size().rename('count').sort_values(ascending=False)
            
            df_plot = overall.reset_index()
            df_plot.columns = ['Crack Type', 'Count']
            
            color_map = {k: v for k, v in zip(df_plot['Crack Type'], DASHBOARD_PALETTE[:len(df_plot)])}
            
            fig = px.bar(
                df_plot,
                x='Count',
                y='Crack Type',
                orientation='h',
                text='Count',
                color='Crack Type',
                color_discrete_map=color_map,
                labels={'Count': 'Number of Cracks', 'Crack Type': 'Crack Type'},
                title="Overall Crack Distribution",
                template='plotly_white',
                hover_data={'Count': True, 'Crack Type': True}
            )
            fig.update_layout(showlegend=False, height=500)
            st.plotly_chart(fig, use_container_width=True)
else:
    # Original code - bridge/tunnel columns exist
    # Group by label - EXACTLY AS BEFORE
    bridge = df[df['bridge'] == 'T'].groupby('label').size().rename('count').sort_values(ascending=False)
    tunnel = df[df['tunnel'] == 'T'].groupby('label').size().rename('count').sort_values(ascending=False)
    normal = df[(df['bridge'] == 'F') & (df['tunnel'] == 'F')].groupby('label').size().rename('count').sort_values(ascending=False)

    # Helper to create horizontal bar chart - EXACTLY AS BEFORE
    def plot_hbar(series, title):
        df_plot = series.reset_index()          # convert Series to DataFrame
        df_plot.columns = ['Crack Type', 'Count']  # rename columns

        # Map colors using your professional palette
        color_map = {k: v for k, v in zip(df_plot['Crack Type'], DASHBOARD_PALETTE[:len(df_plot)])}

        fig = px.bar(
            df_plot,
            x='Count',
            y='Crack Type',
            orientation='h',
            text='Count',
            color='Crack Type',
            color_discrete_map=color_map,
            labels={'Count': 'Number of Cracks', 'Crack Type': 'Crack Type'},
            title=title,
            template='plotly_white',
            hover_data={'Count': True, 'Crack Type': True}
        )
        fig.update_layout(showlegend=False, height=400)
        return fig

    col1, col2, col3 = st.columns(3)

    # Plot each - EXACTLY AS BEFORE
    with col1:
        st.plotly_chart(plot_hbar(bridge, "Bridge Cracks"), use_container_width=True)

    with col2:
        st.plotly_chart(plot_hbar(tunnel, "Tunnel Cracks"), use_container_width=True)

    with col3:
        st.plotly_chart(plot_hbar(normal, "Normal Roads Cracks"), use_container_width=True)

# ==============================================================================
# SECOND SECTION - Top Damaged Roads (EXACTLY AS BEFORE)
# ==============================================================================

st.markdown("---")

# Query with current filters for PCI data
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
    df = cassandra.data
else:
    # Fallback to original query
    cassandra.exec("SELECT x1,x2,y1,y2, road_index, label, ppm FROM crack")
    cassandra.join_roads()
    cassandra.calc_pci()
    df = cassandra.data

# Check if we have the required columns
if df.empty:
    st.warning("No data available for PCI analysis with current filters.")
else:
    # EXACTLY AS BEFORE
    if 'road_index' in df.columns:
        df['road_index'] = df['road_index'].astype(str)
        df = df[df['road_index'] != '-1']
    
    if 'road_index' in df.columns and 'pci' in df.columns:
        group = df.groupby(['road_index']).agg({
            'name': 'first',
            'pci': 'mean',
            'fclass': 'first'
        }).reset_index()

        if 'name' in group.columns:
            group['name'].fillna(group['road_index'], inplace=True)

        if not group.empty:
            plot = group.sort_values(by='pci', ascending=True).iloc[:10]
            top_10_damaged_roads = plot['road_index'].to_list()[:10]

            col1, col2 = st.columns(2)

            with col1:
                # Horizontal bar chart - EXACTLY AS BEFORE
                fig = px.bar(
                    plot,
                    x='pci',
                    y='road_index',   # as roads name may be repeated
                    orientation='h',
                    title="🚧 Top 10 Damaged Roads by PCI",
                    labels={'pci': 'PCI', 'road_index': 'Road Index'},
                    hover_data={'name': True, 'pci': True, 'fclass': True},
                    template='plotly_white',
                    color_discrete_sequence=['#1E3A8A'] 
                )

                fig.update_yaxes(categoryorder='array', categoryarray=plot['road_index'])
                st.plotly_chart(fig, use_container_width=True)

            # ==============================================================================
            # THIRD SECTION - Crack Types for Top Damaged Roads (EXACTLY AS BEFORE)
            # ==============================================================================

            with col2:
                # Filter top 10 damaged roads - EXACTLY AS BEFORE
                top_damaged_df = df[df['road_index'].isin(top_10_damaged_roads)]

                if not top_damaged_df.empty:
                    # Replace missing names with road_index
                    if 'name' in top_damaged_df.columns:
                        top_damaged_df['name'] = top_damaged_df['name'].fillna(top_damaged_df['road_index'])

                    if 'label' in top_damaged_df.columns:
                        # Pivot table: counts of cracks per road and crack type
                        pv = pd.pivot_table(
                            top_damaged_df,
                            index=['road_index', 'name'],   # include name in index
                            columns='label',
                            values='geometry',
                            aggfunc='count'
                        ).fillna(0).astype(int)

                        # Flatten pivot table
                        pv_reset = pv.reset_index()  # now road_index and name are columns

                        # Melt to long-form for Plotly
                        pv_long = pv_reset.melt(
                            id_vars=['road_index', 'name'],
                            var_name='Crack Type',
                            value_name='Count'
                        )

                        # Create stacked horizontal bar chart - EXACTLY AS BEFORE
                        fig = px.bar(
                            pv_long,
                            y='road_index',                # unique identifier
                            x='Count',
                            color='Crack Type',
                            color_discrete_sequence=DASHBOARD_PALETTE,
                            hover_data={'name': True, 'road_index': True, 'Count': True},
                            title='🛠️ Crack Types for the Top 10 Damaged Roads',
                            labels={'road_index': 'Road (ID)', 'Count': 'Number of Cracks'}
                        )

                        fig.update_layout(
                            barmode='stack',
                            yaxis={'categoryorder': 'array', 'categoryarray': top_10_damaged_roads},  # maintain order
                            template='plotly_white',
                        )

                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No label column available for crack type analysis.")
                else:
                    st.info("No data for top damaged roads analysis.")
        else:
            st.info("No road data available for PCI ranking.")
    else:
        st.info("Required columns (road_index or pci) not available for analysis.")

# ==============================================================================
# FOOTER
# ==============================================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #64748b; font-size: 0.9rem; margin-top: 2rem;">
    <i>Analysis updates based on selected filters. Use the sidebar to adjust criteria.</i>
</div>
""", unsafe_allow_html=True)
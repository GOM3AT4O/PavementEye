import streamlit as st
from db import Cassandra
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy.interpolate import make_interp_spline
import numpy as np
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
# ---------------------------------------------------------------------------------

# Title with consistent styling
simple_header("Historical PCI Analysis", "Pavement Condition Index trends over time", "📈")

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

# ==============================================================================
# HISTORICAL PCI ANALYSIS
# ==============================================================================

# Query with current filters
if current_filters['districts'] and current_filters['start_date'] and current_filters['end_date']:
    dists_filter = ", ".join([f"'{d}'" for d in current_filters['districts']])
    start_iso = f"{current_filters['start_date'].isoformat()} 00:00:00"
    end_iso = f"{current_filters['end_date'].isoformat()} 23:59:59"
    
    query = f"""
        SELECT x1,x2,y1,y2, road_index, label, ppm, timestamp 
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
    cassandra.exec("SELECT x1,x2,y1,y2, road_index, label, ppm, timestamp FROM crack")
    cassandra.join_roads()
    cassandra.calc_pci()
    data = cassandra.data.copy()

# Check if we have data
if data.empty:
    st.warning("No data available for PCI analysis with current filters.")
    st.info("Please adjust your filters or try different criteria.")
else:
    # Convert to Web Mercator if geometry exists
    if 'geometry' in data.columns:
        try:
            data = data.to_crs(epsg=3857)
        except:
            st.info("Could not convert coordinate system, but continuing with analysis...")
    
    # Sort by timestamp and set as index - EXACTLY AS BEFORE
    if 'timestamp' in data.columns:
        data = data.sort_values("timestamp")
        data = data.set_index("timestamp")
    
    # Check if we have pci column
    if 'pci' in data.columns:
        # Resample monthly - EXACTLY AS BEFORE
        monthly_pci = data["pci"].resample("ME").mean().fillna(method='ffill')
        
        if not monthly_pci.empty:
            # Prepare data for spline interpolation - EXACTLY AS BEFORE
            x = monthly_pci.index.astype(np.int64) // 10**9  # Convert to Unix timestamp in seconds
            y = monthly_pci.values
            
            # Create spline interpolation - EXACTLY AS BEFORE
            if len(x) > 3:  # Need at least 4 points for cubic spline
                X_Y_Spline1 = make_interp_spline(x, y, k=min(3, len(x) - 1))
                X_1 = np.linspace(x.min(), x.max(), 500)
                Y_1 = X_Y_Spline1(X_1)
                
                # Convert spline X back to datetime
                spline_dates = pd.to_datetime(X_1 * 10**9, unit='s')
                
                # Create Plotly figure
                fig = go.Figure()
                
                # Add original monthly data points
                fig.add_trace(go.Scatter(
                    x=monthly_pci.index,
                    y=monthly_pci.values,
                    mode='markers',
                    name='Monthly Average',
                    marker=dict(
                        color='#1E3A8A',
                        size=8,
                        line=dict(width=1, color='white')
                    ),
                    hovertemplate='<b>Date:</b> %{x|%Y-%m}<br><b>PCI:</b> %{y:.2f}<extra></extra>'
                ))
                
                # Add spline line
                fig.add_trace(go.Scatter(
                    x=spline_dates,
                    y=Y_1,
                    mode='lines',
                    name='Trend Line',
                    line=dict(
                        color='#EF4444',
                        width=3,
                        shape='spline'
                    ),
                    hovertemplate='<b>Date:</b> %{x|%Y-%m}<br><b>PCI:</b> %{y:.2f}<extra></extra>'
                ))
                
                # Update layout
                fig.update_layout(
                    title=dict(
                        text="Monthly PCI Trend",
                        font=dict(size=20, color='#1E293B'),
                        x=0.5,
                        xanchor='center'
                    ),
                    xaxis=dict(
                        title="Month",
                        tickformat="%Y-%m",
                        gridcolor='rgba(128, 128, 128, 0.2)',
                        showgrid=True
                    ),
                    yaxis=dict(
                        title="PCI",
                        gridcolor='rgba(128, 128, 128, 0.2)',
                        showgrid=True
                    ),
                    hovermode='x unified',
                    template='plotly_white',
                    height=500,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    ),
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                
                # Add range slider
                fig.update_xaxes(
                    rangeslider_visible=True,
                    rangeselector=dict(
                        buttons=list([
                            dict(count=1, label="1m", step="month", stepmode="backward"),
                            dict(count=6, label="6m", step="month", stepmode="backward"),
                            dict(count=1, label="YTD", step="year", stepmode="todate"),
                            dict(count=1, label="1y", step="year", stepmode="backward"),
                            dict(step="all")
                        ])
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Display stats
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Current PCI", f"{monthly_pci.iloc[-1]:.2f}" if len(monthly_pci) > 0 else "N/A")
                with col2:
                    change = ((monthly_pci.iloc[-1] - monthly_pci.iloc[0]) / monthly_pci.iloc[0] * 100) if len(monthly_pci) > 1 and monthly_pci.iloc[0] != 0 else 0
                    st.metric("Total Change", f"{change:+.1f}%")
                with col3:
                    st.metric("Best PCI", f"{monthly_pci.max():.2f}")
                with col4:
                    st.metric("Worst PCI", f"{monthly_pci.min():.2f}")
                
                # Additional analysis section
                st.markdown("---")
                st.markdown("### 📊 Additional Analysis")
                
                # Option 1: Bar chart showing monthly PCI
                fig_bar = px.bar(
                    x=monthly_pci.index.strftime('%Y-%m'),
                    y=monthly_pci.values,
                    labels={'x': 'Month', 'y': 'PCI'},
                    title="Monthly PCI Values",
                    color=monthly_pci.values,
                    color_continuous_scale='RdYlGn_r',  # Red-Yellow-Green reversed (green=good)
                )
                
                fig_bar.update_layout(
                    xaxis_tickangle=-45,
                    height=400,
                    coloraxis_colorbar=dict(title="PCI Value")
                )
                
                st.plotly_chart(fig_bar, use_container_width=True)
                
                # Option 2: Display monthly data in a table
                with st.expander("📋 View Monthly PCI Data", expanded=False):
                    monthly_df = pd.DataFrame({
                        'Month': monthly_pci.index.strftime('%Y-%m'),
                        'Average PCI': monthly_pci.values.round(2),
                        'Change (%)': monthly_pci.pct_change().mul(100).round(2)
                    })
                    st.dataframe(monthly_df, use_container_width=True, hide_index=True)
            else:
                st.info("Not enough data points for spline interpolation. Showing basic trend...")
                
                # Create simple line chart for small datasets
                fig = px.line(
                    x=monthly_pci.index,
                    y=monthly_pci.values,
                    title="Monthly PCI Trend",
                    labels={'x': 'Month', 'y': 'PCI'}
                )
                
                fig.update_traces(
                    mode='lines+markers',
                    line=dict(color='#1E3A8A', width=3),
                    marker=dict(color='#EF4444', size=8)
                )
                
                fig.update_layout(
                    height=500,
                    xaxis_tickformat="%Y-%m",
                    template='plotly_white'
                )
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No monthly PCI data available after resampling.")
    else:
        st.warning("PCI column not found in the data.")

# ==============================================================================
# FOOTER
# ==============================================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #64748b; font-size: 0.9rem; margin-top: 2rem;">
    <i>PCI analysis updates based on selected filters. Higher PCI values indicate better road conditions.</i>
</div>
""", unsafe_allow_html=True)
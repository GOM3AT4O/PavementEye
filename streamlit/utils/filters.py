# utils/filters.py
import streamlit as st
import pandas as pd
from datetime import datetime

class FilterManager:
    def __init__(self, cassandra):
        self.cassandra = cassandra
        self.initialize_session_state()
    
    def initialize_session_state(self):
      """Initialize filter state in session"""
      if 'filters' not in st.session_state:
          # Load options first to check for Muntazah
          options = self.load_filter_options()
          
          if 'Muntazah' in options['districts']:
              default_district = ['Muntazah']
          elif options['districts']:
              default_district = [options['districts'][0]]
          else:
              default_district = []
          
          st.session_state.filters = {
              'districts': default_district,
              'confidence': 0.5,
              'start_date': options['min_date'],
              'end_date': options['max_date'],
              'last_update': datetime.now()
          }
      
      if 'filter_options' not in st.session_state:
          options = self.load_filter_options()
          st.session_state.filter_options = options
    
    @st.cache_data(ttl=300)
    def load_filter_options(_self):
        """Load available filter options from database"""
        try:
            # Get distinct districts
            dists = _self.cassandra.exec("SELECT DISTINCT dist FROM crack")
            dists_list = dists.iloc[:, 0].unique().tolist() if not dists.empty else []
            
            # Get confidence range
            conf_result = _self.cassandra.exec("SELECT max(confidence) as max_conf, min(confidence) as min_conf FROM crack")
            min_conf = float(conf_result.iloc[0, 1])
            max_conf = float(conf_result.iloc[0, 0])
            
            # Get date range
            date_result = _self.cassandra.exec("SELECT max(timestamp) as max_ts, min(timestamp) as min_ts FROM crack")
            max_date = pd.to_datetime(date_result.iloc[0, 0]).date()
            min_date = pd.to_datetime(date_result.iloc[0, 1]).date()
            
            return {
                'districts': dists_list,
                'min_confidence': min_conf,
                'max_confidence': max_conf,
                'min_date': min_date,
                'max_date': max_date
            }
        except Exception as e:
            st.error(f"Error loading filter options: {e}")
            return {
                'districts': [],
                'min_confidence': 0.0,
                'max_confidence': 1.0,
                'min_date': None,
                'max_date': None
            }
    
    def render_filters_sidebar(self):
        """Render filters in sidebar"""
        with st.sidebar:
            st.markdown("### 📊 Filters")
            
            # Load filter options
            options = self.load_filter_options()
            st.session_state.filter_options = options
            
            # District filter
            default_district = ['Muntazah'] if 'Muntazah' in options['districts'] else (
                [options['districts'][0]] if options['districts'] else []
            )
            
            current_districts = st.session_state.filters.get('districts', default_district)
            countries = st.multiselect(
                "Select districts",
                options=options['districts'],
                default=current_districts,
                key="sidebar_districts"
            )
            
            # Confidence filter
            current_confidence = st.session_state.filters.get('confidence', 0.5)
            confidence_value = st.slider(
                "Confidence threshold",
                min_value=options['min_confidence'],
                max_value=options['max_confidence'],
                value=current_confidence,
                step=0.05,
                key="sidebar_confidence"
            )
            
            # Date range filter
            current_start = st.session_state.filters.get('start_date', options['min_date'])
            current_end = st.session_state.filters.get('end_date', options['max_date'])
            
            if current_start and current_end:
                default_date_range = (current_start, current_end)
            else:
                default_date_range = (options['min_date'], options['max_date'])
            
            date_range = st.date_input(
                "Select date range",
                value=default_date_range,
                min_value=options['min_date'],
                max_value=options['max_date'],
                key="sidebar_date_range"
            )
            
            # Apply filters button
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Apply", type="primary", use_container_width=True):
                    self.update_filters(
                        districts=countries,
                        confidence=confidence_value,
                        start_date=date_range[0] if len(date_range) == 2 else None,
                        end_date=date_range[1] if len(date_range) == 2 else None
                    )
                    st.rerun()
            
            with col2:
                if st.button("Reset", use_container_width=True):
                    self.reset_filters()
                    st.rerun()
            
            # Show current filters
            with st.expander("Current Filters"):
                filters = self.get_current_filters()
                if filters['districts']:
                    st.write(f"**Districts:** {', '.join(filters['districts'])}")
                st.write(f"**Confidence:** ≥ {filters['confidence']:.2f}")
                if filters['start_date']:
                    st.write(f"**Start Date:** {filters['start_date']}")
                if filters['end_date']:
                    st.write(f"**End Date:** {filters['end_date']}")
    
    def update_filters(self, districts=None, confidence=None, start_date=None, end_date=None):
        """Update filters in session state"""
        updates = {}
        if districts is not None:
            updates['districts'] = districts
        if confidence is not None:
            updates['confidence'] = confidence
        if start_date is not None:
            updates['start_date'] = start_date
        if end_date is not None:
            updates['end_date'] = end_date
        
        if updates:
            st.session_state.filters.update(updates)
            st.session_state.filters['last_update'] = datetime.now()
    
    def reset_filters(self):
      """Reset filters to defaults"""
      options = st.session_state.filter_options
      
      # Check if "Muntazah" is available, otherwise use first district
      if 'Muntazah' in options['districts']:
          default_district = ['Muntazah']
      elif options['districts']:
          default_district = [options['districts'][0]]
      else:
          default_district = []
      
      st.session_state.filters = {
          'districts': default_district,
          'confidence': 0.5,
          'start_date': options['min_date'],
          'end_date': options['max_date'],
          'last_update': datetime.now()
      }
    
    def get_current_filters(self):
        """Get current filter values"""
        return st.session_state.filters.copy()
    
    def get_filter_options(self):
        """Get available filter options"""
        return st.session_state.filter_options.copy()
    
    def get_filtered_data(self):
        """Get data filtered by current filters"""
        filters = self.get_current_filters()
        
        if not filters['districts']:
            st.warning("Please select at least one district")
            return None
        
        if not filters['start_date'] or not filters['end_date']:
            st.warning("Please select both start and end dates")
            return None
        
        # Build query
        dists_filter = ", ".join([f"'{d}'" for d in filters['districts']])
        start_iso = f"{filters['start_date'].isoformat()} 00:00:00"
        end_iso = f"{filters['end_date'].isoformat()} 23:59:59"
        
        query = f"""
            SELECT * FROM crack 
            WHERE dist IN ({dists_filter}) 
            AND confidence >= {filters['confidence']}
            AND timestamp >= '{start_iso}' 
            AND timestamp <= '{end_iso}' 
            ALLOW FILTERING
        """
        
        self.cassandra.exec(query)
        data = self.cassandra.join_roads()
        
        # Drop unnecessary columns if they exist
        columns_to_drop = ['geometry', 'index', 'road_index', 'id']
        columns_to_drop = [col for col in columns_to_drop if col in data.columns]
        return data.drop(columns=columns_to_drop, errors='ignore')
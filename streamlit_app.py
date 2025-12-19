import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from datetime import datetime, timedelta
import random
import requests
import json

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="NIE Powercheck Dashboard",
    page_icon="⚡",
    layout="wide"
)

# --- LIVE DATA SCRAPER ---
@st.cache_data(ttl=300)  # Cache data for 5 minutes
def fetch_nienetworks_data():
    """
    Fetches live fault data directly from the NIE Powercheck JSON endpoint.
    This provides precise lat/long coordinates, avoiding the need for geocoding.
    """
    # The JSON endpoint used by the live map
    url = "https://powercheck.nienetworks.co.uk/data/incidents.json"
    
    # Headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://powercheck.nienetworks.co.uk/',
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse JSON
        try:
            data = response.json()
        except json.JSONDecodeError:
            # Fallback for some servers serving JSON with BOM or weird encoding
            data = json.loads(response.content.decode('utf-8-sig'))
            
        if not data:
            return pd.DataFrame()
        
        # The JSON usually comes as a list of objects or a dictionary with a key like 'incidents'
        # We handle both cases
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            # Look for common keys if it's wrapped
            for key in ['incidents', 'faults', 'outages', 'markers']:
                if key in data:
                    items = data[key]
                    break
            # If still empty, maybe the dict values are the items
            if not items:
                items = list(data.values())

        if not items:
            return pd.DataFrame()

        df = pd.DataFrame(items)
        
        # --- NORMALISE COLUMNS ---
        # Map JSON keys to our Dashboard schema
        # Common keys in these datasets: 'id', 'lat', 'lng', 'type', 'cluster', 'message'
        
        # Create standard columns if they don't exist
        column_mapping = {
            'id': 'Incident ID',
            'eventId': 'Incident ID',
            'lat': 'lat',
            'latitude': 'lat',
            'lng': 'lng',
            'long': 'lng',
            'longitude': 'lng',
            'type': 'Type',
            'faultType': 'Type',
            'desc': 'Message',
            'description': 'Message',
            'cluster': 'Postcode', # Sometimes just an area name
            'title': 'Location',
            'restoreTime': 'Est. Restoration',
            'startDate': 'Reported'
        }
        
        # Rename columns that match
        df = df.rename(columns=column_mapping)
        
        # Ensure we have essential columns
        if 'lat' not in df.columns or 'lng' not in df.columns:
            # If coordinates are missing, we can't map it. 
            # (Note: Some APIs put lat/lng in a 'geometry' object, simplistic flat check here)
            return pd.DataFrame()

        # Clean Data
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lng'] = pd.to_numeric(df['lng'], errors='coerce')
        df = df.dropna(subset=['lat', 'lng'])

        # Fill missing text fields
        if 'Type' not in df.columns:
            df['Type'] = 'Unplanned Outage' # Default
        if 'Postcode' not in df.columns:
            df['Postcode'] = 'NI Area'
        if 'Location' not in df.columns:
            df['Location'] = 'Unknown Location'
        if 'Reported' not in df.columns:
            df['Reported'] = 'Unknown'
        if 'Est. Restoration' not in df.columns:
            df['Est. Restoration'] = 'Pending Update'

        # Add Status
        df['Status'] = 'Active' 
        
        # --- COLOUR CODING ---
        def get_color(type_str):
            t = str(type_str).lower()
            if 'unplanned' in t or 'fault' in t or 'hv' in t: # High Voltage / Unplanned
                return [239, 68, 68, 200]  # Red
            return [245, 158, 11, 200]     # Amber (Planned/Low Voltage)
            
        df['color'] = df['Type'].apply(get_color)

        return df

    except Exception as e:
        # If live JSON fails, we return empty so the UI shows the warning rather than crashing
        # st.error(f"Debug: {e}") # Uncomment for debugging
        return pd.DataFrame()

# --- APP LAYOUT ---

# Header
col_logo, col_title = st.columns([1, 20])
with col_logo:
    st.markdown("## ⚡")
with col_title:
    st.title("NIE Powercheck Dashboard")
    st.caption("Live Data from powercheck.nienetworks.co.uk (JSON Feed)")

# Initialize Session State
if 'data' not in st.session_state:
    with st.spinner('Connecting to NIE Networks Live Feed...'):
        st.session_state.data = fetch_nienetworks_data()
    st.session_state.last_updated = datetime.now()

# Refresh Button
if st.button("Refresh Live Data 🔄"):
    st.cache_data.clear()
    with st.spinner('Fetching latest updates...'):
        st.session_state.data = fetch_nienetworks_data()
    st.session_state.last_updated = datetime.now()
    st.rerun()

df = st.session_state.data

if df.empty:
    st.warning("⚠️ Unable to load live data. The NIE Powercheck service may be restricting access or there are zero active faults.")
    st.info("Tip: This dashboard relies on the public `incidents.json` feed. If NIE changes their API security, this may require a proxy server.")
else:
    # Top Stats
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Incidents", len(df))
    
    # Safely count unplanned faults
    if 'Type' in df.columns:
        unplanned_count = df[df['Type'].str.contains('Unplanned|Fault', case=False, na=False)].shape[0]
    else:
        unplanned_count = 0
        
    m2.metric("Unplanned Faults", unplanned_count)
    m3.metric("Last Check", st.session_state.last_updated.strftime("%H:%M"))
    st.markdown("---")

    # Main Content Grid
    row1_col1, row1_col2 = st.columns([2, 1])

    with row1_col1:
        st.subheader("Network Map")
        
        # PyDeck Map
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position='[lng, lat]',
            get_color='color',
            get_radius=2000,
            pickable=True,
            opacity=0.8,
            stroked=True,
            filled=True,
            line_width_min_pixels=1,
            line_color=[255, 255, 255]
        )

        # Auto-center map based on data
        mid_lat = df['lat'].mean() if not df.empty else 54.65
        mid_lng = df['lng'].mean() if not df.empty else -6.5

        view_state = pdk.ViewState(
            latitude=mid_lat,
            longitude=mid_lng,
            zoom=8,
            pitch=0,
        )

        tooltip = {
            "html": "<b>Location:</b> {Location}<br/>"
                    "<b>Type:</b> {Type}<br/>"
                    "<b>Status:</b> {Status}<br/>"
                    "<b>Restoration:</b> {Est. Restoration}",
            "style": {
                "backgroundColor": "white",
                "color": "black",
                "fontSize": "12px",
                "padding": "10px",
                "borderRadius": "5px",
                "zIndex": "9999",
                "boxShadow": "0 2px 4px rgba(0,0,0,0.2)"
            }
        }

        r = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style=pdk.map_styles.ROAD,
            tooltip=tooltip,
        )

        st.pydeck_chart(r)

    with row1_col2:
        st.subheader("Live Incident List")
        
        # Display list
        # Sort by Unplanned first
        df_sorted = df.sort_values(by='Type', ascending=False)
        
        for index, row in df_sorted.iterrows():
            loc_label = row.get('Location', 'Unknown')
            # If location is empty or generic, try using Postcode
            if not loc_label or loc_label == 'Unknown Location':
                loc_label = row.get('Postcode', 'Fault')
                
            with st.expander(f"{loc_label} ({row.get('Type', 'N/A')})"):
                st.markdown(f"**ID:** {row.get('Incident ID', 'N/A')}")
                st.markdown(f"**Restoration:** {row.get('Est. Restoration', 'Pending')}")
                st.markdown(f"**Info:** {row.get('Message', 'No details available.')}")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; font-size: 0.8rem;'>
        <a href='https://nithroughalens.com' target='_blank' style='text-decoration: none; color: #555;'>
            Northern Ireland Through A Lens | 2025
        </a>
    </div>
    """,
    unsafe_allow_html=True
)

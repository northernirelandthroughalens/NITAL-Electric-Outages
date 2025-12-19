import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from datetime import datetime, timedelta
import random
import requests
from bs4 import BeautifulSoup
import re

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="NIE Powercheck Dashboard",
    page_icon="⚡",
    layout="wide"
)

# --- LIVE DATA SCRAPER ---
@st.cache_data(ttl=300)  # Cache data for 5 minutes to prevent spamming the NIE server
def fetch_nienetworks_data():
    """
    Fetches live fault data from the NIE Powercheck 'TabularFaults' page 
    and geocodes the postcodes using postcodes.io.
    """
    url = "https://powercheck.nienetworks.co.uk/TabularFaults.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Use pandas to parse the HTML table easily
        dfs = pd.read_html(response.text)
        
        if not dfs:
            return pd.DataFrame()
        
        df = dfs[0]
        
        # Clean up column names (Standardise)
        # Expected columns usually: Reference, Type, Postcodes, Off Date, Est Restoration, etc.
        # We rename them to match our dashboard schema
        df.columns = [c.strip() for c in df.columns]
        
        # Map NIE columns to our dashboard columns
        # Note: Actual column names from NIE might vary slightly, so we map loosely
        column_mapping = {
            'Event / Plan Number': 'Incident ID',
            'Outage Type': 'Type', 
            'Postcodes Affected': 'Postcode Raw',
            'Start Time': 'Reported',
            'Estimated Restoration Time': 'Est. Restoration',
            'Cluster': 'Location', # Sometimes Cluster is the best proxy for "Location"
            'Town': 'Town' # Sometimes they have a Town column
        }
        
        df = df.rename(columns=column_mapping)
        
        # Basic cleaning
        if 'Location' not in df.columns:
            df['Location'] = "Unknown Location"
        
        # Geocoding Logic
        # We need to extract a valid Outcode (e.g., BT12) from "BT12 3; BT12 4"
        def get_coordinates(postcode_raw):
            if pd.isna(postcode_raw):
                return None, None
            
            # Extract the first valid looking postcode part (e.g., BT1, BT23)
            # Regex to find the first 'BT' followed by numbers
            match = re.search(r'(BT\d+)', str(postcode_raw).upper())
            if not match:
                return None, None
                
            outcode = match.group(1)
            
            # Fetch lat/long from postcodes.io (Free UK API)
            try:
                # Use a specific user agent for the API
                api_url = f"https://api.postcodes.io/outcodes/{outcode}"
                geo_resp = requests.get(api_url, timeout=2)
                if geo_resp.status_code == 200:
                    data = geo_resp.json()
                    if 'result' in data and data['result']:
                        return data['result']['latitude'], data['result']['longitude']
            except Exception:
                pass
            
            return None, None

        # Apply geocoding (Note: In a high volume app, we would use bulk endpoints)
        coords = df['Postcode Raw'].apply(lambda x: get_coordinates(x))
        df['lat'] = [c[0] for c in coords]
        df['lng'] = [c[1] for c in coords]
        
        # Filter out rows where we couldn't find coordinates
        df = df.dropna(subset=['lat', 'lng'])

        # Add Status (Derived) and Formatting
        df['Status'] = 'Active' # Default status
        df['Customers Affected'] = 'N/A' # Tabular view doesn't always show customer counts
        
        # Assign Colours based on Type
        def get_color(type_str):
            t = str(type_str).lower()
            if 'unplanned' in t or 'fault' in t:
                return [239, 68, 68, 200]  # Red
            return [245, 158, 11, 200]     # Amber
            
        df['color'] = df['Type'].apply(get_color)
        df['Postcode'] = df['Postcode Raw'] # Display version

        return df

    except Exception as e:
        st.error(f"Could not fetch live data from NIE: {e}")
        # Return empty DF on failure so app doesn't crash
        return pd.DataFrame()

# --- APP LAYOUT ---

# Header
col_logo, col_title = st.columns([1, 20])
with col_logo:
    st.markdown("## ⚡")
with col_title:
    st.title("NIE Powercheck Dashboard")
    st.caption("Live Data from powercheck.nienetworks.co.uk")

# Initialize Session State
if 'data' not in st.session_state:
    with st.spinner('Connecting to NIE Networks...'):
        st.session_state.data = fetch_nienetworks_data()
    st.session_state.last_updated = datetime.now()

# Refresh Button
if st.button("Refresh Live Data 🔄"):
    st.cache_data.clear() # Clear cache to force new fetch
    with st.spinner('Fetching latest updates...'):
        st.session_state.data = fetch_nienetworks_data()
    st.session_state.last_updated = datetime.now()
    st.rerun()

df = st.session_state.data

if df.empty:
    st.warning("No active power cuts found on the NIE network at this moment, or the service is temporarily unavailable.")
else:
    # Top Stats
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Incidents", len(df))
    # Count unplanned vs planned
    unplanned_count = df[df['Type'].str.contains('Unplanned', case=False, na=False)].shape[0]
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
            get_radius=4000,  # Radius in meters
            pickable=True,
            opacity=0.8,
            stroked=True,
            filled=True,
            line_width_min_pixels=1,
            line_color=[255, 255, 255]
        )

        # Set view to Northern Ireland
        view_state = pdk.ViewState(
            latitude=54.65,
            longitude=-6.5,
            zoom=8,
            pitch=0,
        )

        tooltip = {
            "html": "<b>Location:</b> {Postcode Raw}<br/>"
                    "<b>Type:</b> {Type}<br/>"
                    "<b>Start:</b> {Reported}<br/>"
                    "<b>Est. Restoration:</b> {Est. Restoration}",
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
        
        # Display list of incidents
        for index, row in df.iterrows():
            with st.expander(f"{row['Postcode']} ({row['Type']})"):
                st.markdown(f"**Incident ID:** {row['Incident ID']}")
                st.markdown(f"**Reported:** {row['Reported']}")
                st.markdown(f"**Restoration:** {row['Est. Restoration']}")
                # If 'Message' or other columns exist, we could add them here

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

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from datetime import datetime, timedelta
import random

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="NIE Powercheck Dashboard",
    page_icon="⚡",
    layout="wide"
)

# --- MOCK DATA GENERATOR (PYTHON VERSION) ---
def generate_mock_faults():
    """Generates realistic fault data for Northern Ireland."""
    incident_types = ['Unplanned Outage', 'Planned Work', 'Equipment Fault', 'Storm Damage']
    
    # Locations including Millisle context
    locations = [
        {'town': 'Belfast (South)', 'postcode': 'BT9', 'lat': 54.57, 'lng': -5.96},
        {'town': 'Bangor', 'postcode': 'BT19', 'lat': 54.66, 'lng': -5.67},
        {'town': 'Derry/Londonderry', 'postcode': 'BT48', 'lat': 55.00, 'lng': -7.34},
        {'town': 'Omagh', 'postcode': 'BT78', 'lat': 54.60, 'lng': -7.30},
        {'town': 'Newry', 'postcode': 'BT34', 'lat': 54.17, 'lng': -6.34},
        {'town': 'Lisburn', 'postcode': 'BT27', 'lat': 54.51, 'lng': -6.04},
        {'town': 'Ballymena', 'postcode': 'BT42', 'lat': 54.86, 'lng': -6.28},
        {'town': 'Enniskillen', 'postcode': 'BT74', 'lat': 54.34, 'lng': -7.64},
        {'town': 'Coleraine', 'postcode': 'BT51', 'lat': 55.13, 'lng': -6.66},
        {'town': 'Dungannon', 'postcode': 'BT70', 'lat': 54.50, 'lng': -6.77},
        {'town': 'Millisle', 'postcode': 'BT22', 'lat': 54.61, 'lng': -5.53},
        {'town': 'Antrim', 'postcode': 'BT41', 'lat': 54.71, 'lng': -6.22},
        {'town': 'Portadown', 'postcode': 'BT62', 'lat': 54.42, 'lng': -6.44}
    ]

    statuses = ['Investigating', 'Engineer Assigned', 'Engineer On Site', 'Work in Progress']
    
    faults = []
    # Generate 5-12 random faults
    count = random.randint(5, 12)
    now = datetime.now()

    for i in range(count):
        loc = random.choice(locations)
        type_ = random.choice(incident_types)
        
        # Colour coding for map [R, G, B, A]
        # Red for Unplanned, Amber for others
        if type_ == 'Unplanned Outage':
            color = [239, 68, 68, 200]  # Red
        else:
            color = [245, 158, 11, 200] # Amber

        faults.append({
            'Incident ID': f"INC-{10000+i}",
            'Type': type_,
            'Location': loc['town'],
            'Postcode': loc['postcode'],
            'lat': loc['lat'],
            'lng': loc['lng'],
            'Status': random.choice(statuses),
            'Customers Affected': random.randint(10, 200),
            'Reported': (now - timedelta(hours=random.randint(0, 2))).strftime("%H:%M"),
            'Est. Restoration': (now + timedelta(hours=random.randint(2, 5))).strftime("%H:%M"),
            'color': color
        })
    
    return pd.DataFrame(faults)

# --- APP LAYOUT ---

# Header
col_logo, col_title = st.columns([1, 20])
with col_logo:
    st.markdown("## ⚡")
with col_title:
    st.title("NIE Powercheck Dashboard")
    st.caption("Live Outage Information (Demo Mode)")

# Initialize Session State for persistence across interactions
if 'data' not in st.session_state:
    st.session_state.data = generate_mock_faults()
    st.session_state.last_updated = datetime.now()

# Refresh Button
if st.button("Refresh Data 🔄"):
    st.session_state.data = generate_mock_faults()
    st.session_state.last_updated = datetime.now()
    st.rerun()

df = st.session_state.data

# Top Stats
st.markdown("---")
m1, m2, m3 = st.columns(3)
m1.metric("Active Faults", len(df))
m2.metric("Customers Affected", df['Customers Affected'].sum())
m3.metric("Restorations Today", 42) # Static demo number
st.markdown("---")

# Main Content Grid
row1_col1, row1_col2 = st.columns([2, 1])

with row1_col1:
    st.subheader("Network Map")
    
    # PyDeck Map (OpenStreetMap style via 'road')
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position='[lng, lat]',
        get_color='color',
        get_radius=3000,  # Radius in meters
        pickable=True,
        opacity=0.8,
        stroked=True,
        filled=True,
        line_width_min_pixels=1,
    )

    # Set view to Northern Ireland
    view_state = pdk.ViewState(
        latitude=54.65,
        longitude=-6.5,
        zoom=7.5,
        pitch=0,
    )

    tooltip = {
        "html": "<b>{Location}</b> ({Postcode})<br/>"
                "<b>Type:</b> {Type}<br/>"
                "<b>Status:</b> {Status}<br/>"
                "<b>Restoration:</b> {Est. Restoration}",
        "style": {
            "backgroundColor": "white",
            "color": "black",
            "fontSize": "12px",
            "padding": "10px",
            "borderRadius": "5px",
            "zIndex": "9999"
        }
    }

    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_style=pdk.map_styles.ROAD,
        tooltip=tooltip,
    )

    st.pydeck_chart(r)
    st.caption(f"Last Updated: {st.session_state.last_updated.strftime('%H:%M:%S')}")

with row1_col2:
    st.subheader("Current Incidents")
    
    # Display list of incidents
    for index, row in df.iterrows():
        with st.expander(f"{row['Location']} ({row['Type']})"):
            st.markdown(f"**Status:** {row['Status']}")
            st.markdown(f"**Est. Restoration:** {row['Est. Restoration']}")
            st.markdown(f"**Customers:** {row['Customers Affected']}")
            st.markdown(f"**Postcode:** {row['Postcode']}")

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

"""Data Sources, Asset Geographic Map, and Model Assumptions.

Provides complete transparency into Deccan Renewables' portfolio topology,
market contracts, and physical assumptions.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.shared import (
    AGENT_CFG,
    ASSETS_CFG,
    MARKET_CFG,
    init_session_state,
    load_yaml,
)

st.set_page_config(page_title="Data & Assumptions — GridMind", page_icon="🗺️", layout="wide")
init_session_state()

assets_data = load_yaml(ASSETS_CFG)
market_data = load_yaml(MARKET_CFG)
agent_data = load_yaml(AGENT_CFG)

st.title("🗺️ Portfolio Asset Map & Operating Assumptions")
st.markdown("Deccan Renewables Pvt. Ltd. portfolio topology across Karnataka, India, with market tariffs and physical specifications.")

# 1. Karnataka Asset Map
st.subheader("1. Renewable Energy Assets Geographic Map")

map_records = []
for s in assets_data.get("solar_farms", []):
    map_records.append({
        "Asset": s["name"],
        "ID": s["id"],
        "Type": "Solar Farm",
        "Capacity (MW)": s["capacity_mw"],
        "Latitude": s["lat"],
        "Longitude": s["lon"],
    })

for w in assets_data.get("wind_farms", []):
    map_records.append({
        "Asset": w["name"],
        "ID": w["id"],
        "Type": "Wind Farm",
        "Capacity (MW)": w["capacity_mw"],
        "Latitude": w["lat"],
        "Longitude": w["lon"],
    })

# Add BESS approximate locations (Pavagada & Tumakuru substations)
map_records.append({
    "Asset": "B1 Pavagada Storage",
    "ID": "B1",
    "Type": "BESS Storage",
    "Capacity (MW)": 60,
    "Latitude": 14.12,
    "Longitude": 77.26,
})
map_records.append({
    "Asset": "B2 Tumakuru Storage",
    "ID": "B2",
    "Type": "BESS Storage",
    "Capacity (MW)": 40,
    "Latitude": 13.36,
    "Longitude": 77.08,
})

df_map = pd.DataFrame(map_records)

fig_map = px.scatter_geo(
    df_map,
    lat="Latitude",
    lon="Longitude",
    color="Type",
    size="Capacity (MW)",
    hover_name="Asset",
    scope="asia",
    center=dict(lat=15.0, lon=76.5),
    title="Karnataka Renewable Portfolio Distribution",
    color_discrete_map={"Solar Farm": "#F59E0B", "Wind Farm": "#10B981", "BESS Storage": "#8B5CF6"},
)
fig_map.update_geos(
    visible=True,
    resolution=50,
    showcountries=True,
    showsubunits=True,
    fitbounds="locations",
)
fig_map.update_layout(template="plotly_white", margin=dict(l=0, r=0, t=40, b=0), height=450)
st.plotly_chart(fig_map, use_container_width=True, key="map_fig_assets")

st.markdown("---")

# 2. Asset Specifications Table
st.subheader("2. Generation & Storage Asset Specifications")
c_tbl1, c_tbl2 = st.columns(2)

with c_tbl1:
    st.write("**Solar & Wind Generating Assets**")
    gen_list = []
    for s in assets_data["solar_farms"]:
        gen_list.append({"ID": s["id"], "Asset": s["name"], "Type": "Solar", "Capacity": f"{s['capacity_mw']} MW", "Coords": f"{s['lat']}, {s['lon']}"})
    for w in assets_data["wind_farms"]:
        gen_list.append({"ID": w["id"], "Asset": w["name"], "Type": "Wind", "Capacity": f"{w['capacity_mw']} MW", "Coords": f"{w['lat']}, {w['lon']}"})
    st.dataframe(pd.DataFrame(gen_list), use_container_width=True, hide_index=True)

with c_tbl2:
    st.write("**Battery Energy Storage Systems (BESS)**")
    bess_list = [
        {"ID": b["id"], "Power Rating": f"{b['power_mw']} MW", "Storage Capacity": f"{b['energy_mwh']} MWh", "Round-trip Eff.": f"{b['eta_charge']*b['eta_discharge']*100:.1f}%", "Safe SoC Range": f"{int(b['soc_min']*100)}% – {int(b['soc_max']*100)}%"}
        for b in assets_data["batteries"]
    ]
    st.dataframe(pd.DataFrame(bess_list), use_container_width=True, hide_index=True)

# 3. Offtake Customer Contracts
st.subheader("3. Round-The-Clock (RTC) Industrial Consumers")
cons_list = [
    {
        "ID": c["id"],
        "Customer": c["name"],
        "Base Load": f"{c['base_mw']} MW",
        "Critical Fraction": f"{int(c['critical_fraction']*100)}% (Always Protected)",
        "Max DR Capacity": f"{c['dr_max_mw']} MW",
        "DR Incentive Rate": f"₹{c['dr_incentive_inr_per_mwh']:,.0f}/MWh",
    }
    for c in assets_data["consumers"]
]
st.dataframe(pd.DataFrame(cons_list), use_container_width=True, hide_index=True)

st.markdown("---")

# 4. Market & Economic Parameters
st.subheader("4. Market Tariffs & Penalty Parameters")
p1, p2, p3, p4 = st.columns(4)
with p1:
    st.metric("Contract Shortfall Penalty", f"₹{market_data['penalties']['contract_shortfall_inr_per_mwh']:,.0f}/MWh")
with p2:
    st.metric("Lost Load (VOLL)", f"₹{market_data['penalties']['value_of_lost_load_inr_per_mwh']:,.0f}/MWh")
with p3:
    st.metric("Grid Emission Factor", f"{market_data['carbon']['grid_emission_factor_tco2_per_mwh']} tCO₂/MWh")
with p4:
    st.metric("Carbon Price", f"₹{market_data['carbon']['carbon_price_inr_per_tco2']:,.0f}/tCO₂")

st.markdown("---")

# 5. CSV Upload Validator
st.subheader("5. Custom Data Ingestion & Tariff Upload")
st.caption("Upload a custom IEX price timeseries or custom demand profile for interactive evaluation.")

uploaded_file = st.file_uploader("Upload CSV (Required column: 'timestamp')", type=["csv"])
if uploaded_file is not None:
    try:
        user_df = pd.read_csv(uploaded_file)
        st.success(f"Uploaded file successfully parsed! {len(user_df)} rows and {len(user_df.columns)} columns detected.")
        st.dataframe(user_df.head(5), use_container_width=True)
    except Exception as e:
        st.error(f"Error parsing uploaded CSV: {e}")

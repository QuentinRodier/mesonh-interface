import cloud_init
import streamlit as st
from config import EXAMPLES_DIR

st.set_page_config(page_title="Meso-NH Tools ", layout="wide")

st.title("🛠️ Meso-NH Tools App")
st.divider()

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.subheader("📝 Namelist Editor")
    st.write("Edit one single namelist file")
    
    if st.button("Edit a Namelist", use_container_width=True):
        st.switch_page("pages/Namelist_Editor.py")

with col2:
    st.subheader("📂 Workspace")
    st.write("Edit multiple namelist files in a directory")
    
    if st.button("Start a Workspace", use_container_width=True):
        st.switch_page("pages/Workspace.py")

with col3:
    st.subheader("⚖️ Compare Namelists")
    st.write(f"Compare 2 namelists and highlight differences")
    
    if st.button("Compare Namelists", use_container_width=True):
        st.switch_page("pages/Compare_Namelist.py")

st.space("medium") 

col4, col5, col6 = st.columns([1, 1, 1])

with col4:
    st.subheader("🌐 Horizontal Grids")
    st.write("Configure horizontal grid with interactive map")
    
    if st.button("Configure Horizontal Grids", use_container_width=True):
        st.switch_page("pages/Horizontal_Grids.py")

with col5:
    st.subheader("📈 Vertical Levels")
    st.write("Configure and play with NAM_VER_GRID parameters")
    
    if st.button("Configure Vertical Levels", use_container_width=True):
        st.switch_page("pages/Vertical_Levels.py")

with col6:
    st.subheader("🎈Initial Radiosoundings and Forcing")
    st.write("Configure and plots free-format data from PRE_IDEA1.nam")
    
    if st.button("Configure & Plot RSOU and FRC data", use_container_width=True):
        st.switch_page("pages/Initial_radiosoundings_forcing.py")

st.space("medium") 

col7, col8, col9 = st.columns([1, 1, 1])
with col7:
    st.subheader("📚 Catalogue Explorer")
    st.write(f"Browse examples namelists and search tools in the catalogue")
    
    if st.button("Explore the Catalogue", use_container_width=True):
        st.switch_page("pages/Catalogue_Explorer.py")

with col8:
    st.subheader("📊 Quick Plots")
    st.write("Plots lines, contours, and vertical profiles from multiple NetCDF")
    
    if st.button("Plots", use_container_width=True):
        st.switch_page("pages/Quick_Plots.py")
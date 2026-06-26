import cloud_init
import streamlit as st

st.set_page_config(page_title="Meso-NH Tools", layout="wide")

pg = st.navigation([
    st.Page("Home.py", title="Home", icon="🏠", default=True),
    st.Page("pages/Namelist_Editor.py", title="Namelist Editor", icon="📝"),
    st.Page("pages/Workspace.py", title="Workspace", icon="📂"),
    st.Page("pages/Compare_Namelist.py", title="Compare Namelists", icon="⚖️"),
    st.Page("pages/Catalogue_Explorer.py", title="Catalogue Explorer", icon="📚"),
    st.Page("pages/Vertical_Levels.py", title="Vertical Levels", icon="📈"),
    st.Page("pages/Horizontal_Grids.py", title="Horizontal Grids", icon="🌐"),
    st.Page("pages/Initial_radiosoundings_forcing.py", title="Initial Profile and Forcing", icon="🎈"),
    st.Page("pages/Quick_Plots.py", title="Quick Plots", icon="📊"),
])
pg.run()

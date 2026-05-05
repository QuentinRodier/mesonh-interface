import streamlit as st
from config import EXAMPLES_DIR

st.set_page_config(page_title="Meso-NH Tools", layout="wide")

st.title("🛠️ Meso-NH Tools")
st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 Namelist Editor")
    st.write("Edit one single namelist file")
    
    if st.button("Launch Editor", use_container_width=True):
        st.switch_page("pages/Namelist_Editor.py")

with col2:
    st.subheader("📂 Workspace")
    st.write("Edit multiple namelist files in a directory")
    
    if st.button("Launch Workspace", use_container_width=True):
        st.switch_page("pages/Workspace.py")

st.divider()

col3, col4 = st.columns([1, 1])

with col3:
    st.subheader("📚 Catalogue Explorer")
    st.write(f"Browse namelists in {EXAMPLES_DIR}")
    
    if st.button("Launch Catalogue Explorer", use_container_width=True):
        st.switch_page("pages/Catalogue_Explorer.py")

with col4:
    st.subheader("📈 Vertical Levels")
    st.write("Configure and play with NAM_VER_GRID parameters")
    
    if st.button("Launch Vertical Levels", use_container_width=True):
        st.switch_page("pages/Vertical_Levels.py")

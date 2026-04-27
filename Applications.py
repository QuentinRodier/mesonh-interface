import streamlit as st

st.set_page_config(page_title="Meso-NH Tools", layout="wide")

st.title("🛠️ Meso-NH Tools")
st.divider()

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 Namelist Editor")
    st.write("Edit one single namelist")

with col2:
    if st.button("Start Editor", use_container_width=True):
        st.switch_page("pages/Namelist_Editor.py")
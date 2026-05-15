import streamlit as st

def save_copied_params(params_dict):
    """Sauvegarde un dictionnaire de paramètres dans le session_state."""
    st.session_state['copied_namelist_params'] = params_dict

def get_copied_params():
    """Récupère les paramètres sauvegardés."""
    return st.session_state.get('copied_namelist_params', None)

def clear_copied_params():
    """Efface les paramètres sauvegardés."""
    if 'copied_namelist_params' in st.session_state:
        del st.session_state['copied_namelist_params']

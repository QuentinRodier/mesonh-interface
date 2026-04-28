import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import docs

st.set_page_config(page_title='Vertical Levels', layout='wide')

if 'kmax' not in st.session_state:
    st.session_state.kmax = 120
if 'zmax' not in st.session_state:
    st.session_state.zmax = 5000.0
if 'zgrd' not in st.session_state:
    st.session_state.zgrd = 10.0
if 'ztop' not in st.session_state:
    st.session_state.ztop = 300.0
if 'sgrd' not in st.session_state:
    st.session_state.sgrd = 4.0
if 'stop' not in st.session_state:
    st.session_state.stop = 5.0

if 'reference_params' not in st.session_state:
    st.session_state.reference_params = None

st.title('📈 Vertical Levels')
st.caption('Configure and play with NAM_VER_GRID parameters')

def compute_levels(kmax, zmax, zgrd, ztop, sgrd, stop):
    rz = [0.0] * (kmax + 1)
    rz[1] = 0.0
    rz[2] = zgrd
    for i in range(2, kmax):
        dz_prev = rz[i] - rz[i-1]
        factor = 1 + (sgrd / 100.0 if rz[i] <= zmax else stop / 100.0)
        rz[i+1] = rz[i] + dz_prev * factor if i + 1 <= kmax else rz[i]
        if (rz[i+1] - rz[i]) >= ztop:
            rz[i+1] = rz[i] + ztop
    return rz[1:kmax+1]

with st.sidebar:
    st.header('Parameters')
    KMAX = st.number_input('NKMAX', value=90, min_value=3, max_value=1000)
    st.session_state.kmax = KMAX
    ZMAX = st.slider('ZZMAX_STRGRD (m)', 0, 15000, int(st.session_state.zmax), key='zmax_slider')
    st.session_state.zmax = ZMAX
    ZGRD = st.slider('ZDZGRD (m)', 0.0, 1000.0, float(st.session_state.zgrd), key='zgrd_slider')
    st.session_state.zgrd = ZGRD
    ZTOP = st.slider('ZDZTOP (m)', 0.0, 2500.0, float(st.session_state.ztop), key='ztop_slider')
    st.session_state.ztop = ZTOP
    SGRD = st.slider('ZSTRGRD (%)', 0.0, 40.0, float(st.session_state.sgrd), key='sgrd_slider')
    st.session_state.sgrd = SGRD
    STOP = st.slider('ZSTRTOP (%)', 0.0, 40.0, float(st.session_state.stop), key='stop_slider')
    st.session_state.stop = STOP

    current_params = {
        'kmax': KMAX, 'zmax': ZMAX, 'zgrd': ZGRD, 
        'ztop': ZTOP, 'sgrd': SGRD, 'stop': STOP
    }

    manual_mode = st.checkbox('Manual mode (YZGRID_TYPE=\'MANUAL\')', value=False, key='manual_mode')
    
    manual_heights = []
    if manual_mode:
        if 'manual_levels' in st.session_state and st.session_state.manual_levels:
            default_text = '\n'.join(str(h) for h in st.session_state.manual_levels)
        else:
            default_text = ''
        
        manual_text = st.text_area('Enter heights (one per line, in meters)', value=default_text, height=150, key='manual_text')

        col_load, col_clear = st.columns([1, 1])
        with col_load:
            if st.button('Load Values'):
                if manual_text.strip():
                    try:
                        manual_heights = [float(line.strip()) for line in manual_text.strip().split('\n') if line.strip()]
                        if manual_heights:
                            st.session_state.manual_levels = manual_heights
                            st.success(f'Loaded {len(manual_heights)} levels!')
                        else:
                            st.warning('No valid heights entered')
                    except ValueError as e:
                        st.error(f'Invalid input: {e}')
                else:
                    st.warning('Enter at least one height')
        with col_clear:
            if st.button('Clear'):
                if 'manual_levels' in st.session_state:
                    del st.session_state.manual_levels
                st.rerun()

    st.divider()
    st.header('Settings')
    
    compare_mode = st.checkbox('Compare mode', value=False, key='compare_mode')
    
    if compare_mode:
        if st.button('Set Current as Reference'):
            st.session_state.reference_params = current_params.copy()
            st.success('Reference set!')
        
        if 'reference_params' in st.session_state:
            st.session_state.compare_params = st.session_state.reference_params
    
    show_zmax_line = st.checkbox('Show ZZMAX_STRGRD line', value=True, key='show_zmax_line')

current_params = {
    'kmax': KMAX, 'zmax': ZMAX, 'zgrd': ZGRD, 
'ztop': ZTOP, 'sgrd': SGRD, 'stop': STOP
    }

if manual_mode and manual_heights:
    levels = manual_heights
    mesh = [levels[i] - levels[i-1] if i > 0 else 0 for i in range(len(levels))]
    idx = list(range(1, len(levels)+1))
else:
    levels = compute_levels(KMAX, ZMAX, ZGRD, ZTOP, SGRD, STOP)
    mesh = [levels[i] - levels[i-1] if i > 0 else 0 for i in range(len(levels))]
    idx = list(range(1, len(levels)+1))

col1, col2 = st.columns([2, 1])

with col1:
    fig1 = go.Figure()
    
    colors = ['lightblue', 'red']
    color_idx = 0
    
    fig1.add_trace(go.Scatter(
        x=mesh[1:], y=levels[1:], mode='lines+markers',
        name='Current', hovertemplate='Level %{customdata}<br>dz=%{x:.2f}<br>z=%{y:.2f}<extra></extra>',
        customdata=idx[1:], line=dict(color=colors[color_idx]), marker=dict(size=6)
    ))
    
    if compare_mode and st.session_state.reference_params:
        ref_params = st.session_state.reference_params
        ref_levels = compute_levels(ref_params['kmax'], ref_params['zmax'], ref_params['zgrd'], ref_params['ztop'], ref_params['sgrd'], ref_params['stop'])
        ref_mesh = [ref_levels[i] - ref_levels[i-1] if i > 0 else 0 for i in range(len(ref_levels))]
        ref_idx = list(range(1, len(ref_levels)+1))
        
        fig1.add_trace(go.Scatter(
            x=ref_mesh[1:], y=ref_levels[1:], mode='lines+markers',
            name='Reference', hovertemplate='Level %{customdata}<br>dz=%{x:.2f}<br>z=%{y:.2f}<extra></extra>',
            customdata=ref_idx[1:], line=dict(color=colors[color_idx + 1]), marker=dict(size=6)
        ))
    
    if show_zmax_line:
        fig1.add_hline(y=ZMAX, line_dash="dash", line_color="grey", annotation_text=f"ZZMAX={ZMAX}m", annotation_position="top right")
    
    fig1.update_layout(
        title='Mesh size with respect to height above ground',
        xaxis_title='Mesh size (m)',
        yaxis_title='Height above ground (m)',
        height=700,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.02)
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    fig2 = go.Figure()
    
    fig2.add_trace(go.Scatter(
        x=mesh[1:], y=[level + 1e-6 for level in levels[1:]], mode='lines+markers',
        name='Current', hovertemplate='Level %{customdata}<br>dz=%{x:.2f}<br>z=%{y:.2f}<extra></extra>',
        customdata=idx[1:], line=dict(color=colors[0]), marker=dict(size=6)
    ))
    
    if compare_mode and st.session_state.reference_params:
        ref_params = st.session_state.reference_params
        ref_levels = compute_levels(ref_params['kmax'], ref_params['zmax'], ref_params['zgrd'], ref_params['ztop'], ref_params['sgrd'], ref_params['stop'])
        ref_mesh = [ref_levels[i] - ref_levels[i-1] if i > 0 else 0 for i in range(len(ref_levels))]
        ref_idx = list(range(1, len(ref_levels)+1))
        
        fig2.add_trace(go.Scatter(
            x=ref_mesh[1:], y=[level + 1e-6 for level in ref_levels[1:]], mode='lines+markers',
            name='Reference', hovertemplate='Level %{customdata}<br>dz=%{x:.2f}<br>z=%{y:.2f}<extra></extra>',
            customdata=ref_idx[1:], line=dict(color=colors[1]), marker=dict(size=6)
        ))
    
    if show_zmax_line:
        fig2.add_hline(y=ZMAX, line_dash="dash", line_color="grey", annotation_text=f"ZZMAX={ZMAX}m", annotation_position="top right")
    
    fig2.update_layout(
        title='Mesh size (log scale)',
        xaxis_title='Mesh size (m)',
        yaxis_title='Height above ground (m)',
        yaxis_type='log',
        height=700,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.02)
    )
    st.plotly_chart(fig2, use_container_width=True)

if 'previous_params' not in st.session_state:
    st.session_state.previous_params = None

if compare_mode and st.session_state.reference_params:
    ref_params = st.session_state.reference_params
    ref_levels = compute_levels(ref_params['kmax'], ref_params['zmax'], ref_params['zgrd'], ref_params['ztop'], ref_params['sgrd'], ref_params['stop'])
    ref_mesh = [ref_levels[i] - ref_levels[i-1] if i > 0 else 0 for i in range(len(ref_levels))]
    ref_idx = list(range(1, len(ref_levels)+1))
    
    col_ref, col_curr = st.columns(2)
    
    with col_ref:
        st.subheader('Reference Levels Table')
        ref_df = pd.DataFrame({
            'Level index': ref_idx,
            'Height (m)': ref_levels,
            'Mesh size (m)': ref_mesh
        })
        st.dataframe(ref_df, use_container_width=True)
    
    with col_curr:
        st.subheader('Current Levels Table')
        curr_df = pd.DataFrame({
            'Level index': idx,
            'Height (m)': levels,
            'Mesh size (m)': mesh
        })
        st.dataframe(curr_df, use_container_width=True)
else:
    df = pd.DataFrame({
        'Level index': idx,
        'Height (m)': levels,
        'Mesh size (m)': mesh
    })
    st.subheader('Levels Table')
    st.dataframe(df, use_container_width=True)

st.divider()
st.text(f"Number of levels in the boundary-layer:")
col_alt1, col_res1 = st.columns([1, 1])
with col_alt1:
    alt_below = st.number_input('Height below (m)', value=2000, min_value=0, max_value=30000, key='alt_below', step=100)
with col_res1:
    count_below = sum(1 for h in levels if h <= alt_below)
    st.text(f"Number of vertical levels below: {count_below}")

st.text(f"Number of levels for the upper vertical relaxation layer (5 to 7 levels recommended):")
col_alt2, col_res2 = st.columns([1, 1])
with col_alt2:
    alt_above = st.number_input('Height above (m) - correspond to XALZBOT', value=10000, min_value=0, max_value=30000, key='alt_above', step=100)
with col_res2:
    count_above = sum(1 for h in levels if h > alt_above)
    st.text(f"Number of vertical levels above: {count_above}")

st.divider()

st.html(docs.render_rst(docs.find_docs('NAM_VER_GRID'), block_name='NAM_VER_GRID'))

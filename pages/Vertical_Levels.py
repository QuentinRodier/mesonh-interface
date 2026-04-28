import streamlit as st
import pandas as pd
import plotly.graph_objects as go

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
    KMAX = st.slider('NKMAX', 3, 200, int(st.session_state.kmax), key='kmax_slider')
    st.session_state.kmax = KMAX
    ZMAX = st.slider('ZZMAX_STRGRD (m)', 0, 15000, int(st.session_state.zmax), key='zmax_slider')
    st.session_state.zmax = ZMAX
    ZGRD = st.slider('ZDZGRD (m)', 0.0, 100.0, float(st.session_state.zgrd), key='zgrd_slider')
    st.session_state.zgrd = ZGRD
    ZTOP = st.slider('ZDZTOP (m)', 0.0, 1000.0, float(st.session_state.ztop), key='ztop_slider')
    st.session_state.ztop = ZTOP
    SGRD = st.slider('ZSTRGRD (%)', 0.0, 20.0, float(st.session_state.sgrd), key='sgrd_slider')
    st.session_state.sgrd = SGRD
    STOP = st.slider('ZSTRTOP (%)', 0.0, 20.0, float(st.session_state.stop), key='stop_slider')
    st.session_state.stop = STOP

    current_params = {
        'kmax': KMAX, 'zmax': ZMAX, 'zgrd': ZGRD, 
        'ztop': ZTOP, 'sgrd': SGRD, 'stop': STOP
    }

    st.divider()
    st.header('Options')
    
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
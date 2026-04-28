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

st.title('📈 Vertical Levels')
st.caption('Configure and play with NAM_VER_GRID parameters')

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

    st.divider()
    st.header('Options')
    show_zmax_line = st.checkbox('Show ZZMAX_STRGRD line', value=True)

def compute_levels():
    KMAX = st.session_state.kmax
    ZMAX = st.session_state.zmax
    ZGRD = st.session_state.zgrd
    ZTOP = st.session_state.ztop
    SGRD = st.session_state.sgrd
    STOP = st.session_state.stop

    rz = [0.0] * (KMAX + 1)
    rz[1] = 0.0
    rz[2] = ZGRD
    for i in range(2, KMAX):
        dz_prev = rz[i] - rz[i-1]
        factor = 1 + (SGRD / 100.0 if rz[i] <= ZMAX else STOP / 100.0)
        rz[i+1] = rz[i] + dz_prev * factor if i + 1 <= KMAX else rz[i]
        if (rz[i+1] - rz[i]) >= ZTOP:
            rz[i+1] = rz[i] + ZTOP
    return rz[1:KMAX+1]

levels = compute_levels()
mesh = [levels[i] - levels[i-1] if i > 0 else 0 for i in range(len(levels))]
idx = list(range(1, len(levels)+1))

df = pd.DataFrame({'Level index (flux point)': idx, 'Height above ground (m)': levels, 'Mesh size (m)': mesh})

col1, col2 = st.columns([2,1])
with col1:
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=df['Mesh size (m)'][1:], y=df['Height above ground (m)'][1:], mode='lines+markers',
        name='Mesh size', hovertemplate='Level %{customdata}<br>dz=%{x:.2f}<br>z=%{y:.2f}<extra></extra>',
        customdata=df['Level index (flux point)'][1:]
    ))
    if show_zmax_line:
        fig1.add_hline(y=st.session_state.zmax, line_dash="dash", line_color="red", annotation_text=f"ZZMAX={st.session_state.zmax}m", annotation_position="top right")
    fig1.update_layout(
        title='Mesh size with respect to height above ground',
        xaxis_title='Mesh size (m)',
        yaxis_title='Height above ground (m)',
        height=700
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df['Mesh size (m)'][1:], y=df['Height above ground (m)'][1:] + 1e-6, mode='lines+markers',
        name='Mesh size (log)', hovertemplate='Level %{customdata}<br>dz=%{x:.2f}<br>z=%{y:.2f}<extra></extra>',
        customdata=df['Level index (flux point)'][1:]
    ))
    if show_zmax_line:
        fig2.add_hline(y=st.session_state.zmax, line_dash="dash", line_color="red", annotation_text=f"ZZMAX={st.session_state.zmax}m", annotation_position="top right")
    fig2.update_layout(
        title='Mesh size with respect to height above ground (log scale)',
        xaxis_title='Mesh size (m)',
        yaxis_title='Height above ground (m)',
        yaxis_type='log',
        height=700
    )
    st.plotly_chart(fig2, use_container_width=True)

st.subheader('Levels Table')
st.dataframe(df, use_container_width=True)
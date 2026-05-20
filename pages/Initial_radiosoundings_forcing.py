import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from modules import parser
import math

st.set_page_config(page_title="Ideal Radiosounding and Forcing", layout="wide")

_RSOU_KINDS_MAP = {
    "STANDARD": {"alt": "P", "wind": "DF", "temp": "T", "moist": "TD"},
    "PUVTHVMR": {"alt": "P", "wind": "UV", "temp": "THV", "moist": "MR"},
    "PUVTHVHU": {"alt": "P", "wind": "UV", "temp": "THV", "moist": "HU"},
    "ZUVTHVMR": {"alt": "Z", "wind": "UV", "temp": "THV", "moist": "MR"},
    "ZUVTHVHU": {"alt": "Z", "wind": "UV", "temp": "THV", "moist": "HU"},
    "PUVTHDMR": {"alt": "P", "wind": "UV", "temp": "THD", "moist": "MR"},
    "PUVTHDHU": {"alt": "P", "wind": "UV", "temp": "THD", "moist": "HU"},
    "ZUVTHDMR": {"alt": "Z", "wind": "UV", "temp": "THD", "moist": "MR"},
    "ZUVTHLMR": {"alt": "Z", "wind": "UV", "temp": "THL", "moist": "MR"},
}

_P0 = 100000.0
_RCP = 0.286


if 'free_format_data' not in st.session_state:
    st.session_state.free_format_data = None
if 'free_format_raw' not in st.session_state:
    st.session_state.free_format_raw = None


def _uv_from_dir_force(d, f):
    r = d * math.pi / 180.0
    return -f * math.sin(r), -f * math.cos(r)


def _theta_from_tp(T, P):
    return T * (_P0 / P) ** _RCP


def _td_to_rh(Td, T):
    a, b = 17.27, 237.7
    Tc, Tdc = T - 273.15, Td - 273.15
    es = 6.112 * math.exp(a * Tc / (b + Tc))
    e = 6.112 * math.exp(a * Tdc / (b + Tdc))
    return min(e / es * 100.0, 100.0) if es > 0 else 0.0


def _mr_to_rh(mr, P):
    return min(mr * P / (0.622 + mr) / 611.0 * 100.0, 100.0) if P > 0 else 0.0


def make_wind_plot(wind_alt, u_vals, v_vals, mod_vals, title="Wind profiles"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=u_vals, y=wind_alt, mode='lines+markers', name='u (m/s)'))
    fig.add_trace(go.Scatter(x=v_vals, y=wind_alt, mode='lines+markers', name='v (m/s)'))
    fig.add_trace(go.Scatter(x=mod_vals, y=wind_alt, mode='lines+markers', name='Wind module (m/s)', line=dict(dash='dot')))
    fig.update_layout(title=title, xaxis_title='Value', yaxis_title='Altitude', height=400, legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.02))
    return fig


def make_thermo_plot(mass_alt, theta_vals, rh_vals, title="Thermodynamic profiles"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=theta_vals, y=mass_alt, mode='lines+markers', name='θ (K)', xaxis='x'))
    fig.add_trace(go.Scatter(x=rh_vals, y=mass_alt, mode='lines+markers', name='RH (%)', xaxis='x2'))
    fig.update_layout(title=title, xaxis_title='θ (K)', xaxis2=dict(overlaying='x', side='top', title='RH (%)'),
                      height=400, legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.02))
    fig.update_traces(xaxis='x', selector=dict(name='θ (K)'))
    fig.update_traces(xaxis='x2', selector=dict(name='RH (%)'))
    return fig


def make_forcing_plot(alt, fields, field_names, title):
    fig = go.Figure()
    for i, name in enumerate(field_names):
        fig.add_trace(go.Scatter(x=[l[i] for l in fields], y=alt, mode='lines+markers', name=name))
    fig.update_layout(title=title, xaxis_title='Value', yaxis_title='Altitude', height=400, legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.02))
    return fig


def get_wind_data(rs):
    kind_info = _RSOU_KINDS_MAP.get(rs.get("kind", "STANDARD"), _RSOU_KINDS_MAP["STANDARD"])
    wind_alt = [w["altitude"] for w in rs["wind_levels"]]
    if kind_info["wind"] == "UV":
        u_vals = [w["var1"] for w in rs["wind_levels"]]
        v_vals = [w["var2"] for w in rs["wind_levels"]]
    else:
        u_vals = []
        v_vals = []
        for w in rs["wind_levels"]:
            u, v = _uv_from_dir_force(w["var1"], w["var2"])
            u_vals.append(u)
            v_vals.append(v)
    mod_vals = [math.sqrt(u**2 + v**2) for u, v in zip(u_vals, v_vals)]
    return wind_alt, u_vals, v_vals, mod_vals


def get_mass_data(rs, ground_pressure=None):
    kind_info = _RSOU_KINDS_MAP.get(rs.get("kind", "STANDARD"), _RSOU_KINDS_MAP["STANDARD"])
    alt_is_p = kind_info["alt"] == "P"

    def _alt(i):
        return rs["mass_levels"][i - 1]["altitude"] if i > 0 else (
            rs["ground_pressure"] if alt_is_p else rs["ground_height"])

    def _get_temp(i):
        return rs["mass_levels"][i - 1]["temperature"] if i > 0 else rs["ground_temperature"]

    def _get_hum(i):
        return rs["mass_levels"][i - 1]["humidity"] if i > 0 else rs["ground_humidity"]

    n = len(rs["mass_levels"]) + 1  # total levels including ground
    mass_alt = []
    theta_vals = []
    rh_vals = []

    for i in range(n):
        mass_alt.append(_alt(i))
        T = _get_temp(i)
        hum = _get_hum(i)
        P = _alt(i) if alt_is_p else (ground_pressure or _P0)

        if kind_info["temp"] == "T":
            theta_vals.append(_theta_from_tp(T, P))
        else:
            theta_vals.append(T)

        if kind_info["moist"] == "HU":
            rh_vals.append(hum)
        elif kind_info["moist"] == "MR":
            rh_vals.append(_mr_to_rh(hum, P))
        elif kind_info["moist"] == "TD":
            rh_vals.append(_td_to_rh(hum, T))
        else:
            rh_vals.append(hum)

    return mass_alt, theta_vals, rh_vals


with st.sidebar:
    st.header("Upload PRE_IDEA1.nam")
    uploaded_file = st.file_uploader("Upload a PRE_IDEA1.nam file", type=['nam', 'NAM', 'txt'])
    if uploaded_file is not None:
        raw = uploaded_file.getvalue().decode("utf-8")
        try:
            data = parser.parse_free_format(raw)
            st.session_state.free_format_data = data
            st.session_state.free_format_raw = raw
            st.success(f"Loaded: {uploaded_file.name}")
            st.rerun()
        except Exception as e:
            st.error(f"Parsing error: {e}")

    if st.session_state.free_format_data:
        d = st.session_state.free_format_data
        st.divider()
        st.write(f"**Radiosounding:** {d['radiosounding_type'] or '—'}")
        if d.get("forcing_type"):
            st.write(f"**Forcing:** {d['forcing_type']}")
        st.divider()
        if st.button("✏️ Generate & Download"):
            out = parser.write_free_format(d)
            st.download_button("⬇️ Download free-format text", out, file_name="free_format.txt", mime="text/plain")
    else:
        st.info("Upload a PRE_IDEA1.nam to get started")

if st.session_state.free_format_data is None:
    st.info("👈 Upload a PRE_IDEA1.nam file in the sidebar")
    st.stop()

data = st.session_state.free_format_data
tab1, tab2 = st.tabs(["Radiosounding", "Forcing"])

with tab1:
    rt = data["radiosounding_type"]
    rs = data.get("radiosounding")
    if rt is None or rs is None:
        st.info("No radiosounding data found.")
    elif rt == "CSTN":
        st.subheader("Constant Brunt-Väisälä (CSTN)")
        col_l, col_r = st.columns([1, 1])
        with col_l:
            d = rs["date"]
            c1, c2, c3, c4 = st.columns(4)
            with c1: nd = st.number_input("Year", value=d["year"], key="cstn_yr")
            with c2: nm = st.number_input("Month", 1, 12, d["month"], key="cstn_mo")
            with c3: ndy = st.number_input("Day", 1, 31, d["day"], key="cstn_dy")
            with c4: nt = st.number_input("Time (s)", value=d["time"], format="%.1f", key="cstn_tm")
            rs["date"] = {"year": int(nd), "month": int(nm), "day": int(ndy), "time": float(nt)}

            rs["ground_thv"] = st.number_input("Ground θᵥ (K)", value=rs["ground_thv"], format="%.4f", key="cstn_thv")
            rs["ground_pressure"] = st.number_input("Ground pressure (Pa)", value=rs["ground_pressure"], format="%.1f", key="cstn_p0")

            n = rs["nlevels"]
            n_new = st.number_input("Number of levels", 1, 200, n, key="cstn_nl")

            if n_new != n:
                old = len(rs["heights"])
                for key in ("heights", "u", "v", "rh"):
                    arr = rs[key]
                    if n_new > old:
                        arr.extend([arr[-1] if arr else 0.0] * (n_new - old))
                    else:
                        rs[key] = arr[:n_new]
                bv = rs["brunt_vaisala"]
                if n_new > 1:
                    bv_needed = n_new - 1
                    if len(bv) > bv_needed:
                        rs["brunt_vaisala"] = bv[:bv_needed]
                    else:
                        rs["brunt_vaisala"] = bv + [bv[-1] if bv else 0.01] * (bv_needed - len(bv))
                else:
                    rs["brunt_vaisala"] = bv[:1] if bv else [0.01]
                rs["nlevels"] = n_new
                st.rerun()

            df = pd.DataFrame({"Height (m)": rs["heights"], "u (m/s)": rs["u"], "v (m/s)": rs["v"], "RH (%)": rs["rh"]})
            edited = st.data_editor(df, num_rows="dynamic", key="cstn_df", use_container_width=True)
            rs["heights"] = edited["Height (m)"].tolist()
            rs["u"] = edited["u (m/s)"].tolist()
            rs["v"] = edited["v (m/s)"].tolist()
            rs["rh"] = edited["RH (%)"].tolist()
            rs["nlevels"] = len(edited)
            if rs["nlevels"] > 1:
                bv_len = rs["nlevels"] - 1
                if len(rs["brunt_vaisala"]) != bv_len:
                    bv = rs["brunt_vaisala"]
                    if len(bv) > bv_len:
                        rs["brunt_vaisala"] = bv[:bv_len]
                    else:
                        rs["brunt_vaisala"] = bv + [bv[-1] if bv else 0.01] * (bv_len - len(bv))
            st.caption("Brunt-Väisälä frequency (layers):")
            bv_df = pd.DataFrame({"N² (s⁻²)": rs["brunt_vaisala"]})
            bv_edited = st.data_editor(bv_df, num_rows="dynamic", key="cstn_bv", use_container_width=True)
            rs["brunt_vaisala"] = bv_edited["N² (s⁻²)"].tolist()

        with col_r:
            h = rs["heights"]
            if h:
                mod = [math.sqrt(u**2 + v**2) for u, v in zip(rs["u"], rs["v"])]
                fig1 = make_wind_plot(h, rs["u"], rs["v"], mod)
                st.plotly_chart(fig1, use_container_width=True)

                # Compute THV profile from BV frequency
                thv = [rs["ground_thv"]]
                bv = rs["brunt_vaisala"]
                g = 9.81
                for i in range(min(len(bv), len(h) - 1)):
                    dz = h[i + 1] - h[i]
                    thv.append(thv[-1] * math.exp(bv[i] * dz / g))
                thv = thv[:len(h)]

                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=thv, y=h, mode='lines+markers', name='θᵥ (K)', xaxis='x'))
                fig2.add_trace(go.Scatter(x=rs["rh"], y=h, mode='lines+markers', name='RH (%)', xaxis='x2'))
                fig2.update_layout(title="Potential temperature and RH",
                                   xaxis=dict(title='θᵥ (K)', side='bottom'),
                                   xaxis2=dict(title='RH (%)', side='top', overlaying='x'),
                                   yaxis_title='Altitude (m)', height=400)
                st.plotly_chart(fig2, use_container_width=True)

    elif rt == "RSOU":
        st.subheader("Radiosounding (RSOU)")
        col_l, col_r = st.columns([1, 1])
        with col_l:
            d = rs["date"]
            c1, c2, c3, c4 = st.columns(4)
            with c1: nd = st.number_input("Year", value=d["year"], key="rsou_yr")
            with c2: nm = st.number_input("Month", 1, 12, d["month"], key="rsou_mo")
            with c3: ndy = st.number_input("Day", 1, 31, d["day"], key="rsou_dy")
            with c4: nt = st.number_input("Time (s)", value=d["time"], format="%.1f", key="rsou_tm")
            rs["date"] = {"year": int(nd), "month": int(nm), "day": int(ndy), "time": float(nt)}

            kind_opts = list(_RSOU_KINDS_MAP.keys())
            k_idx = kind_opts.index(rs.get("kind", "STANDARD")) if rs.get("kind") in kind_opts else 0
            rs["kind"] = st.selectbox("Radiosounding kind", kind_opts, index=k_idx, key="rsou_kind")
            kind_info = _RSOU_KINDS_MAP[rs["kind"]]

            rs["ground_height"] = st.number_input("Ground height (m)", value=rs["ground_height"], format="%.2f", key="rsou_gh")
            rs["ground_pressure"] = st.number_input("Ground pressure (Pa)", value=rs["ground_pressure"], format="%.1f", key="rsou_gp")
            rs["ground_temperature"] = st.number_input("Ground temperature (K)", value=rs["ground_temperature"], format="%.4f", key="rsou_gt")
            rs["ground_humidity"] = st.number_input("Ground humidity", value=rs["ground_humidity"], format="%.4f", key="rsou_ghu")

            st.markdown("**Wind levels**")
            wcols = ["Altitude", "Var1", "Var2"]
            wdf = pd.DataFrame(rs["wind_levels"])[["altitude", "var1", "var2"]]
            wdf.columns = wcols
            wedited = st.data_editor(wdf, num_rows="dynamic", key="wind_df", use_container_width=True)
            rs["wind_levels"] = [{"altitude": r[0], "var1": r[1], "var2": r[2]} for r in wedited.to_numpy()]
            rs["nwind"] = len(rs["wind_levels"])

            st.markdown("**Mass levels** (excluding ground)")
            mcols = ["Altitude", "Temperature", "Humidity"]
            mdf = pd.DataFrame(rs["mass_levels"])[["altitude", "temperature", "humidity"]]
            mdf.columns = mcols
            if rs["mass_levels"] and "cloud" in rs["mass_levels"][0]:
                mdf["Cloud"] = [ml.get("cloud", 0.0) for ml in rs["mass_levels"]]
            if rs["mass_levels"] and "ice" in rs["mass_levels"][0]:
                mdf["Ice"] = [ml.get("ice", 0.0) for ml in rs["mass_levels"]]
            medited = st.data_editor(mdf, num_rows="dynamic", key="mass_df", use_container_width=True)
            rs["mass_levels"] = []
            for r in medited.to_numpy():
                entry = {"altitude": float(r[0]), "temperature": float(r[1]), "humidity": float(r[2])}
                if len(r) > 3:
                    entry["cloud"] = float(r[3])
                if len(r) > 4:
                    entry["ice"] = float(r[4])
                rs["mass_levels"].append(entry)
            rs["nmass"] = len(rs["mass_levels"]) + 1

        with col_r:
            if rs["wind_levels"]:
                wa, uu, vv, mm = get_wind_data(rs)
                st.plotly_chart(make_wind_plot(wa, uu, vv, mm), use_container_width=True)
            if rs["mass_levels"]:
                ma, tt, rhh = get_mass_data(rs, rs["ground_pressure"])
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=tt, y=ma, mode='lines+markers', name='θ (K)'))
                fig.add_trace(go.Scatter(x=rhh, y=ma, mode='lines+markers', name='RH (%)'))
                fig.update_layout(title="Mass profiles", xaxis_title='Value', yaxis_title='Altitude', height=400,
                                  legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.02))
                st.plotly_chart(fig, use_container_width=True)

with tab2:
    ft = data.get("forcing_type")
    fc = data.get("forcing")
    if ft is None or fc is None:
        st.info("No forcing data found.")
    else:
        st.subheader(f"Forcing ({ft})")
        ntimes = fc["ntimes"]

        fc_idx = st.selectbox("Time step", range(ntimes),
                              format_func=lambda i: f"{i+1}: {fc['forcings'][i]['date']['year']}-{fc['forcings'][i]['date']['month']:02d}-{fc['forcings'][i]['date']['day']:02d} {fc['forcings'][i]['date']['time']}s",
                              key="fc_idx")
        f_entry = fc["forcings"][fc_idx]

        col_l, col_r = st.columns([1, 1])
        with col_l:
            d = f_entry["date"]
            c1, c2, c3, c4 = st.columns(4)
            with c1: nd = st.number_input("Year", value=d["year"], key=f"fc_yr_{fc_idx}")
            with c2: nm = st.number_input("Month", 1, 12, d["month"], key=f"fc_mo_{fc_idx}")
            with c3: ndy = st.number_input("Day", 1, 31, d["day"], key=f"fc_dy_{fc_idx}")
            with c4: nt = st.number_input("Time (s)", value=d["time"], format="%.1f", key=f"fc_tm_{fc_idx}")
            f_entry["date"] = {"year": int(nd), "month": int(nm), "day": int(ndy), "time": float(nt)}

            f_entry["ground_height"] = st.number_input("Ground height (m)", value=f_entry["ground_height"], format="%.2f", key=f"fc_gh_{fc_idx}")
            f_entry["ground_pressure"] = st.number_input("Ground pressure (Pa)", value=f_entry["ground_pressure"], format="%.1f", key=f"fc_gp_{fc_idx}")
            f_entry["ground_theta"] = st.number_input("Ground θ (K)", value=f_entry["ground_theta"], format="%.4f", key=f"fc_gt_{fc_idx}")
            f_entry["ground_humidity"] = st.number_input("Ground rv (kg/kg)", value=f_entry["ground_humidity"], format="%.6f", key=f"fc_ghu_{fc_idx}")

            st.markdown("**Forcing levels**")
            fcols = ["Altitude", "u", "v", "θ", "rv", "w", "dθ/dt", "drv/dt", "du/dt", "dv/dt"]
            fdf = pd.DataFrame(f_entry["levels"])[["altitude", "u", "v", "theta", "rv", "w", "dtheta_dt", "drv_dt", "du_dt", "dv_dt"]]
            fdf.columns = fcols
            fedited = st.data_editor(fdf, num_rows="dynamic", key=f"frc_df_{fc_idx}", use_container_width=True)
            f_entry["levels"] = [
                {"altitude": r[0], "u": r[1], "v": r[2], "theta": r[3], "rv": r[4], "w": r[5],
                 "dtheta_dt": r[6], "drv_dt": r[7], "du_dt": r[8], "dv_dt": r[9]}
                for r in fedited.to_numpy()
            ]
            f_entry["nlevels"] = len(f_entry["levels"])

            if fc.get("sounding"):
                st.markdown("**Sounding (PFRC)**")
                scols = ["Pressure (Pa)", "θ (K)", "rv (kg/kg)"]
                sdf = pd.DataFrame(fc["sounding"]["levels"])[["pressure", "theta", "rv"]]
                sdf.columns = scols
                sedited = st.data_editor(sdf, num_rows="dynamic", key="sounding_df", use_container_width=True)
                fc["sounding"]["levels"] = [{"pressure": r[0], "theta": r[1], "rv": r[2]} for r in sedited.to_numpy()]
                fc["sounding"]["nlevels"] = len(fc["sounding"]["levels"])

        with col_r:
            lvls = f_entry["levels"]
            if lvls:
                alt = [l["altitude"] for l in lvls]
                st.plotly_chart(make_forcing_plot(alt, [[l["u"], l["v"], l["theta"], l["rv"], l["w"]] for l in lvls],
                                                   ["u_frc", "v_frc", "θ_frc", "rv_frc", "w_frc"],
                                                   "Forcing profiles"), use_container_width=True)
                st.plotly_chart(make_forcing_plot(alt, [[l["dtheta_dt"], l["drv_dt"], l["du_dt"], l["dv_dt"]] for l in lvls],
                                                   ["dθ/dt", "drv/dt", "du/dt", "dv/dt"],
                                                   "Tendencies"), use_container_width=True)

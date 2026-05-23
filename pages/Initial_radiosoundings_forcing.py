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

_KIND_TEMP_LABEL = {"T": "T (K)", "THV": "θᵥ (K)", "THD": "θ (K)", "THL": "θₗ (K)"}
_KIND_MOIST_LABEL = {"HU": "RH (%)", "MR": "rv (kg/kg)", "TD": "Dew point (K)"}
_KIND_WIND1_LABEL = {"UV": "U (m/s)", "DF": "Direction (°)"}
_KIND_WIND2_LABEL = {"UV": "V (m/s)", "DF": "Force (m/s)"}

_KIND_HELP_TEXT = """
All 9 radiosounding kinds follow a systematic naming convention:

- **1st letter** — vertical coordinate:
  - **P** → Pressure (Pa)
  - **Z** → Height (m)
- **2nd–3rd letters** — wind variables:
  - **UV** → Zonal (U) and meridional (V) wind (m/s)
- **4th–6th letters** — temperature variable:
  - **THV** → Virtual potential temperature (K)
  - **THD** → Dry potential temperature (K)
  - **THL** → Liquid potential temperature (K)
- **7th–8th letters** — moisture variable:
  - **MR** → Vapor mixing ratio (kg/kg)
  - **HU** → Relative humidity (%)

**STANDARD** uses pressure levels (Pa), wind direction (°) and force (m/s),
temperature (K), and dew point (K) — no letter coding.
"""

_P0 = 100000.0
_RCP = 0.286


def make_default_data():
    rsou_rs = {
        "date": {"year": 2000, "month": 1, "day": 1, "time": 0.0},
        "kind": "STANDARD", "ground_height": 0.0, "ground_pressure": 100000.0,
        "ground_temperature": 300.0, "ground_humidity": 50.0,
        "nwind": 1,
        "wind_levels": [{"altitude": 85000.0, "var1": 0.0, "var2": 0.0}],
        "nmass": 2,
        "mass_levels": [{"altitude": 90000.0, "temperature": 290.0, "humidity": 50.0}],
    }
    cstn_rs = {
        "date": {"year": 2000, "month": 1, "day": 1, "time": 0.0},
        "nlevels": 1,
        "ground_thv": 300.0, "ground_pressure": 100000.0,
        "heights": [0.0], "u": [0.0], "v": [0.0], "rh": [50.0],
        "brunt_vaisala": [0.01],
    }
    fc_entry = {"date": {"year": 2000, "month": 1, "day": 1, "time": 0.0},
                "ground_height": 0.0, "ground_pressure": 100000.0,
                "ground_theta": 300.0, "ground_humidity": 0.005,
                "nlevels": 1,
                "levels": [{"altitude": 85000.0, "u": 0.0, "v": 0.0, "theta": 300.0, "rv": 0.005, "w": 0.0,
                            "dtheta_dt": 0.0, "drv_dt": 0.0, "du_dt": 0.0, "dv_dt": 0.0}]}
    forcing = {"ntimes": 1, "forcings": [fc_entry], "sounding": None}
    return {"radiosounding_type": "CSTN", "radiosounding": cstn_rs,
            "radiosounding_cstn": cstn_rs, "radiosounding_rsou": rsou_rs,
            "forcing_type": "ZFRC", "forcing": forcing}


if 'free_format_data' not in st.session_state:
    st.session_state.free_format_data = make_default_data()
if 'upload_hash' not in st.session_state:
    st.session_state.upload_hash = None


def kind_labels(kind):
    info = _RSOU_KINDS_MAP.get(kind)
    if info is None:
        return {"alt": "Altitude", "w1": "Var1", "w2": "Var2", "temp": "Temperature", "moist": "Humidity"}
    return {"alt": "Pressure (Pa)" if info["alt"] == "P" else "Height (m)",
            "w1": _KIND_WIND1_LABEL.get(info["wind"], "Var1"),
            "w2": _KIND_WIND2_LABEL.get(info["wind"], "Var2"),
            "temp": _KIND_TEMP_LABEL.get(info["temp"], "Temperature"),
            "moist": _KIND_MOIST_LABEL.get(info["moist"], "Humidity")}

def _uv_from_dir_force(d, f):
    r = d * math.pi / 180.0
    return -f * math.sin(r), -f * math.cos(r)


def _theta_from_tp(T, P):
    return T * (_P0 / P) ** _RCP


def _td_to_rh(Td, T):
    a, b = 17.27, 237.7
    Tc, Tdc = T - 273.15, Td - 273.15
    es = 6.112 * math.exp(a * Tc / (b + Tc)) if Tc < 100 else 611.0
    e = 6.112 * math.exp(a * Tdc / (b + Tdc)) if Tdc < 100 else 611.0
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
    uploaded_file = st.file_uploader("Import a PRE_IDEA1.nam file", type=['nam', 'NAM', 'txt'])
    if uploaded_file is not None:
        raw = uploaded_file.getvalue()
        h = hash(raw)
        if st.session_state.get("upload_hash") != h:
            try:
                data = parser.parse_free_format(raw.decode("utf-8"))
                rt = data.get("radiosounding_type") or "CSTN"
                data["radiosounding_cstn"] = None
                data["radiosounding_rsou"] = None
                if data.get("radiosounding"):
                    data[f"radiosounding_{rt.lower()}"] = data["radiosounding"]
                st.session_state.free_format_data = data
                st.session_state.upload_hash = h
                st.session_state.radio_type = rt
                if rt == "RSOU" and "rsou_kind" in st.session_state and data.get("radiosounding", {}).get("kind"):
                    st.session_state.rsou_kind = data["radiosounding"]["kind"]
                if data.get("forcing") and data["forcing"]["ntimes"] > 0:
                    st.session_state.fc_idx = 0
                st.success(f"Loaded: {uploaded_file.name}")
            except Exception as e:
                st.error(f"Parsing error: {e}")
    elif st.session_state.get("upload_hash") is not None:
        st.session_state.free_format_data = make_default_data()
        st.session_state.upload_hash = None
        st.session_state.radio_type = "CSTN"
        st.rerun()

    d = st.session_state.free_format_data
    if st.button("✏️ Generate & Download", help="Note: if you came here from Namelist Editor or Workspace, the data are automatically populated in the namelist.", use_container_width=True):
        out = parser.write_free_format(d)
        st.download_button("⬇️ Download free-format text", out, file_name="free_format.txt", mime="text/plain")

data = st.session_state.free_format_data
tab1, tab2 = st.tabs(["Initial Radiosounding", "Idealized Forcings"])

with tab1:
    rt = st.radio("Type", ["CSTN", "RSOU"], index=0 if data["radiosounding_type"] == "CSTN" else 1,
                  horizontal=True, key="radio_type")
    if rt != data.get("radiosounding_type"):
        old_type = data.get("radiosounding_type")
        if old_type is not None and data.get("radiosounding") is not None:
            data[f"radiosounding_{old_type.lower()}"] = data["radiosounding"]
        data["radiosounding_type"] = rt
        saved = data.get(f"radiosounding_{rt.lower()}")
        if saved is not None:
            data["radiosounding"] = saved
        elif rt == "CSTN":
            data["radiosounding"] = {
                "date": {"year": 2000, "month": 1, "day": 1, "time": 0.0},
                "nlevels": 1, "ground_thv": 300.0, "ground_pressure": 100000.0,
                "heights": [0.0], "u": [0.0], "v": [0.0], "rh": [50.0], "brunt_vaisala": [0.01],
            }
        else:
            data["radiosounding"] = {
                "date": {"year": 2000, "month": 1, "day": 1, "time": 0.0},
                "kind": "STANDARD", "ground_height": 0.0, "ground_pressure": 100000.0,
                "ground_temperature": 300.0, "ground_humidity": 50.0,
                "nwind": 1,
                "wind_levels": [{"altitude": 85000.0, "var1": 0.0, "var2": 0.0}],
                "nmass": 2,
                "mass_levels": [{"altitude": 90000.0, "temperature": 290.0, "humidity": 50.0}],
            }
        st.rerun()

    rs = data["radiosounding"]

    if rt == "CSTN":
        col_l, col_r = st.columns([1, 1])
        with col_l:
            d = rs["date"]
            c1, c2, c3, c4 = st.columns(4)
            with c1: nd = st.number_input("Year", value=d["year"], key="cstn_yr")
            with c2: nm = st.number_input("Month", 1, 12, d["month"], key="cstn_mo")
            with c3: ndy = st.number_input("Day", 1, 31, d["day"], key="cstn_dy")
            with c4: nt = st.number_input("Time (s)", value=d["time"], format="%.1f", key="cstn_tm")
            rs["date"] = {"year": int(nd), "month": int(nm), "day": int(ndy), "time": float(nt)}

            cg1, cg2 = st.columns(2)
            with cg1: rs["ground_thv"] = st.number_input("Ground θᵥ (K)", value=rs["ground_thv"], format="%.4f", key="cstn_thv")
            with cg2: rs["ground_pressure"] = st.number_input("Ground P (Pa)", value=rs["ground_pressure"], format="%.1f", key="cstn_p0")

            n = rs["nlevels"]
            n_new = st.number_input("Levels", 1, 200, n, key="cstn_nl")

            if n_new != n:
                old = len(rs["heights"])
                for key in ("heights", "u", "v", "rh"):
                    arr = rs[key]
                    if n_new > old:
                        arr.extend([arr[-1] if arr else 0.0] * (n_new - old))
                    else:
                        rs[key] = arr[:n_new]
                bv = rs["brunt_vaisala"]
                bv_needed = n_new - 1 if n_new > 1 else 1
                if len(bv) > bv_needed:
                    rs["brunt_vaisala"] = bv[:bv_needed]
                else:
                    rs["brunt_vaisala"] = bv + [bv[-1] if bv else 0.01] * (bv_needed - len(bv))
                rs["nlevels"] = n_new
                st.rerun()

            df = pd.DataFrame({"Height (m)": rs["heights"], "u (m/s)": rs["u"], "v (m/s)": rs["v"], "RH (%)": rs["rh"]})
            edited = st.data_editor(df, num_rows="dynamic", key="cstn_df", width='stretch')
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
            bv_df = pd.DataFrame({"N² (s⁻²)": rs["brunt_vaisala"]})
            bv_edited = st.data_editor(bv_df, num_rows="dynamic", key="cstn_bv", width='stretch')
            rs["brunt_vaisala"] = bv_edited["N² (s⁻²)"].tolist()

        with col_r:
            h = rs["heights"]
            if h:
                mod = [math.sqrt(u**2 + v**2) for u, v in zip(rs["u"], rs["v"])]
                fig1 = make_wind_plot(h, rs["u"], rs["v"], mod)
                st.plotly_chart(fig1, width='stretch')

                thv = [rs["ground_thv"]]
                bv = rs["brunt_vaisala"]
                g = 9.81
                for i in range(min(len(bv), len(h) - 1)):
                    dz = h[i + 1] - h[i]
                    thv.append(thv[-1] * math.exp(bv[i] * dz / g))
                thv = thv[:len(h)]

                cr1, cr2 = st.columns(2)
                with cr1:
                    ft = go.Figure()
                    ft.add_trace(go.Scatter(x=thv, y=h, mode='lines+markers', name='θᵥ (K)'))
                    ft.update_layout(title="θᵥ (K)", xaxis_title='K', yaxis_title='Altitude (m)', height=350)
                    st.plotly_chart(ft, width='stretch')
                with cr2:
                    fh = go.Figure()
                    fh.add_trace(go.Scatter(x=rs["rh"], y=h, mode='lines+markers', name='RH (%)'))
                    fh.update_layout(title="RH (%)", xaxis_title='%', yaxis_title='Altitude (m)', height=350)
                    st.plotly_chart(fh, width='stretch')

    elif rt == "RSOU":
        lbl = kind_labels(rs["kind"])
        kind_opts = list(_RSOU_KINDS_MAP.keys())
        k_idx = kind_opts.index(rs.get("kind", "STANDARD")) if rs.get("kind") in kind_opts else 0
        col_k1, col_k2 = st.columns([3, 1])
        with col_k1: rs["kind"] = st.selectbox("Radiosounding kind", kind_opts, index=k_idx, key="rsou_kind", width=150)
        with col_k2:
            with st.popover("ℹ️"):
                st.markdown(_KIND_HELP_TEXT)
        lbl = kind_labels(rs["kind"])

        col_l, col_r = st.columns([1, 1])
        with col_l:
            d = rs["date"]
            c1, c2, c3, c4 = st.columns(4)
            with c1: nd = st.number_input("Year", value=d["year"], key="rsou_yr")
            with c2: nm = st.number_input("Month", 1, 12, d["month"], key="rsou_mo")
            with c3: ndy = st.number_input("Day", 1, 31, d["day"], key="rsou_dy")
            with c4: nt = st.number_input("Time (s)", value=d["time"], format="%.1f", key="rsou_tm")
            rs["date"] = {"year": int(nd), "month": int(nm), "day": int(ndy), "time": float(nt)}

            cg1, cg2, cg3, cg4 = st.columns(4)
            with cg1: rs["ground_height"] = st.number_input("Ground Z (m)", value=rs["ground_height"], format="%.2f", key="rsou_gh")
            with cg2: rs["ground_pressure"] = st.number_input("Ground P (Pa)", value=rs["ground_pressure"], format="%.1f", key="rsou_gp")
            with cg3: rs["ground_temperature"] = st.number_input(f"Ground {lbl['temp']}", value=rs["ground_temperature"], format="%.4f", key="rsou_gt")
            with cg4: rs["ground_humidity"] = st.number_input(f"Ground {lbl['moist']}", value=rs["ground_humidity"], format="%.4f", key="rsou_ghu")

            st.markdown("**Wind levels**")
            wdf = pd.DataFrame({"Altitude": [w["altitude"] for w in rs["wind_levels"]],
                                lbl["w1"]: [w["var1"] for w in rs["wind_levels"]],
                                lbl["w2"]: [w["var2"] for w in rs["wind_levels"]]})
            wedited = st.data_editor(wdf, num_rows="dynamic", key="wind_df", width='stretch')
            col_names = list(wedited.columns)
            rs["wind_levels"] = [{"altitude": r[0], "var1": r[1], "var2": r[2]} for r in wedited.to_numpy()]
            rs["nwind"] = len(rs["wind_levels"])

            st.markdown("**Mass levels**")
            mdata = {"Altitude": [m["altitude"] for m in rs["mass_levels"]],
                     lbl["temp"]: [m["temperature"] for m in rs["mass_levels"]],
                     lbl["moist"]: [m["humidity"] for m in rs["mass_levels"]]}
            if rs["mass_levels"] and "cloud" in rs["mass_levels"][0]:
                mdata["Cloud (kg/kg)"] = [m.get("cloud", 0.0) for m in rs["mass_levels"]]
            if rs["mass_levels"] and "ice" in rs["mass_levels"][0]:
                mdata["Ice (kg/kg)"] = [m.get("ice", 0.0) for m in rs["mass_levels"]]
            mdf = pd.DataFrame(mdata)
            medited = st.data_editor(mdf, num_rows="dynamic", key="mass_df", width='stretch')
            rs["mass_levels"] = []
            for r in medited.to_numpy():
                entry = {"altitude": float(r[0]), "temperature": float(r[1]), "humidity": float(r[2])}
                if len(r) > 3: entry["cloud"] = float(r[3])
                if len(r) > 4: entry["ice"] = float(r[4])
                rs["mass_levels"].append(entry)
            rs["nmass"] = len(rs["mass_levels"]) + 1

        with col_r:
            if rs["wind_levels"]:
                wa, uu, vv, mm = get_wind_data(rs)
                st.plotly_chart(make_wind_plot(wa, uu, vv, mm), width='stretch')
            if rs["mass_levels"]:
                ma, tt, rhh = get_mass_data(rs, rs["ground_pressure"])
                cr1, cr2 = st.columns(2)
                with cr1:
                    ft = go.Figure()
                    ft.add_trace(go.Scatter(x=tt, y=ma, mode='lines+markers', name=lbl["temp"]))
                    ft.update_layout(title=lbl["temp"], xaxis_title='Value', yaxis_title='Altitude', height=350)
                    st.plotly_chart(ft, width='stretch')
                with cr2:
                    fh = go.Figure()
                    fh.add_trace(go.Scatter(x=rhh, y=ma, mode='lines+markers', name=lbl["moist"]))
                    fh.update_layout(title=lbl["moist"], xaxis_title='Value', yaxis_title='Altitude', height=350)
                    st.plotly_chart(fh, width='stretch')

with tab2:
    ft = data.get("forcing_type")
    fc = data.get("forcing")
    if ft is None or fc is None:
        st.info("No forcing data available.")
        if st.button("➕ Create default forcing"):
            fc_entry = {"date": {"year": 2000, "month": 1, "day": 1, "time": 0.0},
                        "ground_height": 0.0, "ground_pressure": 100000.0,
                        "ground_theta": 300.0, "ground_humidity": 0.005,
                        "nlevels": 1,
                        "levels": [{"altitude": 85000.0, "u": 0.0, "v": 0.0, "theta": 300.0, "rv": 0.005, "w": 0.0,
                                    "dtheta_dt": 0.0, "drv_dt": 0.0, "du_dt": 0.0, "dv_dt": 0.0}]}
            data["forcing_type"] = "ZFRC"
            data["forcing"] = {"ntimes": 1, "forcings": [fc_entry], "sounding": None}
            st.rerun()
    else:
        ntimes = fc["ntimes"]

        if 'fc_idx' not in st.session_state:
            st.session_state.fc_idx = 0
        if 'fc_revision' not in st.session_state:
            st.session_state.fc_revision = 0

        fc_idx = st.selectbox("Time stamp", range(ntimes),
                              index=st.session_state.fc_idx,
                              format_func=lambda i: f"{i+1}: {fc['forcings'][i]['date']['year']}-{fc['forcings'][i]['date']['month']:02d}-{fc['forcings'][i]['date']['day']:02d} {fc['forcings'][i]['date']['time']}s",
                              key=f"fc_sel_{st.session_state.fc_revision}")
        st.session_state.fc_idx = fc_idx
        row_btn = st.columns([1, 1, 1], vertical_alignment="bottom")
        with row_btn[0]:
            if st.button("▲ Move up", key="fc_up", disabled=(fc_idx == 0)):
                fc["forcings"][fc_idx], fc["forcings"][fc_idx - 1] = fc["forcings"][fc_idx - 1], fc["forcings"][fc_idx]
                st.session_state.fc_idx = fc_idx - 1
                st.session_state.fc_revision += 1
                st.rerun()
        with row_btn[1]:
            if st.button("▼ Move down", key="fc_down", disabled=(fc_idx >= ntimes - 1)):
                fc["forcings"][fc_idx], fc["forcings"][fc_idx + 1] = fc["forcings"][fc_idx + 1], fc["forcings"][fc_idx]
                st.session_state.fc_idx = fc_idx + 1
                st.session_state.fc_revision += 1
                st.rerun()
        with row_btn[2]:
            c_sub = st.columns(2)
            with c_sub[0]:
                if st.button("➕ Add", key="fc_add"):
                    new_entry = {"date": {"year": 2000, "month": 1, "day": 1, "time": 0.0},
                                "ground_height": 0.0, "ground_pressure": 100000.0,
                                "ground_theta": 300.0, "ground_humidity": 0.005,
                                "nlevels": 1,
                                "levels": [{"altitude": 85000.0, "u": 0.0, "v": 0.0, "theta": 300.0, "rv": 0.005, "w": 0.0,
                                            "dtheta_dt": 0.0, "drv_dt": 0.0, "du_dt": 0.0, "dv_dt": 0.0}]}
                    fc["forcings"].append(new_entry)
                    fc["ntimes"] = len(fc["forcings"])
                    st.session_state.fc_idx = fc["ntimes"] - 1
                    st.session_state.fc_revision += 1
                    st.rerun()
            with c_sub[1]:
                if st.button("🗑️ Delete", key="fc_del", disabled=(ntimes <= 1)):
                    del fc["forcings"][fc_idx]
                    fc["ntimes"] = len(fc["forcings"])
                    if fc_idx >= fc["ntimes"]:
                        st.session_state.fc_idx = fc["ntimes"] - 1
                    st.session_state.fc_revision += 1
                    st.rerun()
        f_entry = fc["forcings"][fc_idx]

        d = f_entry["date"]
        c1, c2, c3, c4 = st.columns(4)
        with c1: nd = st.number_input("Year", value=d["year"], key=f"fc_yr_{fc_idx}")
        with c2: nm = st.number_input("Month", 1, 12, d["month"], key=f"fc_mo_{fc_idx}")
        with c3: ndy = st.number_input("Day", 1, 31, d["day"], key=f"fc_dy_{fc_idx}")
        with c4: nt = st.number_input("Time (s)", value=d["time"], format="%.1f", key=f"fc_tm_{fc_idx}")
        f_entry["date"] = {"year": int(nd), "month": int(nm), "day": int(ndy), "time": float(nt)}

        cg1, cg2, cg3, cg4 = st.columns(4)
        with cg1: f_entry["ground_height"] = st.number_input("Ground Z (m)", value=f_entry["ground_height"], format="%.2f", key=f"fc_gh_{fc_idx}")
        with cg2: f_entry["ground_pressure"] = st.number_input("Ground P (Pa)", value=f_entry["ground_pressure"], format="%.1f", key=f"fc_gp_{fc_idx}")
        with cg3: f_entry["ground_theta"] = st.number_input("Ground θ (K)", value=f_entry["ground_theta"], format="%.4f", key=f"fc_gt_{fc_idx}")
        with cg4: f_entry["ground_humidity"] = st.number_input("Ground rv (kg/kg)", value=f_entry["ground_humidity"], format="%.6f", key=f"fc_ghu_{fc_idx}")

        st.markdown("**Forcing levels**")
        f_df = pd.DataFrame({
            "Altitude": [l["altitude"] for l in f_entry["levels"]],
            "u (m/s)": [l["u"] for l in f_entry["levels"]],
            "v (m/s)": [l["v"] for l in f_entry["levels"]],
            "θ (K)": [l["theta"] for l in f_entry["levels"]],
            "rv (kg/kg)": [l["rv"] for l in f_entry["levels"]],
            "w (m/s)": [l["w"] for l in f_entry["levels"]],
            "dθ/dt (K/s)": [l["dtheta_dt"] for l in f_entry["levels"]],
            "drv/dt (1/s)": [l["drv_dt"] for l in f_entry["levels"]],
            "du/dt (m/s²)": [l["du_dt"] for l in f_entry["levels"]],
            "dv/dt (m/s²)": [l["dv_dt"] for l in f_entry["levels"]],
        })
        fedited = st.data_editor(f_df, num_rows="dynamic", key=f"frc_df_{fc_idx}", width='stretch')
        f_entry["levels"] = [
            {"altitude": r[0], "u": r[1], "v": r[2], "theta": r[3], "rv": r[4], "w": r[5],
             "dtheta_dt": r[6], "drv_dt": r[7], "du_dt": r[8], "dv_dt": r[9]}
            for r in fedited.to_numpy()
        ]
        f_entry["nlevels"] = len(f_entry["levels"])

        lvls = f_entry["levels"]
        if lvls:
            alt = [l["altitude"] for l in lvls]
            cw1, cw2, cw3, cw4 = st.columns(4)
            with cw1:
                st.plotly_chart(
                    make_forcing_plot(alt, [[l["u"], l["v"]] for l in lvls],
                                      ["u (m/s)", "v (m/s)"], "Wind (u, v)"),
                    width='stretch')
                st.plotly_chart(
                    make_forcing_plot(alt, [[l["dtheta_dt"]] for l in lvls],
                                      ["dθ/dt"], "Temperature Tendency (dθ/dt)"),
                    width='stretch')
            with cw2:
                st.plotly_chart(
                    make_forcing_plot(alt, [[l["w"]] for l in lvls],
                                      ["w (m/s)"], "Vertical velocity (w)"),
                    width='stretch')
                st.plotly_chart(
                    make_forcing_plot(alt, [[l["drv_dt"]] for l in lvls],
                                      ["drv/dt"], "Moisture Tendency (drv/dt)"),
                    width='stretch')           
            with cw3:
                st.plotly_chart(
                    make_forcing_plot(alt, [[l["rv"]] for l in lvls],
                                      ["rv (kg/kg)"], "Moisture (rv)"),
                    width='stretch')
                st.plotly_chart(
                    make_forcing_plot(alt, [[l["du_dt"]] for l in lvls],
                                      ["du/dt"], "Zonal Wind Tendency (du/dt)"),
                    width='stretch') 
            with cw4:
                st.plotly_chart(
                    make_forcing_plot(alt, [[l["theta"]] for l in lvls],
                                      ["θ (K)"], "Temperature (θ)"),
                    width='stretch')
                st.plotly_chart(
                    make_forcing_plot(alt, [[l["dv_dt"]] for l in lvls],
                                      ["dv/dt"], "Meridional Wind Tendency (dv/dt)"),
                    width='stretch') 

        if ntimes > 1:
            st.divider()
            st.markdown("**Hovmöller diagrams**")
            all_alts = [l["altitude"] for l in fc["forcings"][0]["levels"]]
            time_labels = [f"{fe['date']['year']}-{fe['date']['month']:02d}-{fe['date']['day']:02d} {fe['date']['time']}s"
                           for fe in fc["forcings"]]
            hov_vars = [
                ("u (m/s)", "u"), ("v (m/s)", "v"), ("w (m/s)", "w"),
                ("rv (kg/kg)", "rv"), ("θ (K)", "theta"),
                ("dθ/dt (K/s)", "dtheta_dt"), ("drv/dt (1/s)", "drv_dt"),
                ("du/dt (m/s²)", "du_dt"), ("dv/dt (m/s²)", "dv_dt"),
            ]
            for i in range(0, len(hov_vars), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(hov_vars):
                        label, key = hov_vars[i + j]
                        z = [[l[key] for l in fe["levels"]] for fe in fc["forcings"]]
                        z_t = list(zip(*z))
                        fig = go.Figure(data=go.Contour(z=z_t, x=time_labels, y=all_alts,
                                                        contours=dict(coloring="fill")))
                        fig.update_layout(title=label, xaxis_title="Time", yaxis_title="Altitude",
                                         height=400)
                        with cols[j]:
                            st.plotly_chart(fig, width='stretch')

        if fc.get("sounding"):
            st.markdown("**Sounding (PFRC)**")
            s_df = pd.DataFrame({
                "Pressure (Pa)": [s["pressure"] for s in fc["sounding"]["levels"]],
                "θ (K)": [s["theta"] for s in fc["sounding"]["levels"]],
                "rv (kg/kg)": [s["rv"] for s in fc["sounding"]["levels"]],
            })
            sedited = st.data_editor(s_df, num_rows="dynamic", key="sounding_df", width='stretch')
            fc["sounding"]["levels"] = [{"pressure": r[0], "theta": r[1], "rv": r[2]} for r in sedited.to_numpy()]
            fc["sounding"]["nlevels"] = len(fc["sounding"]["levels"])

import streamlit as st
import xarray as xr
import plotly.graph_objects as go
import numpy as np
import tempfile
import os

PLOTLY_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                 '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

st.set_page_config(page_title="Quick Plots", layout="wide")

# --- Session State Initialization ---
if 'datasets_dict' not in st.session_state:
    st.session_state.datasets_dict = {}
if 'panels' not in st.session_state:
    st.session_state.panels = []
    st.session_state.next_panel_id = 0
if 'target_panel_id' not in st.session_state:
    st.session_state.target_panel_id = None 
if 'new_panel_pos' not in st.session_state:
    st.session_state.new_panel_pos = 0
if 'target_panel_selector' not in st.session_state:
    st.session_state.target_panel_selector = "➕ Create New Panel"
if 'workspace_path' not in st.session_state:
    st.session_state.workspace_path = ""
if 'workspace_nc_files' not in st.session_state:
    st.session_state.workspace_nc_files = {}

# --- Helper Functions ---

def scan_nc_files(workspace_path):
    """Scans directory for .nc files and builds a file dictionary."""
    nc_files = {}
    if not os.path.exists(workspace_path):
        return {}
    
    for root, dirs, files in os.walk(workspace_path):
        for file in files:
            if file.endswith('.nc'):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, workspace_path)
                
                if file not in nc_files:
                    nc_files[file] = []
                nc_files[file].append({
                    'path': full_path,
                    'relative': rel_path
                })
    return nc_files

def load_nc_from_path(full_path, filename):
    try:
        ds = xr.open_dataset(full_path)
        # Calculate relative path if a workspace is active
        workspace = st.session_state.workspace_path
        rel_path = os.path.relpath(full_path, workspace) if workspace and os.path.isdir(workspace) else None
        
        st.session_state.datasets_dict[filename] = {
            "ds": ds, 
            "temp_path": full_path,
            "original_name": filename,
            "rel_path": rel_path  # Store the relative path here
        }
        st.success(f"Loaded: {filename}")
    except Exception as e:
        st.error(f"Error loading {filename}: {e}")


def add_trace_to_panel_callback(filename, varname, new_pos):
    panel_options = {f"Panel {p['id']}": p['id'] for p in st.session_state.panels}
    panel_options["➕ Create New Panel"] = "new"
    
    current_selection = st.session_state.target_panel_selector
    target_id = panel_options.get(current_selection, "new")
    
    if target_id == "new":
        new_id = st.session_state.next_panel_id
        st.session_state.next_panel_id += 1
        st.session_state.panels.insert(int(new_pos), {
            "id": new_id, "traces": [],
            "show_config": False,
            "colorscale": "Viridis",
            "invert_cmap": False,
            "z_min": None,
            "z_max": None
        })
        target_id = new_id
    
    panel_to_update = next((p for p in st.session_state.panels if p["id"] == target_id), None)
    
    if panel_to_update is not None:
        panel_to_update["traces"].append((filename, varname, PLOTLY_COLORS[len(panel_to_update["traces"]) % len(PLOTLY_COLORS)]))
        st.session_state.target_panel_selector = "➕ Create New Panel"
    else:
        st.error("Target panel not found.")

def delete_panel(panel_id):
    st.session_state.panels = [p for p in st.session_state.panels if p["id"] != panel_id]
    st.rerun()

# --- Sidebar: File Upload & Configuration ---
with st.sidebar:
    st.header("Data")
    
    # --- PART A: File Uploader ---
    uploaded_files = st.file_uploader(
        "Import netCDF files", 
        type=['nc', 'netcdf'], 
        accept_multiple_files=True
    )

    # File Processing Logic (Uploaded)
    current_uploaded_names = []
    if uploaded_files:
        for uploaded_file in uploaded_files:
            current_uploaded_names.append(uploaded_file.name)
            if uploaded_file.name not in st.session_state.datasets_dict:
                try:
                    raw = uploaded_file.getvalue()
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.nc')
                    tmp.write(raw)
                    tmp.close()
                    ds = xr.open_dataset(tmp.name)
                    st.session_state.datasets_dict[uploaded_file.name] = {
                        "ds": ds, 
                        "temp_path": tmp.name,
                        "original_name": uploaded_file.name
                    }
                except Exception as e:
                    st.error(f"Error loading {uploaded_file.name}: {e}")

        # Cleanup deleted files
        files_to_remove = [f for f in st.session_state.datasets_dict if f not in current_uploaded_names and f not in st.session_state.workspace_nc_files]
        for f in files_to_remove:
            path = st.session_state.datasets_dict[f]["temp_path"]
            if os.path.exists(path): os.unlink(path)
            del st.session_state.datasets_dict[f]
        if files_to_remove: st.rerun()
    workspace_input = st.text_input("or load from workspace path", value=st.session_state.workspace_path, key="ws_path_input")
    
    if st.button("🔍 Load Workspace"):
        if os.path.isdir(workspace_input):
            st.session_state.workspace_path = workspace_input
            st.session_state.workspace_nc_files = scan_nc_files(workspace_input)
            st.success(f"Found {len(st.session_state.workspace_nc_files)} .nc files")
        else:
            st.error("Invalid directory")

    if st.session_state.workspace_nc_files:
        # Build Tree structure for view
        tree = {}
        for file_name, file_list in st.session_state.workspace_nc_files.items():
            for f in file_list:
                parts = f['relative'].split(os.sep)
                current = tree
                for part in parts[:-1]:
                    if part not in current: current[part] = {}
                    current = current[part]
                if parts[-1] not in current: current[parts[-1]] = f['path']
                else: current[parts[-1]] = f['path'] # Handle same name in same folder

        def render_tree(subtree, prefix="", indent=0):
            for name in sorted(subtree.keys()):
                path_key = f"{prefix}/{name}" if prefix else name
                content = subtree[name]
                spacer = "&nbsp;&nbsp;&nbsp;&nbsp;" * indent
                
                if isinstance(content, dict):
                    if st.checkbox(f"{spacer}📁 {name}", key=f"tree_dir_{path_key}"):
                        render_tree(content, path_key, indent + 1)
                else:
                    # Content is the absolute path
                    if st.button(f"{spacer}📄 {name}", key=f"tree_file_{path_key}"):
                        load_nc_from_path(content, name)
                        st.rerun()

        with st.expander("📁 Workspace Tree", expanded=True):
            render_tree(tree)

    st.divider()
    st.header("Plots layout")
    col1, col2 = st.columns([1, 1])
    with col1:
        grid_rows = st.number_input("Grid Rows", min_value=1, value=2)
    with col2:
        grid_cols = st.number_input("Grid Columns", min_value=1, value=2)
    col1, col2 = st.columns([1, 1])
    with col1:
        panel_options = {f"Panel {p['id']}": p['id'] for p in st.session_state.panels}
        panel_options["➕ Create New Panel"] = "new"
        st.selectbox("Target Panel", options=list(panel_options.keys()), key="target_panel_selector")
        current_target_id = panel_options.get(st.session_state.target_panel_selector, "new")
    if current_target_id == "new":
        with col2:
            st.session_state.new_panel_pos = st.number_input("Insert at Index", min_value=0, max_value=len(st.session_state.panels), value=len(st.session_state.panels))
    var_cols = st.slider("Variable columns", min_value=1, max_value=6, value=4)
    if st.button("Clear All Plots"):
        st.session_state.panels = []
        st.session_state.next_panel_id = 0
        st.rerun()

# --- Main UI  ---
col_left, col_right = st.columns([1, 3])

with col_left:
    st.markdown("### Variables")
    if st.session_state.datasets_dict:
        tab_titles = sorted(list(st.session_state.datasets_dict.keys()))
        tabs = st.tabs(tab_titles)

        for i, tab_name in enumerate(tab_titles):
            with tabs[i]:
                file_info = st.session_state.datasets_dict[tab_name]
                rel = file_info.get('rel_path')
                display_name = f"{file_info['original_name']} ({rel})" if rel else file_info['original_name']
                st.caption(f"📄 {display_name}")
                ds_context = file_info["ds"]

                # Collect dimension signatures
                dim_groups = {}
                for vn in ds_context.data_vars:
                    var = ds_context[vn]
                    sig = "(" + ", ".join(f"{d}: {var.sizes[d]}" for d in var.dims) + ")"
                    dim_groups.setdefault(sig, []).append(vn)

                all_sigs = sorted(dim_groups.keys())

                scroll_container = st.container(height=700)
                with scroll_container:
                    for sig in all_sigs:
                        with st.expander(f"{sig} — {len(dim_groups[sig])} vars", expanded=False):
                            vns = sorted(dim_groups[sig])
                            for idx in range(0, len(vns), var_cols):
                                row = st.columns(var_cols)
                                for j in range(var_cols):
                                    if idx + j < len(vns):
                                        vn = vns[idx + j]
                                        var = ds_context[vn]
                                        dims_str = ", ".join(f"{d}: {var.sizes[d]}" for d in var.dims)
                                        var = ds_context[vn]

                                        # 1. Build the dimension string (e.g., "lat(100), lon(200)")
                                        dim_info = ", ".join([f"{d}({var.sizes[d]})" for d in var.dims])
                                        # 2. Build the attribute string (e.g., "units: m/s, long_name: wind_speed")
                                        attr_list = []
                                        for k, v in var.attrs.items():
                                            # We cast v to str to handle non-string metadata safely
                                            attr_list.append(f"{k}: {v}")
                                        attr_info = "; ".join(attr_list) if attr_list else ""
                                        tooltip_str = f"{attr_info} |\n Dimensions: {dim_info}"

                                        with row[j]:
                                            st.button(
                                                vn,
                                                key=f"btn_{tab_name}_{sig}_{vn}",
                                                use_container_width=True,
                                                help=tooltip_str,
                                                on_click=add_trace_to_panel_callback,
                                                args=(tab_name, vn, st.session_state.new_panel_pos)
                                            )
    else:
        st.info("Upload or Load a file to begin")

with col_right:
    if not st.session_state.panels:
        st.info("No plots active. Select a variable and click to add to a panel.")
    else:
        for r in range(grid_rows):
            cols = st.columns(grid_cols)
            for c in range(grid_cols):
                idx = r * grid_cols + c
                if idx < len(st.session_state.panels):
                    with cols[c]:
                        panel = st.session_state.panels[idx]
                        names_in_panel = [t[1] for t in panel['traces']]
                        names_str = ", ".join(names_in_panel)
                        title_suffix = f" - {names_str}" if names_in_panel else ""
                        p_col1, p_col2, p_col3 = st.columns([0.6, 0.1, 0.1])
                        p_col1.markdown(f"**Panel {panel['id']}{title_suffix}**")
                        if p_col2.button("🎨", key=f"gear_panel_{panel['id']}"):
                            panel['show_config'] = not panel['show_config']
                            st.rerun()
                        if p_col3.button("🗑️", key=f"del_panel_{panel['id']}"):
                            delete_panel(panel['id'])
                            st.rerun()

                        if panel['show_config']:
                            # Check if any trace in this panel is a heatmap (dims >= 2)
                            has_heatmap_trace = False
                            for f_name, v_name, _ in panel['traces']:
                                if f_name in st.session_state.datasets_dict:
                                    if len(st.session_state.datasets_dict[f_name]["ds"][v_name].dims) >= 2:
                                        has_heatmap_trace = True
                                        break
                            
                            if has_heatmap_trace:
                                with st.expander("Colormap Range", expanded=True):
                                    # Use panel values as the source for the widget
                                    # We use a default 0.0/1.0 if the value is None to prevent errors
                                    z_min_val = float(panel.get('z_min') if panel.get('z_min') is not None else 0.0)
                                    z_max_val = float(panel.get('z_max') if panel.get('z_max') is not None else 1.0)
                                    
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        new_z_min = st.number_input("Min", value=z_min_val, key=f"zmin_ui_{panel['id']}", format="%.8f")
                                    with col2:
                                        new_z_max = st.number_input("Max", value=z_max_val, key=f"zmax_ui_{panel['id']}", format="%.8f")
                                    
                                    # Sync the widget back to the panel state
                                    panel['z_min'] = new_z_min
                                    panel['z_max'] = new_z_max

                            with st.expander("Color", expanded=True):
                                col_cs, col_inv = st.columns([0.7, 0.3])
                                with col_cs:
                                    cs = st.selectbox(
                                        "Colorscale",
                                        options=["Viridis", "Plasma", "Inferno", "Magma",
                                                 "Greys", "YlGnBu", "Greens", "YlOrRd", "Bluered", "RdBu",
                                                 "Reds", "Blues", "Picnic", "Rainbow", "Portland", "Jet",
                                                 "Hot", "Blackbody", "Earth", "Electric",
                                                 "RdYlBu", "RdYlGn", "Spectral", "Coolwarm", "PiYG",
                                                 "PRGn", "BrBG", "PuOr", "RdGy",
                                                 "Twilight", "HSV"],
                                        index=["Viridis", "Plasma", "Inferno", "Magma",
                                               "Greys", "YlGnBu", "Greens", "YlOrRd", "Bluered", "RdBu",
                                               "Reds", "Blues", "Picnic", "Rainbow", "Portland", "Jet",
                                               "Hot", "Blackbody", "Earth", "Electric",
                                               "RdYlBu", "RdYlGn", "Spectral", "Coolwarm", "PiYG",
                                               "PRGn", "BrBG", "PuOr", "RdGy",
                                               "Twilight", "HSV"].index(
                                            panel.get("colorscale", "Viridis")),
                                        key=f"cs_sel_{panel['id']}",
                                        format_func=lambda x: x
                                    )
                                    panel["colorscale"] = cs
                                with col_inv:
                                    inv = st.checkbox("🔄 Invert", value=panel.get("invert_cmap", False),
                                                      key=f"inv_cb_{panel['id']}")
                                    panel["invert_cmap"] = inv
                                for ti, (tfname, tvname, tcolor) in enumerate(panel["traces"]):
                                    new_color = st.color_picker(
                                        f"{tvname}",
                                        value=tcolor,
                                        key=f"trace_color_{panel['id']}_{ti}"
                                    )
                                    panel["traces"][ti] = (tfname, tvname, new_color)

                        colorscale = panel.get("colorscale", "Viridis")
                        if panel.get("invert_cmap", False):
                            colorscale = colorscale + "_r"

                        if panel['traces']:
                            fig = go.Figure()
                            has_data = False
                            for fname, vname, trace_color in panel['traces']:
                                if fname in st.session_state.datasets_dict:
                                    try:
                                        ds = st.session_state.datasets_dict[fname]["ds"]
                                        var = ds[vname]
                                        dims = var.dims

                                        # Detect time dimension (any dim whose name contains 'time')
                                        time_dim = None
                                        for d in dims:
                                            if 'time' in d.lower():
                                                time_dim = d
                                                break

                                        if len(dims) == 1:
                                            fig.add_trace(go.Scatter(
                                                x=var.coords[dims[0]].values,
                                                y=var.values,
                                                mode='lines',
                                                name=f"{fname}:{vname}",
                                                line=dict(color=trace_color)
                                            ))
                                            has_data = True
                                        else:
                                            # Heatmap logic
                                            has_time = time_dim is not None and var.sizes[time_dim] > 1
                                            if has_time and len(dims) >= 2:
                                                other_dims = [d for d in dims if d != time_dim]
                                                slice_data = var
                                                for d in other_dims[1:]:
                                                    slice_data = slice_data.isel({d: 0})
                                                dims_list = list(slice_data.dims)
                                                time_pos = dims_list.index(time_dim)
                                                other_pos = dims_list.index(other_dims[0])
                                                z_data = np.transpose(slice_data.values, axes=(other_pos, time_pos))
                                                x_coord = slice_data.coords[time_dim].values
                                                y_coord = slice_data.coords[other_dims[0]].values
                                            else:
                                                slice_data = var
                                                for d in dims[2:]:
                                                    slice_data = slice_data.isel({d: 0})
                                                if len(slice_data.dims) > 2:
                                                    slice_data = slice_data.isel({slice_data.dims[2]: 0})
                                                z_data = slice_data.values
                                                x_coord = slice_data.coords[slice_data.dims[1]].values if len(slice_data.dims) > 1 else None
                                                y_coord = slice_data.coords[slice_data.dims[0]].values if len(slice_data.dims) > 0 else None
                                            heatmap_kwargs = {
                                            "z": z_data, 
                                            "x": x_coord, 
                                            "y": y_coord,
                                            "colorscale": colorscale,
                                            "name": f"{fname}:{vname}"
                                            }
                                            panel['z_min'] = slice_data.values.min() if panel.get('z_min') is None else panel['z_min']
                                            panel['z_max'] = slice_data.values.max() if panel.get('z_max') is None else panel['z_max']

                                            # Apply zmin/zmax if they have been set in the panel
                                            if panel.get('z_min') is not None:
                                                heatmap_kwargs["zmin"] = panel['z_min']
                                            if panel.get('z_max') is not None:
                                                heatmap_kwargs["zmax"] = panel['z_max']
                                            
                                            fig.add_trace(go.Heatmap(**heatmap_kwargs))
                                            has_data = True
                                    except:
                                        pass
                            if has_data:
                                fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=10), showlegend=True)
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.caption("No compatible data")
                        else:
                            st.caption("Empty Panel")
                else: st.write("")

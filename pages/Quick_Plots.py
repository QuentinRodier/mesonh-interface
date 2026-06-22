import streamlit as st
import xarray as xr
import plotly.graph_objects as go
import numpy as np
import tempfile
import os
import netCDF4 as nc

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
if 'log_scale' not in st.session_state:
    st.session_state.log_scale = False
if 'target_panel_selector' not in st.session_state:
    st.session_state.target_panel_selector = "➕ Create New Panel"
if 'workspace_path' not in st.session_state:
    st.session_state.workspace_path = ""
if 'workspace_nc_files' not in st.session_state:
    st.session_state.workspace_nc_files = {}
if 'var_layout_weight' not in st.session_state:
    st.session_state.var_layout_weight = 1
if 'var_layout_height' not in st.session_state:
    st.session_state.var_layout_height = 400
if 'plots_layout_height' not in st.session_state:
    st.session_state.plots_layout_height = 300
if 'layout_mode' not in st.session_state:
    st.session_state.layout_mode = "Variables on top"
if 'raw_mode' not in st.session_state:
    st.session_state.raw_mode = False
if 'sync_colormap' not in st.session_state:
    st.session_state.sync_colormap = False
if 'sync_colorscale' not in st.session_state:
    st.session_state.sync_colorscale = "Viridis"
if 'sync_invert_cmap' not in st.session_state:
    st.session_state.sync_invert_cmap = False
if 'sync_z_min' not in st.session_state:
    st.session_state.sync_z_min = None
if 'sync_z_max' not in st.session_state:
    st.session_state.sync_z_max = None
# --- Helper Functions ---

def discover_groups(filepath):
    """Return sorted list of all group paths in a netCDF file.
    Root group is represented as empty string ''."""
    def _walk(parent, current_path):
        paths = [current_path]
        for name in parent.groups.keys():
            child = parent.groups[name]
            child_path = f"{current_path}/{name}" if current_path else name
            paths.extend(_walk(child, child_path))
        return paths
    with nc.Dataset(filepath, 'r') as root:
        return sorted(_walk(root, ""))

def open_dataset_with_groups(filepath):
    """Open a netCDF file and return (root_ds, ds_dict, groups, var_to_group).
    
    - ds_dict maps group path -> xr.Dataset ('' for root)
    - groups: list of group paths
    - var_to_group: maps qualified_name -> (group_path, short_name)
    """
    groups = discover_groups(filepath)
    ds_dict = {}
    for gp in groups:
        ds_dict[gp] = xr.open_dataset(filepath, group=gp) if gp else xr.open_dataset(filepath)
    
    var_to_group = {}
    for gp in groups:
        gds = ds_dict[gp]
        for vn in gds.data_vars:
            qualified = vn if not gp else f"{gp}/{vn}"
            var_to_group[qualified] = (gp, vn)
            # Use where to replace sentinel values with NaN
            gds[vn] = gds[vn].where((gds[vn] != 999) & (gds[vn] != 1e20))
    
    return ds_dict[""], ds_dict, groups, var_to_group

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

def load_nc_from_path(full_path, file_key, display_name=None):
    try:
        ds, ds_dict, groups, var_to_group = open_dataset_with_groups(full_path)
        # Calculate relative path if a workspace is active
        workspace = st.session_state.workspace_path
        rel_path = os.path.relpath(full_path, workspace) if workspace and os.path.isdir(workspace) else None
        
        if display_name is None:
            display_name = os.path.basename(full_path)
        
        # Ensure unique key
        unique_key = file_key
        if unique_key in st.session_state.datasets_dict:
            counter = 1
            while f"{file_key}_{counter}" in st.session_state.datasets_dict:
                counter += 1
            unique_key = f"{file_key}_{counter}"
        
        st.session_state.datasets_dict[unique_key] = {
            "ds": ds, 
            "ds_dict": ds_dict,
            "groups": groups,
            "var_to_group": var_to_group,
            "temp_path": full_path,
            "original_name": display_name,
            "rel_path": rel_path
        }
       
        st.success(f"Loaded: {display_name}")
    except Exception as e:
        st.error(f"Error loading {file_key}: {e}")


def compute_spectrum(data, axis_names, dx_coords=None):
    """Compute energy spectrum along given axis names.
    
    Parameters
    ----------
    data : np.ndarray
        1D/2D array (already sliced and averaged over non-selected dims)
    axis_names : list of str
        ['ni'] for 1D or ['ni', 'nj'] for 2D
    dx_coords : dict or None
        Mapping axis_name -> 1D coord array for wavelength computation
    
    Returns
    -------
    wavelengths : np.ndarray
    energies : np.ndarray
    """
    if len(axis_names) == 1:
        ax_idx = 0  # last axis after transpose
        n = data.shape[ax_idx]
        fft_vals = np.fft.rfft(data, axis=ax_idx)
        energy = np.abs(fft_vals)**2
        # Average over realizations (other dims)
        other_axes = tuple(i for i in range(data.ndim) if i != ax_idx)
        if other_axes:
            # Average over remaining dimensions, then squeeze
            energy = np.mean(energy, axis=other_axes)
        energy = np.squeeze(energy)
        dx = 1.0
        if dx_coords and axis_names[0] in dx_coords:
            dx = np.abs(np.diff(dx_coords[axis_names[0]])).mean()
        freqs = np.fft.rfftfreq(n, d=dx)
        pos = freqs > 0
        wavelengths = 1.0 / freqs[pos]
        return wavelengths, energy[pos]
    
    elif len(axis_names) == 2:
        ny, nx = data.shape[-2], data.shape[-1]
        fft2 = np.fft.rfft2(data)
        energy2d = np.abs(fft2)**2
        other_axes = tuple(i for i in range(data.ndim - 2))
        if other_axes:
            energy2d = np.mean(energy2d, axis=other_axes)
        energy2d = np.squeeze(energy2d)
        
        dx = 1.0
        dy = 1.0
        if dx_coords and axis_names[1] in dx_coords:
            dx = np.abs(np.diff(dx_coords[axis_names[1]])).mean()
        if dx_coords and axis_names[0] in dx_coords:
            dy = np.abs(np.diff(dx_coords[axis_names[0]])).mean()
        
        kx = np.fft.rfftfreq(nx, d=dx)
        ky = np.fft.fftfreq(ny, d=dy)
        kx_grid, ky_grid = np.meshgrid(kx, ky)
        k_mag = np.sqrt(kx_grid**2 + ky_grid**2)
        
        # Bin energy by k_mag
        k_max = k_mag.max()
        n_bins = min(ny, nx) // 2
        k_bins = np.linspace(0, k_max, n_bins + 1)
        k_centers = 0.5 * (k_bins[1:] + k_bins[:-1])
        energy_1d = np.zeros(n_bins)
        for i in range(n_bins):
            mask = (k_mag >= k_bins[i]) & (k_mag < k_bins[i + 1])
            if mask.any():
                energy_1d[i] = np.mean(energy2d[mask])
        
        pos = k_centers > 0
        wavelengths = np.where(pos, 1.0 / k_centers, np.nan)
        return wavelengths[pos], energy_1d[pos]


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
            "show_slice": False,
            "slice_configs": {},
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
        accept_multiple_files=True,
        max_upload_size=2000
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
                    ds, ds_dict, groups, var_to_group = open_dataset_with_groups(tmp.name)
                    st.session_state.datasets_dict[uploaded_file.name] = {
                        "ds": ds, 
                        "ds_dict": ds_dict,
                        "groups": groups,
                        "var_to_group": var_to_group,
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
                current[parts[-1]] = f

        def render_tree(subtree, prefix="", indent=0):
            for name in sorted(subtree.keys()):
                path_key = f"{prefix}/{name}" if prefix else name
                content = subtree[name]
                spacer = "&nbsp;&nbsp;&nbsp;&nbsp;" * indent
                
                if isinstance(content, dict) and 'path' not in content:
                    if st.checkbox(f"{spacer}📁 {name}", key=f"tree_dir_{path_key}"):
                        render_tree(content, path_key, indent + 1)
                else:
                    file_path = content['path']
                    file_key = content['relative']
                    if st.button(f"{spacer}📄 {name}", key=f"tree_file_{path_key}"):
                        load_nc_from_path(file_path, file_key, display_name=name)
                        st.rerun()

        with st.expander("📁 Workspace Tree", expanded=True):
            render_tree(tree)

    st.divider()
    st.header("Plots layout")
    col1, col2 = st.columns([1, 1])
    with col1:
        grid_rows = st.number_input("Grid Rows", min_value=1, value=20)
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
    
    if st.button("Clear All Plots"):
        st.session_state.panels = []
        st.session_state.next_panel_id = 0
        st.rerun()
    
    st.session_state.plots_layout_height = st.slider("Graphs Height", min_value=100, max_value=2000, value=st.session_state.plots_layout_height)

    st.divider()
    st.header("Variables layout")
    var_cols = st.slider("Number of columns-variables", min_value=1, max_value=10, value=6)
    st.session_state.layout_mode = st.radio("Position", ["Side by side", "Variables on top"], index=0 if st.session_state.layout_mode == "Side by side" else 1)
    st.session_state.var_layout_weight = st.slider("Width (if side by side)", min_value=1, max_value=5, value=st.session_state.var_layout_weight)
    st.session_state.var_layout_height = st.slider("Height", min_value=100, max_value=2000, value=st.session_state.var_layout_height)

    st.divider()
    st.header("Colormap Sync")
    st.session_state.sync_colormap = st.checkbox(
        "Sync colormap & range across all panels",
        value=st.session_state.sync_colormap,
        key="sync_cmap_cb"
    )
    if st.session_state.sync_colormap:
        st.session_state.sync_colorscale = st.selectbox(
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
                st.session_state.sync_colorscale
            ),
            key="sync_cs_sel",
            format_func=lambda x: x
        )
        st.session_state.sync_invert_cmap = st.checkbox(
            "Invert",
            value=st.session_state.sync_invert_cmap,
            key="sync_inv_cb"
        )
        col_z1, col_z2 = st.columns(2)
        with col_z1:
            z_min_sync_val = st.session_state.sync_z_min if st.session_state.sync_z_min is not None else 0.0
            new_z_min_sync = st.number_input("Z min", value=z_min_sync_val, format="%.6f", key="sync_zmin_inp")
            st.session_state.sync_z_min = new_z_min_sync
        with col_z2:
            z_max_sync_val = st.session_state.sync_z_max if st.session_state.sync_z_max is not None else 1.0
            new_z_max_sync = st.number_input("Z max", value=z_max_sync_val, format="%.6f", key="sync_zmax_inp")
            st.session_state.sync_z_max = new_z_max_sync

# --- Main UI  ---
_var_w = st.session_state.var_layout_weight
if st.session_state.layout_mode == "Side by side":
    col_left, col_right = st.columns([_var_w, 4])
else:
    col_left = st.container()
    col_right = st.container()

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
                ds_dict = file_info.get("ds_dict", {"": ds_context})
                groups = file_info.get("groups", [""])

                # Build hierarchical group tree from flat group paths
                group_tree = {}
                for gp in groups:
                    if not gp:
                        continue
                    parts = gp.split('/')
                    node = group_tree
                    for part in parts:
                        if part not in node:
                            node[part] = {}
                        node = node[part]

                def render_group_vars(group_ds, group_path):
                    if not group_ds or not group_ds.data_vars:
                        return
                    dim_groups = {}
                    for vn in group_ds.data_vars:
                        var = group_ds[vn]
                        ndim = len(var.dims)
                        sig = f"{ndim}D"
                        dim_groups.setdefault(sig, []).append(vn)
                    for sig in sorted(dim_groups.keys()):
                        with st.expander(f"{sig} — {len(dim_groups[sig])} vars", expanded=False):
                            vns = sorted(dim_groups[sig])
                            for idx in range(0, len(vns), var_cols):
                                row = st.columns(var_cols)
                                for j in range(var_cols):
                                    if idx + j < len(vns):
                                        vn = vns[idx + j]
                                        qualified_vn = vn if not group_path else f"{group_path}/{vn}"
                                        var = group_ds[vn]
                                        dim_info = ", ".join([f"{d}({var.sizes[d]})" for d in var.dims])
                                        attr_list = []
                                        for k, v in var.attrs.items():
                                            attr_list.append(f"{k}: {v}")
                                        attr_info = "; ".join(attr_list) if attr_list else ""
                                        tooltip_str = f"{attr_info} |\n Dimensions: {dim_info}"
                                        with row[j]:
                                            st.button(
                                                vn,
                                                key=f"btn_{tab_name}_{sig}_{group_path}_{vn}",
                                                use_container_width=True,
                                                help=tooltip_str,
                                                on_click=add_trace_to_panel_callback,
                                                args=(tab_name, qualified_vn, st.session_state.new_panel_pos)
                                            )

                def render_group_tree(subtree, parent_path):
                    for name in sorted(subtree.keys()):
                        # Flatten chains where a group has no data vars and exactly one child
                        path_parts = [name]
                        cur_subtree = subtree[name]
                        cur_path = f"{parent_path}/{name}" if parent_path else name
                        while True:
                            cur_ds = ds_dict.get(cur_path)
                            has_vars = cur_ds is not None and bool(cur_ds.data_vars)
                            if has_vars or len(cur_subtree) != 1:
                                break
                            only_name = next(iter(cur_subtree))
                            path_parts.append(only_name)
                            cur_path = f"{cur_path}/{only_name}"
                            cur_subtree = cur_subtree[only_name]
                        label = f"📁 {'/'.join(path_parts)}"
                        with st.expander(label, expanded=False):
                            render_group_vars(ds_dict.get(cur_path), cur_path)
                            render_group_tree(cur_subtree, cur_path)

                scroll_container = st.container(height=st.session_state.var_layout_height)
                with scroll_container:
                    render_group_vars(ds_context, "")
                    if group_tree:
                        render_group_tree(group_tree, "")
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
                        p_col1, p_col2, p_col3, p_col4, p_col5, p_col6, p_col7, p_col8 = st.columns([0.15, 0.08, 0.08, 0.1, 0.07, 0.07, 0.15, 0.08])
                        p_col1.markdown(f"**Panel {panel['id']}{title_suffix}**")
                        if p_col2.button("🎨", key=f"gear_panel_{panel['id']}"):
                            panel['show_config'] = not panel['show_config']
                            st.rerun()
                        if p_col3.button("Axes", key=f"slice_panel_{panel['id']}"):
                            panel['show_slice'] = not panel['show_slice']
                            st.rerun()
                        if p_col4.button("Range", key=f"range_panel_{panel['id']}"):
                            panel['show_range'] = not panel.get('show_range', False)
                            st.rerun()
                        if p_col5.button("Raw", key=f"raw_panel_{panel['id']}"):
                            st.session_state.raw_mode = not st.session_state.raw_mode
                            st.rerun()
                        if p_col6.button("Log", key=f"log_panel_{panel['id']}"):
                            st.session_state.log_scale = not st.session_state.log_scale
                            st.rerun()
                        if p_col7.button("Spectra", key=f"spectra_panel_{panel['id']}"):
                            panel['show_spectra'] = not panel.get('show_spectra', False)
                            st.rerun()
                        if p_col8.button("🗑️", key=f"del_panel_{panel['id']}"):
                            delete_panel(panel['id'])
                            st.rerun()

                        if panel['show_config']:
                            # Check if any trace in this panel is a heatmap (dims >= 2)
                            has_heatmap_trace = False
                            for f_name, v_name, _ in panel['traces']:
                                if f_name in st.session_state.datasets_dict:
                                    fi = st.session_state.datasets_dict[f_name]
                                    ds_dict = fi.get("ds_dict", {"": fi["ds"]})
                                    var_map = fi.get("var_to_group", {})
                                    if v_name in var_map:
                                        gp, sn = var_map[v_name]
                                        test_ds = ds_dict[gp]
                                    else:
                                        test_ds = fi["ds"]
                                        sn = v_name
                                    if len(test_ds[sn].dims) >= 2:
                                        has_heatmap_trace = True
                                        break
                            
                            if has_heatmap_trace:
                                with st.expander("Colormap Range", expanded=True):
                                    if st.session_state.sync_colormap:
                                        st.caption("Controlled globally in sidebar")
                                    else:
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
                                if st.session_state.sync_colormap:
                                    st.caption("Colormap controlled globally in sidebar")
                                else:
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

                        if panel.get('show_slice', False):
                            with st.expander("Axis Control", expanded=True):
                                for ti_slice, (tfname, tvname, _) in enumerate(panel['traces']):
                                    if tfname in st.session_state.datasets_dict:
                                        fi_s = st.session_state.datasets_dict[tfname]
                                        ds_dict_s = fi_s.get("ds_dict", {"": fi_s["ds"]})
                                        var_map_s = fi_s.get("var_to_group", {})
                                        if tvname in var_map_s:
                                            gp_s, sn_s = var_map_s[tvname]
                                            ds_s = ds_dict_s[gp_s]
                                        else:
                                            ds_s = fi_s["ds"]
                                            sn_s = tvname
                                        var_s = ds_s[sn_s]
                                        if len(var_s.dims) >= 2:
                                            st.markdown(f"**{tvname}**")
                                            dims_s = list(var_s.dims)
                                            cur_cfg = panel.get("slice_configs", {}).get(ti_slice, {})

                                            col1, col2, col3 = st.columns(3)
                                            with col1:
                                                default_x = cur_cfg.get("x_dim", dims_s[-1]) if cur_cfg.get("x_dim") in dims_s else dims_s[-1]
                                                sel_x = st.selectbox(
                                                    "x-axis", dims_s,
                                                    index=dims_s.index(default_x),
                                                    key=f"slice_x_{panel['id']}_{ti_slice}"
                                                )
                                            with col2:
                                                other_dims = [d for d in dims_s if d != sel_x]
                                                y_options = other_dims + ["— Slice"]
                                                default_y = cur_cfg.get("y_dim")
                                                if default_y is not None and default_y in other_dims:
                                                    default_y_idx = y_options.index(default_y)
                                                else:
                                                    default_y_idx = 0
                                                sel_y_label = st.selectbox(
                                                    "y-axis", y_options,
                                                    index=default_y_idx,
                                                    key=f"slice_y_{panel['id']}_{ti_slice}"
                                                )
                                                sel_y = None if sel_y_label == "— Slice" else sel_y_label
                                            
                                            slice_at = {}
                                            slice_dims = [d for d in dims_s if d != sel_x and (sel_y is None or d != sel_y)]
                                            for si_start in range(0, len(slice_dims), 3):
                                                row = slice_dims[si_start:si_start + 3]
                                                cols_3 = st.columns(3)
                                                for ci, d in enumerate(row):
                                                    with cols_3[ci]:
                                                        default_si = cur_cfg.get("slice_at", {}).get(d, 0)
                                                        slice_at[d] = st.number_input(
                                                            f"Index for {d}",
                                                            min_value=0, max_value=var_s.sizes[d] - 1,
                                                            value=default_si,
                                                            key=f"slice_{panel['id']}_{ti_slice}_{d}"
                                                        )
                                                        # Display the real coordinate value
                                                        current_idx = st.session_state[f"slice_{panel['id']}_{ti_slice}_{d}"]
                                                        coord_val = var_s.coords[d].values[current_idx]
                                                        if isinstance(coord_val, (int, float, np.floating)):
                                                            st.caption(f"Value: {coord_val:.4f}")
                                                        else:
                                                            st.caption(f"Value: {coord_val}")
                                            if 'slice_configs' not in panel:
                                                panel['slice_configs'] = {}
                                            panel['slice_configs'][ti_slice] = {"x_dim": sel_x, "y_dim": sel_y, "slice_at": slice_at}

                                # Count 1D traces for secondary y-axis option (apply slice config to determine final dims)
                                n_scatter = 0
                                for ti_sc, (fn_sc, vn_sc, _) in enumerate(panel['traces']):
                                    if fn_sc in st.session_state.datasets_dict:
                                        fi_sc = st.session_state.datasets_dict[fn_sc]
                                        dd_sc = fi_sc.get("ds_dict", {"": fi_sc["ds"]})
                                        vm_sc = fi_sc.get("var_to_group", {})
                                        gp_sc, sn_sc = (vm_sc[vn_sc]) if vn_sc in vm_sc else ("", vn_sc)
                                        ds_sc = dd_sc[gp_sc] if gp_sc else fi_sc["ds"]
                                        v_sc = ds_sc[sn_sc]
                                        # Apply slice config
                                        sc_cfg = panel.get("slice_configs", {}).get(ti_sc, {})
                                        if sc_cfg and "x_dim" in sc_cfg:
                                            sv_sc = v_sc
                                            for sd, si in sc_cfg.get("slice_at", {}).items():
                                                if sd in sv_sc.dims:
                                                    sv_sc = sv_sc.isel({sd: si})
                                        else:
                                            dims_sc = list(v_sc.dims)
                                            sv_sc = v_sc
                                            for d in dims_sc[:-2]:
                                                sv_sc = sv_sc.isel({d: 0})
                                        if len(sv_sc.dims) == 1:
                                            n_scatter += 1
                            if n_scatter >= 2:
                                    panel['secondary_y'] = st.checkbox(
                                        "Secondary Y-axis (right)",
                                        value=panel.get('secondary_y', False),
                                        key=f"sec_y_{panel['id']}"
                                    )

                        if panel.get('show_range', False):
                            ax_min = ax_max = ay_min = ay_max = None
                            if panel['traces']:
                                try:
                                    fn, vn, _ = panel['traces'][0]
                                    if fn in st.session_state.datasets_dict:
                                        fi = st.session_state.datasets_dict[fn]
                                        dd = fi.get("ds_dict", {"": fi["ds"]})
                                        vm = fi.get("var_to_group", {})
                                        gp, sn = (vm[vn]) if vn in vm else ("", vn)
                                        ds = dd[gp] if gp else fi["ds"]
                                        v = ds[sn]
                                        sc = panel.get("slice_configs", {}).get(0, {})
                                        xd = sc.get("x_dim") or (list(v.dims)[-1] if v.dims else None)
                                        yd = sc.get("y_dim")
                                        sv = v
                                        for sd, si in sc.get("slice_at", {}).items():
                                            if sd in sv.dims:
                                                sv = sv.isel({sd: si})
                                        if yd and xd and xd in sv.dims and yd in sv.dims:
                                            sv = sv.transpose(yd, xd)
                                        if len(sv.dims) > 1:
                                            xc = sv.coords[sv.dims[1]].values
                                            yc = sv.coords[sv.dims[0]].values
                                            if len(xc): ax_min, ax_max = float(xc.min()), float(xc.max())
                                            if len(yc): ay_min, ay_max = float(yc.min()), float(yc.max())
                                except:
                                    pass

                            with st.expander("Range", expanded=True):
                                use_x = st.checkbox("Set X range", value=panel.get('x_range_active', False), key=f"xr_use_{panel['id']}")
                                if use_x:
                                    col_x1, col_x2 = st.columns(2)
                                    with col_x1:
                                        panel['x_range_min'] = st.number_input("X min", value=ax_min if ax_min is not None else 0.0, format="%.6f", key=f"xr_min_{panel['id']}")
                                    with col_x2:
                                        panel['x_range_max'] = st.number_input("X max", value=ax_max if ax_max is not None else 1.0, format="%.6f", key=f"xr_max_{panel['id']}")
                                panel['x_range_active'] = use_x

                                use_y = st.checkbox("Set Y range", value=panel.get('y_range_active', False), key=f"yr_use_{panel['id']}")
                                if use_y:
                                    col_y1, col_y2 = st.columns(2)
                                    with col_y1:
                                        panel['y_range_min'] = st.number_input("Y min", value=ay_min if ay_min is not None else 0.0, format="%.6f", key=f"yr_min_{panel['id']}")
                                    with col_y2:
                                        panel['y_range_max'] = st.number_input("Y max", value=ay_max if ay_max is not None else 1.0, format="%.6f", key=f"yr_max_{panel['id']}")
                                panel['y_range_active'] = use_y

                        if panel.get('show_spectra', False) and panel['traces']:
                            fn, vn, _ = panel['traces'][0]
                            if fn in st.session_state.datasets_dict:
                                fi = st.session_state.datasets_dict[fn]
                                dd = fi.get("ds_dict", {"": fi["ds"]})
                                vm = fi.get("var_to_group", {})
                                gp, sn = (vm[vn]) if vn in vm else ("", vn)
                                ds = dd[gp] if gp else fi["ds"]
                                v = ds[sn]
                                horiz_dims = [d for d in v.dims if 'ni' in d or 'nj' in d]
                                vertical_dims = [d for d in v.dims if d not in horiz_dims]
                                all_other_dims = [d for d in v.dims]
                                if horiz_dims:
                                    with st.expander(f"Spectra Config", expanded=False):
                                        st.caption("Select axes for FFT:")
                                        spec_axes = {}
                                        for hd in horiz_dims:
                                            checked = st.checkbox(hd, value=(len(horiz_dims)==1),
                                                                  key=f"spec_ax_{panel['id']}_{hd}")
                                            if checked:
                                                spec_axes[hd] = True
                                        vert_inputs = {}
                                        for vd in vertical_dims:
                                            vd_size = len(v.coords[vd])
                                            vk = st.number_input(f"{vd} layer (0-{vd_size-1})", min_value=0,
                                            max_value=vd_size-1, value=0,
                                                                 key=f"spec_v_{panel['id']}_{vd}")
                                            vert_inputs[vd] = vk

                                        st.caption("Or average over remaining dims (default):")
                                        avg_remaining = st.checkbox("Average over non-selected dims", value=True,
                                                                     key=f"spec_avg_{panel['id']}")

                                        if st.button("Compute & Add Panel", key=f"spec_comp_{panel['id']}"):
                                            sv = v
                                            dx_coords = {}
                                            for d in all_other_dims:
                                                if d in horiz_dims:
                                                    dx_coords[d] = v.coords[d].values
                                                elif d in vert_inputs:
                                                    sv = sv.isel({d: vert_inputs[d]})
                                                else:
                                                    if avg_remaining:
                                                        sv = sv.mean(dim=d)
                                                    else:
                                                        sv = sv.isel({d: 0})
                                            data_vals = sv.values
                                            if len(spec_axes) == 2:
                                                import itertools
                                                spec_order = [d for d in sv.dims if d in spec_axes]
                                                other_order = [d for d in sv.dims if d not in spec_axes]
                                                sv_t = sv.transpose(*other_order, *spec_order)
                                                have_extra = len(sv_t.dims) > 2
                                                if have_extra:
                                                    for d_rem in other_order:
                                                        sv_t = sv_t.mean(dim=d_rem)
                                                data_vals = sv_t.values
                                                wl, en = compute_spectrum(data_vals, spec_order, dx_coords)
                                            elif len(spec_axes) == 1:
                                                spec_ax_name = list(spec_axes.keys())[0]
                                                spec_order = [d for d in sv.dims if d in spec_axes]
                                                other_order = [d for d in sv.dims if d not in spec_axes]
                                                sv_t = sv.transpose(*other_order, *spec_order)
                                                have_extra = len(sv_t.dims) > 1
                                                if have_extra:
                                                    for d_rem in other_order:
                                                        sv_t = sv_t.mean(dim=d_rem)
                                                data_vals = sv_t.values
                                                wl, en = compute_spectrum(data_vals, spec_order, dx_coords)
                                            else:
                                                wl, en = None, None

                                            if wl is not None and len(wl) > 1:
                                                spec_panel_id = st.session_state.next_panel_id
                                                st.session_state.next_panel_id += 1
                                                st.session_state.panels.append({
                                                    "id": spec_panel_id,
                                                    "spectrum_data": {
                                                        "wavelengths": wl,
                                                        "energies": en,
                                                        "source_var": vn,
                                                        "axes": list(spec_axes.keys()),
                                                    },
                                                    "traces": [],
                                                    "show_config": False,
                                                    "show_spectra": False,
                                                })
                                                panel['show_spectra'] = False
                                                st.success(f"Spectrum panel {spec_panel_id} created")
                                                st.rerun()
                                else:
                                    st.caption("Spectra computation is only possible with horizontal dimensions")

                        if st.session_state.sync_colormap:
                            colorscale = st.session_state.sync_colorscale
                            if st.session_state.sync_invert_cmap:
                                colorscale = colorscale + "_r"
                        else:
                            colorscale = panel.get("colorscale", "Viridis")
                            if panel.get("invert_cmap", False):
                                colorscale = colorscale + "_r"

                        if 'spectrum_data' in panel:
                            sd = panel['spectrum_data']
                            wl = sd['wavelengths']
                            en = sd['energies']
                            fig_spec = go.Figure()
                            fig_spec.add_trace(go.Scatter(
                                x=wl, y=en, mode='lines',
                                name=f"Spectrum {sd['source_var']} {sd['axes']}"
                            ))
                            fig_spec.update_xaxes(title_text="Wavelength (m)", type="log", autorange="reversed")
                            fig_spec.update_yaxes(title_text="Energy", type="log")
                            fig_spec.update_layout(
                                height=st.session_state.plots_layout_height,
                                margin=dict(l=10, r=10, t=30, b=10),
                                showlegend=True
                            )
                            st.plotly_chart(fig_spec, use_container_width=True)
                        elif panel['traces']:
                            fig = go.Figure()
                            has_data = False
                            first_trace_info = None
                            trace_y_labels = []

                            for ti, (fname, vname, trace_color) in enumerate(panel['traces']):
                                if fname in st.session_state.datasets_dict:
                                    try:
                                        file_info = st.session_state.datasets_dict[fname]
                                        ds_dict = file_info.get("ds_dict", {"": file_info["ds"]})
                                        var_map = file_info.get("var_to_group", {})
                                        if vname in var_map:
                                            group_path, short_name = var_map[vname]
                                            ds = ds_dict[group_path]
                                        else:
                                            ds = file_info["ds"]
                                            short_name = vname
                                        var = ds[short_name]
                                        # Apply user slice config or default
                                        slice_cfg = panel.get("slice_configs", {}).get(ti)
                                        if slice_cfg and "x_dim" in slice_cfg and "y_dim" in slice_cfg:
                                            x_dim = slice_cfg["x_dim"]
                                            y_dim = slice_cfg["y_dim"]
                                            sliced = var
                                            for sd, si in slice_cfg.get("slice_at", {}).items():
                                                if sd in sliced.dims:
                                                    sliced = sliced.isel({sd: si})
                                        else:
                                            dims_list = list(var.dims)
                                            x_dim = dims_list[-1] if dims_list else None
                                            y_dim = dims_list[-2] if len(dims_list) >= 2 else None
                                            sliced = var
                                            for d in dims_list[:-2]:
                                                sliced = sliced.isel({d: 0})
                                        dims = sliced.dims
                                        full_label = f"{fname}:{vname}"
                                        legend_name = vname.split('/')[-1]

                                        # Build axis label with units when available
                                        y_label = short_name
                                        if 'units' in var.attrs:
                                            y_label += f" ({var.attrs['units']})"
                                        trace_y_labels.append(y_label)

                                        if len(dims) == 1:
                                            sc_kw = {
                                                "x": sliced.coords[dims[0]].values,
                                                "y": sliced.values,
                                                "mode": 'lines',
                                                "name": legend_name,
                                                "hovertemplate": f"<b>{full_label}</b><br>%{{x}}<br>%{{y}}<extra></extra>",
                                                "line": dict(color=trace_color),
                                            }
                                            if panel.get('secondary_y', False) and ti >= 1:
                                                sc_kw["yaxis"] = "y2"
                                            fig.add_trace(go.Scatter(**sc_kw))
                                            has_data = True
                                            if first_trace_info is None:
                                                first_trace_info = {
                                                    "x_dim": dims[0],
                                                    "x_vals": sliced.coords[dims[0]].values,
                                                    "y_label": y_label,
                                                    "y_vals": sliced.values,
                                                }
                                        elif len(dims) >= 2:
                                            if y_dim is not None and x_dim in dims and y_dim in dims:
                                                sliced = sliced.transpose(y_dim, x_dim)
                                            z_data = sliced.values
                                            x_coord = sliced.coords[sliced.dims[1]].values if len(sliced.dims) > 1 else None
                                            y_coord = sliced.coords[sliced.dims[0]].values if len(sliced.dims) > 0 else None
                                            hm_x_dim = sliced.dims[1] if len(sliced.dims) > 1 else None
                                            hm_y_dim = sliced.dims[0] if len(sliced.dims) > 0 else None
                                            zsmooth = False if st.session_state.raw_mode else "best"

                                            # Log-scale transform
                                            log_scale = st.session_state.log_scale
                                            if log_scale:
                                                z_data = np.where(z_data > 0, np.log10(z_data), np.nan)
                                            cb_title = f"log({y_label})" if log_scale else y_label

                                            heatmap_kwargs = {
                                            "z": z_data, 
                                            "x": x_coord, 
                                            "y": y_coord,
                                            "colorscale": colorscale,
                                            "name": legend_name,
                                            "zsmooth": zsmooth,
                                            "hovertemplate": f"<b>{full_label}</b><br>x: %{{x}}<br>y: %{{y}}<br>z: %{{z}}<extra></extra>"
                                            }
                                            if st.session_state.sync_colormap:
                                                eff_z_min = sliced.values.min() if st.session_state.sync_z_min is None else st.session_state.sync_z_min
                                                eff_z_max = sliced.values.max() if st.session_state.sync_z_max is None else st.session_state.sync_z_max
                                            else:
                                                panel['z_min'] = sliced.values.min() if panel.get('z_min') is None else panel['z_min']
                                                panel['z_max'] = sliced.values.max() if panel.get('z_max') is None else panel['z_max']
                                                eff_z_min = panel['z_min']
                                                eff_z_max = panel['z_max']

                                            # Apply zmin/zmax — on log scale if active
                                            if log_scale:
                                                if eff_z_min is not None and eff_z_min > 0:
                                                    heatmap_kwargs["zmin"] = np.log10(eff_z_min)
                                                if eff_z_max is not None and eff_z_max > 0:
                                                    heatmap_kwargs["zmax"] = np.log10(eff_z_max)
                                            else:
                                                if eff_z_min is not None:
                                                    heatmap_kwargs["zmin"] = eff_z_min
                                                if eff_z_max is not None:
                                                    heatmap_kwargs["zmax"] = eff_z_max

                                            # Colorbar tick labels in original scale when log is active
                                            if log_scale and not np.all(np.isnan(z_data)):
                                                log_min = np.nanmin(z_data)
                                                log_max = np.nanmax(z_data)
                                                if np.isfinite(log_min) and np.isfinite(log_max):
                                                    log_ticks = np.linspace(log_min, log_max, 6)
                                                    orig_ticks = 10 ** log_ticks
                                                    heatmap_kwargs["colorbar"] = {
                                                        "title": {"text": cb_title},
                                                        "tickvals": log_ticks.tolist(),
                                                        "ticktext": [f"{v:.2e}" for v in orig_ticks]
                                                    }
                                            else:
                                                heatmap_kwargs["colorbar"] = {"title": {"text": cb_title}}
                                            
                                            fig.add_trace(go.Heatmap(**heatmap_kwargs))
                                            has_data = True
                                            if first_trace_info is None:
                                                first_trace_info = {
                                                    "x_dim": hm_x_dim,
                                                    "x_vals": x_coord,
                                                    "y_label": hm_y_dim,
                                                    "y_vals": y_coord,
                                                }
                                    except:
                                        pass

                            if has_data:
                                fig.update_layout(height=st.session_state.plots_layout_height, margin=dict(l=10, r=10, t=30, b=10), showlegend=True)
    
                                if first_trace_info:
                                    info = first_trace_info
                                    fig.update_xaxes(title_text=info["x_dim"])
                                    fig.update_yaxes(title_text=info["y_label"])
    
                                    if panel.get('secondary_y', False) and len(trace_y_labels) >= 2:
                                        fig.update_layout(yaxis2=dict(
                                            overlaying="y", side="right",
                                            title_text=trace_y_labels[1],
                                        ))
    
                                    for ax_key, vals in [("xaxis", info["x_vals"]), ("yaxis", info["y_vals"])]:
                                        if vals is not None and len(vals) and np.issubdtype(np.asarray(vals).dtype, np.number):
                                            abs_vals = np.abs(vals)
                                            if abs_vals.max() > 10000 or (abs_vals[abs_vals > 0].min() < 0.001 if np.any(abs_vals > 0) else False):
                                                fig.update_layout({ax_key: {"tickformat": ".0E"}})
    
                                # Apply axis range limits
                                if panel.get('x_range_active', False):
                                    fig.update_xaxes(range=[panel.get('x_range_min'), panel.get('x_range_max')])
                                if panel.get('y_range_active', False):
                                    fig.update_yaxes(range=[panel.get('y_range_min'), panel.get('y_range_max')])
    
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.caption("No compatible data")
                        else:
                            st.caption("Empty Panel")
                else: st.write("")

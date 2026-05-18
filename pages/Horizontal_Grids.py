import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import math
from modules import utils, parser

st.set_page_config(page_title="🌐 Horizontal Grids", layout="wide")

DEFAULT_CENTER = [46.0, 2.0]
MAX_DOMAINS = 8
DOMAIN_COLORS = ['#3388ff', '#e6194b', '#3cb44b', '#ffe119', '#f58231', '#911eb4', '#42d4f4', '#f032e6']

_DEG_PER_M = 1.0 / 111111.0

def deg_lon_per_m(lat):
    return 1.0 / (111111.0 * math.cos(math.radians(lat)))

def get_bounds(d):
    return [[d['sw'][0], d['sw'][1]], [d['ne'][0], d['ne'][1]]]

def compute_domain1_bounds(center_lat, center_lon, nimax, njmax, xdeltax, xdeltay):
    half_w = deg_lon_per_m(center_lat) * nimax * xdeltax / 2
    half_h = _DEG_PER_M * njmax * xdeltay / 2
    return [center_lat - half_h, center_lon - half_w], [center_lat + half_h, center_lon + half_w]

def compute_child_bounds(parent, ixor, iyor, ixsize, iysize, idxratio, idyratio):
    p_sw = parent['sw']
    p_xdeltax = parent['xdeltax']
    p_xdeltay = parent['xdeltay']

    c_sw_lon = p_sw[1] + deg_lon_per_m(p_sw[0]) * ixor * p_xdeltax
    c_sw_lat = p_sw[0] + _DEG_PER_M * iyor * p_xdeltay

    width_m = ixsize * p_xdeltax
    height_m = iysize * p_xdeltay

    c_ne_lon = c_sw_lon + deg_lon_per_m(c_sw_lat) * width_m
    c_ne_lat = c_sw_lat + _DEG_PER_M * height_m

    return [c_sw_lat, c_sw_lon], [c_ne_lat, c_ne_lon]

def make_domain1():
    return {
        'id': 1, 'center_lat': DEFAULT_CENTER[0], 'center_lon': DEFAULT_CENTER[1],
        'nimax': 500, 'njmax': 500, 'xdeltax': 1300.0, 'xdeltay': 1300.0,
        'color': DOMAIN_COLORS[0], 'parent': None, 'sw': None, 'ne': None,
    }

def make_child(domain_id, parent_id, color=None):
    return {
        'id': domain_id, 'parent': parent_id,
        'ixor': 5, 'iyor': 5, 'idxratio': 2, 'idyratio': 2, 'ixsize': 200, 'iysize': 200,
        'color': color or DOMAIN_COLORS[(domain_id - 1) % len(DOMAIN_COLORS)],
        'sw': None, 'ne': None,
    }

def get_domain_dimensions(domain):
    """Get the effective NIMAX and NJMAX for any domain (top-level or nested child)."""
    if domain['parent'] is None:
        # Top-level domain has nimax and njmax directly
        return domain['nimax'], domain['njmax']
    else:
        # Child domain: compute from ixsize, iysize, idxratio, idyratio
        nimax = domain['ixsize'] * domain['idxratio']
        njmax = domain['iysize'] * domain['idyratio']
        return nimax, njmax

def is_factor_235(n):
    while n % 2 == 0:
        n //= 2
    while n % 3 == 0:
        n //= 3
    while n % 5 == 0:
        n //= 5
    return n == 1

def nearest_factor_235(n):
    prev = n - 1
    while prev >= 1 and not is_factor_235(prev):
        prev -= 1
    next_ = n + 1
    while not is_factor_235(next_):
        next_ += 1
    return prev, next_

def delete_domain(domain_id):
    domains = st.session_state.domains
    to_remove = {domain_id}
    added = True
    while added:
        added = False
        for d in domains:
            if d['parent'] in to_remove and d['id'] not in to_remove:
                to_remove.add(d['id'])
                added = True
    st.session_state.domains = [d for d in domains if d['id'] not in to_remove]

if 'domains' not in st.session_state:
    d1 = make_domain1()
    sw, ne = compute_domain1_bounds(d1['center_lat'], d1['center_lon'], d1['nimax'], d1['njmax'], d1['xdeltax'], d1['xdeltay'])
    d1['sw'] = sw
    d1['ne'] = ne
    st.session_state.domains = [d1]

for key in ('map_center', 'map_zoom'):
    if key not in st.session_state:
        st.session_state[key] = None

if 'auto_squared' not in st.session_state:
    st.session_state.auto_squared = True
if 'square_domain' not in st.session_state:
    st.session_state.square_domain = False
if 'upload_counter' not in st.session_state:
    st.session_state.upload_counter = 1
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = {}

st.title("🌐 Horizontal Grids")

needs_rerun = False

col_map, col_ctrl = st.columns([2, 1])

with col_map:
    m = folium.Map(
        location=st.session_state.map_center or DEFAULT_CENTER,
        zoom_start=st.session_state.map_zoom or 5,
        control_scale=True,
        tiles='OpenStreetMap',
        name='Street Map',
    )
    folium.TileLayer(
        tiles='https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        name='orography',
        attr='Map data: © OpenTopoMap contributors',
        max_zoom=17,
        control_scale=True
    ).add_to(m)
    folium.LayerControl().add_to(m)

    for d in st.session_state.domains:
        bounds = get_bounds(d)
        if d['id'] == 1:
            labeltooltip = f"D{d['id']} - {d['nimax']}×{d['njmax']} pts - &Delta;<sub>x</sub>={d['xdeltax']:.0f}m × &Delta;<sub>y</sub>={d['xdeltay']:.0f}m"
        else:
            parent = next(p for p in st.session_state.domains if p['id'] == d['parent'])
            nimax = d['ixsize'] * d['idxratio']
            njmax = d['iysize'] * d['idyratio']
            dx = parent['xdeltax'] / d['idxratio']
            dy = parent['xdeltay'] / d['idyratio']
            labeltooltip = f"D{d['id']} — {nimax}×{njmax} pts — {dx:.0f}m × {dy:.0f}m"
        folium.Rectangle(
            bounds=bounds, color=d['color'], weight=3, fill=True, fillOpacity=0.1,
            tooltip=labeltooltip,
        ).add_to(m)

        center = [(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2]
        folium.Marker(
            location=center,
            icon=folium.DivIcon(html=f'<div style="font-size:12px;font-weight:bold;color:{d["color"]};">D{d["id"]}</div>'),
        ).add_to(m)

    draw = Draw(
        draw_options={
            'rectangle': True, 'polyline': False, 'polygon': False,
            'circle': False, 'marker': False, 'circlemarker': False,
        },
        edit_options={'edit': True, 'remove': False},
    )
    draw.add_to(m)
    output = st_folium(m, height=600, width='100%', key='grid_map')

    if output and output.get('center'):
        new_center = [output['center']['lat'], output['center']['lng']]
        if st.session_state.map_center != new_center:
            st.session_state.map_center = new_center
            needs_rerun = True
    if output and output.get('zoom'):
        st.session_state.map_zoom = output['zoom']

with col_ctrl:
    domains = st.session_state.domains
    d1 = domains[0]

    st.subheader("Domain 1")

    new_color = st.color_picker("Border color", d1['color'], key="color_1")
    col_a, col_b = st.columns(2)
    with col_a:
        new_clat = st.number_input("Center latitude", value=d1['center_lat'], format="%.6f", help="XLATCEN: latitude of the center of domain 1 (in decimals)")
        new_nimax = st.number_input("NIMAX", value=d1['nimax'], min_value=1, step=1, help="NIMAX: number of physical points in east-west direction. Must only be composed of factors 2, 3, and 5.")
        if not is_factor_235(new_nimax):
            prev, next_ = nearest_factor_235(new_nimax)
            st.warning(f"NIMAX must only be composed of factors 2, 3, and 5. Suggested values: {prev} or {next_}.")
        new_xdeltax = st.number_input("XDX (m)", value=d1['xdeltax'], min_value=0.00001, step=100.0, format="%.4f", help=r"XDX (or $\Delta_x$): size of the mesh along the east-west direction (in meters)")
    with col_b:
        new_clon = st.number_input("Center longitude", value=d1['center_lon'], format="%.6f", help="XLONCEN: longitude of the center of domain 1 (in decimals)")
        new_njmax = st.number_input("NJMAX", value=d1['njmax'], min_value=1, step=1, help="NJMAX: number of physical points in south-north direction. Must only be composed of factors 2, 3, and 5.")
        if not is_factor_235(new_njmax):
            prev, next_ = nearest_factor_235(new_njmax)
            st.warning(f"NJMAX must only be composed of factors 2, 3, and 5. Suggested values: {prev} or {next_}.")
        new_xdeltay = st.number_input("XDY (m)", value=d1['xdeltay'], min_value=0.00001, step=100.0, format="%.4f", help=r"XDY (or $\Delta_y$): size of the mesh along the south-north direction (in meters)")

    if st.button("📋 Copy parameters to clipboard", use_container_width=True, help="Copy the above parameters of NAM_CONF_PROJ_GRID to clipboard. Paste it in Namelist Editor or Workspace"):
                # Mapping entre les variables de l'UI et les clés réelles de la namelist
                params_to_copy = {
                    'XLATCEN': new_clat,
                    'XLONCEN': new_clon,
                    'NIMAX': new_nimax,
                    'NJMAX': new_njmax,
                    'XDX': new_xdeltax,
                    'XDY': new_xdeltay
                }
                utils.save_copied_params(params_to_copy)
                st.success("Parameters copied!")

    if st.session_state.auto_squared:
        if new_xdeltax != d1['xdeltax']:
            new_xdeltay = new_xdeltax
        elif new_xdeltay != d1['xdeltay']:
            new_xdeltax = new_xdeltay

    if st.session_state.square_domain:
        if new_nimax != d1['nimax']:
            new_njmax = new_nimax
        elif new_njmax != d1['njmax']:
            new_nimax = new_njmax

    changed = (
        new_clat != d1['center_lat'] or new_clon != d1['center_lon'] or
        new_nimax != d1['nimax'] or new_njmax != d1['njmax'] or
        new_xdeltax != d1['xdeltax'] or new_xdeltay != d1['xdeltay'] or
        new_color != d1['color']
    )
    if changed:
        d1['center_lat'] = new_clat
        d1['center_lon'] = new_clon
        d1['nimax'] = new_nimax
        d1['njmax'] = new_njmax
        d1['xdeltax'] = new_xdeltax
        d1['xdeltay'] = new_xdeltay
        d1['color'] = new_color
        sw, ne = compute_domain1_bounds(new_clat, new_clon, new_nimax, new_njmax, new_xdeltax, new_xdeltay)
        d1['sw'] = sw
        d1['ne'] = ne
        needs_rerun = True

    if output and output.get('last_active_drawing'):
        geo = output['last_active_drawing']
        try:
            coords = geo['geometry']['coordinates'][0]
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            new_clat_map = (min(lats) + max(lats)) / 2
            new_clon_map = (min(lons) + max(lons)) / 2
            delta_lat = (max(lats) - min(lats)) / 2
            delta_lon = (max(lons) - min(lons)) / 2

            new_njmax_map = max(1, int(round((delta_lat * 2) / (_DEG_PER_M * d1['xdeltay']))))
            new_nimax_map = max(1, int(round((delta_lon * 2) / (deg_lon_per_m(new_clat_map) * d1['xdeltax']))))

            d1['center_lat'] = round(new_clat_map, 4)
            d1['center_lon'] = round(new_clon_map, 4)
            d1['nimax'] = new_nimax_map
            d1['njmax'] = new_njmax_map
            sw, ne = compute_domain1_bounds(d1['center_lat'], d1['center_lon'], d1['nimax'], d1['njmax'], d1['xdeltax'], d1['xdeltay'])
            d1['sw'] = sw
            d1['ne'] = ne
            st.rerun()
        except (KeyError, IndexError, TypeError):
            pass
    st.space(size="small")
    if len(domains) < MAX_DOMAINS:
        if st.button("+ Add domain", use_container_width=True, type='secondary'):
            new_id = max(p['id'] for p in domains) + 1
            d = make_child(new_id, 1)
            p = domains[0]
            if st.session_state.auto_center:
                d['ixor'] = max(0, (p['nimax'] - d['ixsize']) // 2)
                d['iyor'] = max(0, (p['njmax'] - d['iysize']) // 2)
            sw, ne = compute_child_bounds(p, d['ixor'], d['iyor'],
                                          d['ixsize'], d['iysize'],
                                          d['idxratio'], d['idyratio'])
            d['sw'] = sw
            d['ne'] = ne
            domains.append(d)
            st.rerun()
    else:
        st.info(f"Maximum {MAX_DOMAINS} domains reached.")

st.divider()

if len(domains) > 1:
    child_domains = domains[1:]
    child_bounds_before = {
        d['id']: (tuple(d['sw']), tuple(d['ne']))
        for d in child_domains
    }

    for row_start in range(0, len(child_domains), 3):
        row_domains = child_domains[row_start:row_start + 3]
        cols = st.columns(3)

        for col_idx, d in enumerate(row_domains):
            with cols[col_idx]:
                st.subheader(f"Domain {d['id']}")

                parent_options = {p['id'] for p in domains if p['id'] < d['id']}
                first_parent = d['parent'] if d['parent'] in parent_options else min(parent_options)
                parent_id = st.selectbox(
                    "Parent", options=sorted(parent_options),
                    format_func=lambda x: f"Domain {x}",
                    index=sorted(parent_options).index(first_parent),
                    key=f"parent_{d['id']}",
                )
                d['parent'] = parent_id
                d['color'] = st.color_picker("Border color", d['color'], key=f"color_{d['id']}")

                for ratio_key in (f"idxratio_{d['id']}", f"idyratio_{d['id']}"):
                    if ratio_key not in st.session_state:
                        st.session_state[ratio_key] = d['idxratio'] if 'idxratio' in ratio_key else d['idyratio']
                for size_key in (f"ixsize_{d['id']}", f"iysize_{d['id']}"):
                    if size_key not in st.session_state:
                        st.session_state[size_key] = d['ixsize'] if 'ixsize' in size_key else d['iysize']

                if st.session_state.auto_squared:
                    widget_idxratio = st.session_state.get(f"idxratio_{d['id']}", d['idxratio'])
                    widget_idyratio = st.session_state.get(f"idyratio_{d['id']}", d['idyratio'])
                    if widget_idxratio != d['idxratio']:
                        st.session_state[f"idyratio_{d['id']}"] = widget_idxratio
                    elif widget_idyratio != d['idyratio']:
                        st.session_state[f"idxratio_{d['id']}"] = widget_idyratio

                if st.session_state.square_domain:
                    widget_ixsize = st.session_state.get(f"ixsize_{d['id']}", d['ixsize'])
                    widget_iysize = st.session_state.get(f"iysize_{d['id']}", d['iysize'])
                    if widget_ixsize != d['ixsize']:
                        st.session_state[f"iysize_{d['id']}"] = widget_ixsize
                    elif widget_iysize != d['iysize']:
                        st.session_state[f"ixsize_{d['id']}"] = widget_iysize

                col_1, col_2 = st.columns(2)
                with col_1:
                    d['ixor'] = st.number_input("IXOR", value=d['ixor'], min_value=0, step=1, key=f"ixor_{d['id']}", help="IXOR: first point I index, according to the parent grid, left to and out of the new physical domain.")
                    d['idxratio'] = st.number_input("IDXRATIO", min_value=1, step=1, key=f"idxratio_{d['id']}", help="IDXRATIO: resolution factor in east-west direction between the parent grid and the new grid. Must only be factor of 2, 3 or 5")
                    d['ixsize'] = st.number_input("IXSIZE", min_value=1, step=1, key=f"ixsize_{d['id']}", help="IXSIZE: number of grid points in east-west direction, according to the parent grid, recovered by the new domain. Must only be factor of 2, 3 or 5")
                    if not is_factor_235(d['ixsize']):
                        prev, next_ = nearest_factor_235(d['ixsize'])
                        st.warning(f"IXSIZE must only be composed of factors 2, 3, and 5. Suggested values: {prev} or {next_}.")
                with col_2:
                    d['iyor'] = st.number_input("IYOR", value=d['iyor'], min_value=0, step=1, key=f"iyor_{d['id']}", help="IYOR: first point J index, according to the parent grid, under and out of the new physical domain.")
                    d['idyratio'] = st.number_input("IDYRATIO", min_value=1, step=1, key=f"idyratio_{d['id']}", help="IDYRATIO: resolution factor in south-north direction between the parent grid and the new grid. Must only be factor of 2, 3 or 5")
                    d['iysize'] = st.number_input("IYSIZE", min_value=1, step=1, key=f"iysize_{d['id']}", help="IYSIZE: number of grid points in south-north direction, according to the parent grid, recovered by the new domain. Must only be factor of 2, 3 or 5")
                    if not is_factor_235(d['iysize']):
                        prev, next_ = nearest_factor_235(d['iysize'])
                        st.warning(f"IYSIZE must only be composed of factors 2, 3, and 5. Suggested values: {prev} or {next_}.")

                d['nimax'] = d['ixsize'] * d['idxratio']
                d['njmax'] = d['iysize'] * d['idyratio']
                parent = next(p for p in domains if p['id'] == d['parent'])
                
                # Get effective dimensions of parent domain
                parent_nimax, parent_njmax = get_domain_dimensions(parent)
                
                # Check if child domain is within parent domain
                if d['ixor'] + d['ixsize'] > parent_nimax or d['iyor'] + d['iysize'] > parent_njmax:
                    st.error(f"Child domain {d['id']} exceeds parent domain {d['parent']} boundaries! "
                             f"Check IXOR+IXSIZE ({d['ixor'] + d['ixsize']}) <= NIMAX ({parent_nimax}) "
                             f"and IYOR+IYSIZE ({d['iyor'] + d['iysize']}) <= NJMAX ({parent_njmax}).")

                child_xdeltax = parent['xdeltax'] / d['idxratio']
                child_xdeltay = parent['xdeltay'] / d['idyratio']
                st.caption(f"NIMAX={d['nimax']}, NJMAX={d['njmax']}, "
                           f"XDELTAX={child_xdeltax:.1f}m, XDELTAY={child_xdeltay:.1f}m")

                if st.button("📋 Copy parameters to clipboard", use_container_width=True, help="Copy the above parameters of NAM_INIFILE_CONF_PROJ to clipboard. Paste it in Namelist Editor or Workspace"):
                    # Mapping entre les variables de l'UI et les clés réelles de la namelist
                    params_to_copy = {
                        'IXOR': d['ixor'],
                        'IYOR': d['iyor'],
                        'IXSIZE': d['ixsize'],
                        'IYSIZE': d['iysize'],
                        'IDXRATIO': d['idxratio'],
                        'IDYRATIO': d['idyratio']
                    }
                    utils.save_copied_params(params_to_copy)
                    st.success("Parameters copied!")

                if st.button(f"Delete Domain {d['id']}", key=f"delete_{d['id']}", use_container_width=True, type='secondary'):
                    delete_domain(d['id'])
                    st.rerun()

                sw, ne = compute_child_bounds(parent, d['ixor'], d['iyor'],
                                              d['ixsize'], d['iysize'],
                                              d['idxratio'], d['idyratio'])
                d['sw'] = sw
                d['ne'] = ne
                d['xdeltax'] = child_xdeltax
                d['xdeltay'] = child_xdeltay

    for d in child_domains:
        cur = (tuple(d['sw']), tuple(d['ne']))
        if child_bounds_before.get(d['id']) != cur:
            needs_rerun = True
            break

with st.sidebar:
    st.session_state.auto_center = st.checkbox(
        "Center child domain",
        value=st.session_state.get('auto_center', True),
    )
    st.session_state.auto_squared = st.checkbox(
        r"Square mesh $\Delta_x = \Delta_y$", 
        value=st.session_state.get('auto_squared', True),
    )
    st.session_state.square_domain = st.checkbox(
        "Square domain",
        value=st.session_state.get('square_domain', False),
    )
    st.divider()
    st.markdown("**Legend**")
    for d in st.session_state.domains:
        if d['id'] == 1:
            label = f"D{d['id']} — Points: {d['nimax']}×{d['njmax']} — Resolution: {d['xdeltax']:.0f}m × {d['xdeltay']:.0f}m"
        else:
            parent = next(p for p in st.session_state.domains if p['id'] == d['parent'])
            n = d['ixsize'] * d['idxratio']
            m = d['iysize'] * d['idyratio']
            dx = parent['xdeltax'] / d['idxratio']
            dy = parent['xdeltay'] / d['idyratio']
            label = f"D{d['id']} — {n}×{m} pts — {dx:.0f}m × {dy:.0f}m"
        st.markdown(
            f"<span style='display:inline-block;width:12px;height:12px;"
            f"background:{d['color']};margin-right:6px;'></span> {label}",
            unsafe_allow_html=True,
        )

    # --- Namelist upload section ---
    st.divider()
    st.markdown("**Import from Namelist**")

    # Show all previously uploaded files
    for domain_id, filename in sorted(st.session_state.uploaded_files.items()):
        st.success(f"D{domain_id}: {filename}")

    # Step 1: File upload
    if 'pending_upload' not in st.session_state:
        st.session_state.pending_upload = None

    next_domain = st.session_state.upload_counter

    if next_domain == 1:
        uploaded_file = st.file_uploader("Upload PRE_PGD1.nam from domain 1", type=None, key="upload_d1")
        if uploaded_file is not None:
            content = uploaded_file.getvalue().decode("utf-8")
            blocks = parser.parse_namelist(content)
            block = blocks.get('NAM_CONF_PROJ_GRID')
            if block is None:
                st.error("Block `&NAM_CONF_PROJ_GRID` not found in file.")
            else:
                def _get_val(name, default):
                    entry = block.entries.get(name)
                    return entry.value if entry is not None else default

                d1 = st.session_state.domains[0]
                new_vals = {
                    'center_lat': float(_get_val('XLATCEN', d1['center_lat'])),
                    'center_lon': float(_get_val('XLONCEN', d1['center_lon'])),
                    'nimax': int(_get_val('NIMAX', d1['nimax'])),
                    'njmax': int(_get_val('NJMAX', d1['njmax'])),
                    'xdeltax': float(_get_val('XDX', d1['xdeltax'])),
                    'xdeltay': float(_get_val('XDY', d1['xdeltay'])),
                }
                st.session_state.pending_upload = {
                    'type': 'domain1',
                    'values': new_vals,
                    'filename': uploaded_file.name,
                }
                st.success(f"Parsed Domain 1 parameters from {uploaded_file.name}. Review below and click Apply.")

        if st.session_state.pending_upload and st.session_state.pending_upload['type'] == 'domain1':
            pu = st.session_state.pending_upload
            v = pu['values']
            st.markdown(f"**Preview — Domain 1** ({pu['filename']})")
            st.table({
                'Parameter': ['XLATCEN', 'XLONCEN', 'NIMAX', 'NJMAX', 'XDX', 'XDY'],
                'Value': [v['center_lat'], v['center_lon'], v['nimax'], v['njmax'], v['xdeltax'], v['xdeltay']],
            })
            if st.button("Apply Domain 1", use_container_width=True, type="primary", key="apply_d1"):
                d1 = st.session_state.domains[0]
                d1['center_lat'] = v['center_lat']
                d1['center_lon'] = v['center_lon']
                d1['nimax'] = v['nimax']
                d1['njmax'] = v['njmax']
                d1['xdeltax'] = v['xdeltax']
                d1['xdeltay'] = v['xdeltay']
                sw, ne = compute_domain1_bounds(d1['center_lat'], d1['center_lon'], d1['nimax'], d1['njmax'], d1['xdeltax'], d1['xdeltay'])
                d1['sw'] = sw
                d1['ne'] = ne
                st.session_state.uploaded_files[1] = pu['filename']
                st.session_state.upload_counter = 2
                st.session_state.pending_upload = None
                st.rerun()

    elif next_domain <= MAX_DOMAINS:
        uploaded_file = st.file_uploader(f"Upload Domain {next_domain} namelist", type=['nam', 'NAM', 'txt'], key=f"upload_d{next_domain}")
        if uploaded_file is not None:
            content = uploaded_file.getvalue().decode("utf-8")
            blocks = parser.parse_namelist(content)
            block = blocks.get('NAM_INIFILE_CONF_PROJ')
            if block is None:
                st.error("Block `&NAM_INIFILE_CONF_PROJ` not found in file.")
            else:
                def _get_val(name, default):
                    entry = block.entries.get(name)
                    return entry.value if entry is not None else default

                new_vals = {
                    'ixor': int(_get_val('IXOR', 5)),
                    'iyor': int(_get_val('IYOR', 5)),
                    'ixsize': int(_get_val('IXSIZE', 200)),
                    'iysize': int(_get_val('IYSIZE', 200)),
                    'idxratio': int(_get_val('IDXRATIO', 2)),
                    'idyratio': int(_get_val('IDYRATIO', 2)),
                }
                st.session_state.pending_upload = {
                    'type': 'child',
                    'values': new_vals,
                    'filename': uploaded_file.name,
                }
                st.success(f"Parsed child domain parameters from {uploaded_file.name}. Select parent and click Apply.")

        if st.session_state.pending_upload and st.session_state.pending_upload['type'] == 'child':
            pu = st.session_state.pending_upload
            v = pu['values']
            st.markdown(f"**Preview — Domain {next_domain}** ({pu['filename']})")
            st.table({
                'Parameter': ['IXOR', 'IYOR', 'IXSIZE', 'IYSIZE', 'IDXRATIO', 'IDYRATIO'],
                'Value': [v['ixor'], v['iyor'], v['ixsize'], v['iysize'], v['idxratio'], v['idyratio']],
            })
            parent_options = {d['id'] for d in st.session_state.domains}
            parent_id = st.selectbox(
                "Parent domain",
                options=sorted(parent_options),
                format_func=lambda x: f"Domain {x}",
                key=f"upload_parent_{next_domain}",
            )
            if st.button(f"Apply Domain {next_domain}", use_container_width=True, type="primary", key=f"apply_d{next_domain}"):
                new_id = next_domain
                d = make_child(new_id, parent_id)
                d['ixor'] = v['ixor']
                d['iyor'] = v['iyor']
                d['ixsize'] = v['ixsize']
                d['iysize'] = v['iysize']
                d['idxratio'] = v['idxratio']
                d['idyratio'] = v['idyratio']
                parent = next(p for p in st.session_state.domains if p['id'] == parent_id)
                sw, ne = compute_child_bounds(parent, d['ixor'], d['iyor'],
                                              d['ixsize'], d['iysize'],
                                              d['idxratio'], d['idyratio'])
                d['sw'] = sw
                d['ne'] = ne
                st.session_state.domains.append(d)
                st.session_state.uploaded_files[new_id] = pu['filename']
                st.session_state.upload_counter = new_id + 1
                st.session_state.pending_upload = None
                st.rerun()

if needs_rerun:
    st.rerun()

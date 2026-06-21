import streamlit as st
import sys
import os

from modules import parser, docs, advise, utils

st.set_page_config(page_title="Workspace", layout="wide")

if 'workspace_path' not in st.session_state:
    st.session_state.workspace_path = None
if 'workspace_files' not in st.session_state:
    st.session_state.workspace_files = {}
if 'workspace_modified' not in st.session_state:
    st.session_state.workspace_modified = set()
if 'selected_file' not in st.session_state:
    st.session_state.selected_file = None
if 'free_format_data' not in st.session_state:
    st.session_state.free_format_data = {}
if 'selected_file_key' not in st.session_state:
    st.session_state.selected_file_key = None
if 'workspace_tree_state' not in st.session_state:
    st.session_state.workspace_tree_state = {}
if 'file_options_dict' not in st.session_state:
    st.session_state.file_options_dict = {}
if 'file_select_main_index' not in st.session_state:
    st.session_state.file_select_main_index = 0
if 'show_empty' not in st.session_state:
    st.session_state.show_empty = False
if 'expand_all' not in st.session_state:
    st.session_state.expand_all = True
if 'colorize_default' not in st.session_state:
    st.session_state.colorize_default = True
if 'show_delete_keys' not in st.session_state:
    st.session_state.show_delete_keys = False
if 'doc_height' not in st.session_state:
    st.session_state.doc_height = 800


DOC_DIR = docs.DOC_DIR

def paste_nam_ver_grid(block, block_name, relative_path):
    copied_data = utils.get_copied_params()
    if not copied_data:
        return

    matched_keys = set()

    for entry_name, entry in block.entries.items():
        for target_key, new_val in copied_data.items():
            if entry.base_name == target_key or entry.name == target_key:
                entry.value = new_val
                entry.raw_line = f"{entry.name} = {new_val}"
                matched_keys.add(target_key)
                potential_keys = [
                    f"{relative_path}_{block_name}_{entry.base_name}",
                    f"{relative_path}_{block_name}_{entry.name}"
                ]
                for k in potential_keys:
                    if k in st.session_state:
                        st.session_state[k] = new_val

    block_params, _ = docs.get_block_params(block_name)
    for target_key, new_val in copied_data.items():
        if target_key not in matched_keys:
            param_def = block_params.get(target_key, {})
            is_array = param_def.get("is_array", False)
            block.entries[target_key] = parser.NamelistEntry(
                name=target_key,
                base_name=target_key,
                value=new_val,
                raw_line=f"{target_key} = {new_val}",
                is_array=is_array,
                array_index=""
            )

def is_default_value(block_name, param_name, current_value):
    defaults = docs.get_block_defaults(block_name)

    if param_name not in defaults:
        return False

    default_value = defaults[param_name]

    try:
        return str(default_value).strip().lower() == str(current_value).strip().lower()
    except:
        return default_value == current_value

def scan_workspace(workspace_path):
    namelist_files = {}
    
    for root, dirs, files in os.walk(workspace_path):
        for file in files:
            if file.endswith('.nam') or '.nam' in file:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, workspace_path)
                
                if file not in namelist_files:
                    namelist_files[file] = []
                namelist_files[file].append({
                    'path': full_path,
                    'relative': rel_path,
                    'blocks': None,
                    'free_format': {}
                })
    
    for file in namelist_files:
        for file_info in namelist_files[file]:
            try:
                with open(file_info['path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                    blocks, free_format = parser.parse_namelist(content)
                    file_info['blocks'] = blocks
                    file_info['free_format'] = free_format
            except Exception as e:
                file_info['blocks'] = {}
                file_info['free_format'] = {}

    return namelist_files


def save_file(relative_path, blocks):
    workspace_path = st.session_state.workspace_path
    full_path = os.path.join(workspace_path, relative_path)
    
    content = parser.write_namelist(blocks)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    st.session_state.workspace_modified.discard(relative_path)


def render_editor(blocks, relative_path):
    editor_width = st.session_state.get('editor_width', 2)
    col_editor, col_doc = st.columns([editor_width, 1])
    
    with col_editor:
        for block_name in blocks:
            block = blocks[block_name]
            
            if not block.entries and not st.session_state.show_empty:
                continue

            # Fetch block params once (includes allowed_values for NAM_BU_* blocks)
            block_params, allowed_vals = {}, {}
            try:
                block_params, allowed_vals = docs.get_block_params(block_name)
            except (ValueError, TypeError):
                pass

            col_block, col_delete = st.columns([10, 1])
            with col_block:
                with st.expander(f"&{block_name} ({len(block.entries)})", expanded=st.session_state.expand_all):
                    if not block.entries:
                        st.caption("Empty block")
                        continue
                    
                    entries = list(block.entries.items())
                    pair_count = st.session_state.get('pair_count', 3)
                    delete_mode = st.session_state.get('show_delete_keys', False)
                    for i in range(0, len(entries), pair_count):
                        pair = entries[i:i+pair_count]
                        if delete_mode:
                            cols = st.columns([1, 1, 1] * pair_count)
                        else:
                            cols = st.columns([1, 1] * pair_count)
                        for j, (param_name, entry) in enumerate(pair):
                            base_idx = j * (3 if delete_mode else 2)
                            if delete_mode:
                                with cols[base_idx]:
                                    if st.button("❌", key=f"del_{relative_path}_{block_name}_{param_name}"):
                                        del block.entries[param_name]
                                        save_file(relative_path, blocks)
                                        st.rerun()
                                name_col = cols[base_idx + 1]
                                val_col = cols[base_idx + 2]
                            else:
                                name_col = cols[base_idx]
                                val_col = cols[base_idx + 1]

                            if getattr(entry, 'is_comment', False):
                                with name_col:
                                    new_val = st.text_area("Comment", value=entry.value, key=f"{relative_path}_{block_name}_{param_name}", label_visibility="collapsed")
                                    entry.value = new_val
                                    entry.raw_line = f"! {new_val}"
                                continue

                            with name_col:
                                is_default = is_default_value(block_name, param_name, entry.value)
                                if st.session_state.colorize_default:
                                    bg = "#587e61" if is_default else "transparent"
                                else:
                                    bg = "transparent"
                                st.markdown(f"""<div style='padding:6px;margin-top:4px;border-radius:6px;
                                            background-color:{bg};font-weight:bold;'>{param_name}</div>""",
                                    unsafe_allow_html=True)
                            with val_col:
                                if isinstance(entry.value, bool):
                                    new_val = st.checkbox(" ", value=entry.value, key=f"{relative_path}_{block_name}_{param_name}", label_visibility="collapsed")
                                    entry.value = new_val
                                elif isinstance(entry.value, (int, float)):
                                    if isinstance(entry.value, int):
                                        new_val = st.number_input(" ", value=entry.value, key=f"{relative_path}_{block_name}_{param_name}", format="%d", label_visibility="collapsed")
                                    else:
                                        decimals = getattr(entry, 'decimals', 4)
                                        new_val = st.number_input(" ", value=float(entry.value), key=f"{relative_path}_{block_name}_{param_name}", format=f"%.{decimals}f", label_visibility="collapsed")
                                    entry.value = new_val
                                elif isinstance(entry.value, str):
                                    if entry.base_name in allowed_vals:
                                        opts = allowed_vals[entry.base_name]
                                        idx = (opts.index(str(entry.value)) + 1) if str(entry.value) in opts else 0
                                        new_val = st.selectbox(" ", options=[""] + opts, index=idx,
                                            key=f"{relative_path}_{block_name}_{param_name}", label_visibility="collapsed")
                                    else:
                                        new_val = st.text_input(" ", value=entry.value, key=f"{relative_path}_{block_name}_{param_name}", label_visibility="collapsed")
                                    entry.value = new_val
                with col_delete:
                    with st.popover("➕"):
                        if block_name == "NAM_DIAG":
                            custom_param_name = st.text_input("Parameter name", key=f"custom_name_{relative_path}_{block_name}")
                            expected_type = advise.get_expected_type(custom_param_name) if custom_param_name else None
                            if expected_type:
                                st.caption(f"Detected type: {expected_type.__name__}")

                            is_array = st.checkbox("Is array", key=f"custom_array_{relative_path}_{block_name}")
                            dims = 1
                            idx_values = []
                            if is_array:
                                dims = st.number_input("Dimensions", min_value=1, max_value=4, value=1, key=f"custom_dims_{relative_path}_{block_name}")
                                for d in range(int(dims)):
                                    val = st.text_input(f"Index dim {d+1}", value="1", key=f"custom_idx_{relative_path}_{block_name}_{d}")
                                    if val and not val.isdigit():
                                        st.error("Integers only")
                                        val = "1"
                                    idx_values.append(val)

                            default_value = ""
                            if expected_type == int:
                                default_value = 0
                            elif expected_type == float:
                                default_value = 0.0
                            elif expected_type == bool:
                                default_value = False

                            if st.button("Add custom param", key=f"add_custom_{relative_path}_{block_name}"):
                                if custom_param_name:
                                    if is_array:
                                        idx_str = ','.join(idx_values)
                                        entry_name = f"{custom_param_name}({idx_str})"
                                        array_index_str = f"({idx_str})"
                                    else:
                                        entry_name = custom_param_name
                                        idx_str = ""
                                        array_index_str = ""

                                    block.entries[entry_name] = parser.NamelistEntry(
                                        name=entry_name,
                                        base_name=custom_param_name,
                                        value=default_value,
                                        raw_line=f"{entry_name} = {default_value}",
                                        is_array=is_array,
                                        array_index=array_index_str
                                    )
                                    save_file(relative_path, blocks)
                                    st.rerun()
                        else:
                            existing_params = set(block.entries.keys())
                            available_params = {k: v for k, v in block_params.items() if k not in existing_params}
                            
                            if available_params:
                                for param, default_val in available_params.items():
                                    is_array = default_val.get('is_array', False) if isinstance(default_val, dict) else False
                                    dimensions = default_val.get('dimensions', 1) if isinstance(default_val, dict) else 1

                                    col_check, col_idx = st.columns([3, 1])
                                    with col_check:
                                        st.checkbox(param, key=f"check_{relative_path}_{block_name}_{param}")
                                    if is_array:
                                        with col_idx:
                                            if dimensions > 1:
                                                idx_cols = st.columns(dimensions)
                                                idx_values = []
                                                for i in range(dimensions):
                                                    with idx_cols[i]:
                                                        val = st.text_input(" ", value="1", 
                                                                     key=f"idx_{relative_path}_{block_name}_{param}_dim{i}",
                                                                     label_visibility="collapsed")
                                                        if val.isdigit():
                                                            idx_values.append(val)
                                                        else:
                                                            st.error("Integers only")
                                                            idx_values.append("1")
                                                idx = ','.join(idx_values)
                                            else:
                                                idx = st.text_input(" ", value="1", 
                                                                     key=f"idx_{relative_path}_{block_name}_{param}", 
                                                                     label_visibility="collapsed")
                                                if not idx.isdigit():
                                                    st.error("Integers only")
                                                    idx = "1"

                                col_pbtn1, col_pbtn2 = st.columns(2)
                                with col_pbtn1:
                                    if st.button("Add selected", key=f"add_{relative_path}_{block_name}"):
                                        for param, default_val in available_params.items():
                                            if st.session_state.get(f"check_{relative_path}_{block_name}_{param}"):
                                                is_array = default_val.get('is_array', False) if isinstance(default_val, dict) else False
                                                if is_array:
                                                    dims = default_val.get('dimensions', 1)
                                                    if dims > 1:
                                                        idx_values = []
                                                        for i in range(dims):
                                                            val = st.session_state.get(f"idx_{relative_path}_{block_name}_{param}_dim{i}", "1")
                                                            if val and val.isdigit():
                                                                idx_values.append(val)
                                                            else:
                                                                idx_values.append("1")
                                                        idx = ','.join(idx_values)
                                                    else:
                                                        idx = st.session_state.get(f"idx_{relative_path}_{block_name}_{param}", "1")
                                                        if idx and not idx.isdigit():
                                                            idx = "1"
                                                    entry_name = f"{param}({idx})"
                                                    base_value = default_val.get('value', default_val) if isinstance(default_val, dict) else default_val
                                                else:
                                                    entry_name = param
                                                    base_value = default_val.get('value', default_val) if isinstance(default_val, dict) else default_val
                                                block.entries[entry_name] = parser.NamelistEntry(
                                                    name=entry_name,
                                                    base_name=param,
                                                    value=base_value,
                                                    raw_line=f"{entry_name} = {base_value}",
                                                    is_array=is_array,
                                                    array_index=f"({idx})" if is_array else ""
                                                )
                                        save_file(relative_path, blocks)
                                        st.rerun()
                                with col_pbtn2:
                                    if st.button("Add All", key=f"addall_{relative_path}_{block_name}"):
                                        for param, default_val in available_params.items():
                                            is_array = default_val.get('is_array', False) if isinstance(default_val, dict) else False
                                            if is_array:
                                                continue
                                            base_value = default_val.get('value', default_val) if isinstance(default_val, dict) else default_val
                                            block.entries[param] = parser.NamelistEntry(
                                                name=param,
                                                base_name=param,
                                                value=base_value,
                                                raw_line=f"{param} = {base_value}",
                                                is_array=False,
                                                array_index=""
                                            )
                                        save_file(relative_path, blocks)
                                        st.rerun()
                            else:
                                st.caption("No params to add")
                    if block_name == "NAM_VER_GRID" or block_name == "NAM_CONF_PROJ_GRID" or block_name == "NAM_INIFILE_CONF_PROJ" \
                        or block_name == "NAM_GRID2_SPA":
                        origin_page = "Horizontal Grids" if block_name == "NAM_CONF_PROJ_GRID" or block_name == "NAM_INIFILE_CONF_PROJ" \
                             or block_name == "NAM_GRID2_SPA" else "Vertical Grids"
                        copied_data = utils.get_copied_params()
                        if copied_data:
                            st.button(
                                "📋", key=f"paste_{block_name}",
                                help=f"Paste {block_name} parameters from clipboard copied in {origin_page} page",
                                on_click=paste_nam_ver_grid,
                                args=(block, block_name, relative_path)
                            )
                        st.subheader(" ")
        ff_data = st.session_state.get('free_format_data', {})
        if ff_data:                
            with st.expander("Free-format data", expanded=bool(st.session_state.get('free_format_data'))):  
                has_rsou = ff_data.get("radiosounding_type") is not None
                has_forcing = ff_data.get("forcing_type") is not None
                has_zhat = ff_data.get("zhat") is not None
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if has_rsou or has_forcing:
                        if st.button("Copy & Edit in 🎈 Radiosoundings and forcing page", key=f"nav_to_rsou_ws_{relative_path}_{block_name}", use_container_width=True):
                            utils.save_copied_params(st.session_state.free_format_data)
                            try:
                                st.switch_page("pages/Initial_radiosoundings_forcing.py")
                            except Exception as e:
                                st.error(f"Navigation failed. Error: {e}")
                with col_btn2:
                    if has_zhat:
                        if st.button("📈 Copy ZHAT to Vertical Levels", key=f"nav_to_zhat_{relative_path}_{block_name}", use_container_width=True):
                            st.session_state.manual_levels = ff_data["zhat"]
                            st.switch_page("pages/Vertical_Levels.py")
                
                ff_data = st.session_state.get('free_format_data', {})
                current_free_text = parser.write_free_format(ff_data)
                new_free_text = st.text_area(" ", value=current_free_text, height=1000)
                
                if new_free_text.strip() != current_free_text.strip():
                    parsed = parser.parse_free_format(new_free_text)
                    st.session_state.free_format_data = parsed
                    st.rerun()
    with col_doc:
        st.subheader("📋 User's guide")
        
        selected_file = st.session_state.get("selected_file")
        current_file = os.path.basename(selected_file["path"]) if selected_file else None
        
        program_type = docs.get_program_type(current_file) if current_file else None
        available_blocks = docs.get_available_blocks(program_type) if program_type else []
        
        block_map = {docs.get_block_title(block): block for block in available_blocks}
        
        block_options = ["Select a namelist group"] + list(block_map.keys())
        selected = st.selectbox(" ", block_options, key="doc_select")
        
        if selected and selected != "Select a namelist group":
            rst_name = block_map[selected]
            doc_content = docs.find_docs(rst_name)            
            if doc_content:
                html = docs.render_rst(doc_content, block_name=selected, height=st.session_state.doc_height)
                if html:
                    st.html(html)
                else:
                    st.warning(f"No documentation for {selected}")
        
        st.subheader("💡 Advise")
        
        if selected_file and selected_file.get("blocks"):
            blocks = selected_file["blocks"]
            current_file = os.path.basename(selected_file["path"])
            results = advise.run_all_checks(blocks, current_file)
            
            total_issues = len(results['blocks']) + len(results['params']) + len(results['values']) + len(results['fortran']) + len(results['conditions'])
            
            if total_issues == 0:
                st.success("✅ All checks passed")
            else:
                st.warning(f"⚠️ {total_issues} issue(s) found")
                
                if results['blocks']:
                    with st.expander(f"❌ Block issues ({len(results['blocks'])})"):
                        for issue in results['blocks']:
                            st.write(f"• {issue}")
                
                if results['params']:
                    with st.expander(f"❌ Parameter issues ({len(results['params'])})"):
                        for issue in results['params']:
                            st.write(f"• {issue}")
                
                if results['values']:
                    with st.expander(f"❌ Value type issues ({len(results['values'])})"):
                        for issue in results['values']:
                            st.write(f"• {issue}")
                
                if results['fortran']:
                    with st.expander(f"🔧 Fortran checks ({len(results['fortran'])})"):
                        for issue in results['fortran']:
                            st.write(f"• {issue}")
                
                if results['conditions']:
                    with st.expander(f"❌ Condition checks ({len(results['conditions'])})"):
                        for issue in results['conditions']:
                            st.error(issue)
        else:
            st.info("Select a file to run Advise checks")


def render_workspace():
    with st.sidebar:
        st.header("📁 Workspace")
        
        workspace_path = st.text_input("Workspace path (relative or absolute)", value=st.session_state.workspace_path or "", key="workspace_path_input")
                
        if st.button("🔄 Load Workspace"):
            if workspace_path and os.path.isdir(workspace_path):
                st.session_state.workspace_path = workspace_path
                st.session_state.workspace_files = scan_workspace(workspace_path)
                st.session_state.workspace_modified = set()
                st.session_state.selected_file = None
                st.success(f"Loaded {len(st.session_state.workspace_files)} files")
            else:
                st.error("Invalid directory")
        
        if st.session_state.workspace_files:
            def build_tree():
                tree = {}
                for file_name, file_list in st.session_state.workspace_files.items():
                    for f in file_list:
                        parts = f['relative'].split(os.sep)
                        current = tree
                        for part in parts[:-1]:
                            if part not in current:
                                current[part] = {}
                            current = current[part]
                        if parts[-1] not in current:
                            current[parts[-1]] = f['relative']
                return tree

            tree = build_tree()

            def init_tree_state(subtree, prefix=""):
                for name in sorted(subtree.keys()):
                    path = f"{prefix}/{name}" if prefix else name
                    content = subtree[name]
                    if isinstance(content, dict):
                        if path not in st.session_state.workspace_tree_state:
                            st.session_state.workspace_tree_state[path] = False
                        init_tree_state(content, path)

            init_tree_state(tree)
            
            def render_tree(subtree, prefix="", indent=0):
                for name in sorted(subtree.keys()):
                    path = f"{prefix}/{name}" if prefix else name
                    content = subtree[name]
                    spacer = "&nbsp;&nbsp;&nbsp;&nbsp;" * indent
                    
                    if isinstance(content, dict):
                        is_expanded = st.checkbox(f"{spacer}📁 {name}", key=f"tree_{path}")
                        if is_expanded:
                            render_tree(content, path, indent + 1)
                    else:
                        if st.button(f"{spacer}📄 {name}", key=f"file_{name}_{content.replace('/', '_').replace('\\', '_')}"):
                            file_info = next((fi for fi in st.session_state.workspace_files.get(name, []) if fi['relative'] == content), None)
                            if file_info:
                                st.session_state.selected_file = file_info
                                st.session_state.free_format_data = file_info.get('free_format', {})

                                for file_name, file_list in st.session_state.workspace_files.items():
                                    for fi in file_list:
                                        if fi['relative'] == content:
                                            if len(file_list) == 1:
                                                file_key = file_name
                                            else:
                                                file_key = f"{file_name} ({content})"
                                            break
                                    else:
                                        continue
                                    break
                                
                                st.session_state.selected_file_key = file_key
                                st.session_state.file_select_main = file_key
                                
                                file_opts = st.session_state.get('file_options', [])
                                file_opts_dict = st.session_state.get('file_options_dict', {})
                                
                                if file_key in file_opts:
                                    st.session_state.file_select_main_index = file_opts.index(file_key)
                                else:
                                    for i, opt in enumerate(file_opts):
                                        if file_opts_dict.get(opt) == content:
                                            st.session_state.file_select_main_index = i
                                            break
                                
                                st.rerun()
            
            with st.expander("📁 Tree View", key="tree_view_expander"):
                render_tree(tree)
            st.write(f"**{len(st.session_state.workspace_files)}** files loaded")

            st.divider()
            st.header("⚙️ Settings")
            
            st.checkbox("Show empty blocks", key="show_empty", value=False)
            st.checkbox("Expand all blocks", key="expand_all", value=True)  
            st.checkbox("Colorize default values", key="colorize_default", value=False)
            show_delete_keys = st.checkbox("Delete a key ❌", value=st.session_state.show_delete_keys, key="toggle_delete_keys")
            if show_delete_keys != st.session_state.show_delete_keys:
                st.session_state.show_delete_keys = show_delete_keys
                st.rerun()
            if st.button("A→Z", key="btn_sort"):
                if st.session_state.selected_file and st.session_state.selected_file.get('blocks'):
                    # Sort the dictionary by keys (block names) alphabetically
                    sorted_blocks = dict(sorted(st.session_state.selected_file['blocks'].items()))
                    st.session_state.selected_file['blocks'] = sorted_blocks
                    st.rerun()
            
            st.divider()
            if st.session_state.selected_file:
                st.header("Edit blocks")
                file_info = st.session_state.selected_file
                relative_path = file_info['relative']
                blocks = file_info['blocks']

                col1, col2 = st.columns([1, 1])
                with col1:
                    with st.popover("🗑️ Delete blocks"):
                        if blocks:
                            for block_name in list(blocks.keys()):
                                st.checkbox(f"&{block_name}", key=f"del_block_{relative_path}_{block_name}")
                            if st.button("Delete selected", key=f"del_blks_btn_{relative_path}"):
                                to_del = [b for b in blocks if st.session_state.get(f"del_block_{relative_path}_{b}")]
                                for b in to_del:
                                    del blocks[b]
                                save_file(relative_path, blocks)
                                st.rerun()
                        else:
                            st.caption("No blocks to delete")
                with col2:
                    if st.button("Remove empty blocks", key=f"rem_empty_{relative_path}"):
                        new_blocks = {name: b for name, b in blocks.items() if b.entries}
                        st.session_state.selected_file['blocks'] = new_blocks
                        save_file(relative_path, blocks)
                        st.rerun()

                filename = os.path.basename(file_info['path'])
                program_type = docs.get_program_type(filename)
                available_blocks = docs.get_available_blocks(program_type) if program_type else []
                existing_in_file = set(blocks.keys())
                possible = [b for b in available_blocks if docs.get_block_title(b) not in existing_in_file]
                
                if possible:
                    block_titles = {b: docs.get_block_title(b) for b in possible}
                    options = ["Add a namelist block"] + list(block_titles.values())
                    
                    col_sel, col_pos = st.columns([3, 1])
                    with col_sel:
                        selected_title = st.selectbox(" ", options, key=f"add_block_sel_{relative_path}")
                    with col_pos:
                        position = st.radio("Position", ["Top", "Bottom"], horizontal=True, key=f"add_pos_short_{relative_path}")
                    
                    if selected_title and selected_title != "Add a namelist block":
                        for block_name, title in block_titles.items():
                            if title == selected_title:
                                defaults = docs.get_block_defaults(block_name)
                                params, _ = docs.get_block_params(block_name)
                                new_block = parser.NamelistBlock(name=title)
                                for p_name, d_val in defaults.items():
                                    is_arr = params.get(p_name, {}).get('is_array', False) if isinstance(params.get(p_name), dict) else False
                                    if is_arr: continue
                                    new_block.entries[p_name] = parser.NamelistEntry(
                                        name=p_name, base_name=p_name, value=d_val,
                                        raw_line=f"{p_name} = {d_val}", is_array=False, array_index=""
                                    )
                                if position == "Top":
                                    new_blocks = {title: new_block}; new_blocks.update(blocks)
                                    blocks.clear(); blocks.update(new_blocks)
                                else:
                                    blocks[title] = new_block
                                save_file(relative_path, blocks)
                                st.rerun()
                                break
                
                with st.popover("Rename Block"):
                    if blocks:
                        rename_target = st.selectbox("Select block", list(blocks.keys()), key=f"rename_target_{relative_path}")
                        new_name = st.text_input("New name", value=rename_target, key=f"rename_input_{relative_path}", label_visibility="collapsed")
                        if st.button("Confirm", use_container_width=True, key=f"confirm_rename_{relative_path}"):
                            if new_name != rename_target:
                                if new_name not in blocks:
                                    block = blocks.pop(rename_target)
                                    block.name = new_name
                                    blocks[new_name] = block
                                    save_file(relative_path, blocks)
                                    st.rerun()
                                else:
                                    st.error("Name already exists")
                    else:
                        st.caption("No blocks to rename")

            st.divider()
            editor_width = st.slider("Editor width", 1, 4, 2, key="editor_width")
            pair_count = st.slider("Pairs per row", 1, 4, 3, key="pair_count_slider")
            doc_height = st.slider("Doc height", 400, 2000, 800, key="doc_height_slider")
            if doc_height != st.session_state.get('doc_height', 800):
                st.session_state.doc_height = doc_height
                st.rerun()
            if pair_count != st.session_state.get('pair_count', 3):
                st.session_state.pair_count = pair_count
                       
            if st.session_state.workspace_modified:
                st.warning(f"**{len(st.session_state.workspace_modified)}** modified")
    
    st.title("📂 Workspace")
    
    if not st.session_state.workspace_files:
        st.info("👈 Enter a workspace path and click 'Load Workspace' to start")
        return
    
    st.subheader("📄 Files")
    
    file_options_dict = {}
    file_options = []
    for file_name, file_list in st.session_state.workspace_files.items():
        if len(file_list) == 1:
            key = file_name
            file_options.append(file_name)
            file_options_dict[file_name] = file_name
        else:
            for f in file_list:
                key = f"{file_name} ({f['relative']})"
                file_options.append(key)
                file_options_dict[key] = f['relative']
    
    st.session_state.file_options = file_options
    st.session_state.file_options_dict = file_options_dict
    
    current_index = 0
    key = st.session_state.get('selected_file_key', '')
    if key and key in file_options:
        try:
            current_index = file_options.index(key)
        except ValueError:
            current_index = 0
    
    selected_index = st.session_state.get('file_select_main_index', current_index)
    
    if selected_index >= len(file_options):
        selected_index = 0
    
    if "file_select_main" not in st.session_state:
        st.session_state.file_select_main = file_options[selected_index]

    selected = st.selectbox(
        "Select file to edit",
        file_options,
        key="file_select_main"
    )    
    current_selected_index = file_options.index(selected) if selected in file_options else 0
    if st.session_state.get('file_select_main_index') != current_selected_index:
        st.session_state.file_select_main_index = current_selected_index
        st.session_state.selected_file_key = selected
        
        rel_path = file_options_dict.get(selected, selected)
        
        file_info = None
        for file_list in st.session_state.workspace_files.values():
            for fi in file_list:
                if fi['relative'] == rel_path:
                    file_info = fi
                    break
            if file_info:
                break
        
        if file_info:
            st.session_state.selected_file = file_info
       
    if st.session_state.selected_file:
        file_info = st.session_state.selected_file
        relative_path = file_info['relative']
        blocks = file_info['blocks']
        
        col_save, col_delete, col_add = st.columns([1, 1, 3])
        with col_save:
            if st.button("💾 Save", key=f"save_{relative_path}"):
                save_file(relative_path, blocks)
                st.success("Saved!")
                
        render_editor(blocks, relative_path)
    #else:
        st.info("Select a file from the dropdown above to edit")

def main():
    if 'pair_count' not in st.session_state:
        st.session_state.pair_count = 3
    render_workspace()

if __name__ == "__main__":
    main()


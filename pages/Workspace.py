import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import parser, docs, advise

st.set_page_config(page_title="Workspace", layout="wide")

if 'workspace_path' not in st.session_state:
    st.session_state.workspace_path = None
if 'workspace_files' not in st.session_state:
    st.session_state.workspace_files = {}
if 'workspace_modified' not in st.session_state:
    st.session_state.workspace_modified = set()
if 'selected_file' not in st.session_state:
    st.session_state.selected_file = None
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


DOC_DIR = docs.DOC_DIR

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
                    'blocks': None
                })
    
    for file in namelist_files:
        for file_info in namelist_files[file]:
            try:
                with open(file_info['path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                    file_info['blocks'] = parser.parse_namelist(content)
            except Exception as e:
                file_info['blocks'] = {}
    
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
                                    new_val = st.checkbox("", value=entry.value, key=f"{relative_path}_{block_name}_{param_name}", label_visibility="collapsed")
                                    entry.value = new_val
                                elif isinstance(entry.value, (int, float)):
                                    if isinstance(entry.value, int):
                                        new_val = st.number_input("", value=entry.value, key=f"{relative_path}_{block_name}_{param_name}", format="%d", label_visibility="collapsed")
                                    else:
                                        decimals = getattr(entry, 'decimals', 4)
                                        new_val = st.number_input("", value=float(entry.value), key=f"{relative_path}_{block_name}_{param_name}", format=f"%.{decimals}f", label_visibility="collapsed")
                                    entry.value = new_val
                                elif isinstance(entry.value, str):
                                    new_val = st.text_input("", value=entry.value, key=f"{relative_path}_{block_name}_{param_name}", label_visibility="collapsed")
                                    entry.value = new_val
                with col_delete:
                    with st.popover("➕"):
                        block_defaults = docs.get_block_params(block_name)
                        existing_params = set(block.entries.keys())
                        available_params = {k: v for k, v in block_defaults.items() if k not in existing_params}

                        if available_params:
                            for param, default_val in available_params.items():
                                st.checkbox(param, key=f"check_{relative_path}_{block_name}_{param}")

                            col_pbtn1, col_pbtn2 = st.columns(2)
                            with col_pbtn1:
                                if st.button("Add selected", key=f"add_{relative_path}_{block_name}"):
                                    for param in available_params:
                                        if st.session_state.get(f"check_{relative_path}_{block_name}_{param}"):
                                            block.entries[param] = parser.NamelistEntry(
                                                name=param,
                                                value=default_val,
                                                raw_line=f"{param} = {default_val}",
                                            )
                                    save_file(relative_path, blocks)
                                    st.rerun()
                            with col_pbtn2:
                                if st.button("Add All", key=f"addall_{relative_path}_{block_name}"):
                                    for param, default_val in available_params.items():
                                        block.entries[param] = parser.NamelistEntry(
                                            name=param,
                                            value=default_val,
                                            raw_line=f"{param} = {default_val}",
                                        )
                                    save_file(relative_path, blocks)
                                    st.rerun()
                        else:
                            st.caption("No params to add")

    with col_doc:
        st.subheader("📋 Documentation")
        
        selected_file = st.session_state.get("selected_file")
        current_file = os.path.basename(selected_file["path"]) if selected_file else None
        
        program_type = docs.get_program_type(current_file) if current_file else None
        available_blocks = docs.get_available_blocks(program_type) if program_type else []
        
        block_map = {docs.get_block_title(block): block for block in available_blocks}
        
        block_options = ["Select a namelist group"] + list(block_map.keys())
        selected = st.selectbox("", block_options, key="doc_select")
        
        if selected and selected != "Select a namelist group":
            rst_name = block_map[selected]
            doc_content = docs.find_docs(rst_name)            
            if doc_content:
                html = docs.render_rst(doc_content, block_name=selected)
                if html:
                    st.html(html)
                else:
                    st.warning(f"No documentation for {selected}")
        
        st.subheader("💡 Advise")
        
        if selected_file and selected_file.get("blocks"):
            blocks = selected_file["blocks"]
            current_file = os.path.basename(selected_file["path"])
            results = advise.run_all_checks(blocks, current_file)
            
            total_issues = len(results['blocks']) + len(results['params']) + len(results['values'])
            
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
            
            def render_tree(subtree, prefix="", indent=0):
                for name in sorted(subtree.keys()):
                    path = f"{prefix}/{name}" if prefix else name
                    content = subtree[name]
                    spacer = "&nbsp;&nbsp;&nbsp;&nbsp;" * indent
                    
                    if isinstance(content, dict):
                        if path not in st.session_state.workspace_tree_state:
                            st.session_state.workspace_tree_state[path] = False
                        is_expanded = st.checkbox(f"{spacer}📁 {name}", value=st.session_state.workspace_tree_state[path], key=f"tree_{path}")
                        st.session_state.workspace_tree_state[path] = is_expanded
                        if is_expanded:
                            render_tree(content, path, indent + 1)
                    else:
                        if st.button(f"{spacer}📄 {name}", key=f"file_{name}_{content.replace('/', '_').replace('\\', '_')}"):
                            file_info = next((fi for fi in st.session_state.workspace_files.get(name, []) if fi['relative'] == content), None)
                            if file_info:
                                st.session_state.selected_file = file_info
                                
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
            
            with st.expander("📁 Tree View"):
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
            
            st.divider()
            editor_width = st.slider("Editor width", 1, 4, 2, key="editor_width")
            pair_count = st.slider("Pairs per row", 1, 4, 3, key="pair_count_slider")
            doc_height = st.slider("Doc height", 400, 2000, 800, key="doc_height_slider")
                       
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
    
    st.divider()
    
    if st.session_state.selected_file:
        file_info = st.session_state.selected_file
        relative_path = file_info['relative']
        blocks = file_info['blocks']
        
        col_save, col_delete, col_add = st.columns([1, 1, 3])
        with col_save:
            if st.button("💾 Save", key=f"save_{relative_path}"):
                save_file(relative_path, blocks)
                st.success("Saved!")

        with col_delete: 
            with st.popover("🗑️ Delete blocks"):
                if blocks:
                    for block_name in list(blocks.keys()):
                        st.checkbox(f"&{block_name}", key=f"del_block_{relative_path}_{block_name}")
                    
                    if st.button("Delete selected", key=f"del_blks_{relative_path}"):
                        blocks_to_delete = [b for b in blocks if st.session_state.get(f"del_block_{relative_path}_{b}")]
                        for block_name in blocks_to_delete:
                            del blocks[block_name]
                        save_file(relative_path, blocks)
                        st.rerun()
                else:
                    st.caption("No blocks to delete")

        with col_add:
            filename = os.path.basename(file_info['path'])
            program_type = docs.get_program_type(filename)
            available_blocks = docs.get_available_blocks(program_type) if program_type else []
            existing_in_file = set(blocks.keys())
            possible = [b for b in available_blocks if docs.get_block_title(b) not in existing_in_file]
            
            if possible:
                block_titles = {b: docs.get_block_title(b) for b in possible}
                options = ["Select a namelist group"] + list(block_titles.values())
                
                col_select, col_pos = st.columns([3, 1])
                with col_select:
                    selected_title = st.selectbox("Add a block", options, key=f"add_block_{relative_path}")
                with col_pos:
                    position = st.radio("Position", ["Top", "Bottom"], horizontal=True, key=f"add_pos_{relative_path}")
                
                if selected_title and selected_title != "Select a namelist group":
                    for block_name, title in block_titles.items():
                        if title == selected_title:
                            defaults = docs.get_block_defaults(block_name)
                            new_block = parser.NamelistBlock(name=title)
                            for param_name, default_value in defaults.items():
                                new_block.entries[param_name] = parser.NamelistEntry(
                                    name=param_name,
                                    value=default_value,
                                    raw_line=f"{param_name} = {default_value}",
                                )
                            if position == "Top":
                                new_blocks = {title: new_block}
                                new_blocks.update(blocks)
                                blocks.clear()
                                blocks.update(new_blocks)
                            else:
                                blocks[title] = new_block
                            save_file(relative_path, file_info['blocks'])
                            st.rerun()
                            break
        
        render_editor(blocks, relative_path)
    #else:
        st.info("Select a file from the dropdown above to edit")


def main():
    if 'pair_count' not in st.session_state:
        st.session_state.pair_count = 3
    render_workspace()


if __name__ == "__main__":
    main()
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import parser, docs

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
if 'workspace_tree_selected' not in st.session_state:
    st.session_state.workspace_tree_selected = {}

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

            with st.expander(f"&{block_name} ({len(block.entries)})", expanded=st.session_state.expand_all):
                if not block.entries:
                    st.caption("Empty block")
                    continue
                
                entries = list(block.entries.items())
                pair_count = st.session_state.get('pair_count', 3)
                for i in range(0, len(entries), pair_count):
                    pair = entries[i:i+pair_count]
                    cols = st.columns([1, 1] * pair_count)
                    for j, (param_name, entry) in enumerate(pair):
                        idx = j * 2
                        with cols[idx]:
                            st.markdown(f"<div style='padding-top:8px'><b>{param_name}</b></div>", unsafe_allow_html=True)
                        with cols[idx + 1]:
                            if isinstance(entry.value, bool):
                                st.checkbox("", value=entry.value, disabled=True, key=f"{relative_path}_{block_name}_{param_name}", label_visibility="collapsed")
                            elif isinstance(entry.value, (int, float)):
                                if isinstance(entry.value, int):
                                    st.number_input("", value=entry.value, disabled=True, key=f"{relative_path}_{block_name}_{param_name}", format="%d", label_visibility="collapsed")
                                else:
                                    decimals = getattr(entry, 'decimals', 4)
                                    st.number_input("", value=float(entry.value), disabled=True, key=f"{relative_path}_{block_name}_{param_name}", format=f"%.{decimals}f", label_visibility="collapsed")
                            elif isinstance(entry.value, str):
                                st.text_input("", value=entry.value, disabled=True, key=f"{relative_path}_{block_name}_{param_name}", label_visibility="collapsed")

    with col_doc:
        st.subheader("📋 Documentation")
        
        block_options = ["<Select a namelist group>"] + list(blocks.keys())
        selected = st.selectbox("", block_options, key=f"doc_select_{relative_path}")
        
        if selected and selected != "<Select a block>":
            doc_content = docs.find_docs(selected)
            if doc_content:
                html = docs.render_rst(doc_content, block_name=selected)
                if html:
                    st.html(html)
                else:
                    st.warning(f"No documentation for {selected}")


def render_workspace():
    with st.sidebar:
        st.header("📚 Catalogue")
        
        workspace_path = st.text_input("Workspace path", value=st.session_state.workspace_path or "examples", key="workspace_path_input")
                
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
                        if path not in st.session_state.workspace_tree_selected:
                            st.session_state.workspace_tree_selected[path] = False

                        col1, col2 = st.columns([1, 8])
                        with col1:
                            selected = st.checkbox("📋", value=st.session_state.workspace_tree_selected[path],
                                key=f"select_{path}")
                            st.session_state.workspace_tree_selected[path] = selected

                        with col2:
                            expanded = st.checkbox(f"{spacer}📁 {name}",
                                value=st.session_state.workspace_tree_state[path],
                                key=f"tree_{path}")
                            st.session_state.workspace_tree_state[path] = expanded

                        if expanded:
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
            
            st.divider()
            st.subheader("📋 Copy to workspace")
            
            target_path = st.text_input("Target workspace folder path (relative or absolute)", value="", key="copy_target_path")
            
            if st.button("📋 Copy to workspace"):
                selected_subdirs = [
                    path
                    for path, selected in st.session_state.workspace_tree_selected.items()
                    if selected
                ]                
                if not selected_subdirs:
                    st.warning("No subdirectory selected in the tree view")
                elif target_path and os.path.isdir(target_path):
                    src_base = st.session_state.workspace_path
                    
                    for subdir_name in selected_subdirs:
                        src_dir = os.path.join(src_base, subdir_name)
                        dest_dir = os.path.join(target_path, subdir_name)
                        
                        if os.path.exists(src_dir):
                            import shutil
                            os.makedirs(dest_dir, exist_ok=True)
                            for item in os.listdir(src_dir):
                                src_item = os.path.join(src_dir, item)
                                dest_item = os.path.join(dest_dir, item)
                                if os.path.isdir(src_item):
                                    shutil.copytree(src_item, dest_item, dirs_exist_ok=True)
                                else:
                                    shutil.copy2(src_item, dest_item)
                    
                    st.success(f"Copied {len(selected_subdirs)} folder(s) to {target_path}")
                else:
                    st.error("Invalid target directory")
            
            st.divider()
            st.header("⚙️ Settings")
            
            show_empty = st.checkbox("Show empty", value=st.session_state.show_empty)
            expand_all = st.checkbox("Expand all", value=st.session_state.expand_all)
            
            editor_width = st.slider("Editor width", 1, 4, 2, key="editor_width")
            pair_count = st.slider("Pairs per row", 1, 4, 3, key="pair_count_slider")
            doc_height = st.slider("Doc height", 400, 2000, 800, key="doc_height_slider")
            
            if show_empty != st.session_state.show_empty:
                st.session_state.show_empty = show_empty
            
            if expand_all != st.session_state.expand_all:
                st.session_state.expand_all = expand_all
            
            if pair_count != st.session_state.get('pair_count', 3):
                st.session_state.pair_count = pair_count
            
            st.divider()
            st.write(f"**{len(st.session_state.workspace_files)}** files loaded")
            
            if st.session_state.workspace_modified:
                st.warning(f"**{len(st.session_state.workspace_modified)}** modified")
    
    st.title("📚 Catalogue Explorer")
    
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
        "Select file to explore. No modification allowed.",
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
        
        render_editor(blocks, relative_path)
        st.info("Select a file from the dropdown above to view")


def main():
    if 'pair_count' not in st.session_state:
        st.session_state.pair_count = 3
    render_workspace()


if __name__ == "__main__":
    main()
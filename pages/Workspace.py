import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import parser

st.set_page_config(page_title="Workspace", layout="wide")

if 'workspace_path' not in st.session_state:
    st.session_state.workspace_path = None
if 'workspace_files' not in st.session_state:
    st.session_state.workspace_files = {}
if 'workspace_modified' not in st.session_state:
    st.session_state.workspace_modified = set()
if 'selected_file' not in st.session_state:
    st.session_state.selected_file = None
if 'show_empty' not in st.session_state:
    st.session_state.show_empty = False
if 'expand_all' not in st.session_state:
    st.session_state.expand_all = True


DOC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "namelists")


def find_docs(block_name):
    possible_files = [
        os.path.join(DOC_DIR, f"{block_name.lower()}.rst"),
        os.path.join(DOC_DIR, f"{block_name.replace('_', '-').lower()}.rst"),
    ]
    for f in possible_files:
        if os.path.exists(f):
            with open(f, 'r', encoding='utf-8') as file:
                content = file.read()
                for old, new in {':ref:': ':code:', ':file:': ':code:',
                                 ':cite:t:': ':code:'}.items():
                    content = content.replace(old, new)
                return content
    return None


def render_rst(rst_content, block_name=None):
    if not rst_content:
        return ""
    
    try:
        from docutils.core import publish_doctree, publish_from_doctree
        
        doctree = publish_doctree(rst_content)
        html = publish_from_doctree(doctree, writer_name='html')
        
        if isinstance(html, bytes):
            html = html.decode('utf-8')
        
        height = st.session_state.get('doc_height', 400)
        
        html = f"""
        <div style="height: {height}px; overflow-y: auto;">
        <style>
        table {{ border-collapse: collapse; margin: 1em 0; }}
        table td, table th {{ border: 1px solid #555; padding: 6px 10px; }}
        table th {{ background: #444; color: #fff; font-weight: bold; }}
        code, pre {{ background: #f5f5f5; color: #333; padding: 2px 4px; }}
        .warning {{ background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; }}
        </style>
        {html}
        </div>
        """
        
        return html
    except Exception as e:
        return f"<pre>Error parsing RST: {e}</pre>"


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

    with col_doc:
        st.subheader("📋 Documentation")
        
        block_options = ["<Select a namelist group>"] + list(blocks.keys())
        selected = st.selectbox("", block_options, key=f"doc_select_{relative_path}")
        
        if selected and selected != "<Select a block>":
            doc_content = find_docs(selected)
            if doc_content:
                html = render_rst(doc_content, block_name=selected)
                if html:
                    st.html(html)
                else:
                    st.warning(f"No documentation for {selected}")


def render_workspace():
    with st.sidebar:
        st.header("📁 Workspace")
        
        workspace_path = st.text_input("Workspace path", value=st.session_state.workspace_path or "", key="workspace_path_input")
                
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
    
    st.title("📂 Workspace")
    
    if not st.session_state.workspace_files:
        st.info("👈 Enter a workspace path and click 'Load Workspace' to start")
        return
    
    st.subheader("📄 Files")
    
    file_options = []
    for file_name, file_list in st.session_state.workspace_files.items():
        if len(file_list) == 1:
            file_options.append(f"{file_name}")
        else:
            for i, f in enumerate(file_list):
                file_options.append(f"{file_name} ({f['relative']})")
    
    selected = st.selectbox("Select file to edit", file_options, key="file_select_main")
    
    if selected:
        if "(" in selected and ")" in selected:
            file_name = selected.split(" (")[0]
            rel_path = selected.split(" (")[1].rstrip(")")
            file_info = next(f for f in st.session_state.workspace_files[file_name] if f['relative'] == rel_path)
        else:
            file_name = selected
            file_info = st.session_state.workspace_files[file_name][0]
        
        st.session_state.selected_file = file_info
    
    st.divider()
    
    if st.session_state.selected_file:
        file_info = st.session_state.selected_file
        relative_path = file_info['relative']
        blocks = file_info['blocks']
        
        with st.expander(f"📄 {relative_path} ({len(blocks)} blocks)", expanded=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("💾 Save", key=f"save_{relative_path}"):
                    save_file(relative_path, blocks)
                    st.success("Saved!")
            with col2:
                if relative_path in st.session_state.workspace_modified:
                    st.warning("Modified")
                else:
                    st.success("Saved")
        
        render_editor(blocks, relative_path)
    else:
        st.info("Select a file from the dropdown above to edit")


def main():
    if 'pair_count' not in st.session_state:
        st.session_state.pair_count = 3
    render_workspace()


if __name__ == "__main__":
    main()
import streamlit as st
import parser

st.set_page_config(page_title="Meso-NH Namelist Editor", layout="wide")

if 'namelist_blocks' not in st.session_state:
    st.session_state.namelist_blocks = {}
if 'current_file' not in st.session_state:
    st.session_state.current_file = None
if 'show_empty' not in st.session_state:
    st.session_state.show_empty = False
if 'expand_all' not in st.session_state:
    st.session_state.expand_all = True
if 'selected_block' not in st.session_state:
    st.session_state.selected_block = None
if 'doc_height' not in st.session_state:
    st.session_state.doc_height = 400


DOC_DIR = "namelists"


def find_docs(block_name):
    import os
    doc_dir = os.path.join(os.path.dirname(__file__), DOC_DIR)
    possible_files = [
        os.path.join(doc_dir, f"{block_name.lower()}.rst"),
        os.path.join(doc_dir, f"{block_name.replace('_', '-').lower()}.rst"),
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


if 'previous_state' not in st.session_state:
    st.session_state.previous_state = None


def save_previous_state():
    blocks = st.session_state.namelist_blocks
    previous = {}
    for name, block in blocks.items():
        entries = {}
        for param_name, entry in block.entries.items():
            entries[param_name] = {'name': entry.name, 'value': entry.value, 'raw_line': entry.raw_line}
        previous[name] = {'entries': entries, 'raw_lines': list(block.raw_lines)}
    st.session_state.previous_state = previous


def undo():
    if st.session_state.previous_state:
        blocks = {}
        for name, data in st.session_state.previous_state.items():
            block = parser.NamelistBlock(name=name)
            block.entries = {}
            for param_name, entry_data in data['entries'].items():
                block.entries[param_name] = parser.NamelistEntry(
                    name=entry_data['name'],
                    value=entry_data['value'],
                    raw_line=entry_data['raw_line']
                )
            block.raw_lines = data['raw_lines']
            blocks[name] = block
        st.session_state.namelist_blocks = blocks
        st.session_state.previous_state = None
        st.rerun()


def render_namelist_view():
    if not st.session_state.namelist_blocks:
        return

    st.subheader("Editor")

    col_dl, col_rst = st.columns([1, 1])
    with col_dl:
        file_content = parser.write_namelist(st.session_state.namelist_blocks)
        st.download_button("Download", file_content, file_name=st.session_state.current_file or "namelist.nam", mime="text/plain")
    with col_rst:
        if st.button("Reset"):
            st.session_state.namelist_blocks = {}
            st.session_state.current_file = None
            st.session_state.previous_state = None
            st.rerun()

    st.divider()

    editor_width = st.session_state.get('editor_width', 2)
    col_editor, col_doc = st.columns([editor_width, 1])
    
    with col_editor:
        for block_name in st.session_state.namelist_blocks:
            block = st.session_state.namelist_blocks[block_name]
            
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
                                new_val = st.checkbox("", value=entry.value, key=f"{block_name}_{param_name}", label_visibility="collapsed")
                                entry.value = new_val
                            elif isinstance(entry.value, (int, float)):
                                if isinstance(entry.value, int):
                                    new_val = st.number_input("", value=entry.value, key=f"{block_name}_{param_name}", format="%d", label_visibility="collapsed")
                                else:
                                    decimals = getattr(entry, 'decimals', 4)
                                    new_val = st.number_input("", value=float(entry.value), key=f"{block_name}_{param_name}", format=f"%.{decimals}f", label_visibility="collapsed")
                                entry.value = new_val
                            elif isinstance(entry.value, str):
                                new_val = st.text_input("", value=entry.value, key=f"{block_name}_{param_name}", label_visibility="collapsed")
                                entry.value = new_val

    with col_doc:
        st.subheader("Documentation")
        
        block_options = ["<Select a namelist group>"] + list(st.session_state.namelist_blocks.keys())
        selected = st.selectbox("", block_options, key="doc_select")
        
        if selected and selected != "<Select a block>":
            doc_content = find_docs(selected)
            if doc_content:
                html = render_rst(doc_content, block_name=selected)
                if html:
                    st.html(html)
                else:
                    st.warning(f"No documentation for {selected}")


def render_upload():
    with st.sidebar:
        st.header("")

        uploaded_file = st.file_uploader("Upload namelist", type=['nam'])

        if uploaded_file is not None:
            if st.session_state.current_file != uploaded_file.name:
                content = uploaded_file.getvalue().decode("utf-8")
                blocks = parser.parse_namelist(content)

                if blocks:
                    st.session_state.namelist_blocks = blocks
                    st.session_state.current_file = uploaded_file.name
                    st.session_state.previous_state = None
                    save_previous_state()
                    st.success(f"Loaded: {uploaded_file.name}")
                else:
                    st.error("Could not parse")

        st.divider()
        st.header("Settings")
        
        show_empty = st.checkbox("Show empty", value=st.session_state.show_empty)
        expand_all = st.checkbox("Expand all", value=st.session_state.expand_all)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.button("A→Z", key="btn_sort", disabled=True)
        with col2:
            if st.button("Remove empty", key="btn_remove_empty"):
                blocks = st.session_state.namelist_blocks
                new_blocks = {name: block for name, block in blocks.items() if block.entries}
                st.session_state.namelist_blocks = new_blocks
                st.rerun()
        
        editor_width = st.slider("Editor width", 1, 4, 2, key="editor_width")
        pair_count = st.slider("Pairs per row", 1, 4, 3, key="pair_count_slider")
        if pair_count != st.session_state.get('pair_count', 3):
            st.session_state.pair_count = pair_count
        doc_height = st.slider("Doc height", 400, 2000, 800, key="doc_height_slider")
        if doc_height != st.session_state.get('doc_height', 400):
            st.session_state.doc_height = doc_height
            st.rerun()
        
        if show_empty != st.session_state.show_empty:
            st.session_state.show_empty = show_empty
        
        if expand_all != st.session_state.expand_all:
            st.session_state.expand_all = expand_all
        
        if show_empty != st.session_state.show_empty or expand_all != st.session_state.expand_all:
            st.rerun()
        
        if st.session_state.namelist_blocks:
            block_names = list(st.session_state.namelist_blocks.keys())
            empty_count = sum(1 for b in st.session_state.namelist_blocks.values() if not b.entries)
            st.sidebar.write(f"**{len(block_names)}** blocks, **{sum(len(b.entries) for b in st.session_state.namelist_blocks.values())}** params ({empty_count} empty)")
            if st.sidebar.button("Show raw"):
                st.sidebar.code(parser.write_namelist(st.session_state.namelist_blocks), language="fortran")


def main():
    if 'pair_count' not in st.session_state:
        st.session_state.pair_count = 3
    st.title("Meso-NH Namelist Editor")
    render_upload()
    render_namelist_view()


if __name__ == "__main__":
    main()
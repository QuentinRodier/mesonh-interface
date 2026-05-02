import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import parser, docs, advise

st.set_page_config(page_title="Namelist Editor", layout="wide")

if 'namelist_blocks' not in st.session_state:
    st.session_state.namelist_blocks = {}
if 'current_file' not in st.session_state:
    st.session_state.current_file = None
if 'show_empty' not in st.session_state:
    st.session_state.show_empty = False
if 'expand_all' not in st.session_state:
    st.session_state.expand_all = True
if 'colorize_default' not in st.session_state:
    st.session_state.colorize_default = True
if 'selected_block' not in st.session_state:
    st.session_state.selected_block = None
if 'doc_height' not in st.session_state:
    st.session_state.doc_height = 400
if 'show_delete_keys' not in st.session_state:
    st.session_state.show_delete_keys = False

def is_default_value(block_name, param_name, current_value):
    defaults = docs.get_block_defaults(block_name)

    if param_name not in defaults:
        return False

    default_value = defaults[param_name]

    try:
        return str(default_value).strip().lower() == str(current_value).strip().lower()
    except:
        return default_value == current_value

def save_previous_state():
    blocks = st.session_state.namelist_blocks
    previous = {}
    for name, block in blocks.items():
        entries = {}
        for param_name, entry in block.entries.items():
            entries[param_name] = {'name': entry.name, 'value': entry.value, 'raw_line': entry.raw_line, 'decimals': entry.decimals}
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
                    raw_line=entry_data['raw_line'],
                    decimals=entry_data.get('decimals', 4)
                )
            block.raw_lines = data['raw_lines']
            blocks[name] = block
        st.session_state.namelist_blocks = blocks
        st.session_state.previous_state = None
        st.rerun()


def render_namelist_view():
    if not st.session_state.namelist_blocks:
        return

    file_content = parser.write_namelist(st.session_state.namelist_blocks)
    st.download_button("Download", file_content, file_name=st.session_state.current_file or "namelist.nam", mime="text/plain")

    st.divider()

    editor_width = st.session_state.get('editor_width', 2)
    col_editor, col_doc = st.columns([editor_width, 1])
    
    with col_editor:
        for block_name in st.session_state.namelist_blocks:
            block = st.session_state.namelist_blocks[block_name]
            
            if not block.entries and not st.session_state.show_empty:
                continue

            col_block, col_delete = st.columns([10, 1])
            with col_delete:
                with st.popover("➕"):
                        block_defaults = docs.get_block_params(block_name)
                        existing_params = set(block.entries.keys())
                        available_params = {k: v for k, v in block_defaults.items() if k not in existing_params}
                        
                        if available_params:
                            for param, default_val in available_params.items():
                                st.checkbox(param, key=f"check_{block_name}_{param}")
                            
                            col_pbtn1, col_pbtn2 = st.columns(2)
                            with col_pbtn1:
                                if st.button("Add selected", key=f"add_{block_name}"):
                                    for param, default_val in available_params.items():
                                        if st.session_state.get(f"check_{block_name}_{param}"):
                                            block.entries[param] = parser.NamelistEntry(
                                                name=param,
                                                value=default_val,
                                                raw_line=f"{param} = {default_val}",
                                            )
                                    st.rerun()
                            with col_pbtn2:
                                if st.button("Add All", key=f"addall_{block_name}"):
                                    for param, default_val in available_params.items():
                                        block.entries[param] = parser.NamelistEntry(
                                            name=param,
                                            value=default_val,
                                            raw_line=f"{param} = {default_val}",
                                        )
                                    st.rerun()
                        else:
                            st.caption("No params to add")
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
                                    if st.button("❌", key=f"del_{block_name}_{param_name}"):
                                        del block.entries[param_name]
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
        st.subheader("📋 Documentation")
        
        current_file = st.session_state.current_file
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
    
    with col_doc:
        st.subheader("💡 Advise")
        
        if st.session_state.namelist_blocks and st.session_state.current_file:
            current_file = st.session_state.current_file
            results = advise.run_all_checks(st.session_state.namelist_blocks, current_file)
            
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
            st.info("Load a namelist to run Advise checks")


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
        st.header("⚙️ Settings")
        
        st.checkbox("Show empty blocks", key="show_empty", value=False)
        st.checkbox("Expand all blocks", key="expand_all", value=True)  
        st.checkbox("Colorize default values", key="colorize_default", value=False)

        col1, col2 = st.columns([1, 1])
        with col1:
            st.button("A→Z", key="btn_sort", disabled=True)
        with col2:
            if st.button("Remove empty", key="btn_remove_empty"):
                blocks = st.session_state.namelist_blocks
                new_blocks = {name: block for name, block in blocks.items() if block.entries}
                st.session_state.namelist_blocks = new_blocks
        
        show_delete_keys = st.checkbox("Delete a key ❌", value=st.session_state.show_delete_keys, key="toggle_delete_keys")
        if show_delete_keys != st.session_state.show_delete_keys:
            st.session_state.show_delete_keys = show_delete_keys
            st.rerun()
        
        current_file = st.session_state.current_file
        if current_file:
            program_type = docs.get_program_type(current_file)
            available_blocks = docs.get_available_blocks(program_type) if program_type else []
            existing_blocks = list(st.session_state.namelist_blocks.keys())
            existing_titles = {docs.get_block_title(b) for b in available_blocks if docs.get_block_title(b) in existing_blocks}
            possible_blocks = [b for b in available_blocks if docs.get_block_title(b) not in existing_blocks]
            
            if possible_blocks:
                block_titles = {b: docs.get_block_title(b) for b in possible_blocks}
                block_options = ["Select a namelist group"] + list(block_titles.values())
                col_add1, col_add2 = st.columns([3, 1])
                with col_add1:
                    selected_title = st.selectbox("Add a block", block_options, key="add_block_select")
                with col_add2:
                    position = st.radio("Position", ["Top", "Bottom"], horizontal=True, key="add_block_position")
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
                                new_blocks.update(st.session_state.namelist_blocks)
                                st.session_state.namelist_blocks = new_blocks
                            else:
                                st.session_state.namelist_blocks[title] = new_block
                            st.rerun()
                            break
        
        with st.popover("🗑️ Delete blocks"):
            if st.session_state.namelist_blocks:
                for block_name in list(st.session_state.namelist_blocks.keys()):
                    st.checkbox(f"&{block_name}", key=f"del_block_{block_name}")
                
                if st.button("Delete selected", key="del_blocks_btn"):
                    blocks_to_delete = [b for b in st.session_state.namelist_blocks if st.session_state.get(f"del_block_{b}")]
                    for block_name in blocks_to_delete:
                        del st.session_state.namelist_blocks[block_name]
                    st.rerun()
            else:
                st.caption("No blocks to delete")
        
        st.divider()

        if st.session_state.namelist_blocks:
            block_names = list(st.session_state.namelist_blocks.keys())
            empty_count = sum(1 for b in st.session_state.namelist_blocks.values() if not b.entries)
            st.sidebar.write(f"**{len(block_names)}** blocks, **{sum(len(b.entries) for b in st.session_state.namelist_blocks.values())}** params ({empty_count} empty)")
            if st.sidebar.button("Show raw"):
                st.sidebar.code(parser.write_namelist(st.session_state.namelist_blocks), language="fortran")

        st.divider()

        editor_width = st.slider("Editor width", 1, 4, 2, key="editor_width")
        pair_count = st.slider("Pairs per row", 1, 4, 3, key="pair_count_slider")
        if pair_count != st.session_state.get('pair_count', 3):
            st.session_state.pair_count = pair_count
        doc_height = st.slider("Doc height", 400, 2000, 800, key="doc_height_slider")
        if doc_height != st.session_state.get('doc_height', 400):
            st.session_state.doc_height = doc_height
            st.rerun()

def main():
    if 'pair_count' not in st.session_state:
        st.session_state.pair_count = 3
    st.title("📝 Single Namelist Editor")
    render_upload()
    render_namelist_view()


if __name__ == "__main__":
    main()
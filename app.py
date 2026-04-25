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
    st.session_state.expand_all = False
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

    for block_name in st.session_state.namelist_blocks:
        block = st.session_state.namelist_blocks[block_name]
        
        if not block.entries and not st.session_state.show_empty:
            continue

        with st.expander(f"&{block_name} ({len(block.entries)} params)", expanded=st.session_state.expand_all):
            if not block.entries:
                st.caption("Empty block")
                continue
            
            cols = st.columns([1, 2])
            
            for param_name, entry in block.entries.items():
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.markdown(f"**{param_name}**")
                with col2:
                    if isinstance(entry.value, bool):
                        new_val = st.checkbox("", value=entry.value, key=f"{block_name}_{param_name}", label_visibility="collapsed")
                        entry.value = new_val
                    elif isinstance(entry.value, (int, float)):
                        if isinstance(entry.value, int):
                            new_val = st.number_input("", value=entry.value, key=f"{block_name}_{param_name}", format="%d", label_visibility="collapsed")
                        else:
                            new_val = st.number_input("", value=float(entry.value), key=f"{block_name}_{param_name}", format="%.4f", label_visibility="collapsed")
                        entry.value = new_val
                    elif isinstance(entry.value, str):
                        new_val = st.text_input("", value=entry.value, key=f"{block_name}_{param_name}", label_visibility="collapsed")
                        entry.value = new_val


def render_upload():
    with st.sidebar:
        st.header("File")

        uploaded_file = st.file_uploader(
            "Upload namelist",
            type=['nam', 'nam_LFI']
        )

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
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            show_empty = st.checkbox("Show empty", value=st.session_state.show_empty)
        with col2:
            expand_all = st.checkbox("Expand all", value=st.session_state.expand_all)
        with col3:
            st.button("A→Z", disabled=True)
        
        if show_empty != st.session_state.show_empty:
            st.session_state.show_empty = show_empty
        
        if expand_all != st.session_state.expand_all:
            st.session_state.expand_all = expand_all
        
        if show_empty != st.session_state.show_empty or expand_all != st.session_state.expand_all:
            st.rerun()
        
        if show_empty != st.session_state.show_empty:
            st.session_state.show_empty = show_empty
            st.rerun()

        if st.session_state.namelist_blocks:
            block_names = list(st.session_state.namelist_blocks.keys())
            empty_count = sum(1 for b in st.session_state.namelist_blocks.values() if not b.entries)
            st.sidebar.write(f"**{len(block_names)}** blocks, **{sum(len(b.entries) for b in st.session_state.namelist_blocks.values())}** params ({empty_count} empty)")
            if st.sidebar.button("Show raw"):
                st.sidebar.code(parser.write_namelist(st.session_state.namelist_blocks), language="fortran")


def main():
    st.title("Meso-NH Namelist Editor")
    render_upload()
    render_namelist_view()


if __name__ == "__main__":
    main()
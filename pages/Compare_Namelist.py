import streamlit as st
import os
from modules import parser, docs

st.set_page_config(page_title="Compare Namelists", layout="wide")

for key, default in [
    ('namelist_a', {}), ('namelist_b', {}),
    ('free_format_a', {}), ('free_format_b', {}),
    ('file_name_a', None), ('file_name_b', None),
    ('program_a', None), ('program_b', None),
    ('diff_results', None),
    ('show_diff_only', True),
    ('show_common', True),
    ('expand_all', True),
    ('hide_default', False),
    ('workspace_files', {}),
    ('workspace_path', None),
    ('upload_method', 'File upload'),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def compare_blocks(blocks_a, blocks_b, hide_default=False):
    all_block_names = set(blocks_a.keys()) | set(blocks_b.keys())
    result = {'only_a': {}, 'only_b': {}, 'different': {}, 'common': {}}

    for name in sorted(all_block_names):
        in_a = name in blocks_a
        in_b = name in blocks_b

        if in_a and not in_b:
            result['only_a'][name] = blocks_a[name]
        elif in_b and not in_a:
            result['only_b'][name] = blocks_b[name]
        else:
            entries_a = blocks_a[name].entries
            entries_b = blocks_b[name].entries
            only_a = {}
            only_b = {}
            changed = {}
            for pname, entry_a in entries_a.items():
                if pname not in entries_b:
                    if hide_default and _is_default_value(name, pname, entry_a.value):
                        continue
                    only_a[pname] = entry_a
                elif _values_differ(entry_a.value, entries_b[pname].value):
                    changed[pname] = (entry_a, entries_b[pname])
            for pname, entry_b in entries_b.items():
                if pname not in entries_a:
                    if hide_default and _is_default_value(name, pname, entry_b.value):
                        continue
                    only_b[pname] = entry_b

            if only_a or only_b or changed:
                result['different'][name] = {
                    'only_a': only_a, 'only_b': only_b, 'changed': changed,
                    'total_a': len(entries_a), 'total_b': len(entries_b),
                }
            else:
                result['common'][name] = blocks_a[name]

    return result


def _values_differ(val_a, val_b):
    if isinstance(val_a, float) and isinstance(val_b, float):
        return abs(val_a - val_b) > 1e-10
    return val_a != val_b


def _is_default_value(block_name, param_name, current_value):
    defaults = docs.get_block_defaults(block_name)
    if param_name not in defaults:
        return False
    try:
        return str(defaults[param_name]).strip().lower() == str(current_value).strip().lower()
    except Exception:
        return defaults[param_name] == current_value


def render_status_bar():
    fa = st.session_state.file_name_a
    fb = st.session_state.file_name_b
    pa = st.session_state.program_a
    pb = st.session_state.program_b

    col1, col2, col3, col4 = st.columns([3, 3, 2, 2])
    with col1:
        st.write(f"**File A:** {fa or '—'}")
    with col2:
        st.write(f"**File B:** {fb or '—'}")
    with col3:
        st.write(f"**Program:** {pa or 'unknown'}")
    with col4:
        if pa and pb:
            if pa == pb:
                st.success("✓ Same type")
            else:
                st.error("✗ Different types!")
        elif fa and fb:
            st.warning("Type unknown for one or both files")


def render_diff_results(diff):
    if not diff:
        return

    total_a = len([b for b in st.session_state.namelist_a])
    total_b = len([b for b in st.session_state.namelist_b])
    n_only_a = len(diff['only_a'])
    n_only_b = len(diff['only_b'])
    n_diff = len(diff['different'])
    n_common = len(diff['common'])

    st.caption(f"Blocks — A: {total_a}  |  B: {total_b}  |  "
               f"🔴 Only in A: {n_only_a}  |  🔵 Only in B: {n_only_b}  |  "
               f"🟡 Different: {n_diff}  |  🟢 Common: {n_common}")

    sections = []

    if diff['only_a']:
        sections.append(("🔴 Only in A", diff['only_a'], 'only_a'))
    if diff['only_b']:
        sections.append(("🔵 Only in B", diff['only_b'], 'only_b'))
    if diff['different']:
        sections.append(("🟡 Different blocks", diff['different'], 'different'))
    if diff['common'] and st.session_state.show_common:
        sections.append(("🟢 Common blocks (identical)", diff['common'], 'common'))

    for label, data, kind in sections:
        with st.expander(f"{label} ({len(data)})", expanded=st.session_state.expand_all):
            if kind in ('only_a', 'only_b', 'common'):
                for block_name, block in data.items():
                    st.markdown(f"**&{block_name}** ({len(block.entries)} params)")
                    if kind == 'common' and not st.session_state.show_diff_only:
                        for pname, entry in block.entries.items():
                            st.text(f"  {pname} = {entry.value}")
                    elif kind != 'common':
                        for pname, entry in block.entries.items():
                            st.text(f"  {pname} = {entry.value}")
            elif kind == 'different':
                for block_name, info in data.items():
                    n_changed = len(info['changed'])
                    n_only_a = len(info['only_a'])
                    n_only_b = len(info['only_b'])
                    total = max(info['total_a'], info['total_b'])
                    st.markdown(f"**&{block_name}** — {n_changed} changed, "
                                f"{n_only_a} only in A, {n_only_b} only in B "
                                f"({total} total params)")
                    if info['changed'] or info['only_a'] or info['only_b']:
                        rows = []
                        for pname, (ea, eb) in info['changed'].items():
                            rows.append({"Parameter": pname, "File A": str(ea.value), "File B": str(eb.value)})
                        for pname, ea in info['only_a'].items():
                            rows.append({"Parameter": pname, "File A": str(ea.value), "File B": "—"})
                        for pname, eb in info['only_b'].items():
                            rows.append({"Parameter": pname, "File A": "—", "File B": str(eb.value)})
                        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_namelist_text(blocks, free_format, label):
    lines = []
    for block_name, block in blocks.items():
        lines.append(f"&{block_name}")
        for pname, entry in block.entries.items():
            lines.append(f"  {pname} = {entry.value}")
        lines.append("/\n")
    for key, val in free_format.items():
        lines.append(f"{key} = {val}")
    text = "\n".join(lines) if lines else "(empty)"
    st.code(text, language="fortran")


def render_sidebar():
    with st.sidebar:

        upload_method = st.radio(
            " ",
            ["File upload", "Workspace path"],
            key="upload_method",
        )

        if upload_method == "File upload":
            _render_file_upload()
        else:
            _render_workspace_upload()

        st.divider()
        st.header("⚙️ Settings")
        st.checkbox("Show differences only", key="show_diff_only")
        st.checkbox("Show common blocks", key="show_common")
        st.checkbox("Expand all blocks", key="expand_all")
        st.checkbox("Hide default values", key="hide_default",
                     help="When a parameter has its default value and is absent in the other file, it is not shown as a difference.")


def _render_file_upload():
    col_a, col_b = st.columns(2)
    with col_a:
        uploaded_a = st.file_uploader("Namelist A", key="upload_a")
        if uploaded_a is not None:
            _process_upload(uploaded_a, 'a')
    with col_b:
        uploaded_b = st.file_uploader("Namelist B", key="upload_b")
        if uploaded_b is not None:
            _process_upload(uploaded_b, 'b')


def _process_upload(uploaded_file, side):
    content = uploaded_file.getvalue().decode("utf-8")
    blocks, free_format = parser.parse_namelist(content)
    if blocks or free_format:
        prog = docs.get_program_type(uploaded_file.name)
        st.session_state[f'namelist_{side}'] = blocks
        st.session_state[f'free_format_{side}'] = free_format
        st.session_state[f'file_name_{side}'] = uploaded_file.name
        st.session_state[f'program_{side}'] = prog
        st.success(f"Loaded: {uploaded_file.name}")
        if prog:
            st.caption(f"Type: {prog}")


def _render_workspace_upload():
    ws_path = st.text_input("Workspace path", key="ws_path")
    if st.button("📂 Load Workspace", key="load_ws"):
        if ws_path and os.path.isdir(ws_path):
            files = {}
            for root, dirs, fnames in os.walk(ws_path):
                for f in fnames:
                    if f.endswith('.nam') or '.nam' in f:
                        full = os.path.join(root, f)
                        rel = os.path.relpath(full, ws_path)
                        if f not in files:
                            files[f] = []
                        files[f].append({'path': full, 'relative': rel})
            st.session_state.workspace_files = files
            st.session_state.workspace_path = ws_path
            st.success(f"Found namelists in workspace")
        else:
            st.error("Invalid directory")

    if st.session_state.workspace_files:
        flat_options = []
        for basename, flist in st.session_state.workspace_files.items():
            for fi in flist:
                label = f"{basename} ({fi['relative']})" if len(flist) > 1 else basename
                flat_options.append((label, fi))
        opts = [opt[0] for opt in flat_options]

        sel_a = st.selectbox("Select file A", opts, key="ws_sel_a")
        sel_b = st.selectbox("Select file B", opts, key="ws_sel_b")

        if st.button("Compare selected", key="compare_ws"):
            for label, fi in flat_options:
                if label == sel_a:
                    _load_workspace_file(fi, 'a')
                if label == sel_b:
                    _load_workspace_file(fi, 'b')


def _load_workspace_file(fi, side):
    try:
        with open(fi['path'], 'r', encoding='utf-8') as f:
            content = f.read()
        blocks, free_format = parser.parse_namelist(content)
        prog = docs.get_program_type(fi['path'])
        st.session_state[f'namelist_{side}'] = blocks
        st.session_state[f'free_format_{side}'] = free_format
        st.session_state[f'file_name_{side}'] = os.path.basename(fi['path'])
        st.session_state[f'program_{side}'] = prog
        st.success(f"Loaded: {fi['relative']}")
    except Exception as e:
        st.error(f"Error loading {fi['relative']}: {e}")


def main():
    render_sidebar()

    st.title("⚖️ Compare Namelists")

    fa = st.session_state.file_name_a
    fb = st.session_state.file_name_b

    if not fa and not fb:
        st.info("👈 Upload or select two namelist files from the sidebar to compare them.")
        return

    if fa and not fb:
        st.info("File A loaded. Upload or select File B to compare.")
        render_status_bar()
        return

    if fb and not fa:
        st.info("File B loaded. Upload or select File A to compare.")
        render_status_bar()
        return

    render_status_bar()

    pa = st.session_state.program_a
    pb = st.session_state.program_b
    if pa and pb and pa != pb:
        st.warning(f"⚠️ The two namelists belong to different programs: "
                   f"'{pa}' vs '{pb}'. Comparison may not be meaningful.")

    blocks_a = st.session_state.namelist_a
    blocks_b = st.session_state.namelist_b
    free_a = st.session_state.free_format_a
    free_b = st.session_state.free_format_b

    if blocks_a and blocks_b:
        diff = compare_blocks(blocks_a, blocks_b, hide_default=st.session_state.hide_default)
        st.session_state.diff_results = diff
        render_diff_results(diff)
        col_a, col_b = st.columns(2)
        with col_a:
            st.write(f"{fa or '—'}")
            sorted_blocks_a = dict(sorted(blocks_a.items()))
            _render_namelist_text(sorted_blocks_a, free_a, "File A")
        with col_b:
            st.write(f"{fb or '—'}")
            sorted_blocks_b = dict(sorted(blocks_b.items()))
            _render_namelist_text(sorted_blocks_b, free_b, "File B")


if __name__ == "__main__":
    main()

import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_DIR = os.path.join(BASE_DIR, "namelists")
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")
EXECUTABLES_DIR = os.path.join(BASE_DIR, "executables_namelists")


PROGRAM_PATTERNS = {
    'prep_ideal_case': ['PRE_IDEA'],
    'prep_pgd': ['PRE_PGD'],
    'prep_nest_pgd': ['PRE_NEST_PGD'],
    'prep_real_case': ['PRE_REAL'],
    'spawning': ['SPAWN'],
    'mesonh': ['EXSEG'],
    'diag': ['DIAG'],
    'spectre': ['SPEC'],
}


def get_program_type(filename):
    filename_upper = filename.upper()
    for program, patterns in PROGRAM_PATTERNS.items():
        for pattern in patterns:
            if pattern in filename_upper:
                return program
    return None


def get_available_blocks(program_type):
    if not program_type:
        return []
    rst_file = os.path.join(EXECUTABLES_DIR, f"{program_type}.rst")
    if not os.path.exists(rst_file):
        return []
    blocks = []
    with open(rst_file, 'r', encoding='utf-8') as f:
        content = f.read()
    for match in re.findall(r'.. include:: namelists/(nam_\w+)\.rst', content):
        if match.startswith('nam_'):
            blocks.append(match)
    return blocks


def get_block_defaults(block_name):
    rst_file = os.path.join(DOC_DIR, f"{block_name}.rst")
    if not os.path.exists(rst_file):
        return {}
    defaults = {}
    with open(rst_file, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    in_table = False
    for line in lines:
        if '.. csv-table::' in line:
            in_table = True
            continue
        if in_table and line.strip().startswith('"') and '"' in line:
            parts = line.split(',')
            if len(parts) >= 3:
                name = parts[0].strip().strip('"')
                ftype = parts[1].strip().strip('"').upper()
                default = parts[2].strip().strip('"')
                if name and default and ftype:
                    if 'CHARACTER' in ftype:
                        defaults[name] = default.strip("'").strip('"')
                    elif 'LOGICAL' in ftype:
                        defaults[name] = default.upper() == '.TRUE.'
                    elif 'INTEGER' in ftype:
                        try:
                            defaults[name] = int(default)
                        except:
                            defaults[name] = 0
                    elif 'REAL' in ftype:
                        try:
                            defaults[name] = float(default)
                        except:
                            defaults[name] = 0.0
        if in_table and line.strip().startswith('.. include::'):
            in_table = False
    return defaults


def get_block_title(block_name):
    rst_file = os.path.join(DOC_DIR, f"{block_name}.rst")
    if not os.path.exists(rst_file):
        return block_name
    with open(rst_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if i + 1 < len(lines) and lines[i + 1].strip().startswith('---'):
            return line.strip()
    return block_name


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


def render_rst(rst_content, block_name=None, height=400):
    if not rst_content:
        return ""
    
    try:
        from docutils.core import publish_doctree, publish_from_doctree
        
        doctree = publish_doctree(rst_content)
        html = publish_from_doctree(doctree, writer_name='html')
        
        if isinstance(html, bytes):
            html = html.decode('utf-8')
        
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
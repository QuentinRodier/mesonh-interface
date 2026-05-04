import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_DIR = os.path.join(BASE_DIR, "namelists")
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")
EXECUTABLES_DIR = os.path.join(BASE_DIR, "executables_namelists")


def is_array_type(type_str):
    """Check if parameter type indicates an array."""
    type_upper = type_str.upper()
    # Array patterns: (:), ARRAY keyword, DIMENSION keyword
    # Also: REAL(NFORCF), INTEGER(NB), LOGICAL(N) where there's a variable name in parens
    if '(:' in type_upper or type_upper.startswith('ARRAY') or 'DIMENSION' in type_upper:
        return True
    # Check for REAL(NAME), INTEGER(NAME), LOGICAL(NAME) patterns
    if re.match(r'(REAL|INTEGER|LOGICAL)\s*\(\s*[A-Za-z_][A-Za-z0-9_]*\s*\)', type_upper):
        return True
    return False


def clean_param_name(name):
    """Remove array indices from parameter name."""
    cleaned = re.sub(r'\([^)]*\)', '', name)
    return cleaned.strip()


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


def parse_csv_line(line):
    """Parse a CSV line respecting quoted fields.
    Handles cases like: "NAME","TYPE(:,:)","VALUE"
    """
    import csv
    import io
    reader = csv.reader(io.StringIO(line))
    return next(reader, [])


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
            parts = parse_csv_line(line)
            if len(parts) >= 3:
                raw_name = parts[0].strip()
                name = clean_param_name(raw_name).replace("\"","")
                ftype = parts[1].strip().upper()
                default = parts[2].strip()
                if name and ftype:
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


def extract_dimension_info(type_str):
    """Extract dimension info from type string.
    Returns: (has_dim_pattern, dimensions, dim_pattern)
    - dimensions: number of dimensions (2 for REAL(:,:))
    - dim_pattern: original pattern like ":,:" for UI generation
    """
    # Only match patterns that look like array dimensions:
    # - Contains ":" (colon for unspecified dimension)
    # - Contains "," (comma for multiple dimensions)
    # - Does NOT match simple type specs like REAL(8) or INTEGER(4)
    match = re.search(r'\(([^)]+)\)', type_str)
    if match:
        dim_str = match.group(1)
        # Check if this looks like an array dimension pattern
        if ':' in dim_str or ',' in dim_str:
            dims = [d.strip() for d in dim_str.split(',')]
            return True, len(dims), dim_str
    return False, 0, ''


def get_block_params(block_name):
    rst_file = os.path.join(DOC_DIR, f"{block_name}.rst")
    if not os.path.exists(rst_file):
        return {}
    params = {}
    with open(rst_file, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    in_table = False
    for line in lines:
        if '.. csv-table::' in line:
            in_table = True
            continue
        if in_table and line.strip().startswith('"') and '"' in line:
            parts = parse_csv_line(line)
            if len(parts) >= 3:
                raw_name = parts[0].strip()
                name = clean_param_name(raw_name).replace("\"","")
                ftype = parts[1].strip().upper()
                default = parts[2].strip()
                is_array = is_array_type(ftype)
                # Extract dimension info
                has_dim, dimensions, dim_pattern = extract_dimension_info(ftype)
                if name and ftype:
                    if 'CHARACTER' in ftype:
                        params[name] = {
                            'value': default.strip("'").strip('"'),
                            'is_array': is_array,
                            'type': ftype,
                            'dimensions': dimensions if has_dim else (1 if is_array else 0),
                            'dim_pattern': dim_pattern
                        }
                    elif 'LOGICAL' in ftype:
                        params[name] = {
                            'value': default.upper() == '.TRUE.',
                            'is_array': is_array,
                            'type': ftype,
                            'dimensions': dimensions if has_dim else (1 if is_array else 0),
                            'dim_pattern': dim_pattern
                        }
                    elif 'INTEGER' in ftype:
                        try:
                            params[name] = {
                                'value': int(default),
                                'is_array': is_array,
                                'type': ftype,
                                'dimensions': dimensions if has_dim else (1 if is_array else 0),
                                'dim_pattern': dim_pattern
                            }
                        except:
                            params[name] = {
                                'value': 0,
                                'is_array': is_array,
                                'type': ftype,
                                'dimensions': dimensions if has_dim else (1 if is_array else 0),
                                'dim_pattern': dim_pattern
                            }
                    elif 'REAL' in ftype:
                        try:
                            params[name] = {
                                'value': float(default),
                                'is_array': is_array,
                                'type': ftype,
                                'dimensions': dimensions if has_dim else (1 if is_array else 0),
                                'dim_pattern': dim_pattern
                            }
                        except:
                            params[name] = {
                                'value': 0.0,
                                'is_array': is_array,
                                'type': ftype,
                                'dimensions': dimensions if has_dim else (1 if is_array else 0),
                                'dim_pattern': dim_pattern
                            }
        if in_table and line.strip().startswith('.. include::'):
            in_table = False
    return params


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
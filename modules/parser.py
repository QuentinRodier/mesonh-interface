import re
from dataclasses import dataclass, field
from typing import Any, Dict, List


# ==========================================================
# Structures
# ==========================================================

@dataclass
class NamelistEntry:
    name: str
    base_name: str
    value: Any
    raw_line: str
    decimals: int = 4
    is_array: bool = False
    array_index: str = ""


@dataclass
class NamelistBlock:
    name: str
    entries: Dict[str, NamelistEntry] = field(default_factory=dict)
    raw_lines: List[str] = field(default_factory=list)


# ==========================================================
# Public API
# ==========================================================

def parse_namelist(content: str) -> Dict[str, NamelistBlock]:
    """
    Parse un fichier Fortran namelist robuste.

    Gère :
      - casse libre
      - séparateur espace ou virgule
      - booléens .TRUE. .FALSE.
      - strings 'abc'
      - float/int
      - exponent D / E
      - multi-lignes
      - blocs vides
    """
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    blocks = {}
    pos = 0
    n = len(content)

    while pos < n:
        amp = content.find("&", pos)
        if amp == -1:
            break

        block, pos = _parse_block(content, amp)
        if block:
            blocks[block.name] = block

    return blocks


def write_namelist(blocks: Dict[str, NamelistBlock]) -> str:
    lines = []

    for block in blocks.values():
        if not block.entries:
            lines.append(f"&{block.name} /")
            continue

        lines.append(f"&{block.name}")

        for entry in block.entries.values():
            value = _format_value(entry.value, entry.decimals)
            lines.append(f"  {entry.name}={value},")

        lines.append(" /")
        lines.append("")

    return "\n".join(lines)


# ==========================================================
# Core parser
# ==========================================================

def _parse_block(content: str, start: int):
    i = start + 1
    n = len(content)

    # nom du bloc
    name = []
    while i < n and (content[i].isalnum() or content[i] == "_"):
        name.append(content[i])
        i += 1

    if not name:
        return None, i

    block_name = "".join(name)

    # lecture jusqu'au / final hors quotes
    params = []
    in_quote = False
    quote_char = None

    while i < n:
        c = content[i]

        if c in ("'", '"'):
            if not in_quote:
                in_quote = True
                quote_char = c
            elif c == quote_char:
                in_quote = False
                quote_char = None

            params.append(c)
            i += 1
            continue

        if c == "/" and not in_quote:
            i += 1
            break

        params.append(c)
        i += 1

    params_text = "".join(params).strip()

    block = NamelistBlock(name=block_name)
    block.raw_lines = [f"&{block_name} {params_text} /"]

    if params_text:
        block.entries = _parse_assignments(params_text)

    return block, i


# ==========================================================
# Assignments parser
# ==========================================================

_assign_re = re.compile(
    r"""
    ([A-Za-z_][A-Za-z0-9_()]*)      # variable
    \s*=\s*
    """,
    re.VERBOSE,
)


def _parse_assignments(text: str) -> Dict[str, NamelistEntry]:
    entries = {}

    matches = list(_assign_re.finditer(text))

    for idx, m in enumerate(matches):
        full_name = m.group(1).upper()

        # Extract base name and array index
        base_name = re.sub(r'\([^)]*\)', '', full_name)
        array_match = re.search(r'(\([^)]*\))', full_name)
        array_index = array_match.group(1) if array_match else ""
        is_array = bool(array_index)

        value_start = m.end()

        if idx + 1 < len(matches):
            value_end = matches[idx + 1].start()
        else:
            value_end = len(text)

        raw_value = text[value_start:value_end].strip()

        # enlever virgule finale éventuelle
        raw_value = raw_value.rstrip(",").strip()

        value = _parse_value(raw_value)
        decimals = _count_decimals(raw_value)

        entry_key = full_name if is_array else base_name

        entries[entry_key] = NamelistEntry(
            name=full_name,
            base_name=base_name,
            value=value,
            raw_line=f"{full_name}={raw_value}",
            decimals=decimals,
            is_array=is_array,
            array_index=array_index
        )

    return entries


# ==========================================================
# Value parser
# ==========================================================

def _count_decimals(s):
    s_clean = s.replace("D", "E").replace("d", "e")
    if "e" in s_clean.lower():
        mantissa = s_clean.lower().split("e")[0]
    else:
        mantissa = s_clean
    if "." in mantissa:
        return len(mantissa.split(".")[1])
    return 0

def _parse_value(s: str):
    s = s.strip()

    if not s:
        return ""

    low = s.lower()

    # bool
    if low in (".true.", ".t.", "true", "t"):
        return True

    if low in (".false.", ".f.", "false", "f"):
        return False

    # string
    if (s.startswith("'") and s.endswith("'")) or \
       (s.startswith('"') and s.endswith('"')):
        return s[1:-1]

    # repetition Fortran : 3*0.
    if "*" in s:
        return s

    # float/int
    s_num = s.replace("D", "E").replace("d", "e")

    try:
        if any(x in s_num for x in ".eE"):
            return float(s_num)
        return int(s_num)
    except ValueError:
        return s


# ==========================================================
# Formatting
# ==========================================================

def _format_value(v, decimals=4):
    if isinstance(v, bool):
        return ".TRUE." if v else ".FALSE."

    if isinstance(v, str):
        if "*" in v:
            return v
        return f"'{v}'"

    if isinstance(v, float):
        return f"{v:.{decimals}f}"

    return str(v)


# ==========================================================
# Exemple
# ==========================================================

if __name__ == "__main__":

    txt = """
&NAM_REAL_PGD /
&NAM_DIMn_PRE NIMAX=1, NJMAX=1 /
&NAM_CONF_PRE LCARTESIAN=.TRUE., NVERB=5,
              CIDEAL='RSOU',  CZS='FLAT', LFORCING=.TRUE., LPACK=.FALSE.,
              LBOUSS=.FALSE., CEQNSYS='DUR', LPERTURB=.FALSE.,
              JPHEXT=1,NHALO=1  /
&NAM_PERT_PRE /
&NAM_CONFn LUSERV=.TRUE. /
&NAM_GRID_PRE XLAT0=35.762 XLON0=-96. /
"""

    data = parse_namelist(txt)

    for name, block in data.items():
        print("=" * 50)
        print(name)
        for k, v in block.entries.items():
            print(k, "=", v.value)

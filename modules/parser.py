import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Optional


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
    is_comment: bool = False
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

def parse_namelist(content: str) -> Tuple[Dict[str, NamelistBlock], dict]:
    """
    Parse a Fortran namelist and any trailing free-format data.
    Returns: (Dict of blocks, Dict of free-format data)
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

    blocks: Dict[str, NamelistBlock] = {}
    pos = 0
    n = len(content)
    last_block: Optional[NamelistBlock] = None

    while pos < n:
        amp = content.find("&", pos)
        if amp == -1:
            break

        # Capture inter-block content (comments between blocks)
        if last_block is not None:
            inter = content[pos:amp].strip()
            if inter:
                _attach_comment_lines(last_block, inter)

        block, pos = _parse_block(content, amp)
        if block:
            # Capture leading content before the first block
            if not blocks:
                leading = content[:amp].strip()
                if leading:
                    _attach_comment_lines(block, leading)
            blocks[block.name] = block
            last_block = block

    # Capture and parse trailing free-format content ---
    free_format_data = {}
    if pos < n:
        trailing = content[pos:].strip()
        if trailing:
            free_format_data = parse_free_format(content[pos:])

    return blocks, free_format_data


def write_namelist(blocks: Dict[str, NamelistBlock], keys_per_row: int = 1) -> str:
    lines = []
    for block in blocks.values():
        lines.append(f"&{block.name}")
        current_row = []
        
        for entry in block.entries.values():
            if entry.is_comment:
                if current_row:
                    lines.append("  " + "".join(current_row))
                    current_row = []
                lines.append(f"  ! {entry.value}")
            else:
                val = _format_value(entry.value, entry.decimals)
                current_row.append(f"{entry.name}={val},")
                if len(current_row) >= keys_per_row:
                    lines.append("  " + "".join(current_row))
                    current_row = []
        
        if current_row:
            lines.append("  " + "".join(current_row))
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
    block.raw_lines = [f"&{block.name} {params_text} /"]

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

    # Filter out matches that fall on ! comment lines
    def _on_comment_line(m) -> bool:
        ls = text.rfind('\n', 0, m.start())
        ls = 0 if ls == -1 else ls + 1
        prefix = text[ls:m.start()]
        in_q = False
        qc = None
        for ch in prefix:
            if ch in ("'", '"'):
                if not in_q:
                    in_q = True
                    qc = ch
                elif ch == qc:
                    in_q = False
                    qc = None
            if ch == '!' and not in_q:
                return True
        return False

    matches = [m for m in matches if not _on_comment_line(m)]

# 1. Handle block-level comments (text before the first assignment)
    if matches:
        pre_text = text[:matches[0].start()]
        if '!' in pre_text:
            comment_val = pre_text.split('!', 1)[1].strip()
            if comment_val:
                entries["_block_comment"] = NamelistEntry(
                    name="Block Comment", base_name="comment",
                    value=comment_val, raw_line="", is_comment=True
                )

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

        # 2. Handle trailing comments on the same line or between assignments
        segment = text[value_start:value_end]
        entry_comment = ""
        if '!' in segment:
            parts = segment.split('!', 1)
            entry_comment = parts[1].strip()
            segment = parts[0] # Only parse the part before the '!' as the value

        raw_value = segment.rstrip(", \t\n\r").strip()

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
            array_index=array_index,
            is_comment=False
        )

        # 3. If a comment was found, create a new entry to represent the comment object
        if entry_comment:
            entries[f"comment_line_{idx}"] = NamelistEntry(
                name=f"Comment {idx}",
                base_name=f"comment_{idx}",
                value=entry_comment,
                raw_line="",
                is_comment=True
            )

    return entries


def _attach_comment_lines(block: NamelistBlock, text: str) -> None:
    """Extract ! comment lines from text and add as entries to block."""
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('!'):
            comment_text = line[1:].strip()
            if comment_text:
                idx = sum(1 for e in block.entries.values() if e.is_comment)
                block.entries[f"_inter_comment_{idx}"] = NamelistEntry(
                    name=f"Comment {idx}",
                    base_name=f"comment_{idx}",
                    value=comment_text,
                    raw_line="",
                    is_comment=True
                )


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
# Free-format parser (PRE_IDEA1.nam after all &NAM_ blocks)
# ==========================================================

_RSOU_KINDS = {
    "STANDARD": "P",
    "PUVTHVMR": "P", "PUVTHVHU": "P",
    "ZUVTHVMR": "Z", "ZUVTHVHU": "Z",
    "PUVTHDMR": "P", "PUVTHDHU": "P",
    "ZUVTHDMR": "Z", "ZUVTHLMR": "Z",
}


def parse_free_format(content: str) -> dict:
    """
    Parse the free-format part of PRE_IDEA1.nam (after all &NAM_ blocks).
    Returns a dict with keys:
      radiosounding_type, radiosounding, forcing_type, forcing
    """
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Find end of last namelist block
    pos = 0
    n = len(content)
    last_block_end = 0

    while pos < n:
        amp = content.find("&", pos)
        if amp == -1:
            break
        i = amp + 1
        while i < n and (content[i].isalnum() or content[i] == "_"):
            i += 1
        in_quote = False
        qchar = None
        while i < n:
            c = content[i]
            if c in ("'", '"'):
                if not in_quote:
                    in_quote = True
                    qchar = c
                elif c == qchar:
                    in_quote = False
                    qchar = None
            elif c == "/" and not in_quote:
                i += 1
                break
            i += 1
        last_block_end = i
        pos = i

    free_text = content[last_block_end:].strip()
    return _parse_free_text_lines(free_text)


def _parse_free_text_lines(text: str) -> dict:
    lines = [l.strip() for l in text.split("\n") if l.strip() and not l.strip().startswith("!")]
    result = {"radiosounding_type": None, "radiosounding": None,
              "forcing_type": None, "forcing": None}
    if not lines:
        return result

    i = 0
    while i < len(lines):
        kw = lines[i].upper()
        i += 1

        if kw == "ZHAT":
            while i < len(lines) and lines[i].upper() not in ("CSTN", "RSOU", "ZHAT", "ZFRC", "PFRC"):
                i += 1
        elif kw == "CSTN":
            result["radiosounding_type"] = "CSTN"
            parsed, consumed = _parse_cstn(lines, i)
            result["radiosounding"] = parsed
            i += consumed
        elif kw == "RSOU":
            result["radiosounding_type"] = "RSOU"
            parsed, consumed = _parse_rsou(lines, i)
            result["radiosounding"] = parsed
            i += consumed
        elif kw in ("ZFRC", "PFRC"):
            result["forcing_type"] = kw
            parsed, consumed = _parse_forcing(lines, i, kw)
            result["forcing"] = parsed
            i += consumed

    return result


def _parse_cstn(lines: List[str], start: int) -> Tuple[dict, int]:
    i = start
    dp = lines[i].split()
    i += 1
    data = {"date": {"year": int(dp[0]), "month": int(dp[1]), "day": int(dp[2]), "time": float(dp[3])},
            "nlevels": int(lines[i])}
    i += 1
    data["ground_thv"] = float(lines[i]); i += 1
    data["ground_pressure"] = float(lines[i]); i += 1
    data["heights"] = [float(x) for x in lines[i].split()]; i += 1
    data["u"] = [float(x) for x in lines[i].split()]; i += 1
    data["v"] = [float(x) for x in lines[i].split()]; i += 1
    data["rh"] = [float(x) for x in lines[i].split()]; i += 1
    data["brunt_vaisala"] = [float(x) for x in lines[i].split()]; i += 1
    return data, i - start


def _parse_rsou(lines: List[str], start: int) -> Tuple[dict, int]:
    i = start
    dp = lines[i].split()
    i += 1
    data = {"date": {"year": int(dp[0]), "month": int(dp[1]), "day": int(dp[2]), "time": float(dp[3])},
            "kind": lines[i].strip("'\"").upper()}
    i += 1
    data["ground_height"] = float(lines[i]); i += 1
    data["ground_pressure"] = float(lines[i]); i += 1
    data["ground_temperature"] = float(lines[i]); i += 1
    data["ground_humidity"] = float(lines[i]); i += 1

    data["nwind"] = int(lines[i]); i += 1
    data["wind_levels"] = []
    for _ in range(data["nwind"]):
        p = lines[i].split()
        data["wind_levels"].append({"altitude": float(p[0]), "var1": float(p[1]), "var2": float(p[2])})
        i += 1

    data["nmass"] = int(lines[i]); i += 1
    data["mass_levels"] = []
    for _ in range(data["nmass"] - 1):
        p = lines[i].split()
        entry = {"altitude": float(p[0]), "temperature": float(p[1]), "humidity": float(p[2])}
        if len(p) > 3:
            entry["cloud"] = float(p[3])
        if len(p) > 4:
            entry["ice"] = float(p[4])
        data["mass_levels"].append(entry)
        i += 1

    return data, i - start


def _parse_forcing(lines: List[str], start: int, kw: str) -> Tuple[dict, int]:
    i = start
    data = {"ntimes": int(lines[i])}
    i += 1
    data["forcings"] = []
    for _ in range(data["ntimes"]):
        dp = lines[i].split(); i += 1
        fc = {"date": {"year": int(dp[0]), "month": int(dp[1]), "day": int(dp[2]), "time": float(dp[3])},
              "ground_height": float(lines[i]), "ground_pressure": float(lines[i+1]),
              "ground_theta": float(lines[i+2]), "ground_humidity": float(lines[i+3])}
        i += 4
        fc["nlevels"] = int(lines[i]); i += 1
        fc["levels"] = []
        for _ in range(fc["nlevels"]):
            p = lines[i].split()
            fc["levels"].append({"altitude": float(p[0]), "u": float(p[1]), "v": float(p[2]),
                                  "theta": float(p[3]), "rv": float(p[4]), "w": float(p[5]),
                                  "dtheta_dt": float(p[6]), "drv_dt": float(p[7]),
                                  "du_dt": float(p[8]), "dv_dt": float(p[9])})
            i += 1
        data["forcings"].append(fc)

    data["sounding"] = None
    if kw == "PFRC" and i < len(lines):
        ns = int(lines[i]); i += 1
        snd = []
        for _ in range(ns):
            p = lines[i].split()
            snd.append({"pressure": float(p[0]), "theta": float(p[1]), "rv": float(p[2])})
            i += 1
        data["sounding"] = {"nlevels": ns, "levels": snd}

    return data, i - start


def write_free_format(data: dict) -> str:
    """Generate the free-format text from a parsed data dict."""
    lines = []
    rs = data.get("radiosounding")
    rt = data.get("radiosounding_type")

    if rt == "CSTN" and rs:
        lines.append("CSTN")
        d = rs["date"]; lines.append(f"{d['year']} {d['month']} {d['day']} {d['time']}")
        lines.append(str(rs["nlevels"]))
        lines.append(str(rs["ground_thv"])); lines.append(str(rs["ground_pressure"]))
        lines.append(" ".join(str(v) for v in rs["heights"]))
        lines.append(" ".join(str(v) for v in rs["u"]))
        lines.append(" ".join(str(v) for v in rs["v"]))
        lines.append(" ".join(str(v) for v in rs["rh"]))
        lines.append(" ".join(str(v) for v in rs["brunt_vaisala"]))

    elif rt == "RSOU" and rs:
        lines.append("RSOU")
        d = rs["date"]; lines.append(f"{d['year']} {d['month']} {d['day']} {d['time']}")
        lines.append(f"'{rs['kind']}'")
        lines.append(str(rs["ground_height"])); lines.append(str(rs["ground_pressure"]))
        lines.append(str(rs["ground_temperature"])); lines.append(str(rs["ground_humidity"]))
        lines.append(str(rs["nwind"]))
        for wl in rs["wind_levels"]:
            lines.append(f"{wl['altitude']} {wl['var1']} {wl['var2']}")
        lines.append(str(rs["nmass"]))
        for ml in rs["mass_levels"]:
            line = f"{ml['altitude']} {ml['temperature']} {ml['humidity']}"
            if "cloud" in ml: line += f" {ml['cloud']}"
            if "ice" in ml: line += f" {ml['ice']}"
            lines.append(line)

    fc = data.get("forcing")
    ft = data.get("forcing_type")
    if ft and fc:
        lines.append(ft)
        lines.append(str(fc["ntimes"]))
        for f_entry in fc["forcings"]:
            d = f_entry["date"]; lines.append(f"{d['year']} {d['month']} {d['day']} {d['time']}")
            lines.append(str(f_entry["ground_height"])); lines.append(str(f_entry["ground_pressure"]))
            lines.append(str(f_entry["ground_theta"])); lines.append(str(f_entry["ground_humidity"]))
            lines.append(str(f_entry["nlevels"]))
            for lvl in f_entry["levels"]:
                lines.append(f"{lvl['altitude']} {lvl['u']} {lvl['v']} {lvl['theta']} {lvl['rv']} {lvl['w']} {lvl['dtheta_dt']} {lvl['drv_dt']} {lvl['du_dt']} {lvl['dv_dt']}")
        if fc.get("sounding"):
            lines.append(str(fc["sounding"]["nlevels"]))
            for snd in fc["sounding"]["levels"]:
                lines.append(f"{snd['pressure']} {snd['theta']} {snd['rv']}")

    return "\n".join(lines) + "\n"


# ==========================================================
# Exemple
# ==========================================================

if __name__ == "__main__":

    txt = """
&NAM_REAL_PGD /
&NAM_DIMn_PRE NIMAX=1, NJMAX=1 ! This is a comment
&NAM_CONF_PRE LCARTESIAN=.TRUE., NVERB=5,
              CIDEAL='RSOU',  CZS='FLAT', LFORCING=.TRUE., LPACK=.FALSE.,
              LBOUSS=.FALSE., CEQNSYS='DUR', LPERTURB=.FALSE.,
              JPHEXT=1,NHALO=1  /
&NAM_PERT_PRE /
&NAM_CONFn LUSERV=.TRUE. /
&NAM_GRID_PRE XLAT0=35.762 XLON0=-96. ! Another comment
"""

    data = parse_namelist(txt)

    for name, block in data.items():
        print("=" * 50)
        print(name)
        for k, v in block.entries.items():
            print(k, "=", v)

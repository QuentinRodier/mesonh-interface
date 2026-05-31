import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from modules import docs
from modules.parser import NamelistBlock


# ==========================================================
# AST for Fortran condition expressions
# ==========================================================

@dataclass
class Comparison:
    var: str
    op: str
    value: str

@dataclass
class LogicalOp:
    op: str
    left: Any
    right: Any

@dataclass
class Not:
    expr: Any


# ==========================================================
# Fortran condition tokenizer
# ==========================================================

def _tokenize_condition(text):
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in ' \t':
            i += 1
            continue
        if c == '(':
            tokens.append(('LPAREN', '('))
            i += 1
            continue
        if c == ')':
            tokens.append(('RPAREN', ')'))
            i += 1
            continue
        if c in ("'", '"'):
            j = i + 1
            while j < n and text[j] != c:
                j += 1
            tokens.append(('STRING', text[i+1:j]))
            i = j + 1
            continue
        if c == '.':
            j = text.find('.', i + 1)
            if j > i:
                word = text[i:j+1].upper()
                if word == '.AND.':
                    tokens.append(('AND', word))
                elif word == '.OR.':
                    tokens.append(('OR', word))
                elif word == '.NOT.':
                    tokens.append(('NOT', word))
                elif word in ('.TRUE.', '.FALSE.'):
                    tokens.append(('VALUE', word))
                elif word in ('.NE.', '.EQ.', '.LT.', '.GT.', '.LE.', '.GE.', '.EQV.', '.NEQV.'):
                    tokens.append(('OP', word))
                i = j + 1
                continue
            i += 1
            continue
        if text[i:i+2] == '==':
            tokens.append(('OP', '=='))
            i += 2
            continue
        if text[i:i+2] == '/=':
            tokens.append(('OP', '/='))
            i += 2
            continue
        if text[i:i+2] == '<=':
            tokens.append(('OP', '<='))
            i += 2
            continue
        if text[i:i+2] == '>=':
            tokens.append(('OP', '>='))
            i += 2
            continue
        if c == '<':
            tokens.append(('OP', '<'))
            i += 1
            continue
        if c == '>':
            tokens.append(('OP', '>'))
            i += 1
            continue
        if c.isdigit() or (c == '.' and i + 1 < n and text[i+1].isdigit()):
            j = i
            has_dot = False
            while j < n and (text[j].isdigit() or (text[j] == '.' and not has_dot)):
                if text[j] == '.':
                    has_dot = True
                j += 1
            tokens.append(('VALUE', text[i:j]))
            i = j
            continue
        if c.isalpha() or c == '_':
            j = i
            while j < n and (text[j].isalnum() or text[j] == '_'):
                j += 1
            tokens.append(('IDENTIFIER', text[i:j]))
            i = j
            continue
        i += 1
    return tokens


# ==========================================================
# Recursive descent parser for Fortran conditions
# ==========================================================

def _parse_expr(tokens, pos=0):
    node, pos = _parse_term(tokens, pos)
    while pos < len(tokens) and tokens[pos][0] == 'OR':
        pos += 1
        right, pos = _parse_term(tokens, pos)
        node = LogicalOp('OR', node, right)
    return node, pos

def _parse_term(tokens, pos=0):
    node, pos = _parse_factor(tokens, pos)
    while pos < len(tokens) and tokens[pos][0] == 'AND':
        pos += 1
        right, pos = _parse_factor(tokens, pos)
        node = LogicalOp('AND', node, right)
    return node, pos

def _parse_factor(tokens, pos=0):
    if pos >= len(tokens):
        raise ValueError("Unexpected end of expression")
    if tokens[pos][0] == 'NOT':
        pos += 1
        node, pos = _parse_factor(tokens, pos)
        return Not(node), pos
    if tokens[pos][0] == 'LPAREN':
        pos += 1
        node, pos = _parse_expr(tokens, pos)
        if pos >= len(tokens) or tokens[pos][0] != 'RPAREN':
            raise ValueError("Missing closing parenthesis")
        pos += 1
        return node, pos
    return _parse_comparison(tokens, pos)

def _parse_comparison(tokens, pos=0):
    if pos >= len(tokens):
        raise ValueError("Expected value/comparison")
    if tokens[pos][0] == 'IDENTIFIER':
        var = tokens[pos][1]
        pos += 1
        if pos < len(tokens) and tokens[pos][0] == 'OP':
            op = tokens[pos][1]
            pos += 1
            if pos >= len(tokens):
                raise ValueError("Expected value after operator")
            if tokens[pos][0] in ('VALUE', 'STRING', 'IDENTIFIER'):
                value = tokens[pos][1]
                pos += 1
                return Comparison(var, op, value), pos
            raise ValueError(f"Expected value, got {tokens[pos]}")
        return Comparison(var, '==', '.TRUE.'), pos
    if tokens[pos][0] in ('VALUE', 'STRING'):
        value = tokens[pos][1]
        pos += 1
        return Comparison('.TRUE.', '==', value), pos
    raise ValueError(f"Unexpected token: {tokens[pos]}")

def _parse_condition_text(text):
    tokens = _tokenize_condition(text)
    if not tokens:
        return None
    try:
        node, pos = _parse_expr(tokens)
        if pos < len(tokens):
            return None
        return node
    except (ValueError, IndexError):
        return None


# ==========================================================
# Fortran condition finder helpers
# ==========================================================

def _extract_condition_from_if(if_line):
    """Extract condition text from 'IF (condition) THEN' or 'ELSE IF (condition) THEN'."""
    paren = if_line.find('(')
    if paren == -1:
        return ''
    depth = 0
    for i in range(paren, len(if_line)):
        if if_line[i] == '(':
            depth += 1
        elif if_line[i] == ')':
            depth -= 1
            if depth == 0:
                return if_line[paren + 1:i].strip()
    return ''


def _find_enclosing_if(lines, call_idx):
    """Scan backward from call_idx to find the IF(...) containing the CALL."""
    depth = 0
    for i in range(call_idx - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith('END IF') or upper == 'ENDIF' or upper.startswith('ENDIF '):
            depth += 1
            continue
        if upper.startswith('ELSE IF') or upper.startswith('ELSEIF'):
            if depth == 0:
                return i, _extract_condition_from_if(line)
            continue
        if upper == 'ELSE' or upper.startswith('ELSE '):
            continue
        if upper.startswith('IF ') or upper.startswith('IF('):
            if depth == 0:
                return i, _extract_condition_from_if(line)
            depth -= 1
    return None, None


def _extract_write_messages(lines, if_idx, call_idx):
    """Extract text from WRITE(ILUOUT,*) statements between IF and CALL."""
    messages = []
    for i in range(if_idx + 1, call_idx):
        line = lines[i].strip()
        if not line:
            continue
        if 'WRITE(ILUOUT,*)' in line.upper():
            for q in ("'", '"'):
                start = line.find(q)
                if start != -1:
                    end = line.find(q, start + 1)
                    if end != -1:
                        text = line[start + 1:end].strip()
                        if text.startswith('*'):
                            text = text[1:].strip()
                        if text:
                            messages.append(text)
                        break
    return messages


def _is_single_var_condition(tokens):
    """Check if condition tokens contain only one identifier (for CASE lookup)."""
    return sum(1 for t in tokens if t[0] == 'IDENTIFIER') == 1


def _find_select_case(lines, if_idx):
    """Scan upward to find SELECT CASE(var) and the matching CASE(vals)."""
    case_var = None
    case_values = None
    i = if_idx - 1
    while i >= 0:
        line = lines[i].strip()
        if not line:
            i -= 1
            continue
        upper = line.upper()
        if upper.startswith('END SELECT'):
            depth = 1
            i -= 1
            while i >= 0 and depth > 0:
                inner = lines[i].strip().upper()
                if inner.startswith('END SELECT'):
                    depth += 1
                elif inner.startswith('SELECT CASE'):
                    depth -= 1
                i -= 1
            continue
        if upper.startswith('CASE(') or upper.startswith('CASE ('):
            if case_values is None:
                paren = line.find('(')
                end_paren = line.find(')')
                if paren != -1 and end_paren > paren:
                    vals = line[paren + 1:end_paren]
                    case_values = [v.strip().strip("'\"") for v in vals.split(',')]
            i -= 1
            continue
        if upper.startswith('CASE DEFAULT'):
            i -= 1
            continue
        if upper.startswith('SELECT CASE'):
            paren = line.find('(')
            end_paren = line.find(')')
            if paren != -1 and end_paren > paren:
                case_var = line[paren + 1:end_paren].strip()
            break
        i -= 1
    return case_var, case_values


# ==========================================================
# Condition evaluation
# ==========================================================

def _find_entry(blocks, var_name):
    """Find a NamelistEntry by base_name across all blocks."""
    target = var_name.upper()
    for block in blocks.values():
        for entry in block.entries.values():
            if entry.base_name.upper() == target:
                return entry
    return None


def _fortran_compare(entry_value, op, expected_str):
    """Compare a namelist entry value with an expected string using a Fortran operator."""
    actual_raw = str(entry_value).strip().strip("'\"").upper()
    expected_raw = str(expected_str).strip().strip("'\"").upper()
    _BOOL_MAP = {'.TRUE.': '.TRUE.', 'TRUE': '.TRUE.', 'T': '.TRUE.', '.T.': '.TRUE.',
                 '.FALSE.': '.FALSE.', 'FALSE': '.FALSE.', 'F': '.FALSE.', '.F.': '.FALSE.'}
    actual = _BOOL_MAP.get(actual_raw, actual_raw)
    expected = _BOOL_MAP.get(expected_raw, expected_raw)
    if op in ('.EQ.', '==', '.EQV.'):
        return actual == expected
    if op in ('.NE.', '/=', '.NEQV.'):
        return actual != expected
    if op in ('<', '.LT.'):
        try:
            return float(actual) < float(expected)
        except ValueError:
            return actual < expected
    if op in ('>', '.GT.'):
        try:
            return float(actual) > float(expected)
        except ValueError:
            return actual > expected
    if op in ('<=', '.LE.'):
        try:
            return float(actual) <= float(expected)
        except ValueError:
            return actual <= expected
    if op in ('>=', '.GE.'):
        try:
            return float(actual) >= float(expected)
        except ValueError:
            return actual >= expected
    return False


def _evaluate_ast(node, blocks):
    """Evaluate an AST node against namelist blocks. Returns True/False/None."""
    if isinstance(node, Comparison):
        entry = _find_entry(blocks, node.var)
        if entry is None:
            return None
        return _fortran_compare(entry.value, node.op, node.value)
    if isinstance(node, Not):
        val = _evaluate_ast(node.expr, blocks)
        return None if val is None else not val
    if isinstance(node, LogicalOp):
        left = _evaluate_ast(node.left, blocks)
        right = _evaluate_ast(node.right, blocks)
        if left is None or right is None:
            return None
        return left and right if node.op == 'AND' else left or right
    return None


def _strip_outer_quotes(s):
    """Strip only the outermost matching quote pair, not all quote chars."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    if len(s) >= 2 and s[0] in ("'", '"') and s[-1] in ("'", '"'):
        return s[1:-1]
    return s


def _extract_print_msg_message(line):
    """Extract the 4th argument (message) from a CALL PRINT_MSG(...) line."""
    idx = line.upper().find('CALL PRINT_MSG(')
    if idx == -1:
        return None
    paren = line.find('(', idx)
    if paren == -1:
        return None
    args_str = line[paren + 1:]
    depth = 0
    clean = []
    for c in args_str:
        if c == '(':
            depth += 1
            clean.append(c)
        elif c == ')':
            if depth == 0:
                break
            depth -= 1
            clean.append(c)
        else:
            clean.append(c)
    clean_str = ''.join(clean).rstrip(', ')
    args = _split_fortran_args(clean_str)
    if len(args) >= 4:
        msg = _strip_outer_quotes(args[3])
        if msg:
            return msg
    return None


# ==========================================================
# Top-level condition API
# ==========================================================

def parse_fortran_conditions(fortran_path):
    """Parse Fortran file for CALL PRINT_MSG(NVERB_FATAL...) and extract conditions.

    Returns list of dicts with keys: raw, ast, messages, case_var, case_values, severity.
    """
    if not os.path.exists(fortran_path):
        return []

    with open(fortran_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    content = _preprocess_fortran(content)
    lines = content.split('\n')

    results = []
    for i, line in enumerate(lines):
        upper = line.upper().strip()
        if 'CALL PRINT_MSG(NVERB_FATAL' in upper:
            if_line_idx, condition_text = _find_enclosing_if(lines, i)
            if if_line_idx is None:
                continue

            ast = _parse_condition_text(condition_text)
            if ast is None:
                continue

            messages = _extract_write_messages(lines, if_line_idx, i)

            if not messages:
                msg = _extract_print_msg_message(line)
                if msg:
                    messages = [msg]

            tokens = _tokenize_condition(condition_text)
            case_var = None
            case_values = None
            if _is_single_var_condition(tokens):
                case_var, case_values = _find_select_case(lines, if_line_idx)

            results.append({
                'raw': condition_text,
                'ast': ast,
                'messages': messages,
                'case_var': case_var,
                'case_values': case_values,
                'severity': 'FATAL',
            })
    return results


def check_fortran_conditions(blocks, condition_checks):
    """Evaluate condition checks against namelist blocks. Returns list of issue strings."""
    issues = []
    for check in condition_checks:
        ast = check['ast']
        case_var = check.get('case_var')
        case_values = check.get('case_values')
        messages = check.get('messages', [])

        full_ast = ast
        if case_var and case_values:
            case_ors = None
            for val in case_values:
                cond = Comparison(case_var, '==', val)
                case_ors = cond if case_ors is None else LogicalOp('OR', case_ors, cond)
            full_ast = LogicalOp('AND', case_ors, ast)

        result = _evaluate_ast(full_ast, blocks)
        if result is True:
            if messages:
                msg = messages[0]
            else:
                parts = []
                if case_var and case_values:
                    vals = ' or '.join(f"'{v}'" for v in case_values)
                    parts.append(f"{case_var} = {vals}")
                parts.append(f"({check.get('raw', '?')})")
                msg = '⚠️ Conflicting values: ' + ' AND '.join(parts)
            issues.append(msg)
    return issues


def check_block_names(blocks, program_type):
    """Check that all namelist blocks exist in the program's documentation."""
    issues = []
    if not program_type:
        return issues

    available_blocks = docs.get_available_blocks(program_type)
    valid_titles = {docs.get_block_title(b) for b in available_blocks}

    for block_name in blocks.keys():
        if block_name not in valid_titles:
            issues.append(f"Block '{block_name}' not found in {program_type} documentation")

    return issues


def check_param_names(blocks, program_type):
    """Check that all parameters in blocks exist in the documentation."""
    issues = []
    if not program_type:
        return issues

    available_blocks = docs.get_available_blocks(program_type)
    block_map = {docs.get_block_title(b): b for b in available_blocks}

    for block_name, block in blocks.items():
        short_name = block_map.get(block_name)
        if not short_name:
            continue

        valid_params = docs.get_block_params(short_name)
        valid_param_names = set(valid_params.keys())

        for param_name, entry in block.entries.items():
            base_param = entry.base_name
            if entry.is_comment:
                continue
            if base_param not in valid_param_names:
                issues.append(f"Parameter '{param_name}' in block '{block_name}' not found in documentation")

    return issues


def check_param_values(blocks):
    """Check that parameter values match expected types based on first letter."""
    issues = []
    type_map = {
        ('N', 'I', 'J'): int,
        ('C', 'H'): str,
        ('L', 'O'): bool,
        ('X',): float,
    }

    for block_name, block in blocks.items():
        for param_name, entry in block.entries.items():
            if not param_name or entry.is_comment:
                continue
            # Use base_name (without array index) for first letter check
            check_name = entry.base_name if hasattr(entry, 'base_name') else param_name
            first_letter = check_name[0].upper()

            expected_type = None
            for letters, t in type_map.items():
                if first_letter in letters:
                    expected_type = t
                    break

            if expected_type is None:
                continue

            value = entry.value
            actual_type = type(value)

            if expected_type == int and actual_type != int:
                issues.append(
                    f"Parameter '{param_name}' in '{block_name}': "
                    f"starts with '{first_letter}' → expected integer, got {actual_type.__name__}"
                )
            elif expected_type == str and actual_type != str:
                issues.append(
                    f"Parameter '{param_name}' in '{block_name}': "
                    f"starts with '{first_letter}' → expected string, got {actual_type.__name__}"
                )
            elif expected_type == bool and actual_type != bool:
                issues.append(
                    f"Parameter '{param_name}' in '{block_name}': "
                    f"starts with '{first_letter}' → expected boolean, got {actual_type.__name__}"
                )
            elif expected_type == float and actual_type not in (int, float):
                issues.append(
                    f"Parameter '{param_name}' in '{block_name}': "
                    f"starts with '{first_letter}' → expected float, got {actual_type.__name__}"
                )

    return issues


def _preprocess_fortran(content):
    """Join Fortran continuation lines and remove comments."""
    content = re.sub(r'&\s*\n\s*&', '', content)
    content = re.sub(r'&\s*\n\s*', ' ', content)
    result = []
    in_quote = False
    in_comment = False
    quote_char = None
    for c in content:
        if in_comment:
            if c == '\n':
                in_comment = False
                result.append(c)
            continue
        if c in "'\"":
            if not in_quote:
                in_quote = True
                quote_char = c
            elif c == quote_char:
                in_quote = False
            result.append(c)
        elif c == '!' and not in_quote:
            in_comment = True
        else:
            result.append(c)
    return ''.join(result)


def _split_fortran_args(args_str):
    """Split Fortran argument string by commas, respecting quoted strings."""
    args = []
    current = []
    in_quote = False
    quote_char = None
    for c in args_str:
        if c in "'\"":
            if not in_quote:
                in_quote = True
                quote_char = c
            elif c == quote_char:
                in_quote = False
            current.append(c)
        elif c == ',' and not in_quote:
            args.append(''.join(current).strip())
            current = []
        else:
            current.append(c)
    remaining = ''.join(current).strip()
    if remaining:
        args.append(remaining)
    return args


def parse_fortran_checks(fortran_path, function_names=None):
    """
    Parse Fortran source for CALL FUNCTION_NAME(...) patterns.

    Extracts param name (2nd arg) and allowed values (4th+ args):
      CALL TEST_NAM_VAR(ILUOUT,'PARAM_NAME',VAR_NAME,'VAL1','VAL2',...)

    Args:
        fortran_path: Path to .f90 file.
        function_names: List of function names to scan (default: ['TEST_NAM_VAR']).

    Returns:
        Dict[str, List[str]]: {param_name: [allowed_value1, ...]}
    """
    if function_names is None:
        function_names = ['TEST_NAM_VAR']

    if not os.path.exists(fortran_path):
        return {}

    with open(fortran_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    content = _preprocess_fortran(content)

    func_pattern = '|'.join(re.escape(fn) for fn in function_names)
    pattern = re.compile(
        r"CALL\s+(?:" + func_pattern + r")\s*\(([^)]+)\)",
        re.IGNORECASE,
    )

    checks = {}
    for match in pattern.finditer(content):
        args_str = match.group(1)
        args = _split_fortran_args(args_str)
        if len(args) < 4:
            continue
        param_name = args[1].strip().strip("'\"")
        allowed_values = [v.strip().strip("'\"") for v in args[3:]]
        checks[param_name] = allowed_values
    return checks


def check_param_values_from_fortran(blocks, fortran_checks):
    """Check parameter values against allowed values parsed from Fortran."""
    issues = []
    for block_name, block in blocks.items():
        for param_name, entry in block.entries.items():
            if entry.is_comment:
                continue
            base_name = entry.base_name if hasattr(entry, 'base_name') else param_name
            if base_name not in fortran_checks:
                continue
            allowed = fortran_checks[base_name]
            str_value = str(entry.value).strip().strip("'\"")
            if str_value.upper() not in (v.upper() for v in allowed):
                allowed_str = ', '.join(allowed)
                issues.append(
                    f"Parameter '{param_name}' in '{block_name}': "
                    f"value '{str_value}' not allowed. Allowed: {allowed_str}"
                )
    return issues


def run_all_checks(blocks, current_file):
    """Run all checks and return results."""
    program_type = docs.get_program_type(current_file) if current_file else None

    fortran_checks = {}
    mesonh_code_dir = os.getenv(
        "MESONH_CODE_DIR",
        str(Path(__file__).resolve().parent.parent),
    )
    fortran_files_to_check = [
        {
            "path": os.path.join(mesonh_code_dir, "src", "MNH", "read_exsegn.f90"),
            "function_names": None
        },
        {
            "path": os.path.join(mesonh_code_dir, "src", "PHYEX", "turb", "modd_turbn.f90"),
            "function_names": ['CHECK_NAM_VAL_CHAR']
        },
        {
            "path": os.path.join(mesonh_code_dir, "src", "PHYEX", "micro", "modd_param_lima.f90"),
            "function_names": ['CHECK_NAM_VAL_CHAR']
        },
        {
            "path": os.path.join(mesonh_code_dir, "src", "PHYEX", "turb", "modd_param_mfshalln.f90"),
            "function_names": ['CHECK_NAM_VAL_CHAR']
        },
        {
            "path": os.path.join(mesonh_code_dir, "src", "PHYEX", "micro", "modd_param_icen.f90"),
            "function_names": ['CHECK_NAM_VAL_CHAR']
        },
        {
            "path": os.path.join(mesonh_code_dir, "src", "PHYEX", "micro", "modd_nebn.f90"),
            "function_names": ['CHECK_NAM_VAL_CHAR']
        }
    ]

    fortran_checks = {}
    condition_checks = []
    for file_info in fortran_files_to_check:
        fortran_path = file_info["path"]
        if os.path.exists(fortran_path):
            result = parse_fortran_checks(fortran_path, function_names=file_info["function_names"])
            fortran_checks.update(result)
            condition_checks.extend(parse_fortran_conditions(fortran_path))

    results = {
        'blocks': check_block_names(blocks, program_type),
        'params': check_param_names(blocks, program_type),
        'values': check_param_values(blocks),
        'fortran': check_param_values_from_fortran(blocks, fortran_checks),
        'conditions': check_fortran_conditions(blocks, condition_checks),
    }

    return results

import os
import re
from pathlib import Path

import streamlit as st

from modules import docs
from modules.parser import NamelistBlock


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
            if not param_name:
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
    fortran_path = os.path.join(mesonh_code_dir, "src", "MNH", "read_exsegn.f90")
    if os.path.exists(fortran_path):
        fortran_checks = parse_fortran_checks(fortran_path)

    results = {
        'blocks': check_block_names(blocks, program_type),
        'params': check_param_names(blocks, program_type),
        'values': check_param_values(blocks),
        'fortran': check_param_values_from_fortran(blocks, fortran_checks),
    }

    return results

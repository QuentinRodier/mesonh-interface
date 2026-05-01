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

        for param_name in block.entries.keys():
            if param_name not in valid_param_names:
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
            first_letter = param_name[0].upper()

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


def run_all_checks(blocks, current_file):
    """Run all checks and return results."""
    program_type = docs.get_program_type(current_file) if current_file else None

    results = {
        'blocks': check_block_names(blocks, program_type),
        'params': check_param_names(blocks, program_type),
        'values': check_param_values(blocks),
    }

    return results
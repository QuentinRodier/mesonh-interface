# Meso-NH Interface

A Streamlit-based web application for editing Meso-NH namelist files. This tool provides an intuitive interface for creating, editing, and managing namelist configurations used in Meso-NH atmospheric modeling simulations.

## Features

- **Namelist Editor**: Edit single namelist files with an interactive UI
- **Workspace Mode**: Edit multiple namelist files in a directory
- **Catalogue Explorer**: Browse and explore example namelists
- **Vertical Levels Configurator**: Configure NAM_VER_GRID parameters with visualization
- **Documentation Integration and Advises**: Direct access to parameter documentation from RST files and Meso-NH code

## Requirements

- Python >= 3.10
- Two external Meso-NH repositories:
  - **Meso-NH CODE repo**: https://src.koda.cnrs.fr/mesonh/mesonh-code
  - **Meso-NH DOC repo**: https://github.com/JorisPianezze/mesonh_doc

## Installation

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd mesonh-interface
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux/Mac:
   source .venv/bin/activate
   ```

3. Install the package in editable mode:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the first-time setup wizard:
   ```bash
   mesonh-setup
   ```
   This will prompt you for the paths to the Meso-NH CODE and DOC repositories and create a `.env` file.

   Alternatively, manually create a `.env` file by copying `.env.example` and adjusting the paths.

## Usage

Launch the application:
```bash
streamlit run mesonh-interface/Applications.py
```

This will open the application in your web browser. From the home page, you can navigate to:
- **Namelist Editor**: Edit a single namelist file
- **Workspace**: Edit multiple namelists in a directory
- **Catalogue Explorer**: Browse example namelists
- **Vertical Levels**: Configure vertical grid parameters

## Configuration

The application uses two environment variables (stored in `.env` file):

| Variable | Description |
|----------|-------------|
| `MESONH_CODE_DIR` | Path to Meso-NH CODE repo (must contain `examples/` folder) |
| `MESONH_DOC_DIR` | Path to Meso-NH DOC repo (must contain `docs/source/documentation/users_guide/executables_namelists/`) |

You can also set these as system environment variables instead of using `.env`.

## Project Structure

```
mesonh-interface/
├── pyproject.toml              # Project metadata and dependencies
├── README.md                   # This file
├── .env.example                # Template for environment variables
├── .env                        # Your local configuration (created by setup)
├── mesonh-interface/
│   ├── __init__.py
│   ├── config.py               # Configuration management
│   ├── Applications.py         # Main entry point
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── docs.py             # Documentation parsing
│   │   ├── parser.py           # Namelist file parser
│   │   └── advise.py           # Parameter advice/validation
│   └── pages/
│       ├── __init__.py
│       ├── Namelist_Editor.py  # Single file editor
│       ├── Workspace.py        # Multi-file workspace
│       ├── Catalogue_Explorer.py # Browse examples
│       └── Vertical_Levels.py  # Vertical grid configurator
└── (external repos referenced via env vars, not included)
```
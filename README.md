# Meso-NH Interface

A Streamlit-based web application for editing Meso-NH namelist files. This tool provides an intuitive interface for creating, editing, and managing namelist configurations used in Meso-NH atmospheric modeling simulations.

## Features

- **Namelist Editor**: Edit single namelist files with an interactive UI, integrated documentation, and advice checks
- **Workspace Mode**: Edit multiple namelist files in a directory
- **Catalogue Explorer**: Browse and explore example namelists
- **Horizontal Grids**: Configure horizontal grid parameters (NIMAX, NJMAX, projection) with interactive Leaflet map and multi-domain support
- **Vertical Levels Configurator**: Configure NAM_VER_GRID parameters with visualization
- **Initial Radiosoundings and Forcing**: Edit CSTN, RSOU, and forcing data for PRE_IDEA1.nam with profile plots and Hovmöller diagrams
- **Quick Plots**: Visualize netCDF output files with per-variable plots, colormap selection, and per-trace color management
- **Experiment Design**: Design complete Meso-NH experiments (ideal/realistic, multi-domain, multi-segment) with automatic architecture generation, namelist curation, and workflow advice
- **Documentation Integration and Advises**: Direct access to parameter documentation from RST files and Meso-NH code

## Requirements

- Python >= 3.10
- Two external Meso-NH repositories:
  - **Meso-NH CODE repo**: https://src.koda.cnrs.fr/mesonh/mesonh-code
  - **Meso-NH DOC repo**: https://github.com/JorisPianezze/mesonh_doc

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/QuentinRodier/mesonh-interface.git
   cd mesonh-interface
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
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
   python3 -m config setup
   ```
   This will prompt you for the paths to the Meso-NH CODE and DOC repositories and create a `.env` file.

   Alternatively, manually create a `.env` file by copying `.env.example` and adjusting the paths.

## Usage

Launch the application:
```bash
streamlit run Applications.py
```

This will open the application in your web browser. From the sidebar navigation you can access:
- **Home**: Landing page with links to all tools
- **Namelist Editor**: Edit a single namelist file
- **Workspace**: Edit multiple namelists in a directory
- **Catalogue Explorer**: Browse example namelists
- **Horizontal Grids**: Configure horizontal grids with an interactive map
- **Vertical Levels**: Configure vertical grid parameters
- **Initial Radiosoundings and Forcing**: Edit radiosounding and forcing data
- **Quick Plots**: Visualize netCDF output files
- **Experiment Design**: Design complete Meso-NH experiments

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
├── README.md                   # This file
├── requirements.txt            # Dependencies
├── .env.example                # Template for environment variables
├── .env                        # Your local configuration (created by setup)
├── Applications.py             # Main entry point (st.Page navigation hub)
├── Home.py                     # Landing page
├── config.py                   # Configuration management
├── modules/
│   ├── __init__.py
│   ├── docs.py             # Documentation parsing
│   ├── parser.py           # Namelist file parser (blocks + free-format)
│   ├── advise.py           # Parameter advice/validation
│   ├── utils.py            # Utility functions (clipboard, etc.)
│   └── experiment.py       # Experiment design logic (steps, ingredients, curation)
├── pages/
│   ├── __init__.py
│   ├── Namelist_Editor.py              # Single file editor
│   ├── Workspace.py                    # Multi-file workspace
│   ├── Catalogue_Explorer.py           # Browse examples
│   ├── Horizontal_Grids.py             # Horizontal grid configurator
│   ├── Vertical_Levels.py              # Vertical grid configurator
│   ├── Initial_radiosoundings_forcing.py # Radiosounding & forcing data
│   ├── Quick_Plots.py                  # netCDF visualization
│   └── Experiment_Design.py            # Experiment workflow design
└── (external repos referenced via env vars, not included)
```
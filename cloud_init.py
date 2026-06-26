import os
import subprocess
import sys

_CLOUD_DIR = "/mount/src"

if os.path.isdir(_CLOUD_DIR):
    _REPOS = {
        "MESONH_CODE_DIR": ("mesonh-code", "https://src.koda.cnrs.fr/mesonh/mesonh-code.git"),
        "MESONH_DOC_DIR": ("mesonh-doc", "https://github.com/JorisPianezze/mesonh_doc.git"),
    }
    for _env_var, (_dirname, _repo_url) in _REPOS.items():
        if not os.environ.get(_env_var):
            _dest = os.path.join(_CLOUD_DIR, _dirname)
            if not os.path.isdir(_dest):
                try:
                    subprocess.run(
                        ["git", "clone", "--depth", "1", _repo_url, _dest],
                        check=True, capture_output=True, timeout=120,
                    )
                except Exception:
                    continue
            os.environ[_env_var] = _dest

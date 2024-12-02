from pathlib import Path

_MAX_DEPTH = 5


def _get_project_root_dir() -> Path:
    current_dir = Path().cwd()
    for _ in range(_MAX_DEPTH):
        if (current_dir / "pyproject.toml").exists():
            return current_dir
        current_dir = current_dir.parent

    raise FileNotFoundError("the project root directory could not be found")


_project_root = _get_project_root_dir()

resources_dir = _project_root / "resources"

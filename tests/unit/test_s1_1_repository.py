"""Section 1.1: clean branch and tooling."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", path], cwd=ROOT, check=False
    )
    return result.returncode == 0


@pytest.mark.parametrize(
    "path", [".env", ".env.production", ".env.staging", ".env.local", ".env.backup"]
)
def test_s1_1_02_env_files_with_secrets_are_never_committable(path: str) -> None:
    assert _ignored(path)


def test_s1_1_02_env_example_template_is_committed() -> None:
    assert not _ignored(".env.example")
    assert (ROOT / ".env.example").is_file()


def test_s1_1_04_no_old_code_left_on_the_branch() -> None:
    old_paths = (
        "legacy",
        "config",
        "models",
        "routes",
        "schemas/login.py",
        "services",
        "utils",
        "main.py",
        "config_manager.py",
        "requirement.txt",
    )
    for old in old_paths:
        assert not (ROOT / old).exists(), f"old code still present: {old}"

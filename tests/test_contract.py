"""Contract tests for PEP 621 metadata, version consistency, and repository integrity."""

from __future__ import annotations

from pathlib import Path
import re

import absorber
from absorber import config

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
README_PATH = REPO_ROOT / "README.md"
README_DE_PATH = REPO_ROOT / "README_de.md"
LICENSE_PATH = REPO_ROOT / "LICENSE"
THIRD_PARTY_LICENSES_PATH = REPO_ROOT / "THIRD_PARTY_LICENSES.txt"


def _read_pyproject() -> str:
    return PYPROJECT_PATH.read_text(encoding="utf-8")


def test_pep621_metadata_fields():
    content = _read_pyproject()
    assert 'name = "absorber"' in content
    assert 'requires-python = ">=3.11"' in content
    assert 'license = { text = "MIT" }' in content
    assert "[project.urls]" in content
    assert 'Homepage = "https://github.com/file-bricks/absorber"' in content
    assert 'Repository = "https://github.com/file-bricks/absorber"' in content
    assert 'Issues = "https://github.com/file-bricks/absorber/issues"' in content
    assert 'Changelog = "https://github.com/file-bricks/absorber/blob/main/CHANGELOG.md"' in content
    assert '"Programming Language :: Python :: 3.11"' in content
    assert '"Programming Language :: Python :: 3.12"' in content
    assert '"Programming Language :: Python :: 3.13"' in content
    assert '"License :: OSI Approved :: MIT License"' in content


def test_version_parity():
    content = _read_pyproject()
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    assert match is not None, "pyproject.toml must define project version"
    pyproject_version = match.group(1)
    assert absorber.__version__ == pyproject_version


def test_essential_files_and_licenses():
    assert LICENSE_PATH.is_file(), "LICENSE must exist"
    license_text = LICENSE_PATH.read_text(encoding="utf-8")
    assert "MIT License" in license_text

    assert THIRD_PARTY_LICENSES_PATH.is_file(), "THIRD_PARTY_LICENSES.txt must exist"
    third_party_text = THIRD_PARTY_LICENSES_PATH.read_text(encoding="utf-8")
    assert "PySide6" in third_party_text
    assert "LGPL" in third_party_text

    readme_en = README_PATH.read_text(encoding="utf-8")
    assert "THIRD_PARTY_LICENSES.txt" in readme_en
    assert "LICENSE" in readme_en

    readme_de = README_DE_PATH.read_text(encoding="utf-8")
    assert "THIRD_PARTY_LICENSES.txt" in readme_de
    assert "LICENSE" in readme_de


def test_config_defaults_contract():
    expected_keys = {
        "mode",
        "target_dir",
        "text_formats",
        "copy_file_lists",
        "path_to_clipboard",
        "model_naming",
        "model",
        "ollama_url",
        "virtual_retention_days",
        "recent_max",
    }
    assert expected_keys.issubset(set(config.DEFAULTS.keys()))

"""Fakes that stand in for QMimeData, QImage and QUrl, so the core tests need no GUI."""

from __future__ import annotations

from pathlib import Path

import pytest


class FakeImage:
    """Enough of QImage for absorber: it can be asked to save itself."""

    def __init__(self, payload: bytes = b"\x89PNG-fake", ok: bool = True):
        self.payload = payload
        self.ok = ok

    def save(self, path: str, fmt: str = "PNG") -> bool:
        if not self.ok:
            return False
        Path(path).write_bytes(self.payload)
        return True


class FakeUrl:
    def __init__(self, local: str):
        self._local = local

    def toLocalFile(self) -> str:  # noqa: N802 - mirrors the Qt name
        return self._local


class FakeMime:
    """Duck-typed QMimeData."""

    def __init__(self, text: str = "", html: str = "", image=None, urls=None):
        self._text = text
        self._html = html
        self._image = image
        self._urls = [FakeUrl(u) for u in (urls or [])]

    def hasText(self) -> bool:  # noqa: N802
        return bool(self._text)

    def text(self) -> str:
        return self._text

    def hasHtml(self) -> bool:  # noqa: N802
        return bool(self._html)

    def html(self) -> str:
        return self._html

    def hasImage(self) -> bool:  # noqa: N802
        return self._image is not None

    def imageData(self):  # noqa: N802
        return self._image

    def hasUrls(self) -> bool:  # noqa: N802
        return bool(self._urls)

    def urls(self):
        return self._urls


@pytest.fixture
def cfg(tmp_path):
    """Default config pointed at a temp directory."""
    from absorber.config import DEFAULTS

    conf = dict(DEFAULTS)
    conf["target_dir"] = str(tmp_path / "out")
    conf["model_naming"] = False
    return conf

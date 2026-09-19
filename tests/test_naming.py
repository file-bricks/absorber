from datetime import datetime

import pytest

from absorber.naming import (
    OllamaNamer,
    build_stem,
    fallback_name,
    slugify,
    unique_path,
)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hello wonderful world", "hello-wonderful-world"),
        ("Grüße aus München", "gruesse-aus-muenchen"),
        ("one two three four five six seven", "one-two-three-four-five"),
        ("  ...  ", ""),
        ("", ""),
        ("C:\\Users\\test — path?", "c-users-test-path"),
        ("Straße & Größe", "strasse-groesse"),
    ],
)
def test_slugify(text, expected):
    assert slugify(text) == expected


def test_fallback_name_uses_text_slug():
    name = fallback_name("text", "Meeting notes from today")
    assert name.endswith("_meeting-notes-from-today")
    assert name.startswith(datetime.now().strftime("%Y-%m-%d"))


def test_fallback_name_for_image_has_no_slug():
    assert fallback_name("image").endswith("_image")


def test_fallback_name_without_usable_text_falls_back_to_kind():
    assert fallback_name("text", "!!! ???").endswith("_text")


def test_unique_path_free_slot(tmp_path):
    assert unique_path(tmp_path, "note", "txt") == tmp_path / "note.txt"


def test_unique_path_collisions(tmp_path):
    (tmp_path / "note.txt").write_text("a", encoding="utf-8")
    assert unique_path(tmp_path, "note", "txt") == tmp_path / "note_2.txt"
    (tmp_path / "note_2.txt").write_text("b", encoding="utf-8")
    assert unique_path(tmp_path, "note", "txt") == tmp_path / "note_3.txt"


def test_unique_path_accepts_dotted_extension(tmp_path):
    assert unique_path(tmp_path, "x", ".md") == tmp_path / "x.md"


# --- the local model ------------------------------------------------------


def fake_http(tags=None, response="Quarterly Budget Draft", fail_on=None):
    """Build an injectable http callable returning canned Ollama answers."""

    def http(url, payload, timeout):
        if fail_on and fail_on in url:
            raise OSError("boom")
        if url.endswith("/api/tags"):
            names = ["llama3:8b"] if tags is None else tags
            return {"models": [{"name": n} for n in names]}
        return {"response": response}

    return http


def test_available_model_picks_first_when_auto():
    namer = OllamaNamer("http://x", "auto", http=fake_http(tags=["a:1", "b:2"]))
    assert namer.available_model() == "a:1"


def test_available_model_honours_explicit_choice():
    namer = OllamaNamer("http://x", "b:2", http=fake_http(tags=["a:1", "b:2"]))
    assert namer.available_model() == "b:2"


def test_available_model_none_when_requested_model_missing():
    namer = OllamaNamer("http://x", "nope", http=fake_http(tags=["a:1"]))
    assert namer.available_model() is None


def test_available_model_none_when_unreachable():
    namer = OllamaNamer("http://x", "auto", http=fake_http(fail_on="/api/tags"))
    assert namer.available_model() is None


def test_available_model_none_when_no_models_installed():
    namer = OllamaNamer("http://x", "auto", http=fake_http(tags=[]))
    assert namer.available_model() is None


def test_suggest_returns_slug():
    namer = OllamaNamer("http://x", "auto", http=fake_http())
    assert namer.suggest("some long text") == "quarterly-budget-draft"


def test_suggest_none_when_generate_fails():
    namer = OllamaNamer("http://x", "auto", http=fake_http(fail_on="/api/generate"))
    assert namer.suggest("text") is None


def test_suggest_none_on_empty_model_answer():
    namer = OllamaNamer("http://x", "auto", http=fake_http(response="   "))
    assert namer.suggest("text") is None


def test_suggest_truncates_the_sample():
    seen = {}

    def http(url, payload, timeout):
        if url.endswith("/api/tags"):
            return {"models": [{"name": "m"}]}
        seen["prompt"] = payload["prompt"]
        return {"response": "ok name"}

    OllamaNamer("http://x", "auto", http=http).suggest("y" * 5000)
    assert seen["prompt"].endswith("y" * 800)
    assert not seen["prompt"].endswith("y" * 801)


def test_build_stem_uses_model_when_available():
    namer = OllamaNamer("http://x", "auto", http=fake_http())
    stem = build_stem("text", "hello", namer)
    assert stem == f"{datetime.now().strftime('%Y-%m-%d')}_quarterly-budget-draft"


def test_build_stem_falls_back_when_model_silent():
    namer = OllamaNamer("http://x", "auto", http=fake_http(fail_on="/api/tags"))
    assert build_stem("text", "hello there", namer).endswith("_hello-there")


def test_build_stem_without_namer():
    assert build_stem("text", "hello there").endswith("_hello-there")


def test_build_stem_never_asks_the_model_for_images():
    def http(url, payload, timeout):
        raise AssertionError("the model must not be asked to name an image")

    namer = OllamaNamer("http://x", "auto", http=http)
    assert build_stem("image", "", namer).endswith("_image")

from absorber import recent


def test_load_missing_file(tmp_path):
    assert recent.load(tmp_path / "nope.json") == []


def test_load_broken_file(tmp_path):
    broken = tmp_path / "recent.json"
    broken.write_text("[[[", encoding="utf-8")
    assert recent.load(broken) == []


def test_add_puts_newest_first(tmp_path):
    store = tmp_path / "recent.json"
    recent.add(["a.txt"], store=store)
    assert recent.add(["b.txt"], store=store) == ["b.txt", "a.txt"]


def test_add_keeps_a_batch_in_order(tmp_path):
    store = tmp_path / "recent.json"
    assert recent.add(["a", "b", "c"], store=store) == ["a", "b", "c"]


def test_add_moves_a_repeat_to_the_front(tmp_path):
    store = tmp_path / "recent.json"
    recent.add(["a", "b"], store=store)
    assert recent.add(["a"], store=store) == ["a", "b"]


def test_add_caps_the_list(tmp_path):
    store = tmp_path / "recent.json"
    for i in range(15):
        entries = recent.add([f"f{i}"], limit=10, store=store)
    assert len(entries) == 10
    assert entries[0] == "f14"


def test_existing_hides_deleted_files(tmp_path):
    store = tmp_path / "recent.json"
    here = tmp_path / "here.txt"
    here.write_text("x", encoding="utf-8")
    recent.add([str(here), str(tmp_path / "gone.txt")], store=store)
    assert recent.existing(store=store) == [str(here)]

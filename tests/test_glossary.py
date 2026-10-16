import json

import pytest

from app import config, glossary


@pytest.fixture
def g():
    return json.loads((config.ROOT / "data" / "glossaries" / "armenian-classics.json").read_text())


def ids(entries):
    return [e["id"] for e in entries]


def dish_ids(entries):
    return [e["id"] for e in entries if e.get("kind") != "ingredient"]


def test_matches_dish_with_modifiers(g):
    hits = set(dish_ids(glossary.match(g, "Խորոված խոզի Խոզի չալաղաջ, սոխ, լավաշ")))
    assert hits == {"khorovats", "chalaghaj", "lavash"}


def test_short_word_needs_whole_word(g):
    # "Խաշ" (khash) must not fire inside "Խաշլամա" (khashlama)
    assert ids(glossary.match(g, "Խաշլամա")) == ["khashlama"]


def test_tolerates_ocr_typo(g):
    assert "ghapama" in ids(glossary.match(g, "Ղափամմա"))


def test_matches_russian_menu(g):
    assert "khorovats" in ids(glossary.match(g, "Хоровац из баранины"))


def test_no_false_positive(g):
    assert glossary.match(g, "Կարտոֆիլ ֆրի") == []


def test_correction_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "GLOSSARY_DIR", tmp_path)
    glossary.upsert_correction("my-place", "Տատիկի ապուր", "en", "Grandma's Soup", "Lentil soup")
    entry = glossary.match(glossary.load("my-place"), "Տատիկի ապուր")[0]
    assert entry["translations"]["en"]["name"] == "Grandma's Soup"
    assert entry["translations"]["en"]["owner"] is True
    # A second correction for another language updates the same entry.
    glossary.upsert_correction("my-place", "Տատիկի ապուր", "ru", "Бабушкин суп", "")
    assert len(glossary.load("my-place")["entries"]) == 1


def test_fuzzy_is_word_aligned(g):
    # "Փախլավա" (pakhlava) contains the letters of "լավա" but is not lavash.
    assert dish_ids(glossary.match(g, "Փախլավա Ընկույզ, մեղր")) == ["pakhlava"]


def test_dietary_guard_drops_false_vegetarian():
    from app.pipeline import check_dietary
    assert check_dietary(["vegetarian"], "Տոլմա", "Աղացած միս, բրինձ") == []
    assert check_dietary(["vegetarian"], "Ղափամա", "Դդում բրնձով") == ["vegetarian"]
    assert check_dietary([], "Խորոված խոզի") == ["contains-pork"]


def test_inflected_forms_match(g):
    assert "khoriz" in ids(glossary.match(g, "Քաղցր խմորեղեն խորիզով"))
    assert "lavash" in ids(glossary.match(g, "Шашлык с лавашом"))


def test_snap_fixes_ocr_letter_swaps(g):
    assert glossary.snap_words(g, "Մանքի")[0] == "Մանթի"
    assert glossary.snap_words(g, "Գաքա")[0] == "Գաթա"


def test_snap_leaves_unknown_and_short_words(g):
    assert glossary.snap_words(g, "Կարտոֆիլ ֆրի") == ("Կարտոֆիլ ֆրի", [])
    assert glossary.snap_words(g, "Թան")[1] == []


def test_clean_merges_vision_duplicates():
    from app.pipeline import _clean
    menu = {"title": "", "currency": "", "sections": [{"name": "A", "items": [
        {"name": "Գաթա", "description": "քաղցր", "price": ""},
        {"name": "Գաթա", "description": "", "price": "1200"},
    ]}]}
    items = _clean(menu, None)["sections"][0]["items"]
    assert [(i["name"], i["description"], i["price"]) for i in items] == [("Գաթա", "քաղցր", "1200")]


def test_snap_joins_ocr_split_word(g):
    assert glossary.snap_words(g, "Բ ատուրմո")[0] == "Բաստուրմա"


def test_ingredient_words_match_inflected(g):
    hits = set(ids(glossary.match(g, "Դդում բրնձով, չամիչով և մեղրով")))
    assert {"pumpkin", "raisins", "honey"} <= hits


def test_dietary_guard_drops_invented_pork():
    from app.pipeline import check_dietary
    assert check_dietary(["contains-pork"], "Բաստուրմա", "Չորացրած տավարի միս", "Basturma", "Cured beef") == []


def test_owner_correction_beats_the_model(tmp_path, monkeypatch):
    from app import pipeline
    monkeypatch.setattr(config, "GLOSSARY_DIR", tmp_path)
    glossary.upsert_correction("cafe", "Տատիկի ապուր", "en", "Grandma's Lentil Soup", "Red lentils, apricot, mint.")

    def fake_model(model, prompt, schema, images=None, system=None):
        return {"title": "Menu", "sections": [{"name": "Soups", "items": [
            {"id": "d1", "name": "Grandmother Soup", "description": "A soup.", "dietary": []}]}]}, {}
    monkeypatch.setattr(pipeline, "chat_json", fake_model)

    menu = pipeline._with_ids({"title": "Ճաշացանկ", "currency": "դր.", "sections": [
        {"name": "Ապուրներ", "items": [{"name": "Տատիկի ապուր", "description": "Ոսպ", "price": "900"}]}]})
    res, _ = pipeline.translate(menu, "hy", "en", "cafe")
    item = res["sections"][0]["items"][0]
    assert (item["name"], item["description"], item["price"]) == \
        ("Grandma's Lentil Soup", "Red lentils, apricot, mint.", "900")
    assert res["currency"] == "AMD"

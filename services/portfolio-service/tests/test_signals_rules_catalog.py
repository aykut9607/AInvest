"""The rule catalog reads every numbered rule once and ties pictures only to rules that exist."""

import re

from signals.rules import rules_catalog as rc


def test_every_numbered_table_row_is_read_once():
    for f in rc.FAMILIES:
        text = (rc.HERE / f.words).read_text(encoding="utf-8")
        ids = [r.id for r in rc.read_rules(text)]
        rows = re.findall(rf"^\|\s*({rc.ID})\s*\|", text, re.M)          # code-status tables repeat a few numbers
        assert len(ids) == len(set(ids)) and set(ids) == set(rows), f.name
        assert all(r.words for r in rc.read_rules(text)), f.name


def test_links_point_to_real_pictures_and_real_rules():
    known = {r.id for f in rc.FAMILIES for r in rc.read_rules((rc.HERE / f.words).read_text(encoding="utf-8"))}
    titles = {f.key: [p.title for p in rc.read_pictures(f.key, (rc.HERE / f.pictures).read_text(encoding="utf-8"))]
              for f in rc.FAMILIES if f.pictures}
    for (key, start), ids in rc.LINKS.items():
        assert any(t.startswith(start) for t in titles[key]), (key, start)
        assert set(ids.split()) <= known, ids


def test_number_ranges():
    assert rc.numbers_in("Mum formasyonları (SM-01…04)") == ["SM-01", "SM-02", "SM-03", "SM-04"]
    assert rc.numbers_in("PA-03, PA-04a") == ["PA-03", "PA-04a"]


def test_escaped_pipes_stay_in_one_cell():
    assert rc.cells(r"| RK-02 | a / \|b\| | N |") == ["RK-02", "a / |b|", "N"]

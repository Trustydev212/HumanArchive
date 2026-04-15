"""Test graph module: load archive, build relations, category tree, prism."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.graph import build_perspective_prism, load_archive_graph


@pytest.fixture
def mini_archive(tmp_path, sample_memory, memory_with_pii):
    """Tạo một archive tmp với 2 event + 1 relation."""
    root = tmp_path
    (root / "events").mkdir()

    # Event A: flood
    ea = root / "events" / "2024-example-flood-demo"
    ea.mkdir()
    sample_memory["event"]["event_id"] = "2024-example-flood-demo"
    sample_memory["event"]["tags"] = ["lũ", "hư-cấu"]
    sample_memory["event"]["categories"] = ["natural-disaster/flood"]
    # relation trỏ đến event B
    sample_memory.setdefault("context", {})["relations"] = [
        {"event_id": "2024-example-dam-demo", "type": "caused_by"}
    ]
    # Recompute memory_id vì content thay đổi
    import hashlib as _h
    def _id(m):
        c = {k: v for k, v in m.items() if k != "memory_id"}
        return _h.sha256(
            json.dumps(c, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()[:16]

    sample_memory["memory_id"] = _id(sample_memory)
    (ea / f"{sample_memory['memory_id']}.json").write_text(
        json.dumps(sample_memory, ensure_ascii=False), encoding="utf-8"
    )

    # Event B: dam
    eb = root / "events" / "2024-example-dam-demo"
    eb.mkdir()
    dam_memory = dict(sample_memory)
    dam_memory["event"] = {
        "event_id": "2024-example-dam-demo",
        "name": "Quyết định xả đập (hư cấu)",
        "date": "2024-09-09",
        "tags": ["đập", "hư-cấu"],
        "categories": ["technological/infrastructure-failure"],
    }
    dam_memory["perspective"] = {"role": "authority", "proximity": "direct"}
    dam_memory["context"] = {}
    dam_memory["memory_id"] = _id(dam_memory)
    (eb / f"{dam_memory['memory_id']}.json").write_text(
        json.dumps(dam_memory, ensure_ascii=False), encoding="utf-8"
    )
    return root


class TestLoadArchive:
    def test_loads_all_events(self, mini_archive):
        g = load_archive_graph(mini_archive)
        assert len(g.nodes) == 2
        event_ids = {n.event_id for n in g.nodes}
        assert "2024-example-flood-demo" in event_ids
        assert "2024-example-dam-demo" in event_ids

    def test_relation_edge_captured(self, mini_archive):
        g = load_archive_graph(mini_archive)
        edges = [(e.source, e.target, e.type) for e in g.edges]
        assert (
            "2024-example-flood-demo",
            "2024-example-dam-demo",
            "caused_by",
        ) in edges

    def test_tags_aggregated(self, mini_archive):
        g = load_archive_graph(mini_archive)
        assert "lũ" in g.tag_counts
        assert "đập" in g.tag_counts

    def test_category_tree_is_nested(self, mini_archive):
        g = load_archive_graph(mini_archive)
        # 'natural-disaster' và 'technological' đều là root
        assert "natural-disaster" in g.category_tree
        assert "technological" in g.category_tree
        # flood là con của natural-disaster
        assert "flood" in g.category_tree["natural-disaster"]

    def test_empty_archive(self, tmp_path):
        g = load_archive_graph(tmp_path)
        assert g.nodes == []
        assert g.edges == []

    def test_withdrawn_memory_excluded(self, mini_archive, withdrawn_memory):
        # Thêm memory withdrawn vào event flood — event vẫn tồn tại vì có memory khác public
        e = mini_archive / "events" / "2024-example-flood-demo"
        withdrawn_memory["event"]["event_id"] = "2024-example-flood-demo"
        (e / f"{withdrawn_memory['memory_id']}.json").write_text(
            json.dumps(withdrawn_memory, ensure_ascii=False), encoding="utf-8"
        )
        g = load_archive_graph(mini_archive)
        node = next(n for n in g.nodes if n.event_id == "2024-example-flood-demo")
        # memory_count chỉ đếm cái đang viewable
        assert node.memory_count == 1


class TestPerspectivePrism:
    def test_prism_groups_by_role(self, mini_archive):
        prism = build_perspective_prism(
            "2024-example-flood-demo", archive_root=mini_archive
        )
        assert prism["event_id"] == "2024-example-flood-demo"
        # fixture sample_memory có role=witness
        assert "witness" in prism["roles"]

    def test_missing_roles_listed(self, mini_archive):
        prism = build_perspective_prism(
            "2024-example-flood-demo", archive_root=mini_archive
        )
        # Event flood chỉ có 1 memory (witness) → 5 role còn lại missing
        assert len(prism["missing_roles"]) >= 5

    def test_not_found_raises(self, mini_archive):
        with pytest.raises(FileNotFoundError):
            build_perspective_prism("does-not-exist", archive_root=mini_archive)

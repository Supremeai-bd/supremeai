"""M2-B — budgeter tests (pure)."""

from __future__ import annotations

from context.budget import ContextBudget, pack_items
from context.items import ContextItem, ItemKind, Provenance, SummaryLevel


def _prov(ref: str, user: str = "u1") -> Provenance:
    return Provenance(source_type="memory", source_ref=ref, user_id=user, scope_level="chat")


def _item(
    ref: str, content: str, score: float, kind=ItemKind.memory, level=SummaryLevel.L0
) -> ContextItem:
    return ContextItem(
        item_id=ref,
        kind=kind,
        summary_level=level,
        content=content,
        score=score,
        provenance=_prov(ref),
    )


def _four_chars(text: str) -> int:
    return len(text) // 4


class TestPacking:
    def test_all_fit(self):
        items = [_item("a", "x" * 40, 0.9), _item("b", "y" * 40, 0.8)]
        packed, report = pack_items(
            items, ContextBudget(total_tokens=100), estimate_tokens=_four_chars
        )
        assert [i.item_id for i in packed] == ["a", "b"]
        assert report.admitted_tokens == 20
        assert report.dropped == ()

    def test_score_desc_priority(self):
        items = [_item("low", "x" * 40, 0.2), _item("high", "y" * 40, 0.9)]
        packed, _ = pack_items(items, ContextBudget(total_tokens=10), estimate_tokens=_four_chars)
        assert [i.item_id for i in packed] == ["high"]

    def test_over_budget_dropped_and_reported(self):
        items = [
            _item("a", "x" * 40, 0.9),  # 10 tokens
            _item("b", "y" * 40, 0.8),  # 10 tokens
            _item("c", "z" * 40, 0.7),  # 10 tokens
        ]
        packed, report = pack_items(
            items, ContextBudget(total_tokens=25), estimate_tokens=_four_chars
        )
        assert len(packed) == 2
        assert report.dropped[0]["item_id"] == "c"
        assert report.dropped[0]["reason"] == "over_total_budget"

    def test_below_min_score_never_admitted(self):
        items = [_item("weak", "x" * 40, 0.1)]
        packed, report = pack_items(
            items, ContextBudget(total_tokens=100, min_score=0.5), estimate_tokens=_four_chars
        )
        assert packed == []
        assert report.dropped[0]["reason"] == "below_min_score"

    def test_per_kind_cap(self):
        items = [
            _item("m1", "x" * 40, 0.9, kind=ItemKind.memory),
            _item("m2", "x" * 40, 0.8, kind=ItemKind.memory),
            _item("f1", "x" * 40, 0.7, kind=ItemKind.file),
        ]
        packed, _ = pack_items(
            items,
            ContextBudget(total_tokens=100, per_kind={"memory": 10}),
            estimate_tokens=_four_chars,
        )
        assert [i.item_id for i in packed] == ["m1", "f1"]

    def test_dedup_by_item_id(self):
        items = [_item("a", "x" * 40, 0.9), _item("a", "x" * 40, 0.9)]
        packed, report = pack_items(
            items, ContextBudget(total_tokens=100), estimate_tokens=_four_chars
        )
        assert len(packed) == 1
        assert report.requested_items == 2

    def test_dedup_by_source_ref_and_level(self):
        p1 = ContextItem(
            item_id="id-1",
            kind=ItemKind.memory,
            summary_level=SummaryLevel.L0,
            content="same",
            score=0.9,
            provenance=_prov("src-1"),
        )
        p2 = ContextItem(
            item_id="id-2",
            kind=ItemKind.memory,
            summary_level=SummaryLevel.L0,
            content="same",
            score=0.8,
            provenance=_prov("src-1"),
        )
        packed, _ = pack_items(
            [p1, p2], ContextBudget(total_tokens=100), estimate_tokens=_four_chars
        )
        assert [i.item_id for i in packed] == ["id-1"]

    def test_cheaper_level_wins_ties(self):
        l2 = _item("raw", "x" * 40, 0.9, level=SummaryLevel.L2)
        l0 = _item("sum", "x" * 40, 0.9, level=SummaryLevel.L0)
        packed, _ = pack_items(
            [l2, l0], ContextBudget(total_tokens=10), estimate_tokens=_four_chars
        )
        assert [i.item_id for i in packed] == ["sum"]

    def test_report_is_honest(self):
        items = [_item(f"i{n}", "x" * 40, 0.5) for n in range(5)]
        _, report = pack_items(items, ContextBudget(total_tokens=12), estimate_tokens=_four_chars)
        assert report.requested_items == 5
        assert report.admitted_items + len(report.dropped) == 5
        assert report.admitted_tokens <= 12

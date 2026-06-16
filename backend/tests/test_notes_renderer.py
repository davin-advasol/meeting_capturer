from app.models import ActionItem, Notes, TimelineEntry
from app.notes.renderer import render_markdown


def test_render_markdown_has_all_sections():
    notes = Notes(
        summary="The team reviewed the rollout.",
        action_items=[
            ActionItem(task="Ship auth fix", owner="Speaker 2", due="2026-06-18"),
            ActionItem(task="Draft comms", owner=None, due=None),
        ],
        decisions=["Delay billing migration to Q4"],
        topic_timeline=[TimelineEntry(start=612.4, topic="Billing risks")],
        open_questions=["Who owns the backfill?"],
    )
    md = render_markdown(notes, title="Weekly Sync")

    assert md.startswith("# Weekly Sync — Notes")
    assert "## Summary" in md
    assert "The team reviewed the rollout." in md
    assert "- [ ] **Speaker 2** — Ship auth fix (due 2026-06-18)" in md
    assert "- [ ] Draft comms" in md
    assert "## Decisions" in md
    assert "- Delay billing migration to Q4" in md
    assert "## Topic Timeline" in md
    assert "- [10:12] Billing risks" in md
    assert "## Open Questions" in md
    assert "- Who owns the backfill?" in md


def test_render_markdown_omits_empty_sections():
    md = render_markdown(Notes(summary="Just a summary."), title="X")
    assert "## Action Items" not in md
    assert "## Summary" in md

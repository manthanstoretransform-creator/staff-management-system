"""
Coverage for the task list's hand-built resizable-column model
(TaskSection._resize_columns / TaskRow.set_column_widths).

The task list is a header row lined up against each TaskRow's own
independently-built layout, not a real QTableWidget/QHeaderView -- so
"draggable columns" only works if the header and every visible row read
from one shared width model and are kept in sync on every drag. These tests
exercise that model directly (the same calls ColumnResizeHandle.dragged
ultimately triggers) rather than simulating real mouse events.
"""
from unittest.mock import MagicMock

from ui.task_table import (
    COLUMN_DEFAULT_WIDTHS,
    COLUMN_MIN_WIDTHS,
    COLUMN_ORDER,
    TaskRow,
    TaskSection,
)


def _make_section() -> TaskSection:
    return TaskSection(api=MagicMock(), task_service=MagicMock())


def test_dragging_right_grows_left_column_and_shrinks_right(qapp):
    section = _make_section()
    before = dict(section._column_widths)
    # created (default 130, floor 100) has 30px of headroom to give up --
    # stay comfortably inside that so this test isn't itself exercising the
    # floor-clamping behavior covered separately below.
    delta = 20
    assert delta < before["created"] - COLUMN_MIN_WIDTHS["created"]

    section._resize_columns("task", "created", delta)

    assert section._column_widths["task"] == before["task"] + delta
    assert section._column_widths["created"] == before["created"] - delta
    assert section._column_widths["tracked"] == before["tracked"]  # untouched
    assert section._column_widths["action"] == before["action"]    # untouched


def test_neither_column_can_be_dragged_below_its_floor(qapp):
    section = _make_section()
    before_total = section._column_widths["task"] + section._column_widths["created"]

    section._resize_columns("task", "created", -100_000)  # absurdly large drag

    assert section._column_widths["task"] == COLUMN_MIN_WIDTHS["task"]
    # The whole trade is conserved between just these two columns.
    after_total = section._column_widths["task"] + section._column_widths["created"]
    assert after_total == before_total


def test_dragging_the_other_direction_clamps_the_other_column(qapp):
    section = _make_section()
    before_total = section._column_widths["task"] + section._column_widths["created"]

    section._resize_columns("task", "created", 100_000)

    assert section._column_widths["created"] == COLUMN_MIN_WIDTHS["created"]
    after_total = section._column_widths["task"] + section._column_widths["created"]
    assert after_total == before_total


def test_header_labels_and_all_visible_rows_stay_in_sync_after_a_drag(qapp):
    section = _make_section()
    section._project = {"id": 1, "project_name": "Demo"}
    section._tasks = [{"id": 1, "name": "Task A"}, {"id": 2, "name": "Task B"}]
    section._rebuild_rows()
    assert len(section._task_rows) == 2

    section._resize_columns("tracked", "action", 25)

    expected = section._column_widths
    assert section._column_header_labels["tracked"].width() == expected["tracked"]
    assert section._column_header_labels["action"].width() == expected["action"]
    for row in section._task_rows:
        assert row._tracked_widget.width() == expected["tracked"]
        assert row._action_widget.width() == expected["action"]


def test_new_rows_pick_up_the_current_column_widths(qapp):
    """A row built *after* a drag (e.g. from a later search/filter) must use
    the already-adjusted widths, not the original defaults."""
    section = _make_section()
    section._resize_columns("task", "created", 50)
    widened = dict(section._column_widths)

    section._project = {"id": 1, "project_name": "Demo"}
    section._tasks = [{"id": 1, "name": "Task A"}]
    section._rebuild_rows()

    row = section._task_rows[0]
    assert row._name_widget.width() == widened["task"]
    assert row._created_label.width() == widened["created"]


def test_task_row_defaults_to_the_standard_widths_when_none_given(qapp):
    row = TaskRow({"id": 1, "name": "Solo"}, project_id=1, project_name="P", project_color="#000")
    assert row._name_widget.width() == COLUMN_DEFAULT_WIDTHS["task"]


def test_all_four_columns_are_covered_by_the_shared_model(qapp):
    assert set(COLUMN_ORDER) == {"task", "created", "tracked", "action"}
    assert set(COLUMN_DEFAULT_WIDTHS) == set(COLUMN_ORDER)
    assert set(COLUMN_MIN_WIDTHS) == set(COLUMN_ORDER)


def test_memo_column_is_the_only_one_with_a_stretch_factor(qapp):
    """Regression: on a window wider than the four columns' combined pixel
    widths, a purely fixed-width layout leaves a dead gap after ACTION
    instead of filling the table -- reported as "table structure is
    broken" on a wide screen. TASK must be the sole stretchy column (in
    both the header and every row) so it absorbs that leftover space
    instead of leaving it empty."""
    section = _make_section()
    header_layout = section._column_header_labels["task"].parentWidget().layout()
    for i in range(header_layout.count()):
        widget = header_layout.itemAt(i).widget()
        if widget is section._column_header_labels["task"]:
            assert header_layout.stretch(i) == 1
        elif widget is not None:
            assert header_layout.stretch(i) == 0

    section._project = {"id": 1, "project_name": "Demo"}
    section._tasks = [{"id": 1, "name": "Task A"}]
    section._rebuild_rows()
    row = section._task_rows[0]
    row_layout = row.layout()
    for i in range(row_layout.count()):
        widget = row_layout.itemAt(i).widget()
        if widget is row._name_widget:
            assert row_layout.stretch(i) == 1
        elif widget is not None:
            assert row_layout.stretch(i) == 0

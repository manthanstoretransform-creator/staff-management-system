"""
Coverage for TaskSection's "Active: Task Name" indicator, shown inline on
the title line right after the project name while a task is running. The
idle "No task currently running" message is a separate, unchanged widget
below the title -- the two are never shown at the same time.
"""
from unittest.mock import MagicMock

from ui.task_table import TaskSection


def _make_section() -> TaskSection:
    return TaskSection(api=MagicMock(), task_service=MagicMock())


def test_idle_state_shows_only_the_idle_message(qapp):
    section = _make_section()
    section._update_current_task_indicator()
    assert not section._current_task_lbl.isHidden()
    assert section._current_task_lbl.text() == "No task currently running"
    assert section._active_task_lbl.isHidden()


def test_running_state_shows_active_label_inline_and_hides_idle_message(qapp):
    section = _make_section()
    section._tasks = [{"id": 1, "name": "Design homepage"}]
    section._running_task_id = 1
    section._update_current_task_indicator()

    assert not section._active_task_lbl.isHidden()
    assert section._active_task_lbl.text() == "Active: <b>Design homepage</b>"
    assert section._current_task_lbl.isHidden()


def test_active_label_sits_on_the_same_line_as_the_project_title(qapp):
    """_title_label and _active_task_lbl are both direct items of the same
    QHBoxLayout ("title_hbox") -- the idle message below lives in a
    different layout entirely."""
    section = _make_section()
    header_row = section._title_label.parent()
    header_layout = header_row.layout()

    def find_layout_containing(layout, widget):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget() is widget:
                return layout
            if item.layout() is not None:
                found = find_layout_containing(item.layout(), widget)
                if found is not None:
                    return found
        return None

    title_layout = find_layout_containing(header_layout, section._title_label)
    active_layout = find_layout_containing(header_layout, section._active_task_lbl)
    idle_layout = find_layout_containing(header_layout, section._current_task_lbl)

    assert title_layout is active_layout
    assert title_layout is not idle_layout

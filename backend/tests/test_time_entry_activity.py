import pytest
from app.services.time_entry_activity_service import calculate_activity_percentage
from app.schemas.time_entry_activity import TimeEntryActivityCreate, TimeEntryActivityBatchCreate


def test_activity_percentage_calculation():
    # 0 activity = 0%
    assert calculate_activity_percentage(0, 0, 0) == 0

    # Half activity
    # 60 / 120 * 0.40 + 15 / 30 * 0.30 + 200 / 400 * 0.30 = 0.20 + 0.15 + 0.15 = 0.50 -> 50%
    assert calculate_activity_percentage(60, 15, 200) == 50

    # Max / overload activity caps at 100%
    assert calculate_activity_percentage(300, 100, 1000) == 100

    # Low activity
    # 12 / 120 * 0.40 + 3 / 30 * 0.30 + 40 / 400 * 0.30 = 0.04 + 0.03 + 0.03 = 0.10 -> 10%
    assert calculate_activity_percentage(12, 3, 40) == 10


def test_activity_schema_validation():
    # Valid payload
    payload = TimeEntryActivityCreate(
        organization_id=1,
        time_entry_id=10,
        keyboard_strokes=50,
        mouse_clicks=10,
        mouse_movements=100,
        activity_percentage=75
    )
    assert payload.activity_percentage == 75

    # Batch payload
    batch = TimeEntryActivityBatchCreate(activities=[payload])
    assert len(batch.activities) == 1

import datetime

import pytest

from manman.models import StatusInfo, StatusType


def test_field_validator():
    """Test the status_type field validator."""

    status1 = StatusInfo.create("TestClass", StatusType.RUNNING, worker_id=1)
    assert status1.status_type == StatusType.RUNNING

    status2 = StatusInfo(
        class_name="TestClass",
        status_type="RUNNING",  # String instead of enum
        worker_id=1,
    )
    assert status2.status_type == StatusType.RUNNING

    # Test 3: Invalid string value (should fail)
    with pytest.raises(ValueError):
        StatusInfo(
            class_name="TestClass",
            status_type="INVALID_STATUS",  # Invalid string
            worker_id=1,
        )

    status4 = StatusInfo(
        class_name="TestClass",
        status_type=StatusType.CREATED,
        worker_id=1,
        as_of=datetime.datetime.now(datetime.timezone.utc),
    )
    assert status4.status_type == StatusType.CREATED

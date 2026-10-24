from unittest.mock import Mock
from shorts.scheduler import wait_for_worker_lock


def test_restart_waits_for_old_worker_to_release_lock():
    acquire = Mock(side_effect=[PermissionError(), PermissionError(), None])
    sleep = Mock()
    assert wait_for_worker_lock(acquire, attempts=4, sleep=sleep)
    assert acquire.call_count == 3
    assert sleep.call_count == 2


def test_busy_worker_is_not_duplicated():
    acquire = Mock(side_effect=PermissionError())
    assert not wait_for_worker_lock(acquire, attempts=2, sleep=Mock())
    assert acquire.call_count == 2

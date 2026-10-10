import pytest

from minetoofar.ui.camera import follow_axis


def test_target_inside_the_middle_third_leaves_the_camera_alone() -> None:
    # view 60 -> margin 20 -> with cam 10 the dead zone is columns 30..49
    assert follow_axis(10, 30, 60, 200) == 10
    assert follow_axis(10, 49, 60, 200) == 10


def test_camera_scrolls_when_the_target_leaves_the_zone() -> None:
    assert follow_axis(10, 29, 60, 200) == 9
    assert follow_axis(10, 50, 60, 200) == 11
    assert follow_axis(10, 120, 60, 200) == 81  # lands on the zone's right edge


def test_camera_stays_inside_the_level() -> None:
    assert follow_axis(0, 2, 60, 200) == 0
    assert follow_axis(140, 199, 60, 200) == 140
    assert follow_axis(50, 5, 60, 200) == 0


def test_level_smaller_than_the_view_pins_the_camera_at_zero() -> None:
    assert follow_axis(0, 30, 100, 80) == 0
    assert follow_axis(7, 30, 100, 80) == 0


@pytest.mark.parametrize("view", [0, 1, 2, 3])
def test_tiny_views_do_not_misbehave(view: int) -> None:
    for target in (0, 5, 79):
        cam = follow_axis(0, target, view, 80)
        assert 0 <= cam <= max(0, 80 - view)
        assert view == 0 or cam <= target < cam + view

from fixoflow.ui.overlay import (
    anchored_origin,
    dragged_origin,
    nearest_zone,
    zone_origin,
)

FRAME = (0.0, 0.0, 1440.0, 900.0)
IDLE = (92.0, 30.0)


def test_zone_origins_pin_the_pill_to_three_shared_slots():
    assert zone_origin('bottom-center', IDLE, FRAME) == ((1440 - 92) / 2, 10.0)
    assert zone_origin('top-center', IDLE, FRAME) == ((1440 - 92) / 2, 900 - 30 - 10)
    assert zone_origin('bottom-right', IDLE, FRAME) == (1440 - 92 - 10, 10.0)


def test_resize_keeps_each_zone_anchor_edge():
    old_size, new_size = IDLE, (208.0, 36.0)
    bottom = anchored_origin('bottom-center', (674.0, 10.0), old_size, new_size)
    assert bottom == (674.0 - (208 - 92) / 2, 10.0)
    top = anchored_origin('top-center', (674.0, 860.0), old_size, new_size)
    assert top == (674.0 - (208 - 92) / 2, 890.0 - 36.0)
    right = anchored_origin('bottom-right', (1338.0, 10.0), old_size, new_size)
    assert right == (1430.0 - 208.0, 10.0)


def test_dropped_pill_snaps_to_the_closest_zone():
    size = (208.0, 36.0)
    assert nearest_zone((720.0, 18.0), size, FRAME) == 'bottom-center'
    assert nearest_zone((720.0, 882.0), size, FRAME) == 'top-center'
    assert nearest_zone((1300.0, 25.0), size, FRAME) == 'bottom-right'


def test_drag_converts_web_screen_deltas_to_window_origin():
    # WebKit screen coordinates grow downward; window origins grow upward.
    origin = dragged_origin((600.0, 12.0), (700.0, 500.0), (760.0, 460.0), IDLE, FRAME)
    assert origin == (660.0, 52.0)


def test_drag_is_clamped_inside_the_visible_frame():
    origin = dragged_origin((600.0, 12.0), (700.0, 500.0), (5000.0, -5000.0), IDLE, FRAME)
    assert origin == (1440 - 92, 900 - 30)
    origin = dragged_origin((600.0, 12.0), (700.0, 500.0), (-5000.0, 5000.0), IDLE, FRAME)
    assert origin == (0.0, 0.0)

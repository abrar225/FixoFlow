from fixoflow.ui.overlay import (
    dragged_origin,
    nearest_zone,
    zone_origin,
)

FRAME = (0.0, 0.0, 1440.0, 900.0)
IDLE = (116.0, 30.0)


def test_zone_origins_pin_the_pill_to_four_shared_slots():
    assert zone_origin('bottom-center', IDLE, FRAME) == ((1440 - 116) / 2, 10.0)
    assert zone_origin('top-center', IDLE, FRAME) == ((1440 - 116) / 2, 900 - 30 - 10)
    assert zone_origin('bottom-left', IDLE, FRAME) == (10.0, 10.0)
    assert zone_origin('bottom-right', IDLE, FRAME) == (1440 - 116 - 10, 10.0)


def test_resize_re_derives_the_canonical_slot_for_every_zone():
    # Resizing is idempotent: whatever state changes raced before it, the
    # origin always lands on the zone's canonical slot for the new size.
    size = (216.0, 36.0)
    assert zone_origin('bottom-center', size, FRAME) == ((1440 - 216) / 2, 10.0)
    assert zone_origin('top-center', size, FRAME) == ((1440 - 216) / 2, 900 - 36 - 10)
    assert zone_origin('bottom-left', size, FRAME) == (10.0, 10.0)
    assert zone_origin('bottom-right', size, FRAME) == (1440 - 216 - 10, 10.0)


def test_dropped_pill_snaps_to_the_closest_zone():
    size = (216.0, 36.0)
    assert nearest_zone((720.0, 18.0), size, FRAME) == 'bottom-center'
    assert nearest_zone((720.0, 882.0), size, FRAME) == 'top-center'
    assert nearest_zone((80.0, 25.0), size, FRAME) == 'bottom-left'
    assert nearest_zone((1380.0, 25.0), size, FRAME) == 'bottom-right'


def test_drag_converts_web_screen_deltas_to_window_origin():
    # WebKit screen coordinates grow downward; window origins grow upward.
    origin = dragged_origin((600.0, 12.0), (700.0, 500.0), (760.0, 460.0), IDLE, FRAME)
    assert origin == (660.0, 52.0)


def test_drag_is_clamped_inside_the_visible_frame():
    origin = dragged_origin((600.0, 12.0), (700.0, 500.0), (5000.0, -5000.0), IDLE, FRAME)
    assert origin == (1440 - 116, 900 - 30)
    origin = dragged_origin((600.0, 12.0), (700.0, 500.0), (-5000.0, 5000.0), IDLE, FRAME)
    assert origin == (0.0, 0.0)

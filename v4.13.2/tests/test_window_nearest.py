from src.capture.window import nearest_by_ts

def test_nearest_by_ts():
    items = [
        {"ts":"2026-01-01T00:00:00+00:00","x":1},
        {"ts":"2026-01-01T00:00:02+00:00","x":2},
        {"ts":"2026-01-01T00:00:05+00:00","x":3},
    ]
    n = nearest_by_ts(items, "2026-01-01T00:00:03+00:00")
    assert n["x"] == 2

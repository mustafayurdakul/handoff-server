from sensorkit.readings import parse
from sensorkit.stats import alarms, summary


def test_summary():
    s = summary([1.0, 2.0, 6.0])
    assert (s.count, s.min, s.max, s.mean) == (3, 1.0, 6.0, 3.0)


def test_alarms_outside_range():
    readings = parse("timestamp,sensor,value\n2026-10-01T08:00:00,t,5\n2026-10-01T08:01:00,t,50\n")
    assert [r.value for r in alarms(readings, low=0, high=10)] == [50.0]

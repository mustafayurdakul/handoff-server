import pytest

from sensorkit.readings import by_sensor, parse

CSV = """timestamp,sensor,value
2026-10-01T08:00:00,temp-1,21.5
2026-10-01T08:00:00,press-1,1.20
2026-10-01T08:01:00,temp-1,22.0
"""


def test_parse_reads_every_row():
    readings = parse(CSV)
    assert len(readings) == 3
    assert readings[0].sensor == "temp-1"
    assert readings[0].value == 21.5


def test_parse_names_the_bad_line():
    with pytest.raises(ValueError, match="line 3"):
        parse("timestamp,sensor,value\n2026-10-01T08:00:00,t,1\n2026-10-01T08:01:00,t,oops\n")


def test_by_sensor_groups_in_order():
    groups = by_sensor(parse(CSV))
    assert list(groups) == ["temp-1", "press-1"]
    assert [r.value for r in groups["temp-1"]] == [21.5, 22.0]

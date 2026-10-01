import unittest
from datetime import date, datetime, timedelta, timezone

import yaml
from geode.configs.config_base import ConfigBase, DatetimeField


class TimestampConfig(ConfigBase):
    timestamp = DatetimeField()


class DatetimeFieldTests(unittest.TestCase):
    def test_date_becomes_utc_midnight(self) -> None:
        field = DatetimeField()
        field.load(date(2024, 2, 29))
        self.assertEqual(field.value, datetime(2024, 2, 29, tzinfo=timezone.utc))

    def test_yaml_date_loads_through_config(self) -> None:
        config = TimestampConfig()
        config.load(yaml.safe_load("timestamp: 2024-02-29"))
        self.assertEqual(config.timestamp, datetime(2024, 2, 29, tzinfo=timezone.utc))
        self.assertEqual(config.to_dict()["timestamp"], config.timestamp)

    def test_datetime_values_keep_their_timezone(self) -> None:
        values = (
            datetime(2024, 2, 29, 12, 30, tzinfo=timezone.utc).replace(tzinfo=None),
            datetime(2024, 2, 29, 12, 30, tzinfo=timezone(timedelta(hours=9))),
        )
        for value in values:
            with self.subTest(value=value):
                field = DatetimeField()
                field.load(value)
                self.assertIs(field.value, value)

    def test_iso_string_keeps_its_timezone(self) -> None:
        field = DatetimeField()
        field.load("2024-02-29T12:30:00+09:00")
        self.assertEqual(
            field.value,
            datetime(2024, 2, 29, 12, 30, tzinfo=timezone(timedelta(hours=9))),
        )

    def test_unsupported_value_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            DatetimeField().load([])


if __name__ == "__main__":
    unittest.main()

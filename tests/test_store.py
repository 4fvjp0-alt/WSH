import json
import tempfile
import unittest
from pathlib import Path

from helpers import expense, ids, make_trip
from settle import store
from settle.engine import compute
from settle.models import SCHEMA_VERSION, Book, migrate


class TestStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "data.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_missing_file_gives_empty_book(self):
        self.assertEqual(store.load(self.path).trips, [])

    def test_roundtrip_preserves_settlement(self):
        trip = make_trip(rates={"JPY": 9.2}, rounding_unit=100)
        m = ids(trip)
        trip.expenses = [
            expense("e1", 30000, m["민수"], currency="JPY",
                    adjustments={m["지영"]: 1000}),
            expense("e2", 50000, m["지영"]),
        ]
        book = Book(trips=[trip], current_trip_id=trip.id)
        store.save(book, self.path)
        restored = store.load(self.path)
        self.assertEqual(compute(trip).rounded_net,
                         compute(restored.trips[0]).rounded_net)

    def test_save_makes_backup(self):
        book = Book(trips=[make_trip()])
        store.save(book, self.path)
        store.save(book, self.path)
        self.assertTrue(self.path.with_suffix(".json.bak").exists())

    def test_file_is_readable_utf8_json(self):
        store.save(Book(trips=[make_trip()]), self.path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], SCHEMA_VERSION)
        self.assertIn("민수", self.path.read_text(encoding="utf-8"))

    def test_future_version_is_rejected(self):
        with self.assertRaises(ValueError):
            migrate({"version": SCHEMA_VERSION + 1})

    def test_category_hints_persist(self):
        book = Book(trips=[make_trip()], category_hints={"우리동네가게": "식비"})
        store.save(book, self.path)
        self.assertEqual(store.load(self.path).category_hints["우리동네가게"], "식비")


if __name__ == "__main__":
    unittest.main()

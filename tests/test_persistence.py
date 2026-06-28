"""Persistence adapter tests — the file backend round-trips, and the stores sit behind the interface
so a Postgres/Neon swap is one class later. Uses a temp FileStore (no touching real state/)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.persistence import FileStore, Persistence  # noqa: E402


class TestFileStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = FileStore(root=self.tmp)

    def test_round_trip(self):
        self.assertIsNone(self.store.load("notes"))
        self.assertFalse(self.store.exists("notes"))
        self.store.save("notes", {"notes": [{"id": "P01"}], "seq": 2})
        self.assertTrue(self.store.exists("notes"))
        self.assertEqual(self.store.load("notes"), {"notes": [{"id": "P01"}], "seq": 2})

    def test_overwrite_and_delete(self):
        self.store.save("absences", {"absences": [], "next_id": 1})
        self.store.save("absences", {"absences": [{"id": 1}], "next_id": 2})
        self.assertEqual(self.store.load("absences")["next_id"], 2)
        self.store.delete("absences")
        self.assertFalse(self.store.exists("absences"))

    def test_corrupt_file_is_tolerated(self):
        path = os.path.join(self.tmp, "notes.json")
        with open(path, "w") as fh:
            fh.write("{ not json")
        self.assertIsNone(self.store.load("notes"))

    def test_interface_compliance(self):
        self.assertIsInstance(self.store, Persistence)


class TestStoresUseAdapter(unittest.TestCase):
    """NoteStore / AbsenceStore must persist through an injected backend (the swap seam)."""

    def test_absence_store_round_trips_via_backend(self):
        from api.absences import AbsenceStore
        backend = FileStore(root=tempfile.mkdtemp())
        s1 = AbsenceStore(backend=backend)
        s1.add("Alex", "2026-10-06", "sick")
        # a fresh store on the SAME backend sees the persisted record
        s2 = AbsenceStore(backend=backend)
        self.assertEqual(len(s2.list()), 1)
        self.assertEqual(s2.list()[0]["worker"], "Alex")

    def test_note_store_round_trips_via_backend(self):
        from api.notes import NoteStore
        backend = FileStore(root=tempfile.mkdtemp())
        s1 = NoteStore(backend=backend)
        nid = s1.next_id()
        s1.add({"id": nid, "raw_text": "picking felt overstaffed", "author": "Mara"})
        s2 = NoteStore(backend=backend)
        self.assertEqual([n["id"] for n in s2.list()], [nid])


if __name__ == "__main__":
    unittest.main()

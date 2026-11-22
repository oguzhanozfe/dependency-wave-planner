import json, unittest
from pathlib import Path
from pipeline import prepare, export


class WaveTests(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(Path(__file__).with_name("example.json").read_text())
        self.e = prepare(self.d)

    def test_scc_collapses_but_preserves_prerequisites(self):
        cycle = next(c for c in self.e["candidates"] if c["atomic_cycle"])
        self.assertEqual(cycle["members"], ["collector", "shared-codec"])
        self.assertEqual(cycle["requires_units"], ["unit:common-schema"])
        self.assertEqual(cycle["wave"], 2)

    def test_partial_dependency_block(self):
        with self.assertRaises(ValueError):
            export(self.d, self.e, [self.e["candidates"][-1]])

    def test_reverse_rollback_order(self):
        files = export(self.d, self.e, self.e["candidates"])
        self.assertEqual(
            [r["wave"] for r in json.loads(files["rollback-order.json"])], [3, 2, 1]
        )

    def test_deterministic_reordered_input_and_unknown_edge(self):
        self.assertEqual(
            self.e, prepare(dict(self.d, packages=list(reversed(self.d["packages"]))))
        )
        self.d["packages"][0]["depends_on"] = ["missing"]
        with self.assertRaises(ValueError):
            prepare(self.d)

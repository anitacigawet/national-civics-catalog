from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("build_huggingface_release.py")
SPEC = importlib.util.spec_from_file_location("hf_builder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class HuggingFaceBuildTests(unittest.TestCase):
    def test_build_is_exact_and_national_file_is_lf_concatenation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            applied = builder.build(builder.ROOT, output, apply=True)
            expected_record_count = sum(
                len(path.read_text(encoding="utf-8").splitlines())
                for path in (builder.ROOT / "states").glob("*.jsonl")
            )
            self.assertEqual(applied["records"], expected_record_count)
            verified = builder.build(builder.ROOT, output, apply=False)
            self.assertEqual(verified["mismatches"], [])
            expected = b"".join(
                path.read_bytes() for path in sorted((builder.ROOT / "states").glob("*.jsonl"))
            )
            self.assertEqual((output / "data" / "national.jsonl").read_bytes(), expected)
            card = (output / "README.md").read_text(encoding="utf-8")
            self.assertTrue(card.startswith("---\nlicense: cc0-1.0"))
            self.assertIn('"ScootSolute/national-civics-catalog"', card)
            self.assertTrue((output / ".github" / "scripts" / "validate_catalog.py").is_file())
            self.assertTrue((output / ".github" / "scripts" / "migrate_v1_to_v2.py").is_file())
            self.assertTrue((output / ".github" / "workflows" / "validate.yml").is_file())
            self.assertEqual(
                (output / ".gitattributes").read_bytes(),
                (builder.ROOT / builder.HF_GITATTRIBUTES_SOURCE).read_bytes(),
            )
            self.assertFalse(any(output.rglob("*.pyc")))

    def test_build_rejects_unexpected_public_file(self) -> None:
        for relative in ("stale-public-file.md", "data/stale.jsonl"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary)
                builder.build(builder.ROOT, output, apply=True)
                stale = output / relative
                stale.parent.mkdir(parents=True, exist_ok=True)
                stale.write_text("stale", encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "unexpected Hugging Face files"):
                    builder.build(builder.ROOT, output, apply=False)

    def test_apply_rejects_stale_tree_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            builder.build(builder.ROOT, output, apply=True)
            changed_readme = b"locally changed before rejected build\n"
            (output / "README.md").write_bytes(changed_readme)
            (output / "stale-public-file.md").write_text("stale", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unexpected Hugging Face files"):
                builder.build(builder.ROOT, output, apply=True)
            self.assertEqual((output / "README.md").read_bytes(), changed_readme)


if __name__ == "__main__":
    unittest.main()

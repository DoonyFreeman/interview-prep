"""Offline regression tests: python -m unittest discover -s scripts -p test_build_private_openspec_bundle.py."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, TextStringObject

from build_private_openspec_bundle import TITLE, build_bundle


class BundleTest(unittest.TestCase):
    def setUp(self):
        scratch = TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        root = Path(scratch.name)
        self.common, self.original, self.output = (root / name for name in ("common.pdf", "source.pdf", "out.pdf"))
        public = PdfWriter()
        public.add_blank_page(101, 200)
        public.add_outline_item("Common", 0)
        public.write(self.common)

    def original_writer(self):
        private = PdfWriter()
        for width in range(201, 207):
            private.add_blank_page(width, 200)
        parent = private.add_outline_item("Chapter", 0)
        child = private.add_outline_item("Nested section", 1, parent=parent)
        return private, child

    def test_local_bookmark_and_bundle(self):
        private, _ = self.original_writer()
        private.add_attachment("provenance.txt", b"synthetic passive metadata")
        private.write(self.original)
        before = self.original.read_bytes()
        build_bundle(self.common, self.original, self.output)
        result = PdfReader(self.output)
        self.assertEqual([int(p.mediabox.width) for p in result.pages], [101, *range(201, 207)])
        self.assertEqual([(o.title, result.get_destination_page_number(o)) for o in result.outline],
                         [("Common", 0), (TITLE, 1)])
        self.assertFalse(result.attachments)
        self.assertEqual(self.original.read_bytes(), before)

    def test_nested_external_bookmark_is_rejected_before_output(self):
        private, child = self.original_writer()
        child.get_object()[NameObject("/A")] = DictionaryObject({
            NameObject("/S"): NameObject("/URI"),
            NameObject("/URI"): TextStringObject("https://example.invalid/"),
        })
        private.write(self.original)
        with self.assertRaisesRegex(ValueError, "unsupported action"):
            build_bundle(self.common, self.original, self.output)
        self.assertFalse(self.output.exists())

    def test_unparseable_input_is_rejected_before_output(self):
        from pypdf.errors import PdfReadError

        self.original.write_bytes(b"%PDF-1.4\n")
        with self.assertRaises(PdfReadError):
            build_bundle(self.common, self.original, self.output)
        self.assertFalse(self.output.exists())

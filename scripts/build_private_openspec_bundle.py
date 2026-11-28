#!/usr/bin/env python3
"""Build the personal bundle offline. Keep private inputs and outputs outside Git."""
from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject


ROOT = Path(__file__).resolve().parents[1]
TITLE = "OpenSpec и Agent Engineering"
PRIVATE_PAGES = 6


def _validate_original(private: PdfReader) -> None:
    if private.is_encrypted or len(private.pages) != PRIVATE_PAGES:
        raise ValueError("Expected six unencrypted pages")
    # Traverse reachable PDF objects, not extracted outline destinations: the
    # latter can silently omit actions. Indirect references can form cycles.
    page_refs = {page.indirect_reference for page in private.pages}
    pending = [private.trailer.raw_get("/Root")]
    seen = set()
    blocked = {"/OpenAction", "/AA", "/AcroForm", "/JavaScript", "/JS", "/Annots"}
    while pending:
        value = pending.pop()
        if isinstance(value, IndirectObject):
            key = (value.idnum, value.generation)
            if key in seen:
                continue
            seen.add(key)
            if len(seen) > 100_000:
                raise ValueError("PDF structure is too large to verify")
            value = value.get_object()
        if isinstance(value, DictionaryObject):
            if blocked.intersection(value) or value.get("/Type") == "/RichMedia":
                raise ValueError("PDF has active or unsupported content")
            if "/A" in value:
                action = value["/A"]
                # A plain GoTo bookmark to a page in this file is navigation,
                # not an external action. Do not admit chained actions.
                if not isinstance(action, DictionaryObject) or not set(action) <= {"/Type", "/S", "/D"}:
                    raise ValueError("PDF has an unsupported action")
                destination = action.get("/D")
                if (action.get("/S") != "/GoTo" or not isinstance(destination, ArrayObject)
                        or not destination or not isinstance(destination[0], IndirectObject)
                        or destination[0] not in page_refs):
                    raise ValueError("PDF has a nonlocal or unsupported action")
            pending.extend(value.values())
        elif isinstance(value, ArrayObject):
            pending.extend(value)


def build_bundle(public: Path, original: Path, output: Path) -> None:
    for path in (original, output):
        if path.resolve().is_relative_to(ROOT):
            raise ValueError("Private files must be outside the checkout")
    if output.resolve() in {original.resolve(), public.resolve()}:
        raise ValueError("Output must not overwrite an input")
    common = PdfReader(public)
    private = PdfReader(BytesIO(original.read_bytes()), strict=True)
    _validate_original(private)
    if len(common.pages) == 0:
        raise ValueError("Common bundle must not be empty")

    writer = PdfWriter()
    excluded = ("/Annots", "/AA", "/A", "/AF")
    writer.append(common, import_outline=True, excluded_fields=excluded)
    start = len(writer.pages)
    for page in private.pages:
        # Do not import the document catalog, including embedded provenance files.
        writer.add_page(page, excluded_keys=excluded)
    writer.add_outline_item(TITLE, start)
    writer.add_metadata({"/Title": "Персональный сборник InterviewPrep"})
    # Never overwrite an existing output; prepare within a private directory.
    with open(output, "xb", opener=_private_open) as stream:
        writer.write(stream)


def _private_open(path: str, flags: int) -> int:
    import os

    return os.open(path, flags, 0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_bundle(args.public, args.original, args.output)
    except Exception:
        parser.exit(1, "Unable to build the private bundle; check the inputs and output location.\n")


if __name__ == "__main__":
    main()

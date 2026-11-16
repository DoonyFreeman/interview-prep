"""Install the pinned INT8 E5 assets and build the assistant's lesson index."""
from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import dataclass
from hashlib import file_digest, sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from typing import BinaryIO
from urllib.request import urlopen

import httpx

ROOT = Path(__file__).resolve().parents[1]
ASSET_REPO = "https://huggingface.co/Xenova/multilingual-e5-small/resolve/761b726dd34fb83930e26aab4e9ac3899aa1fa78"


@dataclass(frozen=True)
class Asset:
    path: str
    size: int
    sha256: str


ASSETS = (
    Asset("tokenizer.json", 17_082_730, "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39"),
    Asset("onnx/model_int8.onnx", 118_054_593, "4d24e2bc01a447951524466ef533e52944bf48509e6552810bcee1a2711cb02c"),
)
_INDEX_METADATA = {"version", "source_fingerprint", "model_fingerprint", "dimension", "generation", "chunks"}


def _verified(path: Path, asset: Asset) -> bool:
    if not path.is_file() or path.stat().st_size != asset.size:
        return False
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest() == asset.sha256


def _write_verified(source: BinaryIO, path: Path, asset: Asset) -> None:
    digest = sha256()
    remaining = asset.size
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as target:
        while remaining:
            block = source.read(min(remaining, 1024 * 1024))
            if not block:
                break
            digest.update(block)
            target.write(block)
            remaining -= len(block)
        if remaining or source.read(1) or digest.hexdigest() != asset.sha256:
            raise ValueError(f"File does not match pinned size and SHA-256: {asset.path}")


def prepare_model(model_dir: Path, *, source_dir: Path | None = None) -> None:
    """Verify cached assets and stage all replacements before installing any."""
    for asset in ASSETS:
        destination = model_dir / asset.path
        if destination.is_symlink() or not destination.resolve().is_relative_to(model_dir.resolve()):
            raise ValueError(f"Model file points outside its asset directory: {asset.path}")
    pending = [asset for asset in ASSETS if not _verified(model_dir / asset.path, asset)]
    if not pending:
        return
    download_context = httpx.create_ssl_context() if source_dir is None else None
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".e5-download-", dir=model_dir.parent) as temporary:
        staging = Path(temporary)
        for asset in pending:
            try:
                source = (
                    (source_dir / asset.path).open("rb") if source_dir is not None
                    else urlopen(f"{ASSET_REPO}/{asset.path}", timeout=30, context=download_context)
                )
            except OSError as exc:
                raise OSError(f"Cannot read {asset.path}: {exc}") from None
            with closing(source):
                _write_verified(source, staging / asset.path, asset)
        for asset in pending:
            destination = model_dir / asset.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            (staging / asset.path).replace(destination)


def check_index_destination(index: Path, model_dir: Path) -> None:
    """Only replace an existing assistant index, never an app DB or model file."""
    path = index.resolve()
    if index.is_symlink() or any(path == (model_dir / asset.path).resolve() for asset in ASSETS):
        raise ValueError("Index destination must be separate from the model files and cannot be a symlink")
    if not index.exists():
        return
    try:
        if index.is_file():
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                if {"chunks", "chunks_fts", "metadata"} <= tables:
                    keys = {row[0] for row in conn.execute("SELECT key FROM metadata")}
                    if _INDEX_METADATA <= keys:
                        return
    except sqlite3.Error:
        pass
    raise ValueError(f"Existing file is not an assistant index: {index}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, help="Use these local, already downloaded model files")
    parser.add_argument("--model-dir", type=Path, default=ROOT / "backend/data/assistant/e5")
    parser.add_argument("--index", type=Path, default=ROOT / "backend/data/assistant/lessons.sqlite3")
    parser.add_argument("--content-dir", type=Path, default=ROOT / "content")
    args = parser.parse_args()
    try:
        check_index_destination(args.index, args.model_dir)
        prepare_model(args.model_dir, source_dir=args.source_dir)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"E5 assets unavailable: {exc}\n")

    from app.assistant.embeddings import EmbeddingError
    from app.assistant.retrieval import RetrievalUnavailable, build_index

    try:
        check_index_destination(args.index, args.model_dir)
        stats = build_index(args.content_dir, args.model_dir, args.index)
    except (RetrievalUnavailable, EmbeddingError, ImportError, OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Index build failed: {exc}\n")
    print(json.dumps(stats))


if __name__ == "__main__":
    main()

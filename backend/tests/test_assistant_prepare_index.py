"""Regression tests for installing pinned model files from an offline copy."""
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from pathlib import Path
import sqlite3
import ssl
import sys

import pytest


@pytest.fixture
def prepare(monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts/assistant_prepare_index.py"
    spec = spec_from_file_location("assistant_prepare_index", script)
    module = module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    files = {"tokenizer.json": b"test tokenizer", "onnx/model_int8.onnx": b"test onnx data"}
    monkeypatch.setattr(module, "ASSETS", tuple(
        module.Asset(path, len(text), sha256(text).hexdigest()) for path, text in files.items()
    ))
    return module, files


def test_reuses_verified_files_without_needing_download(prepare, tmp_path):
    module, files = prepare
    source = tmp_path / "source"
    model = tmp_path / "model"
    for name, data in files.items():
        asset = source / name
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_bytes(data)

    module.prepare_model(model, source_dir=source)
    module.prepare_model(model, source_dir=tmp_path / "missing")

    assert {name: (model / name).read_bytes() for name in files} == files


def test_online_download_uses_trusted_ca_and_verifies_hostname(prepare, monkeypatch, tmp_path):
    module, files = prepare
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    downloaded = []

    def download(url, *, timeout, context):
        name = url.removeprefix(module.ASSET_REPO + "/")
        assert context.cert_store_stats()["x509_ca"] > 0
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname
        downloaded.append(name)
        return BytesIO(files[name])

    monkeypatch.setattr(module, "urlopen", download)
    module.prepare_model(tmp_path / "e5")

    assert downloaded == list(files)


@pytest.mark.parametrize("bad_model", (b"", b"x" * len(b"test onnx data"), b"test onnx data plus extra"))
def test_corrupt_file_leaves_existing_assets_untouched(prepare, tmp_path, bad_model):
    module, files = prepare
    source = tmp_path / "source"
    (source / "onnx").mkdir(parents=True)
    (source / "tokenizer.json").write_bytes(files["tokenizer.json"])
    (source / "onnx/model_int8.onnx").write_bytes(bad_model)
    model = tmp_path / "model"
    model.mkdir()
    (model / "tokenizer.json").write_bytes(b"existing tokenizer")

    with pytest.raises(ValueError, match="model_int8.onnx"):
        module.prepare_model(model, source_dir=source)

    assert (model / "tokenizer.json").read_bytes() == b"existing tokenizer"
    assert not (model / "onnx/model_int8.onnx").exists()


def test_cannot_use_model_path_or_application_database_as_index(prepare, tmp_path):
    module, _ = prepare
    model = tmp_path / "e5"
    with pytest.raises(ValueError, match="separate"):
        module.check_index_destination(model / "tokenizer.json", model)

    app_db = tmp_path / "app.db"
    with sqlite3.connect(app_db) as connection:
        connection.execute("CREATE TABLE conversations (id INTEGER)")
    with pytest.raises(ValueError, match="not an assistant index"):
        module.check_index_destination(app_db, model)


def test_rebuilding_recognized_index_is_allowed(prepare, tmp_path):
    module, _ = prepare
    index = tmp_path / "index.sqlite3"
    with sqlite3.connect(index) as conn:
        conn.execute("CREATE TABLE chunks (id INTEGER)")
        conn.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(body)")
        conn.execute("CREATE TABLE metadata (key TEXT, value TEXT)")
        conn.executemany("INSERT INTO metadata VALUES (?, 'old')", [(key,) for key in module._INDEX_METADATA])

    module.check_index_destination(index, tmp_path / "e5")


def test_model_asset_symlink_cannot_redirect_installation(prepare, tmp_path):
    module, _ = prepare
    model = tmp_path / "e5"
    outside = tmp_path / "outside"
    model.mkdir()
    outside.mkdir()
    (model / "onnx").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="outside"):
        module.prepare_model(model)

    assert not list(outside.iterdir())

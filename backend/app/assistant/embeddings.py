"""Local multilingual E5 embeddings for the offline builder and query retrieval."""
from __future__ import annotations

import hashlib
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from numpy.typing import NDArray


class EmbeddingError(RuntimeError):
    """The local embedding model could not be loaded or used."""


class Embedder(Protocol):
    @property
    def fingerprint(self) -> str: ...

    def embed(self, texts: list[str], *, passage: bool) -> NDArray: ...


class E5Embedder:
    """A lazy, CPU-only multilingual-e5-small INT8 ONNX session."""

    def __init__(self, model_dir: Path) -> None:
        self._model_dir = model_dir
        self._lock = Lock()
        self._runtime = None
        self._fingerprint = None
        self._signature = None

    def _files(self) -> tuple[Path, Path]:
        tokenizer = self._model_dir / "tokenizer.json"
        model = self._model_dir / "onnx" / "model_int8.onnx"
        if not model.is_file():
            model = self._model_dir / "model_int8.onnx"
        return tokenizer, model

    @property
    def fingerprint(self) -> str:
        with self._lock:
            try:
                files = self._files()
                signature = self._file_signature(files)
                if signature != self._signature:
                    hashes = []
                    for path in files:
                        with path.open("rb") as artifact:
                            hashes.append(hashlib.file_digest(artifact, "sha256").hexdigest())
                    if signature != self._file_signature(files):
                        raise EmbeddingError("The local E5 model files changed while being validated")
                    self._fingerprint = "multilingual-e5-small-int8-v1:" + ":".join(hashes)
                    self._signature = signature
                    self._runtime = None
            except OSError as exc:
                raise EmbeddingError(
                    "Install tokenizer.json and model_int8.onnx in the model directory"
                ) from exc
            return self._fingerprint

    @staticmethod
    def _file_signature(files: tuple[Path, Path]) -> tuple:
        return tuple(
            (path, stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            for path in files for stat in (path.stat(),)
        )

    def _load(self):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        files = self._files()
        tokenizer_path, model_path = files
        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        tokenizer.enable_truncation(max_length=512)
        pad_id = tokenizer.token_to_id("<pad>")
        if pad_id is None:
            raise EmbeddingError("The local E5 tokenizer is missing its padding token")
        tokenizer.enable_padding(pad_id=pad_id, pad_token="<pad>")

        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        input_names = {item.name for item in session.get_inputs()}
        if not {"input_ids", "attention_mask"} <= input_names:
            raise EmbeddingError("The local E5 graph is missing required inputs")
        if self._signature is not None and self._file_signature(files) != self._signature:
            raise EmbeddingError("The local E5 model files changed before inference")
        return tokenizer, session, input_names

    def embed(self, texts: list[str], *, passage: bool) -> NDArray:
        prefix = "passage: " if passage else "query: "
        with self._lock:
            try:
                import numpy as np

                if not texts:
                    return np.empty((0, 384), dtype=np.float32)
                if self._runtime is None:
                    self._runtime = self._load()
                tokenizer, session, input_names = self._runtime
                inputs = [prefix + text for text in texts]
                if len(inputs) == 1:
                    encoded = [tokenizer.encode(inputs[0])]
                else:
                    encoded = tokenizer.encode_batch(inputs)
                attention = np.asarray([item.attention_mask for item in encoded], dtype=np.int64)
                feed = {
                    "input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
                    "attention_mask": attention,
                }
                if "token_type_ids" in input_names:
                    feed["token_type_ids"] = np.asarray([item.type_ids for item in encoded], dtype=np.int64)

                hidden = session.run(["last_hidden_state"], feed)[0]
                if hidden.shape != (*attention.shape, 384):
                    raise EmbeddingError("The local E5 graph returned unexpected token embeddings")
                mask = attention[..., None]
                token_sum = np.sum(hidden * mask, axis=1, dtype=np.float32)
                pooled = token_sum / np.sum(mask, axis=1, dtype=np.float32)
                return pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
            except EmbeddingError:
                raise
            except Exception as exc:
                raise EmbeddingError("Local E5 tokenization or inference failed") from exc

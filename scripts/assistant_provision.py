"""Install the assistant configuration sent to the production deploy command."""
from __future__ import annotations

import base64
import binascii
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import sys
import tempfile

_MAX_PAYLOAD = 256 * 1024
_SCOPES = {"GIGACHAT_API_PERS", "GIGACHAT_API_B2B", "GIGACHAT_API_CORP"}
_FIELDS = {"credentials", "scope", "model", "ca_pem"}
_CERTIFICATE = re.compile(
    r"-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n]+\r?\n-----END CERTIFICATE-----"
)


def _read_config(*, allow_payload: bool) -> tuple[str, str] | None:
    stream = sys.stdin.buffer
    line = stream.readline(_MAX_PAYLOAD + 1)
    if len(line) > _MAX_PAYLOAD or (line and not line.endswith(b"\n")) or stream.read(1):
        raise ValueError
    if line in (b"", b"\n"):
        return None
    if not allow_payload:
        raise PermissionError

    payload = json.loads(base64.b64decode(line[:-1], validate=True))
    if not isinstance(payload, dict) or payload.keys() != _FIELDS:
        raise ValueError
    if not all(isinstance(value, str) for value in payload.values()):
        raise ValueError

    credentials, scope, model, ca_pem = (payload[field] for field in ("credentials", "scope", "model", "ca_pem"))
    if not re.fullmatch(r"[A-Za-z0-9+/_-]{1,4096}={0,2}", credentials):
        raise ValueError
    if scope not in _SCOPES or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", model):
        raise ValueError
    if not ca_pem.isascii():
        raise ValueError
    ca_pem = ca_pem.strip() + "\n"
    certificates = list(_CERTIFICATE.finditer(ca_pem))
    if not certificates or _CERTIFICATE.sub("", ca_pem).strip():
        raise ValueError
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    for cert in certificates:
        context.load_verify_locations(cadata=cert.group())

    env = (
        "ASSISTANT_ENABLED=true\n"
        f"GIGACHAT_CREDENTIALS={credentials}\n"
        f"GIGACHAT_SCOPE={scope}\n"
        f"GIGACHAT_MODEL={model}\n"
        "GIGACHAT_CA_FILE=/app/gigachat-ca.pem\n"
    )
    return env, ca_pem


def _point_current(current: Path, generation: str, staging: Path) -> None:
    pending = staging / "next"
    pending.unlink(missing_ok=True)
    pending.symlink_to(generation, target_is_directory=True)
    pending.replace(current)


def _install_config(directory: Path, env: str, ca_pem: str) -> str:
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink():
        raise OSError
    directory.chmod(0o700)
    with (directory / "provision.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = directory / "current"
        previous = current.readlink().name if current.is_symlink() else ""
        if previous and (current / "previous").exists():
            raise OSError
        generation = Path(tempfile.mkdtemp(prefix="config-", dir=directory))
        try:
            with (generation / "app.env").open("x", encoding="ascii") as env_file:
                os.fchmod(env_file.fileno(), 0o600)
                env_file.write(env)
            ca_path = generation / "ca.pem"
            ca_path.write_text(ca_pem, encoding="ascii")
            ca_path.chmod(0o644)
            (generation / "previous").write_text(previous, encoding="ascii")
            _point_current(current, generation.name, generation)
        except OSError:
            shutil.rmtree(generation, ignore_errors=True)
            raise
    return generation.name


def _finish_config(directory: Path, action: str, name: str) -> None:
    if not re.fullmatch(r"config-[A-Za-z0-9_-]{8,64}", name):
        raise OSError
    with (directory / "provision.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = directory / "current"
        generation = directory / name
        saved = generation / "previous"
        if current.readlink() != Path(name):
            raise OSError
        previous = saved.read_text(encoding="ascii")
        if previous and not re.fullmatch(r"config-[A-Za-z0-9_-]{8,64}", previous):
            raise OSError
        if action == "rollback":
            if previous:
                _point_current(current, previous, generation)
            else:
                current.unlink()
            shutil.rmtree(generation, ignore_errors=True)
        else:
            saved.unlink()
            if previous:
                shutil.rmtree(directory / previous, ignore_errors=True)


def main() -> int:
    directory = Path(".assistant")
    args = sys.argv[1:]
    if len(args) == 2 and args[0] in {"commit", "rollback"}:
        try:
            _finish_config(directory, *args)
        except (OSError, ValueError):
            print("[deploy] ERROR: could not finish assistant configuration update", file=sys.stderr)
            return 1
        return 0
    if args not in (["prepare"], ["check-empty"]):
        return 1
    try:
        config = _read_config(allow_payload=args == ["prepare"])
    except PermissionError:
        print("[deploy] ERROR: assistant provisioning requires a pinned deployment", file=sys.stderr)
        return 1
    except (ValueError, binascii.Error, ssl.SSLError, RecursionError):
        print("[deploy] ERROR: invalid assistant provisioning payload", file=sys.stderr)
        return 1
    if config is None:
        return 0
    try:
        generation = _install_config(directory, *config)
    except OSError:
        print("[deploy] ERROR: could not store assistant configuration", file=sys.stderr)
        return 1
    print(generation)
    return 0


if __name__ == "__main__":
    sys.exit(main())

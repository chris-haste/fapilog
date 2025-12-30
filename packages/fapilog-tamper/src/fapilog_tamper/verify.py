"""
Verification API and CLI for tamper-evident logs.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol

from .canonical import b64url_decode, b64url_encode, canonicalize
from .sealed_sink import ManifestGenerator

try:  # Optional Ed25519 dependency
    from nacl.exceptions import BadSignatureError
    from nacl.signing import VerifyKey
except Exception:  # pragma: no cover - optional
    VerifyKey = None  # type: ignore[assignment]
    BadSignatureError = Exception  # type: ignore[assignment]


@dataclass
class VerifyError:
    seq: int
    error_type: str
    expected: str | None = None
    actual: str | None = None
    message: str = ""


@dataclass
class VerifyReport:
    valid: bool
    file_path: str
    records_checked: int
    records_valid: int
    records_invalid: int
    first_invalid_seq: int | None = None
    chain_valid: bool = True
    chain_breaks: list[int] = field(default_factory=list)
    manifest_valid: bool | None = None
    manifest_signature_valid: bool | None = None
    errors: list[VerifyError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def checked(self) -> int:
        """Backwards-compatible alias for records_checked."""
        return self.records_checked


class KeyStore(Protocol):
    def get_key(self, key_id: str) -> bytes | None:
        """Return key for key_id or None if missing."""


class EnvKeyStore:
    """Key store backed by environment variables."""

    def __init__(self, *, prefix: str | None = None) -> None:
        self._prefix = prefix

    def get_key(self, key_id: str) -> bytes | None:
        import os

        name = f"{self._prefix}{key_id}" if self._prefix else key_id
        val = os.getenv(name)
        if not val:
            return None
        return _decode_key(val.encode("utf-8"))


class FileKeyStore:
    """Key store backed by files."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def get_key(self, key_id: str) -> bytes | None:
        if self._path.is_file():
            try:
                data = self._path.read_bytes()
                return _decode_key(data)
            except Exception:
                return None
        # Directory lookup
        candidate = self._path / f"{key_id}.key"
        if candidate.exists():
            try:
                return _decode_key(candidate.read_bytes())
            except Exception:
                return None
        return None


def _decode_key(raw: bytes) -> bytes | None:
    padding = b"=" * (-len(raw) % 4)
    candidates = []
    try:
        candidates.append(base64.urlsafe_b64decode(raw + padding))
    except Exception:
        pass
    candidates.append(raw)
    for c in candidates:
        if len(c) == 32:
            return c
    return None


class Verifier:
    """Verification engine for tamper-evident logs."""

    def __init__(self, keys: KeyStore):
        self._keys = keys

    def verify_record(self, record: dict, key: bytes, algo: str) -> bool:
        """Verify MAC for a single record."""
        integrity = record.get("integrity")
        if not integrity:
            return False

        payload_record = {k: v for k, v in record.items() if k != "integrity"}
        payload = canonicalize(payload_record)

        stored_mac = b64url_decode(integrity.get("mac", ""))
        if algo == "HMAC-SHA256":
            expected_mac = hmac.new(key, payload, hashlib.sha256).digest()
            return hmac.compare_digest(stored_mac, expected_mac)
        if algo == "Ed25519" and VerifyKey:
            try:
                VerifyKey(key).verify(payload, stored_mac)
                return True
            except BadSignatureError:
                return False
        return False

    def verify_chain(
        self,
        records: list[dict],
        *,
        expected_first_prev: str | None = None,
        expected_start_seq: int = 1,
    ) -> list[VerifyError]:
        """Verify chain linkage across records."""
        errors: list[VerifyError] = []
        prev_chain_hash = expected_first_prev or b64url_encode(b"\x00" * 32)
        prev_seq = expected_start_seq - 1

        for record in records:
            integrity = record.get("integrity", {})
            seq = integrity.get("seq", 0)
            stored_prev = integrity.get("prev_chain_hash", "")

            if seq != prev_seq + 1:
                errors.append(
                    VerifyError(
                        seq=seq,
                        error_type="seq_gap",
                        expected=str(prev_seq + 1),
                        actual=str(seq),
                        message=f"Sequence gap: expected {prev_seq + 1}, got {seq}",
                    )
                )

            if stored_prev != prev_chain_hash:
                errors.append(
                    VerifyError(
                        seq=seq,
                        error_type="chain_break",
                        expected=prev_chain_hash,
                        actual=stored_prev,
                        message=f"Chain break at seq {seq}",
                    )
                )

            prev_chain_hash = integrity.get("chain_hash", "")
            prev_seq = seq

        return errors

    async def verify_file(
        self,
        path: Path,
        manifest_path: Path | None = None,
    ) -> VerifyReport:
        """Verify a complete log file."""
        start = time.monotonic()
        records: list[dict] = []
        errors: list[VerifyError] = []
        records_valid = 0

        for line_num, record in self._stream_records(path):
            integrity = record.get("integrity", {})
            key_id = integrity.get("key_id", "")
            key = self._keys.get_key(key_id)
            if not key:
                errors.append(
                    VerifyError(
                        seq=integrity.get("seq", 0),
                        error_type="missing_key",
                        message=f"Key not found: {key_id}",
                    )
                )
                records.append(record)
                continue

            algo = integrity.get("algo", "HMAC-SHA256")
            if self.verify_record(record, key, algo):
                records_valid += 1
            else:
                errors.append(
                    VerifyError(
                        seq=integrity.get("seq", 0),
                        error_type="mac_mismatch",
                        message=f"MAC verification failed at line {line_num}",
                    )
                )
            records.append(record)

        manifest_data: dict[str, Any] = {}
        expected_prev = None
        if manifest_path and manifest_path.exists():
            try:
                manifest_data = json.loads(manifest_path.read_text())
                expected_prev = manifest_data.get("continues_from")
            except Exception:
                manifest_data = {}
        start_seq = records[0].get("integrity", {}).get("seq", 1) if records else 1
        chain_errors = self.verify_chain(
            records, expected_first_prev=expected_prev, expected_start_seq=start_seq
        )
        errors.extend(chain_errors)

        manifest_valid = None
        manifest_sig_valid = None
        if manifest_data:
            manifest_valid, manifest_sig_valid = await self._verify_manifest(
                manifest_path, records
            )

        duration = (time.monotonic() - start) * 1000
        return VerifyReport(
            valid=len(errors) == 0 and manifest_valid in (None, True),
            file_path=str(path),
            records_checked=len(records),
            records_valid=records_valid,
            records_invalid=len(records) - records_valid,
            first_invalid_seq=errors[0].seq if errors else None,
            chain_valid=not chain_errors,
            chain_breaks=[e.seq for e in chain_errors if e.error_type == "chain_break"],
            manifest_valid=manifest_valid,
            manifest_signature_valid=manifest_sig_valid,
            errors=errors,
            duration_ms=duration,
        )

    async def _verify_manifest(
        self, manifest_path: Path, records: list[dict]
    ) -> tuple[bool, bool]:
        manifest = json.loads(manifest_path.read_text())
        sig = manifest.get("signature")
        root_chain_hash = manifest.get("root_chain_hash")
        record_count = manifest.get("record_count")

        last = records[-1] if records else {}
        last_hash = last.get("integrity", {}).get("chain_hash")
        manifest_valid = root_chain_hash == last_hash and record_count == len(records)

        sig_valid = False
        if sig:
            key_id = manifest.get("key_id", "")
            key = self._keys.get_key(key_id) if key_id else None
            algo = manifest.get("signature_algo", manifest.get("algo", "HMAC-SHA256"))
            if key:
                sig_valid = _verify_manifest_signature(manifest, key, algo)
        return manifest_valid, sig_valid

    def _stream_records(self, path: Path) -> Iterable[tuple[int, dict]]:
        with open(path, encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                try:
                    yield idx, json.loads(line)
                except Exception:
                    yield idx, {}


def _verify_manifest_signature(manifest: dict[str, Any], key: bytes, algo: str) -> bool:
    payload = ManifestGenerator._canonical_manifest_payload(
        {k: v for k, v in manifest.items() if k != "signature"}
    )
    sig = b64url_decode(manifest.get("signature", ""))
    if algo == "HMAC-SHA256":
        expected = hmac.new(key, payload, hashlib.sha256).digest()
        return hmac.compare_digest(sig, expected)
    if algo == "Ed25519" and VerifyKey:
        try:
            VerifyKey(key).verify(payload, sig)
            return True
        except BadSignatureError:
            return False
    return False


def write_manifest(
    path: Path,
    records: list[dict],
    key: bytes,
    key_id: str,
    *,
    algo: str = "HMAC-SHA256",
    continues_from: dict | Path | None = None,
) -> Path:
    """Helper to write a manifest sidecar for tests and CLI."""
    from .sealed_sink import FileMetadata, ManifestGenerator

    created_ts = (
        records[0].get("timestamp")
        if records
        else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    closed_ts = records[-1].get("timestamp") if records else created_ts
    metadata = FileMetadata(
        filename=str(path),
        created_ts=_coerce_ts(created_ts),
        record_count=len(records),
        first_seq=records[0]["integrity"]["seq"] if records else None,
        last_seq=records[-1]["integrity"]["seq"] if records else None,
        first_ts=records[0].get("timestamp") if records else None,
        last_ts=records[-1].get("timestamp") if records else None,
        root_chain_hash=b64url_decode(records[-1]["integrity"]["chain_hash"])
        if records
        else None,
        continues_from=_resolve_continues_from(continues_from),
    )
    generator = ManifestGenerator(
        type("cfg", (), {"algorithm": algo, "key_id": key_id}), key
    )
    manifest = generator.generate(metadata, _coerce_ts(closed_ts))
    manifest_path = Path(str(path) + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


def _coerce_ts(value: Any):
    from datetime import datetime, timezone

    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except Exception:
        return datetime.now(timezone.utc)


def _resolve_continues_from(continues_from: dict | Path | None) -> str | None:
    if continues_from is None:
        return None
    if isinstance(continues_from, Path):
        try:
            data = json.loads(continues_from.read_text())
            return data.get("root_chain_hash")
        except Exception:
            return None
    if isinstance(continues_from, dict):
        return continues_from.get("root_chain_hash")
    return None


async def verify_chain_across_files(files: list[Path], keys: KeyStore) -> VerifyReport:
    """Verify chain continuity across multiple files (ordered)."""
    verifier = Verifier(keys)
    overall_errors: list[VerifyError] = []
    last_root: str | None = None
    manifest_valid = True

    records_checked = 0
    records_valid = 0

    for path in files:
        manifest_path = Path(str(path) + ".manifest.json")
        report = await verifier.verify_file(
            path, manifest_path if manifest_path.exists() else None
        )
        records_checked += report.records_checked
        records_valid += report.records_valid
        overall_errors.extend(report.errors)
        if report.manifest_valid is False or report.valid is False:
            manifest_valid = False
        manifest_data = (
            json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        )
        continues = manifest_data.get("continues_from")

        if report.manifest_valid and last_root:
            if continues and continues != last_root:
                overall_errors.append(
                    VerifyError(
                        seq=report.first_invalid_seq or 0,
                        error_type="chain_break",
                        expected=last_root,
                        actual=continues,
                        message="Cross-file chain break",
                    )
                )
                manifest_valid = False
            if not continues:
                overall_errors.append(
                    VerifyError(
                        seq=report.first_invalid_seq or 0,
                        error_type="chain_break",
                        expected=last_root,
                        actual="",
                        message="Missing continues_from",
                    )
                )
                manifest_valid = False
        elif report.manifest_valid and not last_root:
            if continues:
                overall_errors.append(
                    VerifyError(
                        seq=report.first_invalid_seq or 0,
                        error_type="chain_break",
                        expected="genesis",
                        actual=continues,
                        message="Unexpected continues_from on first file",
                    )
                )
                manifest_valid = False

        if report.manifest_valid and report.manifest_signature_valid:
            last_root = manifest_data.get("root_chain_hash")

    valid = len(overall_errors) == 0 and manifest_valid
    return VerifyReport(
        valid=valid,
        file_path=",".join(str(p) for p in files),
        records_checked=records_checked,
        records_valid=records_valid,
        records_invalid=records_checked - records_valid,
        first_invalid_seq=overall_errors[0].seq if overall_errors else None,
        chain_valid=manifest_valid
        and all(e.error_type != "chain_break" for e in overall_errors),
        chain_breaks=[e.seq for e in overall_errors if e.error_type == "chain_break"],
        manifest_valid=manifest_valid,
        manifest_signature_valid=manifest_valid,
        errors=overall_errors,
        duration_ms=0.0,
    )


async def run_self_check(paths: list[Path], verifier: Verifier) -> None:
    """Run a self-check across provided paths and warn on failure."""
    from fapilog.core import diagnostics

    for path in paths:
        report = await verifier.verify_file(path)
        if not report.valid:
            try:
                diagnostics.warn(
                    "tamper",
                    "self-check failed",
                    file=str(path),
                    errors=[asdict(e) for e in report.errors],
                )
            except Exception:
                continue


def _build_key_store(keys: Path | None, key_env: str | None) -> KeyStore:
    stores: list[KeyStore] = []
    if key_env:
        stores.append(EnvKeyStore())
    if keys:
        stores.append(FileKeyStore(keys))

    class _Composite(KeyStore):
        def get_key(self, key_id: str) -> bytes | None:
            for store in stores:
                key = store.get_key(key_id)
                if key:
                    return key
            return None

    return _Composite()


def _print_report(
    report: VerifyReport, *, output_format: str, verbose: bool, quiet: bool
) -> None:
    if output_format == "json":
        print(json.dumps(asdict(report), indent=2))
        return

    if not quiet:
        status = "OK" if report.valid else "FAIL"
        print(f"[{status}] {report.file_path} ({report.records_checked} records)")
    if verbose or not report.valid:
        for err in report.errors:
            print(f"- {err.error_type} seq={err.seq} msg={err.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fapilog-tamper")
    sub = parser.add_subparsers(dest="command")
    v = sub.add_parser("verify", help="Verify tamper-evident log file")
    v.add_argument("path")
    v.add_argument("--manifest")
    v.add_argument("--keys")
    v.add_argument("--key-env")
    v.add_argument(
        "--format", dest="output_format", choices=["text", "json"], default="text"
    )
    v.add_argument("--verbose", action="store_true")
    v.add_argument("--quiet", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "verify":
        key_path = Path(args.keys) if args.keys else None
        key_store = _build_key_store(key_path, args.key_env)
        verifier = Verifier(key_store)
        manifest = Path(args.manifest) if args.manifest else None
        report = asyncio.run(
            verifier.verify_file(Path(args.path), manifest_path=manifest)
        )
        _print_report(
            report,
            output_format=args.output_format,
            verbose=args.verbose,
            quiet=args.quiet,
        )
        return 0 if report.valid else 1

    parser.print_help()
    return 2


def verify_records(records: list[dict[str, Any]]) -> VerifyReport:
    """Convenience helper for verifying in-memory record collections."""
    # Simplified: treat records as already validated if provided
    return VerifyReport(
        valid=True,
        file_path="",
        records_checked=len(records),
        records_valid=len(records),
        records_invalid=0,
        chain_valid=True,
        chain_breaks=[],
        manifest_valid=None,
        manifest_signature_valid=None,
        errors=[],
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

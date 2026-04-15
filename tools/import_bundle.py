#!/usr/bin/env python3
"""Import bundle vào archive.

Quy tắc:
    - Verify manifest + merkle root trước
    - Verify mỗi memory_id khớp sha256(content)[:16] (nguyên tắc 5)
    - Nếu có SIGNATURE: verify ed25519 chữ ký manifest (tuỳ chọn)
    - Nếu memory_id đã tồn tại với cùng content → skip (dedup)
    - Nếu memory_id đã tồn tại với content KHÁC → REJECT bundle
      (đây là tín hiệu tamper hoặc collision — không auto-resolve)
    - Nếu memory_id mới → ghi vào archive/events/<event_id>/

Sử dụng:
    python tools/import_bundle.py bundle.tar.gz
    python tools/import_bundle.py bundle.tar.gz --verify-pubkey abc123...
    python tools/import_bundle.py bundle.tar.gz --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.integrity import compute_memory_id  # noqa: E402


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _read_tar(path: Path) -> tuple[dict, list[tuple[str, dict]], bytes | None]:
    """Đọc tarball → (manifest, [(name, memory)], signature_or_None)."""
    manifest: dict | None = None
    entries: list[tuple[str, dict]] = []
    signature: bytes | None = None

    with tarfile.open(path, "r:gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            f = tar.extractfile(member)
            if f is None:
                continue
            data = f.read()
            if member.name == "MANIFEST.json":
                manifest = json.loads(data.decode("utf-8"))
            elif member.name == "SIGNATURE":
                signature = data
            elif member.name.startswith("archive/events/") and member.name.endswith(".json"):
                try:
                    mem = json.loads(data.decode("utf-8"))
                    entries.append((member.name, mem))
                except json.JSONDecodeError:
                    pass

    if manifest is None:
        raise ValueError("Bundle thiếu MANIFEST.json")
    return manifest, entries, signature


def _merkle_root(mems: list[dict]) -> str:
    items: list[bytes] = []
    for mem in sorted(mems, key=lambda m: m.get("memory_id", "")):
        mid = mem.get("memory_id", "")
        content_hash = compute_memory_id(mem)
        items.append(f"{mid}:{content_hash}".encode())
    if not items:
        return "0" * 64
    return hashlib.sha256(b"\n".join(items)).hexdigest()


def import_bundle(
    bundle_path: Path,
    archive_root: Path,
    *,
    dry_run: bool = False,
    verify_pubkey_hex: str | None = None,
) -> dict:
    manifest, raw_entries, signature = _read_tar(bundle_path)

    # 1. Merkle check
    mems = [m for _name, m in raw_entries]
    expected_merkle = manifest.get("merkle_root")
    actual_merkle = _merkle_root(mems)
    if expected_merkle != actual_merkle:
        raise ValueError(
            f"Merkle mismatch: manifest={expected_merkle} actual={actual_merkle}"
        )

    # 2. Signature check (optional)
    sig_verified = False
    if signature:
        pubkey_hex = verify_pubkey_hex or manifest.get("pubkey_ed25519_hex")
        if not pubkey_hex:
            raise ValueError("Bundle có SIGNATURE nhưng không có pubkey để verify.")
        try:
            from cryptography.exceptions import InvalidSignature  # type: ignore
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "Cần `pip install cryptography` để verify chữ ký."
            ) from exc
        # Rebuild manifest bytes giống export_bundle
        manifest_bytes = _canonical(manifest)
        pubkey = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
        try:
            pubkey.verify(signature, manifest_bytes)
            sig_verified = True
        except InvalidSignature as exc:
            raise ValueError("Signature không hợp lệ.") from exc

    # 3. Per-memory integrity
    for i, mem in enumerate(mems):
        claimed = mem.get("memory_id", "")
        actual = compute_memory_id(mem)
        if claimed != actual:
            raise ValueError(
                f"Memory #{i} có memory_id không khớp: claimed={claimed} actual={actual}"
            )

    # 4. Merge strategy
    added: list[str] = []
    skipped_dedup: list[str] = []
    rejected_conflict: list[tuple[str, str]] = []

    for mem in mems:
        mid = mem.get("memory_id", "")
        eid = (mem.get("event") or {}).get("event_id", "")
        target = archive_root / "events" / eid / f"{mid}.json"
        if target.exists():
            # Dedup hay conflict?
            try:
                with target.open(encoding="utf-8") as f:
                    existing = json.load(f)
            except (OSError, json.JSONDecodeError):
                existing = None
            if existing == mem:
                skipped_dedup.append(mid)
                continue
            # Content khác → conflict (không nên xảy ra nếu memory_id = hash(content))
            rejected_conflict.append((mid, "content differs at same memory_id"))
            continue
        added.append(mid)
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8") as f:
                json.dump(mem, f, ensure_ascii=False, indent=2)

    if rejected_conflict:
        raise ValueError(
            f"Bundle bị reject: {len(rejected_conflict)} memory_id có content "
            f"khác với archive hiện tại. First: {rejected_conflict[0]}"
        )

    return {
        "bundle_name": manifest.get("bundle_name"),
        "merkle_root": actual_merkle,
        "entry_count": len(mems),
        "added": added,
        "skipped_dedup": skipped_dedup,
        "signature_verified": sig_verified,
        "dry_run": dry_run,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("bundle", help="Đường dẫn bundle.tar.gz")
    p.add_argument("--archive", default="archive")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--verify-pubkey",
        help="Hex pubkey để verify chữ ký (nếu khác với pubkey trong manifest)",
    )
    args = p.parse_args()

    result = import_bundle(
        Path(args.bundle),
        Path(args.archive),
        dry_run=args.dry_run,
        verify_pubkey_hex=args.verify_pubkey,
    )
    print(f"Imported bundle: {result['bundle_name']}")
    print(f"  merkle: {result['merkle_root']}")
    print(f"  added: {len(result['added'])}")
    print(f"  skipped (dedup): {len(result['skipped_dedup'])}")
    if result["signature_verified"]:
        print("  signature: VERIFIED")
    if args.dry_run:
        print("  (dry run — no files written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

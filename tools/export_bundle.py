#!/usr/bin/env python3
"""Export archive thành bundle — đơn vị trao đổi giữa các HumanArchive node.

Bundle là một file .tar.gz chứa:
    - archive/events/*                       (dữ liệu)
    - MANIFEST.json                          (metadata + merkle root + counts)
    - SIGNATURE (tuỳ chọn, ed25519 nếu có cryptography)

Federation v1 KHÔNG phải P2P gossip. Đây là:
    - Export: đóng gói snapshot có thể verify
    - Import: merge vào archive khác, dedup tự nhiên nhờ content-addressing
    - Mirror: node khác có thể fetch bundle qua HTTP/IPFS/Arweave/USB

Quy tắc merge:
    - Cùng memory_id, cùng content (hash khớp) → skip (dedup)
    - Cùng memory_id, content khác → reject bundle (tamper signal)
    - memory_id mới → thêm vào archive

Sử dụng:
    python tools/export_bundle.py --output bundle.tar.gz
    python tools/export_bundle.py --sign-key private.pem --output bundle.tar.gz
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from core.integrity import compute_memory_id, verify_memory_id  # noqa: E402


MANIFEST_VERSION = "1"


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def _collect_memories(archive_root: Path) -> list[tuple[str, str, dict]]:
    """Trả về list (event_id, memory_id, memory_dict)."""
    out: list[tuple[str, str, dict]] = []
    events_root = archive_root / "events"
    if not events_root.exists():
        return out
    for event_dir in sorted(events_root.iterdir()):
        if not event_dir.is_dir():
            continue
        for p in sorted(event_dir.glob("*.json")):
            if p.name.startswith("_") or ".amend." in p.name:
                continue
            try:
                with p.open(encoding="utf-8") as f:
                    mem = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(mem, dict):
                continue
            eid = (mem.get("event") or {}).get("event_id", "")
            mid = mem.get("memory_id", "")
            if not eid or not mid:
                continue
            out.append((eid, mid, mem))
    return out


def _merkle_root(entries: list[tuple[str, str, dict]]) -> str:
    """Merkle root = sha256 của (sorted memory_id + content_hash)."""
    items: list[bytes] = []
    for _eid, mid, mem in sorted(entries, key=lambda t: t[1]):
        content_hash = compute_memory_id(mem)
        items.append(f"{mid}:{content_hash}".encode())
    if not items:
        return "0" * 64
    root = hashlib.sha256(b"\n".join(items)).hexdigest()
    return root


def build_bundle(
    archive_root: Path,
    output: Path,
    *,
    bundle_name: str | None = None,
    sign_key_path: Path | None = None,
) -> dict:
    entries = _collect_memories(archive_root)

    # Verify integrity trước khi export — không export dữ liệu bị tamper
    tampered = [(eid, mid) for eid, mid, mem in entries if verify_memory_id(mem).tampered]
    if tampered:
        raise ValueError(
            f"Refuse to export: {len(tampered)} memories have tampered memory_id. "
            f"Fix archive integrity first. First: {tampered[0]}"
        )

    merkle = _merkle_root(entries)
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "bundle_name": bundle_name or f"bundle-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entry_count": len(entries),
        "event_count": len({eid for eid, _, _ in entries}),
        "merkle_root": merkle,
        "protocol": "humanarchive/v1",
    }
    manifest_bytes = _canonical(manifest)

    # Tuỳ chọn: sign bằng ed25519
    signature_bytes: bytes | None = None
    pubkey_bytes: bytes | None = None
    if sign_key_path:
        try:
            from cryptography.hazmat.primitives import serialization  # type: ignore
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "Cần `pip install cryptography` để sign bundle."
            ) from exc
        with sign_key_path.open("rb") as f:
            priv = serialization.load_pem_private_key(f.read(), password=None)
        if not isinstance(priv, Ed25519PrivateKey):
            raise ValueError("Key phải là ed25519.")
        signature_bytes = priv.sign(manifest_bytes)
        pubkey_bytes = priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        manifest["pubkey_ed25519_hex"] = pubkey_bytes.hex()
        manifest_bytes = _canonical(manifest)

    # Đóng gói tar.gz
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as tar:
        for eid, mid, mem in entries:
            data = _canonical(mem)
            info = tarfile.TarInfo(name=f"archive/events/{eid}/{mid}.json")
            info.size = len(data)
            info.mtime = 0  # deterministic
            tar.addfile(info, io.BytesIO(data))

        info = tarfile.TarInfo("MANIFEST.json")
        info.size = len(manifest_bytes)
        info.mtime = 0
        tar.addfile(info, io.BytesIO(manifest_bytes))

        if signature_bytes:
            info = tarfile.TarInfo("SIGNATURE")
            info.size = len(signature_bytes)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(signature_bytes))

    return manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", default="archive")
    p.add_argument("--output", default="bundle.tar.gz")
    p.add_argument("--name", help="Tên bundle (mặc định: timestamp)")
    p.add_argument("--sign-key", help="Đường dẫn ed25519 private key PEM (tuỳ chọn)")
    args = p.parse_args()

    manifest = build_bundle(
        Path(args.archive),
        Path(args.output),
        bundle_name=args.name,
        sign_key_path=Path(args.sign_key) if args.sign_key else None,
    )
    print(f"Exported bundle: {args.output}")
    print(f"  entries: {manifest['entry_count']}")
    print(f"  events:  {manifest['event_count']}")
    print(f"  merkle:  {manifest['merkle_root']}")
    if args.sign_key:
        print(f"  signed:  {manifest.get('pubkey_ed25519_hex', '')[:32]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())

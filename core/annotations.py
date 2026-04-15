"""Annotation layer — thêm context/correction/dispute cho memory đã tồn tại
mà KHÔNG sửa memory gốc.

Tầng annotation tồn tại song song với archive/events/, nằm ở
archive/annotations/<target_memory_id>/<annotation_id>.json.

Nguyên tắc 5 được bảo toàn ở CẢ HAI tầng:
    * Memory gốc: bất biến
    * Annotation: content-addressed, bất biến (sửa = tạo annotation mới
      type="correction" trỏ tới annotation cũ)

Các type annotation:
    - context        : "xin bổ sung thông tin..."
    - correction     : "detail X có thể là Y thay vì Z" (không gán 'sai')
    - dispute        : "tôi không đồng ý với phần này" (không phán xét)
    - vouching       : "tôi cũng chứng kiến, xác nhận điểm này"
    - review         : "approve" | "request-changes" (staging workflow)
    - warning        : community-flagged cảnh báo (không xoá, không ẩn)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal

AnnotationType = Literal[
    "context", "correction", "dispute", "vouching", "review", "warning"
]


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_annotation_id(annotation: dict) -> str:
    clone = {k: v for k, v in annotation.items() if k not in ("annotation_id", "signature")}
    return hashlib.sha256(_canonical(clone).encode("utf-8")).hexdigest()[:16]


@dataclass
class Annotation:
    annotation_id: str
    target_memory_id: str
    author_id: str
    type: AnnotationType
    content: str
    created_at: str
    suggested_changes: dict | None = None
    signature: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "schema_version": "1.0",
            "annotation_id": self.annotation_id,
            "target_memory_id": self.target_memory_id,
            "author_id": self.author_id,
            "type": self.type,
            "content": self.content,
            "created_at": self.created_at,
        }
        if self.suggested_changes is not None:
            d["suggested_changes"] = self.suggested_changes
        if self.signature is not None:
            d["signature"] = self.signature
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        return cls(
            annotation_id=d["annotation_id"],
            target_memory_id=d["target_memory_id"],
            author_id=d["author_id"],
            type=d["type"],
            content=d["content"],
            created_at=d["created_at"],
            suggested_changes=d.get("suggested_changes"),
            signature=d.get("signature"),
        )


def create_annotation(
    *,
    target_memory_id: str,
    author_id: str,
    type: AnnotationType,
    content: str,
    suggested_changes: dict | None = None,
) -> Annotation:
    """Sinh một annotation mới với annotation_id computed.

    Không ký — signature được thêm sau bằng sign_annotation().
    """
    if type not in (
        "context", "correction", "dispute", "vouching", "review", "warning"
    ):
        raise ValueError(f"type không hợp lệ: {type}")
    if not content or len(content) < 1:
        raise ValueError("content không được rỗng")

    base = {
        "schema_version": "1.0",
        "target_memory_id": target_memory_id,
        "author_id": author_id,
        "type": type,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if suggested_changes:
        base["suggested_changes"] = suggested_changes

    anno_id = compute_annotation_id(base)
    base["annotation_id"] = anno_id
    return Annotation.from_dict(base)


# --------------------------------------------------------------------------
# File layout
# --------------------------------------------------------------------------

def annotation_dir(archive_root: Path | str, memory_id: str) -> Path:
    return Path(archive_root) / "annotations" / memory_id


def save_annotation(annotation: Annotation, archive_root: Path | str) -> Path:
    d = annotation_dir(archive_root, annotation.target_memory_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{annotation.annotation_id}.json"
    if path.exists():
        # Content-addressed: cùng nội dung → cùng ID, idempotent
        return path
    with path.open("w", encoding="utf-8") as f:
        json.dump(annotation.to_dict(), f, ensure_ascii=False, indent=2)
    return path


def load_annotations(
    archive_root: Path | str, memory_id: str
) -> list[Annotation]:
    """Load tất cả annotation cho một memory. Sort theo created_at."""
    d = annotation_dir(archive_root, memory_id)
    if not d.exists():
        return []
    out: list[Annotation] = []
    for p in sorted(d.glob("*.json")):
        try:
            with p.open(encoding="utf-8") as f:
                out.append(Annotation.from_dict(json.load(f)))
        except (OSError, json.JSONDecodeError, KeyError):
            continue
    out.sort(key=lambda a: a.created_at)
    return out


def iter_all_annotations(archive_root: Path | str) -> Iterable[Annotation]:
    root = Path(archive_root) / "annotations"
    if not root.exists():
        return
    for mem_dir in sorted(root.iterdir()):
        if not mem_dir.is_dir():
            continue
        for p in sorted(mem_dir.glob("*.json")):
            try:
                with p.open(encoding="utf-8") as f:
                    yield Annotation.from_dict(json.load(f))
            except (OSError, json.JSONDecodeError, KeyError):
                continue


# --------------------------------------------------------------------------
# Signing (optional, cần `pip install cryptography`)
# --------------------------------------------------------------------------

def sign_annotation(annotation: Annotation, private_key_pem: bytes) -> Annotation:
    """Ký annotation bằng ed25519. Trả annotation mới có signature."""
    try:
        from cryptography.hazmat.primitives import serialization  # type: ignore
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # type: ignore
    except ImportError as exc:
        raise ImportError("Cần `pip install cryptography` để ký annotation.") from exc

    priv = serialization.load_pem_private_key(private_key_pem, password=None)
    if not isinstance(priv, Ed25519PrivateKey):
        raise ValueError("Key phải là ed25519.")

    unsigned = annotation.to_dict()
    unsigned.pop("signature", None)
    payload = _canonical(unsigned).encode()
    sig = priv.sign(payload).hex()
    annotation.signature = sig
    return annotation


def verify_annotation(annotation: Annotation, pubkey_hex: str) -> bool:
    """Verify signature của annotation bằng ed25519 pubkey."""
    if not annotation.signature:
        return False
    try:
        from cryptography.exceptions import InvalidSignature  # type: ignore
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # type: ignore
    except ImportError:
        return False

    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
    except ValueError:
        return False

    unsigned = annotation.to_dict()
    unsigned.pop("signature", None)
    payload = _canonical(unsigned).encode()
    try:
        pub.verify(bytes.fromhex(annotation.signature), payload)
        return True
    except (InvalidSignature, ValueError):
        return False

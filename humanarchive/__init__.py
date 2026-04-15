"""HumanArchive — Decentralized collective memory archive.

Without judgment. With consent. Multi-perspective by design.

    >>> from humanarchive import analyze_memory, generate_historical_entry
    >>> entry = generate_historical_entry("1975-saigon-fall-a3f2")

See:
    - README.md for quickstart
    - docs/ethics.md for the 5 immutable principles
    - docs/workflows.md for multi-user patterns
"""

__version__ = "0.7.0"
__author__ = "HumanArchive contributors"
__license__ = "MIT (code), CC-BY-SA 4.0 (content)"

# Re-export the public API from core/ so users can write `from humanarchive import X`
try:
    from core.ai_engine import (  # noqa: F401
        analyze_memory,
        cross_reference,
        generate_historical_entry,
    )
    from core.integrity import (  # noqa: F401
        compute_memory_id,
        is_publicly_viewable,
        verify_memory_id,
    )
    from core.annotations import (  # noqa: F401
        create_annotation,
        load_annotations,
        save_annotation,
    )
    from core.graph import (  # noqa: F401
        build_perspective_prism,
        load_archive_graph,
    )
except ImportError:
    # Package-only install (no core/ bundled) — the CLI still works via subprocess.
    pass

__all__ = [
    "__version__",
    "analyze_memory",
    "cross_reference",
    "generate_historical_entry",
    "compute_memory_id",
    "is_publicly_viewable",
    "verify_memory_id",
    "create_annotation",
    "load_annotations",
    "save_annotation",
    "build_perspective_prism",
    "load_archive_graph",
]

"""
EVA Storage Lifecycle Management (Phase 11).

Central module for every storage write, cleanup, and quota check
inside EVA. All file operations must go through StorageManager.

Design principles:
    - 100% local. No cloud, no telemetry.
    - Customer's PC owns all data.
    - Protected content (knowledge, memory, skills) never auto-deleted.
    - Ephemeral content (temp screenshots, cache) auto-cleaned.
    - Cold data archived to HDD when configured.

Public API:
    from app.storage.manager import StorageManager
    StorageManager.save(category="screenshots", filename="x.png", content=b"...")
"""
from app.storage.manager import StorageManager, StorageError  # noqa: F401
from app.storage.policies import RetentionPolicy, PolicyError  # noqa: F401
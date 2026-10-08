"""Rename-Engine (§15/§16) - siehe engine.py fuer den vollstaendigen
Sicherheitsablauf (Vorlage -> Vorschau -> Bestaetigung -> Ausfuehrung mit
Rollback)."""
from __future__ import annotations

from genesis_core.rename.engine import (
    RenameApplyNotConfirmedError,
    RenameApplyResult,
    RenameBatchFailedError,
    RenamePreviewItem,
    apply_renames,
    preview_renames,
)
from genesis_core.rename.templates import (
    RenameTemplateError,
    render_template,
    sanitize_filename_component,
)

__all__ = [
    "RenameApplyNotConfirmedError",
    "RenameApplyResult",
    "RenameBatchFailedError",
    "RenamePreviewItem",
    "RenameTemplateError",
    "apply_renames",
    "preview_renames",
    "render_template",
    "sanitize_filename_component",
]

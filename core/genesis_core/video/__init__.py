"""Film-/Serien-Modul (§24): Tag-basierte Metadaten + Episode-Erkennung.

Siehe `tags.py` (reines Lesen eingebetteter Tags) und `engine.py`
(Episode-vs-Film-Erkennung + bestätigungspflichtige DB-Übernahme). Bewusst
OHNE Online-Provider - siehe Moduldocstring in `engine.py`.
"""
from genesis_core.video.engine import (
    EpisodeDetectionResult,
    VideoApplyNotConfirmedError,
    apply_episode_metadata,
    apply_movie_metadata,
    detect_episode,
)
from genesis_core.video.tags import VideoTagSnapshot, read_video_tags

__all__ = [
    "EpisodeDetectionResult",
    "VideoApplyNotConfirmedError",
    "VideoTagSnapshot",
    "apply_episode_metadata",
    "apply_movie_metadata",
    "detect_episode",
    "read_video_tags",
]

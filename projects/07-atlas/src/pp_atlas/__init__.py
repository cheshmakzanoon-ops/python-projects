"""Atlas permission-aware offline retrieval public interface."""

from pp_atlas.auth import Principal
from pp_atlas.catalog import IncompatibleCatalog
from pp_atlas.engine import Engine, StaleGeneration
from pp_atlas.index.segments import CorruptSegment
from pp_atlas.models import Document, Hit, SearchResult

__all__ = [
    "CorruptSegment",
    "Document",
    "Engine",
    "Hit",
    "IncompatibleCatalog",
    "Principal",
    "SearchResult",
    "StaleGeneration",
]

"""검색·RRF·컨텍스트 조립 사이에서 공유하는 값 객체."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SearchFilters:
    room: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


@dataclass(frozen=True)
class RankedHit:
    chunk_id: int
    content_hash: str
    rank: int
    score: float
    source: str


@dataclass(frozen=True)
class FusedHit:
    chunk_id: int
    content_hash: str
    score: float
    ranks: dict[str, int] = field(default_factory=dict)
    raw_scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    chunk_id: int
    content_hash: str
    room: str
    start_at: datetime
    end_at: datetime
    start_seq: int
    end_seq: int
    participants: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class ContextItem:
    citation_id: str
    hit: FusedHit
    chunk: Chunk


@dataclass(frozen=True)
class CitationCheck:
    cited: tuple[str, ...]
    unknown: tuple[str, ...]
    factual_sentences: int
    cited_sentences: int

    @property
    def coverage(self) -> float:
        if self.factual_sentences == 0:
            return 1.0
        return self.cited_sentences / self.factual_sentences


@dataclass(frozen=True)
class SearchRun:
    original_query: str
    masked_query: str
    bm25: tuple[RankedHit, ...]
    vector: tuple[RankedHit, ...]
    hybrid: tuple[FusedHit, ...]
    chunks: dict[int, Chunk]
    timings_ms: dict[str, float]


@dataclass(frozen=True)
class AgentResult:
    run: SearchRun
    context_items: tuple[ContextItem, ...]
    rendered_context: str
    answer: str | None
    citation_check: CitationCheck | None

from datetime import datetime

from agent import PersonalDataAgent
from models import Chunk, FusedHit, RankedHit, SearchRun


class FakeEngine:
    def search(self, *args, **kwargs):
        now = datetime(2025, 1, 1)
        content_hash = "a" * 40
        hit = RankedHit(1, content_hash, 1, 1.0, "bm25")
        fused = FusedHit(1, content_hash, 1 / 61, {"bm25": 1}, {"bm25": 1.0})
        chunk = Chunk(1, content_hash, "방", now, now, 1, 2, ("가명",), "마감은 금요일")
        return SearchRun("질문", "질문", (hit,), (), (fused,), {1: chunk}, {})


class StubGenerator:
    def generate(self, *, system, user):
        assert "EVIDENCE" in user
        return "마감은 금요일입니다. [C1]"


def test_agent_runs_without_real_provider_or_network():
    result = PersonalDataAgent(FakeEngine(), StubGenerator()).ask("마감은?")
    assert result.answer.endswith("[C1]")
    assert result.citation_check.unknown == ()

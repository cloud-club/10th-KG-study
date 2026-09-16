"""W3 검색과 RAG 흐름을 확인하는 로컬 Streamlit UI."""
import os
import re
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent import answer_from_chunks, assemble_context  # noqa: E402
from gen1_es import search_bm25  # noqa: E402
from gen2_pgvector import search_vector  # noqa: E402
from hybrid_search import RETRIEVER_LIMIT, fuse_search_results  # noqa: E402


def mask_applicant_portfolio(row: dict) -> dict:
    """지원자 포트폴리오 제목 앞의 회사명을 Context와 화면에서 가린다."""
    title = row.get("title", "")
    if "지원자" not in title or "포트폴리오" not in title:
        return {**row, "display_id": row["id"]}
    match = re.match(r"^(.+?)(?=[ _]?지원자(?:[ _]))", title)
    if not match:
        return {**row, "display_id": row["id"]}

    company = match.group(1)
    masked = {**row}
    for field in ("title", "source", "heading", "text"):
        masked[field] = masked.get(field, "").replace(company, "OO기업")
    masked["display_id"] = row["id"].replace(company.replace(" ", "_"), "OO기업", 1)
    return masked


def show_chunk(row: dict, label: str, score_label: str, score: float) -> None:
    with st.expander(f"{label} · {row['title']}"):
        st.write(f"**Chunk ID:** `{row.get('display_id', row['id'])}`")
        st.write(f"**Source:** {row['source']}")
        st.write(f"**Heading:** {row['heading'] or '-'}")
        st.write(f"**{score_label}:** `{score:.5f}`")
        st.text(row["text"])


def display_trace(trace: dict, rows: list[dict]) -> dict:
    ids = {row["id"]: row.get("display_id", row["id"]) for row in rows}
    shown = {**trace}
    for key in ("input_chunk_ids", "included_chunk_ids"):
        shown[key] = [ids.get(chunk_id, chunk_id) for chunk_id in trace[key]]
    for key in ("excluded", "truncated"):
        shown[key] = [{**item, "id": ids.get(item["id"], item["id"])} for item in trace[key]]
    return shown


def run_search(question: str, mask_company: bool) -> dict:
    try:
        bm25 = search_bm25(question, RETRIEVER_LIMIT)
    except Exception as error:
        return {"error": f"Elasticsearch에 연결할 수 없습니다. `docker compose up -d` 후 다시 시도하세요. ({error})"}

    try:
        vector = search_vector(question, RETRIEVER_LIMIT)
    except Exception as error:
        return {"error": f"PostgreSQL/pgvector에 연결할 수 없습니다. `docker compose up -d` 후 다시 시도하세요. ({error})"}

    if mask_company:
        bm25 = [mask_applicant_portfolio(row) for row in bm25]
        vector = [mask_applicant_portfolio(row) for row in vector]
    else:
        bm25 = [{**row, "display_id": row["id"]} for row in bm25]
        vector = [{**row, "display_id": row["id"]} for row in vector]

    hybrid = fuse_search_results(bm25, vector, limit=5)
    context, mapping, trace = assemble_context(hybrid)
    result = {
        "question": question,
        "bm25": bm25[:5],
        "vector": vector[:5],
        "hybrid": hybrid,
        "context": context,
        "mapping": mapping,
        "trace": trace,
        "answer": None,
        "rag_error": None,
    }

    if os.getenv("OPENAI_API_KEY"):
        try:
            result["answer"] = answer_from_chunks(question, hybrid)
        except Exception as error:
            if "OpenAI API 오류 (401)" in str(error):
                result["rag_error"] = "OPENAI_API_KEY가 올바르지 않습니다. 키를 다시 설정하고 Streamlit을 재시작하세요."
            else:
                result["rag_error"] = f"답변 생성 중 오류가 발생했습니다: {error}"
    else:
        result["rag_error"] = "RAG 답변에는 `OPENAI_API_KEY`가 필요합니다. 검색 결과는 아래에서 확인할 수 있습니다."
    return result


st.set_page_config(page_title="Personal RAG", layout="wide")
st.title("Personal RAG")
st.caption("내 Notion 데이터의 검색 → Context → 답변 → 인용 검증 흐름을 확인합니다.")

with st.form("question_form"):
    question = st.text_input("질문", placeholder="청바지에서 로그 추적을 어떻게 구현했지?")
    mask_company = st.checkbox("지원자 포트폴리오 회사명 마스킹", value=True)
    submitted = st.form_submit_button("질문하기", type="primary")

if submitted:
    if question.strip():
        with st.spinner("검색하고 있습니다..."):
            st.session_state["result"] = run_search(question.strip(), mask_company)
    else:
        st.warning("질문을 입력해주세요.")

result = st.session_state.get("result")
if result:
    if result.get("error"):
        st.error(result["error"])
    else:
        rag_tab, search_tab = st.tabs(["RAG", "Search Debug"])

        with rag_tab:
            if result["rag_error"]:
                st.warning(result["rag_error"])
            if result["answer"]:
                answer = result["answer"]
                st.subheader("Answer")
                st.markdown(answer["answer"])
                col1, col2 = st.columns(2)
                col1.metric("Citation Verified", str(answer["citation_verified"]))
                col2.metric("Grounded (model)", str(answer["model_grounded"]))

                st.subheader("Citations")
                if not answer["citations"]:
                    st.info("인용이 없습니다.")
                by_id = {row["id"]: row for row in result["hybrid"]}
                for citation in answer["citations"]:
                    chunk = by_id.get(citation["chunk_id"], {})
                    mark = "✓ Verified" if citation["valid"] else "✗ Verification Failed"
                    with st.expander(f'Citation [{citation["source"]}] · {mark}', expanded=not citation["valid"]):
                        display_id = chunk.get("display_id", citation["chunk_id"] or "unknown")
                        st.write(f'**Chunk ID:** `{display_id}`')
                        st.write(f'**Source:** {chunk.get("source", "-")}')
                        st.write(f'**Snippet:** {citation["snippet"]}')

            st.subheader("Context Debug")
            trace = result["trace"]
            st.write(f'**Context length:** `{trace["context_chars"]}` chars')
            for number, chunk in result["mapping"].items():
                st.write(f'`[{number}]` → `{chunk.get("display_id", chunk["id"])}`')
            with st.expander("Context 원문 보기"):
                st.text(result["context"])
            with st.expander("Context trace"):
                st.json(display_trace(trace, result["hybrid"]))

            st.subheader("Hybrid Top-5")
            if not result["hybrid"]:
                st.info("검색 결과가 없습니다.")
            for row in result["hybrid"]:
                label = f'Hybrid #{row["rank"]} · BM25 {row["bm25_rank"] or "-"} · Vector {row["vector_rank"] or "-"}'
                show_chunk(row, label, "RRF Score", row["rrf_score"])

        with search_tab:
            bm25_col, vector_col, hybrid_col = st.columns(3)
            with bm25_col:
                st.subheader("BM25")
                for row in result["bm25"]:
                    show_chunk(row, f'BM25 #{row["rank"]}', "BM25 Score", row["score"])
            with vector_col:
                st.subheader("Vector")
                for row in result["vector"]:
                    show_chunk(row, f'Vector #{row["rank"]}', "Cosine Similarity", row["score"])
            with hybrid_col:
                st.subheader("Hybrid RRF")
                for row in result["hybrid"]:
                    label = f'#{row["rank"]} · B {row["bm25_rank"] or "-"} · V {row["vector_rank"] or "-"}'
                    show_chunk(row, label, "RRF Score", row["rrf_score"])

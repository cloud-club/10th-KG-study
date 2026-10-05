#!/usr/bin/env python3
"""기업분석 에이전트 챗봇 UI.

새 검색/답변 로직을 만들지 않고 chat.py(단순 RAG), agentic_chat.py(재질의 루프)를
그대로 불러와 화면만 씌운다. 실행: `streamlit run src/app.py`
"""

import streamlit as st

import common_path  # noqa: F401
from agentic_chat import run_agentic_search
from chat import answer_question
from hybrid_search import load_chunk_lookup
from index_es import DEFAULT_INDEX
from index_pgvector import DEFAULT_DSN
from search_common.elasticsearch import DEFAULT_ES_URL
from search_common.embeddings import DEFAULT_MODEL, DEFAULT_OLLAMA_URL
from search_common.llm import DEFAULT_CHAT_MODEL

try:
    import psycopg
except ImportError as error:
    raise SystemExit("pgvector 단계는 `pip install -r requirements.txt`가 필요합니다.") from error


st.set_page_config(page_title="기업분석 에이전트", page_icon="\U0001f4c8")


@st.cache_resource
def get_chunk_lookup() -> dict[str, dict]:
    return load_chunk_lookup()


@st.cache_resource
def get_connection() -> "psycopg.Connection":
    return psycopg.connect(DEFAULT_DSN, autocommit=True)


def render_sources(chunks: list[dict]) -> None:
    if not chunks:
        return
    with st.expander(f"참고한 근거 {len(chunks)}건"):
        for rank, chunk in enumerate(chunks, start=1):
            st.markdown(f"**[{rank}] {chunk['title']}** ({chunk['date']})")
            st.caption(f"chunk={chunk['id']} · {chunk['url']}")


def render_trace(trace: list[dict]) -> None:
    if not trace:
        return
    with st.expander(f"에이전트 사고 과정 {len(trace)}단계"):
        for step in trace:
            if step["type"] == "decompose":
                st.markdown(f"**질문 분해** → {len(step['sub_queries'])}개 하위 질의")
                for sub_query in step["sub_queries"]:
                    st.caption(f"· {sub_query}")
            elif step["type"] == "search":
                label = "분해 검색" if step["phase"] == "decompose" else f"검색 (hop {step['hop']})"
                st.markdown(f"**{label}**: `{step['query']}`")
                st.caption(f"새로 찾은 청크 {len(step['new_chunk_ids'])}개: {', '.join(step['new_chunk_ids']) or '없음'}")
            elif step["type"] == "judge":
                hop_label = f"hop {step['hop']}" if step["hop"] is not None else "최대 홉 도달"
                st.markdown(f"**판단 ({hop_label})**: `{step['action'].upper()}`")
                st.caption(step["payload"])
            elif step["type"] == "final_answer":
                reason = "정상 답변" if step["reason"] == "answered" else "최대 홉 도달로 강제 답변"
                st.markdown(f"**최종 답변 확정** ({reason})")


st.title("기업분석 에이전트")
st.caption("삼성전자·SK하이닉스 뉴스룸·공시 69개 청크 기반 하이브리드(RRF) 검색 + RAG")

with st.sidebar:
    mode = st.radio(
        "검색 방식",
        ["일반 RAG (검색 1회)", "에이전틱 검색 (재질의 루프)"],
        help="에이전틱 검색은 멀티홉 질문에서 LLM이 스스로 재검색을 시도한다.",
    )
    max_hops = st.slider("최대 재질의 횟수", 1, 5, 3, disabled="에이전틱" not in mode)
    decompose = st.checkbox(
        "질문 분해(query decomposition) 먼저 시도",
        disabled="에이전틱" not in mode,
        help="첫 홉 전에 질문을 독립적인 하위 질의로 나눠 각각 검색한다.",
    )
    st.markdown("---")
    st.markdown(
        "예시 질문\n"
        "- 삼성전자 HBM4E 12단 제품의 용량은?\n"
        "- 삼성전자가 요즘 주목하는 기술은?\n"
        "- AMD에 HBM4를 공급하는 회사가 최근 공시에서 밝힌 반도체 클러스터는?"
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(message.get("chunks", []))
            render_trace(message.get("trace", []))

question = st.chat_input("질문을 입력하세요")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        trace: list[dict] = []
        with st.spinner("검색하고 답변을 생성하는 중..."):
            conn = get_connection()
            chunk_lookup = get_chunk_lookup()
            if "에이전틱" in mode:
                answer, chunks, queries_tried, trace = run_agentic_search(
                    conn, question, chunk_lookup,
                    es_url=DEFAULT_ES_URL, index=DEFAULT_INDEX,
                    embed_model=DEFAULT_MODEL, chat_model=DEFAULT_CHAT_MODEL,
                    ollama_url=DEFAULT_OLLAMA_URL, size=5, max_hops=max_hops, decompose=decompose,
                )
                if len(queries_tried) > 1:
                    st.caption(f"재검색 {len(queries_tried) - 1}회: {queries_tried[1:]}")
            else:
                answer, chunks = answer_question(conn, question, chunk_lookup)
        st.markdown(answer)
        render_sources(chunks)
        render_trace(trace)

    st.session_state.messages.append({"role": "assistant", "content": answer, "chunks": chunks, "trace": trace})

"""청크 전략(특히 크기)을 바꿔가며 grep/BM25/pgvector 검색을 실험하는 GUI.

    streamlit run app.py

사이드바에서 청크 방식을 고르고 "청크 생성 + 색인"을 누르면 그 설정으로
Elasticsearch 인덱스를 다시 만든다(무료, 로컬). pgvector는 체크박스로
켜야만 재색인한다 — OpenAI 임베딩 호출이라 켤 때마다 비용이 든다는 걸
버튼 옆에 그대로 적어뒀다.
"""

from __future__ import annotations

import time

import streamlit as st

from common import ES_INDEX, PG_TABLE, QUERIES_PATH
from evaluate import evaluate, hit_at_k, mrr, ranked_source_paths
from index_elasticsearch import index_chunks as index_es
from index_pgvector import index_chunks as index_pg
from parse_vault import chunk_config_key, chunks_path_for, parse_vault, to_dicts, write_chunks
from search_elasticsearch import search_bm25
from search_grep import search_grep
from search_pgvector import search_vector

st.set_page_config(page_title="worklog-search 실험", layout="wide")
st.title("옵시디언 작업기록 검색 — 청크 전략 실험")
st.caption("청크 방식·크기를 바꿔가며 grep / BM25(nori) / pgvector 결과가 어떻게 달라지는지 본다.")


# ------------------------------------------------------------- 사이드바: 청크 설정

st.sidebar.header("1. 청크 설정")
mode = st.sidebar.radio(
    "청크 방식",
    ["heading", "fixed"],
    format_func=lambda m: "## 소제목 단위 (기본)" if m == "heading" else "고정 글자 수 (크기 실험용)",
)
size = 800
overlap = 100
if mode == "fixed":
    size = st.sidebar.slider("청크 크기 (글자 수)", min_value=100, max_value=2000, value=800, step=100)
    overlap = st.sidebar.slider("겹침 (글자 수)", min_value=0, max_value=min(500, size - 50), value=min(100, size - 50), step=50)

config_key = chunk_config_key(mode, size, overlap)
index_name = f"{ES_INDEX}_{config_key}"
table_name = f"{PG_TABLE}_{config_key}"
st.sidebar.caption(f"설정 키: `{config_key}`")

include_vector = st.sidebar.checkbox(
    "pgvector 포함 (OpenAI 임베딩 호출 — 비용 발생)", value=False
)

if st.sidebar.button("청크 생성 + 색인", type="primary"):
    with st.spinner("청크 생성 중..."):
        raw_chunks = parse_vault(mode=mode, size=size, overlap=overlap)
        write_chunks(raw_chunks, chunks_path_for(mode, size, overlap))
        chunks = to_dicts(raw_chunks)
        st.session_state["chunks"] = chunks
        st.session_state["config_key"] = config_key

    with st.spinner(f"Elasticsearch 색인 중... (인덱스: {index_name})"):
        try:
            count = index_es(chunks, index_name=index_name)
            st.sidebar.success(f"BM25 색인 완료: {count}청크")
        except RuntimeError as error:
            st.sidebar.error(f"Elasticsearch 색인 실패: {error}\ndocker compose up -d elasticsearch 를 먼저 실행하세요.")

    if include_vector:
        with st.spinner(f"pgvector 임베딩·색인 중... (OpenAI 호출, 테이블: {table_name})"):
            try:
                count = index_pg(chunks, table_name=table_name)
                st.sidebar.success(f"pgvector 색인 완료: {count}행")
            except Exception as error:  # noqa: BLE001 - API 키 누락 등 다양한 예외를 그대로 보여줌
                st.sidebar.error(f"pgvector 색인 실패: {error}")

chunks = st.session_state.get("chunks")

if chunks is None:
    st.info("왼쪽에서 청크 설정을 고르고 **청크 생성 + 색인**을 눌러 시작하세요.")
    st.stop()

# ------------------------------------------------------------- 청크 통계

lengths = [len(c["content"]) for c in chunks]
docs = {c["source_path"] for c in chunks}
col1, col2, col3, col4 = st.columns(4)
col1.metric("문서 수", len(docs))
col2.metric("청크 수", len(chunks))
col3.metric("평균 청크 길이(자)", f"{sum(lengths) / len(lengths):.0f}")
col4.metric("최소~최대 길이", f"{min(lengths)} ~ {max(lengths)}")

st.divider()

# ------------------------------------------------------------- 2. 질문 검색

st.header("2. 질문으로 세 방식 비교")

try:
    example_queries = [
        (line_no, __import__("json").loads(line)) for line_no, line in enumerate(QUERIES_PATH.read_text(encoding="utf-8").splitlines()) if line.strip()
    ]
except FileNotFoundError:
    example_queries = []

query_options = ["(직접 입력)"] + [f"{q['id']} · {q['query']}" for _, q in example_queries]
picked = st.selectbox("평가 질문에서 고르거나 직접 입력", query_options)
if picked == "(직접 입력)":
    query = st.text_input("질문", value="이미지 레지스트리를 왜 하나로 안 합쳤지")
else:
    idx = query_options.index(picked) - 1
    query = example_queries[idx][1]["query"]
    st.caption(f"expected_primary: {example_queries[idx][1]['expected_primary']}")

limit = st.slider("검색 결과 개수", 1, 10, 3)

if st.button("검색 실행"):
    cols = st.columns(3)
    methods = [
        ("grep", cols[0], lambda: search_grep(query, limit=limit, chunks=chunks)),
        ("BM25(nori)", cols[1], lambda: search_bm25(query, limit=limit, index_name=index_name)),
    ]
    if include_vector:
        methods.append(("pgvector", cols[2], lambda: search_vector(query, limit=limit, table_name=table_name)))

    for name, col, fn in methods:
        with col:
            st.subheader(name)
            try:
                rows, elapsed = fn()
            except Exception as error:  # noqa: BLE001
                st.error(f"실패: {error}")
                continue
            st.caption(f"{len(rows)}건 · {elapsed:.1f}ms")
            for rank, item in enumerate(rows, 1):
                doc = item[0] if isinstance(item, tuple) else item
                score = item[1] if isinstance(item, tuple) else None
                heading = f"#{doc['heading']}" if doc.get("heading") else ""
                score_text = f" · {score:.3f}" if score is not None else ""
                st.markdown(f"**{rank}. {doc['source_path']}{heading}**{score_text}")
                st.text(" ".join(doc["content"].split())[:200])

    if not include_vector:
        cols[2].info("pgvector는 사이드바에서 켜야 여기서도 같이 비교됩니다.")

st.divider()

# ------------------------------------------------------------- 3. 이 설정으로 전체 평가

st.header("3. 이 청크 설정으로 19문항 전체 평가")
st.caption("Hit@3 / MRR을 지금 청크 설정 기준으로 다시 계산한다. 청크 크기를 바꿔서 색인한 뒤 다시 눌러보면 숫자가 어떻게 변하는지 바로 보인다.")

if st.button("전체 평가 실행"):
    methods = ("grep", "bm25", "vector") if include_vector else ("grep", "bm25")
    progress = st.progress(0.0, text="시작...")
    total = len(list(QUERIES_PATH.read_text(encoding="utf-8").splitlines()))

    def on_progress(q, _state={"n": 0}):
        _state["n"] += 1
        progress.progress(_state["n"] / total, text=f"{q['id']} 처리 중...")

    started = time.perf_counter()
    results = evaluate(chunks=chunks, index_name=index_name, table_name=table_name, methods=methods, on_progress=on_progress)
    progress.empty()
    st.caption(f"{len(results)}문항 · {time.perf_counter() - started:.1f}초")

    import pandas as pd

    rows = []
    for m in methods:
        n = len(results)
        rows.append(
            {
                "방식": m,
                "Hit@3": sum(r[f"{m}_hit@3"] for r in results) / n,
                "MRR": sum(r[f"{m}_mrr"] for r in results) / n,
            }
        )
    st.subheader(f"전체 (n={len(results)}, 청크 설정: {config_key})")
    st.dataframe(pd.DataFrame(rows).set_index("방식").style.format("{:.2f}"), width="stretch")

    by_type: dict[str, list] = {}
    for r in results:
        by_type.setdefault(r["type"], []).append(r)
    type_rows = []
    for type_name in sorted(by_type):
        rs = by_type[type_name]
        row = {"type": type_name, "n": len(rs)}
        for m in methods:
            row[f"{m}_mrr"] = sum(r[f"{m}_mrr"] for r in rs) / len(rs)
        type_rows.append(row)
    st.subheader("유형별 MRR")
    st.dataframe(pd.DataFrame(type_rows).set_index("type").style.format("{:.2f}", subset=[c for c in type_rows[0] if c not in ("type", "n")]), width="stretch")

    with st.expander("문항별 원본 결과"):
        st.dataframe(pd.DataFrame(results), width="stretch")

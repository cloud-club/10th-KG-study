"""청킹·검색·RAG·지식 그래프를 한 화면에서 비교하는 Streamlit 앱.

실행:
    cd members/ur2e/labs/01-worklog-search/src
    streamlit run app.py
"""

from __future__ import annotations

import json
import html
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable

import pandas as pd
import streamlit as st

from common import ES_INDEX, ES_URL, PG_TABLE, QUERIES_PATH
from evaluate import evaluate
from graph_retrieval import graph_evidence, merge_evidence
from hybrid_search import search_hybrid
from index_elasticsearch import index_chunks as index_es
from index_pgvector import index_chunks as index_pg
from knowledge_graph import graphviz_dot, load_graph, relevant_subgraph
from parse_vault import chunk_config_key, chunks_path_for, parse_vault, to_dicts, write_chunks
from rag_agent import DEFAULT_CHAT_MODEL, answer_question
from search_elasticsearch import search_bm25
from search_grep import search_grep
from search_pgvector import search_vector


st.set_page_config(page_title="Worklog Copilot", page_icon="✦", layout="wide")
st.markdown(
    """
    <style>
    .stApp {
        background:
          radial-gradient(circle at 12% 0%, rgba(45, 212, 191, .10), transparent 27rem),
          radial-gradient(circle at 90% 12%, rgba(99, 102, 241, .11), transparent 30rem),
          #0b1020;
    }
    [data-testid="stSidebar"] {
        background: rgba(10, 15, 30, .94);
        border-right: 1px solid rgba(148, 163, 184, .14);
    }
    .block-container {max-width: 1440px; padding-top: 2rem; padding-bottom: 4rem;}
    .hero {
        padding: 1.6rem 1.8rem;
        border: 1px solid rgba(148, 163, 184, .16);
        border-radius: 24px;
        background: linear-gradient(135deg, rgba(15, 23, 42, .92), rgba(30, 41, 59, .72));
        box-shadow: 0 18px 60px rgba(0, 0, 0, .20);
        margin-bottom: 1.2rem;
    }
    .hero-kicker {color: #5eead4; font-size: .78rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase;}
    .hero-title {font-size: 2rem; font-weight: 800; margin: .2rem 0 .3rem; color: #f8fafc;}
    .hero-copy {color: #a8b4c8; margin: 0; max-width: 760px; line-height: 1.65;}
    .status-pill {
        display: inline-block; padding: .22rem .55rem; border-radius: 999px;
        margin: .1rem .2rem .1rem 0; font-size: .76rem; font-weight: 700;
        background: rgba(45, 212, 191, .12); color: #5eead4; border: 1px solid rgba(45, 212, 191, .22);
    }
    .source-card {
        padding: .65rem .8rem; border-radius: 12px; margin: .35rem 0;
        background: rgba(30, 41, 59, .58); border: 1px solid rgba(148, 163, 184, .14);
        color: #cbd5e1; font-size: .86rem;
    }
    [data-testid="stChatMessage"] {
        border: 1px solid rgba(148, 163, 184, .12);
        border-radius: 18px;
        background: rgba(15, 23, 42, .62);
        padding: .5rem .75rem;
    }
    [data-baseweb="tab-list"] {gap: .4rem;}
    [data-baseweb="tab"] {border-radius: 12px 12px 0 0; padding-left: 1rem; padding-right: 1rem;}
    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, .58); border: 1px solid rgba(148, 163, 184, .12);
        padding: .75rem 1rem; border-radius: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <section class="hero">
      <div class="hero-kicker">Personal Knowledge Workspace</div>
      <div class="hero-title">✦ Worklog Copilot</div>
      <p class="hero-copy">옵시디언 작업기록에서 근거를 찾고, 출처와 함께 답합니다. 평소에는 챗봇으로 사용하고 필요할 때 검색·청킹·그래프 실험을 열어보세요.</p>
    </section>
    """,
    unsafe_allow_html=True,
)


def load_example_queries() -> list[dict[str, Any]]:
    try:
        return [
            json.loads(line)
            for line in QUERIES_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except FileNotFoundError:
        return []


@st.cache_data(ttl=5, show_spinner=False)
def elasticsearch_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{ES_URL}/_cluster/health", timeout=0.4):
            return True
    except (OSError, urllib.error.URLError):
        return False


def query_picker(label: str, key: str, default: str) -> str:
    examples = load_example_queries()
    options = ["(직접 입력)"] + [f"{item['id']} · {item['query']}" for item in examples]
    picked = st.selectbox(label, options, key=f"{key}_picker")
    if picked == "(직접 입력)":
        return st.text_input("질문", value=default, key=f"{key}_input")
    selected = examples[options.index(picked) - 1]
    st.caption(f"정답 문서: {', '.join(selected['expected_primary'])}")
    return selected["query"]


def unpack_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        if isinstance(row, tuple):
            document, score = row
            normalized.append({**document, "display_score": float(score)})
        else:
            normalized.append(row)
    return normalized


def render_results(name: str, rows: list[Any], elapsed: float) -> None:
    normalized = unpack_rows(rows)
    st.subheader(name)
    st.caption(f"{len(normalized)}건 · {elapsed:.1f}ms")
    if not normalized:
        st.info("검색 결과가 없습니다.")
        return
    for rank, item in enumerate(normalized, start=1):
        heading = f"#{item['heading']}" if item.get("heading") else ""
        if "rrf_score" in item:
            ranks = item.get("ranks", {})
            score_text = (
                f"RRF {item['rrf_score']:.6f} · "
                f"BM25 {ranks.get('bm25', '-')}위 · Vector {ranks.get('vector', '-')}위"
            )
        elif "display_score" in item:
            score_text = f"점수 {item['display_score']:.4f}"
        else:
            score_text = "문자열 일치"
        with st.expander(f"{rank}. {item['source_path']}{heading} · {score_text}"):
            st.write(item["content"])


def render_evidence_cards(evidence: list[dict[str, Any]]) -> None:
    for number, item in enumerate(evidence, start=1):
        heading = f"#{item['heading']}" if item.get("heading") else ""
        preview = " ".join(item["content"].split())[:220]
        source_label = html.escape(f"{item['source_path']}{heading}")
        safe_preview = html.escape(preview)
        st.markdown(
            f'<div class="source-card"><b>[C{number}] {source_label}</b><br>{safe_preview}</div>',
            unsafe_allow_html=True,
        )


st.sidebar.markdown("## ✦ Worklog Copilot")
st.sidebar.caption("내 작업기록을 검색하고 연결하는 개인 지식 도우미")
api_ready = bool(os.environ.get("OPENAI_API_KEY", "").strip())
api_status = "API 연결됨" if api_ready else "OPENAI_API_KEY 필요"
es_ready = elasticsearch_ready()
search_status = "BM25 준비됨" if es_ready else "검색 엔진 꺼짐"
st.sidebar.markdown(
    f'<span class="status-pill">26 documents</span><span class="status-pill">{api_status}</span>'
    f'<span class="status-pill">{search_status}</span>',
    unsafe_allow_html=True,
)
st.sidebar.divider()
st.sidebar.header("데이터 준비")
mode = st.sidebar.radio(
    "청크 방식",
    ["heading", "fixed"],
    format_func=lambda value: "## 소제목 단위" if value == "heading" else "고정 글자 수",
)
size = 800
overlap = 100
if mode == "fixed":
    size = st.sidebar.slider("청크 크기(글자)", 100, 2000, 800, 100)
    overlap = st.sidebar.slider("겹침(글자)", 0, min(500, size - 50), min(100, size - 50), 50)

config_key = chunk_config_key(mode, size, overlap)
index_name = f"{ES_INDEX}_{config_key}"
table_name = f"{PG_TABLE}_{config_key}"
st.sidebar.caption(f"설정 키: `{config_key}`")

include_vector = st.sidebar.checkbox(
    "pgvector 사용",
    value=False,
    help="색인 버튼을 누르면 OpenAI 임베딩 API를 호출하므로 비용이 발생합니다.",
)
rrf_k = st.sidebar.number_input("RRF k", min_value=0, max_value=200, value=60, step=10)
candidate_limit = st.sidebar.slider("각 검색의 RRF 후보 수", 5, 50, 20, 5)

if st.sidebar.button("청크 생성 + 색인", type="primary"):
    with st.spinner("청크 생성 중..."):
        raw_chunks = parse_vault(mode=mode, size=size, overlap=overlap)
        write_chunks(raw_chunks, chunks_path_for(mode, size, overlap))
        chunks = to_dicts(raw_chunks)
        st.session_state["chunks"] = chunks
        st.session_state["config_key"] = config_key

    try:
        count = index_es(chunks, index_name=index_name)
        st.sidebar.success(f"BM25 색인 완료: {count}청크")
    except Exception as error:  # noqa: BLE001
        st.sidebar.error(f"Elasticsearch 색인 실패: {error}")

    if include_vector:
        try:
            count = index_pg(chunks, table_name=table_name)
            st.sidebar.success(f"pgvector 색인 완료: {count}행")
        except Exception as error:  # noqa: BLE001
            st.sidebar.error(f"pgvector 색인 실패: {error}")

# 색인 전에도 청크 모양과 그래프는 볼 수 있다.
chunks = st.session_state.get("chunks")
if chunks is None or st.session_state.get("config_key") != config_key:
    chunks = to_dicts(parse_vault(mode=mode, size=size, overlap=overlap))

chat_tab, search_tab, chunk_tab, graph_tab, evaluation_tab = st.tabs(
    ["✦ 내 챗봇", "검색 비교", "청킹 실험실", "지식 그래프", "평가"]
)


with chunk_tab:
    st.header("청크가 실제로 어떻게 잘렸는지 확인")
    lengths = [len(chunk["content"]) for chunk in chunks]
    documents = sorted({chunk["source_path"] for chunk in chunks})
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("문서 수", len(documents))
    col2.metric("청크 수", len(chunks))
    col3.metric("평균 길이", f"{sum(lengths) / len(lengths):.0f}자")
    col4.metric("최소~최대", f"{min(lengths)}~{max(lengths)}자")

    selected_document = st.selectbox("원본 문서", documents)
    preview_chunks = [chunk for chunk in chunks if chunk["source_path"] == selected_document]
    st.caption(f"이 문서는 현재 설정에서 {len(preview_chunks)}개 청크로 나뉩니다.")
    for index, chunk in enumerate(preview_chunks, start=1):
        heading = chunk.get("heading") or "문서 전체"
        with st.expander(f"청크 {index} · {heading} · {len(chunk['content'])}자", expanded=index == 1):
            st.code(chunk["chunk_id"], language=None)
            st.write(chunk["content"])


with search_tab:
    st.header("같은 질문을 검색 방식별로 비교")
    query = query_picker(
        "평가 질문을 고르거나 직접 입력하세요.",
        "comparison",
        "이미지 레지스트리를 왜 하나로 안 합쳤지",
    )
    limit = st.slider("최종 결과 수", 1, 10, 5, key="comparison_limit")

    if st.button("네 방식으로 검색", key="comparison_run"):
        columns = st.columns(4)
        methods: list[tuple[str, Callable[[], tuple[list[Any], float]]]] = [
            ("grep", lambda: search_grep(query, limit=limit, chunks=chunks)),
            ("BM25", lambda: search_bm25(query, limit=limit, index_name=index_name)),
        ]
        if include_vector:
            methods.extend(
                [
                    ("Vector", lambda: search_vector(query, limit=limit, table_name=table_name)),
                    (
                        "Hybrid RRF",
                        lambda: search_hybrid(
                            query,
                            limit=limit,
                            candidate_limit=max(candidate_limit, limit),
                            rank_constant=int(rrf_k),
                            index_name=index_name,
                            table_name=table_name,
                        ),
                    ),
                ]
            )

        for column, (name, search_fn) in zip(columns, methods):
            with column:
                try:
                    rows, elapsed = search_fn()
                    render_results(name, rows, elapsed)
                except Exception as error:  # noqa: BLE001
                    st.subheader(name)
                    st.error(str(error))
        if not include_vector:
            columns[2].info("사이드바에서 pgvector를 켜면 Vector 결과가 표시됩니다.")
            columns[3].info("Hybrid RRF는 BM25와 Vector가 모두 필요합니다.")


with chat_tab:
    header_col, settings_col = st.columns([3, 1])
    with header_col:
        st.header("내 작업기록에 물어보기")
        st.caption("답변의 [C#]를 펼치면 실제로 사용한 옵시디언 청크를 확인할 수 있습니다.")
    with settings_col:
        if st.button("대화 지우기", use_container_width=True):
            st.session_state["chat_messages"] = []
            st.rerun()

    mode_options = ["BM25", "Graph"] if es_ready else ["Graph", "BM25"]
    if include_vector:
        mode_options.extend(["Vector", "Hybrid RRF", "Hybrid + Graph"])
    option_col, evidence_col, model_col = st.columns([1.3, 1, 1.4])
    with option_col:
        retrieval_mode = st.selectbox("검색 모드", mode_options, index=0)
    with evidence_col:
        evidence_limit = st.select_slider("근거 수", options=[3, 4, 5, 6, 8], value=5)
    with model_col:
        chat_model = st.text_input("답변 모델", value=DEFAULT_CHAT_MODEL)

    if not include_vector:
        st.info("Vector와 Hybrid를 사용하려면 사이드바에서 **pgvector 사용**을 켜고 청크를 색인하세요. BM25와 Graph는 그대로 사용할 수 있습니다.")
    if not es_ready:
        st.warning("현재 Elasticsearch가 꺼져 있어 Graph 모드를 기본으로 선택했습니다. BM25/Hybrid를 쓰려면 Docker를 실행하고 사이드바에서 색인하세요.")

    st.markdown("##### 이런 질문으로 시작해보세요")
    quick_questions = [
        "인증서 갱신 후 어떤 검증을 해야 하지?",
        "이미지 레지스트리를 왜 하나로 안 합쳤지?",
        "인증서 만료 장애 이후 남은 후속 작업은 뭐였지?",
    ]
    quick_columns = st.columns(3)
    quick_prompt = None
    for column, question in zip(quick_columns, quick_questions):
        with column:
            if st.button(question, use_container_width=True, key=f"quick_{question}"):
                quick_prompt = question

    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = []

    if not st.session_state["chat_messages"]:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(
                "안녕하세요. 장애 대응, 작업 절차, 운영 결정처럼 **예전에 기록한 내용을 근거와 함께** 찾아드릴게요."
            )

    for message in st.session_state["chat_messages"]:
        avatar = "🤖" if message["role"] == "assistant" else "🙂"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])
            if message.get("evidence"):
                with st.expander(f"사용한 근거 {len(message['evidence'])}개"):
                    render_evidence_cards(message["evidence"])
            if message.get("meta"):
                st.caption(message["meta"])

    typed_prompt = st.chat_input("예: 인증서 장애 때 어떤 조치와 검증을 했지?")
    prompt = typed_prompt or quick_prompt
    if prompt:
        st.session_state["chat_messages"].append({"role": "user", "content": prompt})
        started = time.perf_counter()
        try:
            if retrieval_mode == "BM25":
                raw_rows, _ = search_bm25(prompt, evidence_limit, index_name=index_name)
                evidence = unpack_rows(raw_rows)
            elif retrieval_mode == "Vector":
                raw_rows, _ = search_vector(prompt, evidence_limit, table_name=table_name)
                evidence = unpack_rows(raw_rows)
            elif retrieval_mode == "Graph":
                evidence = graph_evidence(prompt, load_graph(), chunks, limit=evidence_limit)
            elif retrieval_mode == "Hybrid RRF":
                raw_rows, _ = search_hybrid(
                    prompt,
                    limit=evidence_limit,
                    candidate_limit=max(candidate_limit, evidence_limit),
                    rank_constant=int(rrf_k),
                    index_name=index_name,
                    table_name=table_name,
                )
                evidence = unpack_rows(raw_rows)
            else:
                raw_rows, _ = search_hybrid(
                    prompt,
                    limit=evidence_limit,
                    candidate_limit=max(candidate_limit, evidence_limit),
                    rank_constant=int(rrf_k),
                    index_name=index_name,
                    table_name=table_name,
                )
                hybrid_evidence = unpack_rows(raw_rows)
                local_graph_evidence = graph_evidence(prompt, load_graph(), chunks, limit=evidence_limit)
                evidence = merge_evidence(hybrid_evidence, local_graph_evidence, evidence_limit)

            answer = answer_question(prompt, evidence, model=chat_model)
            elapsed = (time.perf_counter() - started) * 1000
            st.session_state["chat_messages"].append(
                {
                    "role": "assistant",
                    "content": answer,
                    "evidence": evidence,
                    "meta": f"{retrieval_mode} · 근거 {len(evidence)}개 · {elapsed:.0f}ms",
                }
            )
        except Exception as error:  # noqa: BLE001
            st.session_state["chat_messages"].append(
                {
                    "role": "assistant",
                    "content": f"지금은 답변을 만들지 못했어요. `{error}`",
                    "meta": "사이드바의 색인 상태와 OPENAI_API_KEY를 확인해 주세요.",
                }
            )
        st.rerun()


with graph_tab:
    st.header("작업기록 지식 그래프 v1")
    st.caption("빨강=장애, 파랑=시스템, 노랑=원인, 초록=조치, 보라=결정, 분홍=할 일, 회색=근거 문서")
    graph = load_graph()
    graph_query = st.text_input(
        "그래프에서 찾을 개념",
        value="인증서 만료 장애의 조치와 검증",
        help="라벨·설명과 겹치는 노드를 찾고 1-hop 이웃까지 표시합니다.",
    )
    visible_graph = relevant_subgraph(graph, graph_query)
    if not visible_graph["nodes"]:
        st.warning("질문과 겹치는 그래프 노드가 없습니다.")
    else:
        st.graphviz_chart(graphviz_dot(visible_graph), width="stretch")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("노드")
            st.dataframe(
                pd.DataFrame(visible_graph["nodes"])[["type", "label", "description"]],
                hide_index=True,
                width="stretch",
            )
        with col2:
            st.subheader("엣지와 근거")
            st.dataframe(pd.DataFrame(visible_graph["edges"]), hide_index=True, width="stretch")
    st.info("이 화면은 그래프 설계 검증용입니다. 다음 단계에서 Graph 검색 결과를 챗봇 근거로 합칩니다.")


with evaluation_tab:
    st.header("검색과 RAG 답변을 따로 평가")
    st.caption("검색기는 Hit@3·MRR로, 생성 답변은 RAGAS 관점으로 나눠서 봅니다.")
    ragas_tab, retrieval_tab = st.tabs(["RAGAS 답변 평가", "19문항 검색 평가"])

    with ragas_tab:
        st.subheader("같은 답변을 세 방향에서 확인")
        metric_columns = st.columns(3)
        with metric_columns[0]:
            st.metric("Context Recall", "검색 누락 확인")
            st.caption("기준 정답 ↔ 검색 문맥")
            st.write("답에 필요한 정보를 검색기가 빠뜨리지 않았는지 봅니다.")
        with metric_columns[1]:
            st.metric("Faithfulness", "근거 이탈 확인")
            st.caption("생성 답변 ↔ 검색 문맥")
            st.write("답변의 각 주장이 가져온 근거로 뒷받침되는지 봅니다.")
        with metric_columns[2]:
            st.metric("Factual Correctness", "정답 일치 확인")
            st.caption("생성 답변 ↔ 기준 정답")
            st.write("답변이 기준 정답의 사실을 맞게 포함했는지 봅니다.")

        st.markdown(
            """
            ```text
            질문 ──▶ 검색 문맥 ──▶ 생성 답변
              │          │             │
              └─ 기준 정답(reference) ─┘

            Context Recall      : 기준 정답 ↔ 검색 문맥
            Faithfulness        : 생성 답변 ↔ 검색 문맥
            Factual Correctness : 생성 답변 ↔ 기준 정답
            ```
            """
        )

        examples = load_example_queries()
        selected_label = st.selectbox(
            "평가 데이터 한 건 살펴보기",
            [f"{item['id']} · {item['query']}" for item in examples],
            key="ragas_example",
        )
        selected = examples[[f"{item['id']} · {item['query']}" for item in examples].index(selected_label)]
        reference = "\n".join(f"- {point}" for point in selected["answer_points"])
        expected_documents = [*selected["expected_primary"], *selected["expected_supporting"]]

        sample_columns = st.columns(2)
        with sample_columns[0]:
            st.markdown("##### `user_input`")
            st.info(selected["query"])
            st.markdown("##### `reference` — 기준 정답")
            st.markdown(reference)
        with sample_columns[1]:
            st.markdown("##### 정답 근거 문서")
            for path in expected_documents:
                st.code(path, language=None)
            st.markdown("##### 실행할 때 채워지는 값")
            st.write("`retrieved_contexts`: 선택한 검색 모드가 반환한 원문 청크")
            st.write("`response`: Worklog Copilot이 근거를 바탕으로 만든 답변")

        st.info(
            "현재 화면은 RAGAS 평가 데이터와 지표를 검증하는 단계입니다. "
            "실제 RAGAS 점수는 평가용 LLM을 여러 번 호출하므로 자동 실행하지 않습니다."
        )

    with retrieval_tab:
        st.subheader("19문항 전체 검색 평가")
        st.caption("같은 질문셋으로 Hit@3과 MRR을 비교합니다. Hybrid는 pgvector를 켰을 때 포함됩니다.")
        if st.button("전체 평가 실행"):
            methods = ("grep", "bm25", "vector", "hybrid") if include_vector else ("grep", "bm25")
            query_count = len(load_example_queries())
            progress = st.progress(0.0, text="시작...")
            state = {"done": 0}

            def on_progress(item: dict[str, Any]) -> None:
                state["done"] += 1
                progress.progress(state["done"] / query_count, text=f"{item['id']} 처리 중...")

            started = time.perf_counter()
            results = evaluate(
                chunks=chunks,
                index_name=index_name,
                table_name=table_name,
                methods=methods,
                on_progress=on_progress,
                hybrid_candidate_limit=int(candidate_limit),
                hybrid_rank_constant=int(rrf_k),
            )
            progress.empty()
            st.caption(f"{len(results)}문항 · {time.perf_counter() - started:.1f}초")

            summary_rows = []
            for method in methods:
                count = len(results)
                summary_rows.append(
                    {
                        "방식": method,
                        "Hit@3": sum(row[f"{method}_hit@3"] for row in results) / count,
                        "MRR": sum(row[f"{method}_mrr"] for row in results) / count,
                    }
                )
            st.dataframe(
                pd.DataFrame(summary_rows).set_index("방식").style.format("{:.2f}"),
                width="stretch",
            )
            with st.expander("문항별 결과"):
                st.dataframe(pd.DataFrame(results), width="stretch")

"""기존 그래프에 앱 성과 분석 에이전트의 설계 추가."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

PREFIX = "analytics-design:"
LABELS = {"Workspace", "Project", "AnalystAgent", "DataTool", "MetricDefinition", "AnalysisRule", "Workflow", "ReportDesign", "DataRequirement"}
RELATIONS = {"HAS_PROJECT", "PLANS_ANALYTICS_ASSISTANT", "PLANS_TO_QUERY", "PLANS_TO_TRACK", "PLANS_TO_RUN", "PLANS_TO_PRODUCE", "PLANS_TO_USE", "PLANS_TO_READ_FROM", "REQUIRES_SOURCE", "PLANS_TO_ENFORCE"}


def design():
    nodes, edges = [], []

    def node(key, label, name, **props):
        nodes.append({"id": PREFIX + key, "label": label, "name": name, **props})
        return key

    def edge(source, relation, target):
        edges.append({"source": PREFIX + source, "relation": relation, "target": PREFIX + target})

    node("workspace", "Workspace", "내 작업 공간", description="콘텐츠 계정과 앱 운영 프로젝트를 분리해 연결하는 공통 작업 공간")
    node("app-project", "Project", "앱 운영 프로젝트", name_status="unspecified", description="실제 앱 이름 미확정; 기존 다른 앱 프로젝트와 구분")
    node("agent", "AnalystAgent", "앱 광고·구독 성과 분석 에이전트", status="planned", access_status="not_configured", description="도구에서 최신 수치를 조회하고 그래프의 정의·규칙으로 해석하는 설계")
    edge("workspace", "HAS_PROJECT", "app-project")
    edge("app-project", "PLANS_ANALYTICS_ASSISTANT", "agent")
    tools = [
        ("ga4", "GA4", "유입·앱 이벤트 조회 후보"),
        ("amplitude", "Amplitude", "퍼널·코호트·리텐션 조회 후보"),
        ("admob", "Google AdMob", "앱 내부 광고 수익 조회 후보"),
        ("revenuecat", "RevenueCat", "체험·구독·유료 전환 조회 후보"),
        ("firebase", "Firebase", "앱 이벤트·설정 조회 후보; GA4와 중복 집계 방지"),
        ("cloudflare", "Cloudflare Analytics", "웹·서비스 트래픽, 요청·오류·성능 조회 후보; 활성화된 제품의 범위 확인 필요"),
        ("supabase", "Supabase", "앱 DB·인증 사용자·제품 상태 조회 후보; 실제 스키마 확인 필요"),
    ]
    for key, name, role in tools:
        node(key, "DataTool", name, role=role, integration_status="not_configured")
        edge("agent", "PLANS_TO_QUERY", key)
    node("acquisition-source", "DataRequirement", "광고 집행 매체 확인 필요", description="광고비·노출·클릭·광고 설치의 출처. AdMob 앱 광고 수익과 구분", status="unresolved")
    edge("agent", "REQUIRES_SOURCE", "acquisition-source")

    metrics = [
        ("cpi", "CPI", "광고비 / 매체가 집계한 광고 설치 수", "acquisition-source"),
        ("cpm", "CPM", "광고비 / 광고 노출 수 × 1000", "acquisition-source"),
        ("ctr", "CTR", "광고 클릭 수 / 광고 노출 수", "acquisition-source"),
        ("cpc", "CPC", "광고비 / 광고 클릭 수", "acquisition-source"),
        ("first-open", "신규 사용자·첫 실행", "집계 기간 내 최초 실행 사용자 수; 자연 유입 포함 여부를 명시", "ga4"),
        ("onboarding", "온보딩 퍼널", "첫 실행 → 회원가입 → 온보딩 완료 → 첫 기능; 각 단계 고유 사용자 기준", "amplitude"),
        ("d1", "D1 리텐션", "기준 이벤트 코호트 중 N-day D1 재방문 사용자 비율; 가입과 첫 실행 기준을 구분", "amplitude"),
        ("paid", "첫 유료 결제율", "첫 실행 코호트의 24시간 내 첫 유료 결제 사용자 / 동일 코호트 첫 실행 사용자", "revenuecat"),
        ("trial", "무료 체험 시작", "체험 시작 사용자 수; 유료 결제 수와 별도 집계", "revenuecat"),
        ("ad-revenue", "앱 내부 광고 수익", "보고 기간의 AdMob 광고 수익; 통화·시간대 명시", "admob"),
    ]
    for key, name, definition, source in metrics:
        node(key, "MetricDefinition", name, definition=definition,
             aggregation_dimensions=["기간", "국가", "OS"], definition_status="proposed", event_mapping_status="not_configured")
        edge("agent", "PLANS_TO_TRACK", key)
        edge(key, "REQUIRES_SOURCE" if source == "acquisition-source" else "PLANS_TO_READ_FROM", source)

    rules = [
        ("trial-rule", "체험과 유료 결제 구분", "무료 체험 시작은 첫 유료 결제로 계산하지 않는다"),
        ("cohort-rule", "24시간 관측 완료 코호트", "24시간 미경과 사용자는 최종 24시간 전환율에서 제외하거나 잠정값으로 표시한다"),
        ("freshness-rule", "출처·갱신 시각·표본 표시", "출처, 조회 시각, 기간, 시간대, 표본 수를 보고서에 표시한다"),
        ("identity-rule", "사용자 식별·중복 집계 구분", "광고 설치와 첫 실행을 혼용하지 않는다. GA4·Firebase 동일 이벤트를 중복 합산하지 않는다. Supabase 사용자와 도구별 ID 연결 기준을 확인한다"),
        ("cause-rule", "관측과 개선 가설 구분", "변화만으로 원인을 확정하지 않고 개선 제안에 근거와 검증 방법을 붙인다"),
    ]
    for key, name, description in rules:
        node(key, "AnalysisRule", name, description=description)
        edge("agent", "PLANS_TO_ENFORCE", key)
    node("daily", "Workflow", "하루 1회 조회·검증·분석", cadence="daily", timezone="Asia/Seoul", scheduling_status="not_configured")
    node("report", "ReportDesign", "일일 성과·개선 보고서", sections=["주요 변화", "데이터 이상", "개선 가설과 검증 방법", "이전 실험 후속 확인"], storage_policy="보고서·판단 이력은 보존; 최신 수치 조회는 원본 도구")
    edge("agent", "PLANS_TO_RUN", "daily")
    edge("daily", "PLANS_TO_PRODUCE", "report")
    for key, _, _ in tools:
        edge("daily", "PLANS_TO_USE", key)
    return nodes, edges


def load(tx, nodes, edges):
    for item in nodes:
        label = item["label"]
        if label not in LABELS:
            raise ValueError(label)
        props = {k: v for k, v in item.items() if k != "label"}
        props.update(display_name=item["name"], provenance="user_requested_design", design_status="planned")
        tx.run(f"MERGE (n:AnalyticsDesign:{label} {{id: $id}}) ON CREATE SET n += $props", id=item["id"], props=props).consume()
    for item in edges:
        relation = item["relation"]
        if relation not in RELATIONS:
            raise ValueError(relation)
        tx.run(f"MATCH (s:AnalyticsDesign {{id: $source}}), (t:AnalyticsDesign {{id: $target}}) MERGE (s)-[r:{relation}]->(t) ON CREATE SET r.design_status = 'planned'", **item).consume()
    tx.run("""MATCH (p:Profile {id: 'junyounge'})-[r:PLANS_ANALYTICS_ASSISTANT]->(a:AnalyticsDesign {id: $agent})
        WHERE r.provenance = 'user_requested_design'
        DELETE r""", agent=PREFIX + "agent").consume()
    tx.run("""MATCH (w:AnalyticsDesign:Workspace {id: $workspace}), (p:Profile {id: 'junyounge'})
        MERGE (w)-[r:HAS_ACCOUNT]->(p)
        ON CREATE SET r.provenance = 'user_requested_design'""", workspace=PREFIX + "workspace").consume()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="DB 접속 없이 설계를 표시")
    args = parser.parse_args()
    nodes, edges = design()
    if args.preview:
        print(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=2))
        return
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        parser.error("NEO4J_PASSWORD 환경 변수가 필요합니다.")
    from neo4j import GraphDatabase
    with GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"), auth=(os.environ.get("NEO4J_USER", "neo4j"), password)) as driver:
        with driver.session(database=os.environ.get("NEO4J_DATABASE")) as session:
            session.execute_write(load, nodes, edges)
            count = session.run("MATCH (n:AnalyticsDesign) WHERE n.id STARTS WITH $prefix RETURN count(n) AS nodes", prefix=PREFIX).single()["nodes"]
            relations = session.run("MATCH (n:AnalyticsDesign)-[r]->() WHERE n.id STARTS WITH $prefix RETURN count(r) AS relations", prefix=PREFIX).single()["relations"]
            print(json.dumps({"design_nodes": count, "outgoing_design_relationships": relations, "metric_observations_added": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()

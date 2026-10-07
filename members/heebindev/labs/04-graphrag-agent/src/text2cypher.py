import argparse
import json
import re

from common import neo4j_query, openai_response, response_text


SCHEMA = """노드: (:Entity {id, name, kind})
관계: IS_A, USES, MANAGES, HAS_STATE, TRANSITIONS_TO, SCHEDULED_BY, REQUIRES, PREVENTS
관계 속성: evidence(문자열 목록), chunk_ids(문자열 목록)"""

FORBIDDEN = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|LOAD\s+CSV|CALL|FOREACH|USE|ALTER|GRANT|DENY|REVOKE)\b",
    re.IGNORECASE,
)


def generate_cypher(question: str, model: str) -> tuple[str, str]:
    prompt = f"""아래 Neo4j 스키마만 사용해 사용자의 질문을 읽기 전용 Cypher로 바꾸세요.

{SCHEMA}

규칙:
- MATCH, OPTIONAL MATCH, WITH, WHERE, RETURN, ORDER BY, LIMIT만 사용합니다.
- 존재하지 않는 라벨, 관계, 속성을 만들지 않습니다.
- 결과는 최대 50개로 제한합니다.

예시 1
질문: SJF와 직접 연결된 엔티티는?
Cypher: MATCH (s:Entity {{name: 'SJF'}})-[r]-(o:Entity) RETURN s.name AS subject, type(r) AS relation, o.name AS object LIMIT 50

예시 2
질문: 관계가 가장 많은 엔티티는?
Cypher: MATCH (e:Entity)-[r]-() RETURN e.name AS entity, count(r) AS relation_count ORDER BY relation_count DESC LIMIT 10

사용자 질문: {question}
"""
    response = openai_response(
        {
            "model": model,
            "reasoning": {"effort": "minimal"},
            "max_output_tokens": 2000,
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "cypher_query",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "cypher": {"type": "string"},
                            "explanation": {"type": "string"},
                        },
                        "required": ["cypher", "explanation"],
                        "additionalProperties": False,
                    },
                }
            },
        }
    )
    result = json.loads(response_text(response))
    return result["cypher"].strip(), result["explanation"].strip()


def validate_read_only(cypher: str) -> str:
    cleaned = cypher.strip().strip("`").strip()
    if ";" in cleaned.rstrip(";"):
        raise ValueError("여러 Cypher 문장을 한 번에 실행할 수 없습니다.")
    cleaned = cleaned.rstrip(";").strip()
    if FORBIDDEN.search(cleaned):
        raise ValueError("데이터를 변경할 수 있는 Cypher가 포함되어 실행을 막았습니다.")
    if not re.match(r"^(MATCH|OPTIONAL\s+MATCH)\b", cleaned, re.IGNORECASE):
        raise ValueError("MATCH 또는 OPTIONAL MATCH로 시작하는 읽기 질의만 허용합니다.")
    if not re.search(r"\bRETURN\b", cleaned, re.IGNORECASE):
        raise ValueError("RETURN이 없는 질의는 실행하지 않습니다.")
    if not re.search(r"\bLIMIT\b", cleaned, re.IGNORECASE):
        cleaned += " LIMIT 50"
    return cleaned


def main():
    parser = argparse.ArgumentParser(description="자연어 질문을 읽기 전용 Cypher로 변환")
    parser.add_argument("question")
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--dry-run", action="store_true", help="스키마만 확인하고 API를 호출하지 않음")
    parser.add_argument("--generate-only", action="store_true", help="Cypher를 만들되 Neo4j에서 실행하지 않음")
    args = parser.parse_args()

    if args.dry_run:
        print("LLM에 주입할 Neo4j 스키마:\n")
        print(SCHEMA)
        print("\n--dry-run: OpenAI API와 Neo4j를 호출하지 않았습니다.")
        return

    cypher, explanation = generate_cypher(args.question, args.model)
    safe_cypher = validate_read_only(cypher)
    print(f"생성된 Cypher:\n{safe_cypher}\n")
    print(f"설명: {explanation}")
    if args.generate_only:
        print("\n--generate-only: Neo4j에서는 실행하지 않았습니다.")
        return

    rows = neo4j_query(safe_cypher)
    print(f"\n실행 결과 ({len(rows)}행):")
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

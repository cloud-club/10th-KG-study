-- 카카오톡 대화 적재용 스키마. 여러 번 실행해도 안전합니다 (IF NOT EXISTS / OR REPLACE).
-- 실행: ingest.py 가 자동으로 적용. 수동은 docker compose exec -T postgres psql -U kg -d kg < schema.sql

CREATE SCHEMA IF NOT EXISTS kakao;

-- 채팅방 하나 = 내보내기 파일 하나. 같은 파일을 다시 넣으면 갱신됩니다.
CREATE TABLE IF NOT EXISTS kakao.rooms (
  id            serial       PRIMARY KEY,
  name          text         NOT NULL,                  -- 첫 줄 "<이름> 카카오톡 대화"
  source_file   text         NOT NULL UNIQUE,           -- 파일명 (재적재 키)
  exported_at   timestamp,                              -- "저장한 날짜", KST
  message_count integer      NOT NULL DEFAULT 0,
  imported_at   timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kakao.messages (
  id       bigserial PRIMARY KEY,
  room_id  integer   NOT NULL REFERENCES kakao.rooms(id) ON DELETE CASCADE,
  seq      integer   NOT NULL,   -- 파일 안 순서 (같은 분 안의 순서 보존)
  line_no  integer   NOT NULL,   -- 원본 txt 줄 번호 (디버깅용)
  sent_at  timestamp NOT NULL,   -- KST, 분 단위 (내보내기에 초가 없음)
  sender   text,                 -- NULL 이면 시스템 이벤트 (입장/퇴장/초대)
  kind     text      NOT NULL,   -- text | photo | video | voice | emoticon | file | deleted | shop | link | system_*
  content  text      NOT NULL,   -- 여러 줄이면 \n 로 이어짐
  UNIQUE (room_id, seq)
);

CREATE INDEX IF NOT EXISTS messages_room_sent_idx   ON kakao.messages (room_id, sent_at);
CREATE INDEX IF NOT EXISTS messages_room_sender_idx ON kakao.messages (room_id, sender);
CREATE INDEX IF NOT EXISTS messages_room_kind_idx   ON kakao.messages (room_id, kind);
-- pg_trgm: ILIKE '%단어%' 가속 (infra/postgres/init/01-extensions.sql 에서 확장 생성됨)
CREATE INDEX IF NOT EXISTS messages_content_trgm_idx ON kakao.messages USING gin (content gin_trgm_ops);

-- 누가 얼마나 말했나
CREATE OR REPLACE VIEW kakao.sender_stats AS
SELECT r.name AS room, m.sender,
       count(*)                                  AS messages,
       count(*) FILTER (WHERE m.kind = 'text')   AS text_messages,
       min(m.sent_at)                            AS first_at,
       max(m.sent_at)                            AS last_at
FROM kakao.messages m
JOIN kakao.rooms r ON r.id = m.room_id
WHERE m.sender IS NOT NULL
GROUP BY r.name, m.sender;

-- 날짜별 메시지 수 (활동 히트맵용)
CREATE OR REPLACE VIEW kakao.daily_counts AS
SELECT r.name AS room, m.sent_at::date AS day, count(*) AS messages
FROM kakao.messages m
JOIN kakao.rooms r ON r.id = m.room_id
GROUP BY r.name, m.sent_at::date;

"""KG_TEST_DSN 지정 시 별도 임시 스키마에서만 실행하는 통합 테스트."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import merge_uses as m
import store_kg


@unittest.skipUnless(os.environ.get('KG_TEST_DSN'),'KG_TEST_DSN 미설정')
class PostgresIntegration(unittest.TestCase):
    def test_apply_idempotency_unmerge_and_changed_db_guard(self):
        import psycopg
        from psycopg import sql
        dsn=os.environ['KG_TEST_DSN']
        name='kg_merge_test_'+uuid.uuid4().hex
        with psycopg.connect(dsn,autocommit=True) as admin:
            original=m.snapshot(admin)
            admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
            try:
                with psycopg.connect(dsn) as conn, tempfile.TemporaryDirectory() as directory:
                    conn.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(name)))
                    conn.execute('CREATE TABLE chunks(chunk_id TEXT PRIMARY KEY)')
                    for statement in store_kg.SCHEMA_SQL.split(';'):
                        if statement.strip(): conn.execute(statement)
                    with conn.cursor() as cursor:
                        cursor.executemany('INSERT INTO chunks VALUES (%s)',[(id_,) for id_ in sorted({e['chunk_id'] for e in original['edges']})])
                    m.restore(conn,original); conn.commit()
                    before=m.snapshot(conn); conn.commit()
                    group=next(g for g in m.candidates(before) if g['blocking']['project']=='kg:teamficial' and g['blocking']['technology']=='kg:tech-redis' and g['blocking']['status']=='implemented')
                    ids=sorted(n['entity_id'] for n in group['nodes'] if n['purpose'] is not None)[:2]
                    nodes={n['entity_id']:n for n in group['nodes']}
                    plan={'source_hash':m.digest(before),'needs_review':[], 'merges':[{
                        'canonical_use_id':ids[0],'merged_use_ids':ids[1:],
                        'purpose':nodes[ids[0]]['purpose'],'pair_judgments':[{
                            'pair':ids,'decision':'same','reason':'임시 스키마 테스트 fixture'}]}]}
                    out=Path(directory); run='merge-v1-2026-10-06'
                    with contextlib.redirect_stdout(io.StringIO()):
                        m.apply(conn,plan,run,out)
                        after=m.snapshot(conn); conn.commit()
                        self.assertEqual(len(before['entities'])-len(after['entities']),1)
                        m.apply(conn,plan,run,out)
                        self.assertEqual(m.digest(m.snapshot(conn)),m.digest(after)); conn.commit()
                        followup={'source_hash':m.digest(after),'needs_review':[], 'merges':[],
                                  'dropped_edges':[dict(after['edges'][0],edge_id=after['edges'][0]['id'],reason='후속 run 복원 테스트')]}
                        next_run='merge-v2-2026-10-07'
                        m.apply(conn,followup,next_run,out)
                        with self.assertRaises(ValueError): m.apply(conn,plan,run,out,undo=True)
                        conn.rollback()
                        m.apply(conn,followup,next_run,out,undo=True)
                        self.assertEqual(m.digest(m.snapshot(conn)),m.digest(after)); conn.commit()
                        conn.execute("UPDATE entities SET label=label||' changed' WHERE entity_id=%s",(ids[0],)); conn.commit()
                        with self.assertRaises(ValueError): m.apply(conn,plan,run,out,undo=True)
                        conn.rollback()
                        m.restore(conn,after); conn.commit()
                        m.apply(conn,plan,run,out,undo=True)
                        self.assertEqual(m.digest(m.snapshot(conn)),m.digest(before)); conn.commit()
                        m.apply(conn,plan,run,out,undo=True)
                self.assertEqual(m.digest(m.snapshot(admin)),m.digest(original))
            finally:
                admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(name)))


if __name__=='__main__': unittest.main()

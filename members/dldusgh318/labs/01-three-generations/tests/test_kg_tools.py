"""MCP 도구 로직의 오프라인 테스트. DB·모델 없이 돈다."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import kg_tools as k

TECHS = [{'entity_id': i, 'label': l} for i, l in [
    ('kg:tech-redis', 'redis'), ('kg:tech-spring-data-redis', 'spring data redis'),
    ('kg:tech-prometheus', 'prometheus'), ('kg:tech-peurometeuseu', '프로메테우스'),
    ('kg:tech-spring-boot', 'spring boot'), ('kg:tech-docker', 'docker')]]


class NormalizeTechnologyTests(unittest.TestCase):
    def ids(self, name):
        return [m['id'] for m in k.normalize_technology(name, TECHS)['matched']]

    def test_aliases_map_to_one_node(self):
        for name in ('redis', 'Redis', ' REDIS ', '레디스', 'kg:tech-redis'):
            self.assertEqual(self.ids(name), ['kg:tech-redis'], name)

    def test_related_nodes_are_reported_not_merged(self):
        result = k.normalize_technology('레디스', TECHS)
        self.assertEqual([m['id'] for m in result['related_not_merged']], ['kg:tech-spring-data-redis'])

    def test_korean_label_node_grouped_with_english(self):
        self.assertEqual(sorted(self.ids('프로메테우스')), ['kg:tech-peurometeuseu', 'kg:tech-prometheus'])
        self.assertEqual(sorted(self.ids('prometheus')), ['kg:tech-peurometeuseu', 'kg:tech-prometheus'])

    def test_spacing_variants(self):
        self.assertEqual(self.ids('스프링 부트'), ['kg:tech-spring-boot'])
        self.assertEqual(self.ids('Spring-Boot'), ['kg:tech-spring-boot'])

    def test_unknown_name_is_not_guessed(self):
        self.assertEqual(self.ids('엘라스틱서치'), [])

    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            k.normalize_technology('  ', TECHS)


class NormalizeProjectTests(unittest.TestCase):
    def test_korean_and_english_names(self):
        self.assertEqual(k.normalize_project('팀피셜'), 'kg:teamficial')
        self.assertEqual(k.normalize_project('TEAMFICIAL'), 'kg:teamficial')
        self.assertEqual(k.normalize_project('SeCause'), 'kg:secause')
        self.assertEqual(k.normalize_project('kg:moandi'), 'kg:moandi')
        self.assertIsNone(k.normalize_project(None))

    def test_unknown_project_rejected(self):
        with self.assertRaises(ValueError):
            k.normalize_project('없는프로젝트')


class RunCypherGuardTests(unittest.TestCase):
    """정적 검사에서 막히는 쿼리는 Neo4j에 접속하지 않아야 한다."""

    def setUp(self):
        k._driver.cache_clear()
        self._driver = k._driver
        k._driver = lambda: self.fail('정적 검사 단계에서 DB에 접속하면 안 된다')

    def tearDown(self):
        k._driver = self._driver

    def test_writes_and_procedures_blocked_before_db(self):
        for query in ('MATCH (n) DETACH DELETE n', 'CREATE (n:X)', 'MATCH (n) SET n.x=1',
                      'CALL db.labels()', 'LOAD CSV FROM "file:///x" AS r RETURN r',
                      'MATCH (n) RETURN n // 주석', 'MATCH (n) RETURN n; MATCH (m) RETURN m',
                      'MATCH (u) RETURN u.id AS use'):
            result = k.run_cypher(query)
            self.assertFalse(result['ok'], query)

    def test_empty_and_oversized_queries(self):
        self.assertFalse(k.run_cypher('   ')['ok'])
        self.assertFalse(k.run_cypher("MATCH (n) WHERE n.id = '" + 'a' * k.MAX_CYPHER_CHARS + "' RETURN n")['ok'])


if __name__ == '__main__':
    unittest.main()

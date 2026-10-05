import importlib.util
import sys
import unittest
from pathlib import Path


def _load(module_name: str):
    module_path = Path(__file__).parents[1] / "src" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


embed_ollama = _load("embed_ollama")


class ToPgvectorLiteralTest(unittest.TestCase):
    def test_formats_as_bracketed_comma_separated_floats(self):
        # 파이썬 숫자 목록을 pgvector가 읽는 문자열 형식으로 바꾼다.
        literal = embed_ollama.to_pgvector_literal([0.1, -0.52, 0.81])

        self.assertEqual("[0.1,-0.52,0.81]", literal)

    def test_empty_vector_is_empty_brackets(self):
        # 빈 목록도 같은 대괄호 형식을 유지한다.
        self.assertEqual("[]", embed_ollama.to_pgvector_literal([]))


if __name__ == "__main__":
    unittest.main()

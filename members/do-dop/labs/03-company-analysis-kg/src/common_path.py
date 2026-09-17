"""직접 실행한 스크립트에서도 공통 검색 모듈을 불러오게 한다."""

import sys
from pathlib import Path


DO_DOP_ROOT = Path(__file__).resolve().parents[3]
if str(DO_DOP_ROOT) not in sys.path:
    sys.path.insert(0, str(DO_DOP_ROOT))


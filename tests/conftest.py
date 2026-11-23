import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The runtime modules register their classes at import time and therefore need
# the platform's ``socioverse`` package to import at all. The stub supplies only
# ABC bases, the register decorator and schema containers; every behaviour under
# test is the real code in ``asch/``. It must be installed at collection time,
# not in a fixture, because test modules import ``asch.*`` during collection.
sys.path.insert(0, str(ROOT / "scripts"))
from commshim import install  # noqa: E402

install()


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def stimulus_root() -> Path:
    return ROOT
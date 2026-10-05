import pytest
from evaluation_platform.service import Platform
from evaluation_platform.connectors.phoenix import PhoenixConnector


class UnitJudge:
    """Explicit test double only; actual model is required by the separately marked E2E suite."""
    def assess(self, criteria, question, answer, reference):
        return 0.9, "unit-test-double", {"backend": "unit-test-double"}


@pytest.fixture
def platform(tmp_path):
    p = Platform(tmp_path, phoenix=PhoenixConnector(enabled=False), judge=UnitJudge())
    p.register("sample_agents/langgraph_agent")
    yield p
    p.phoenix.close()

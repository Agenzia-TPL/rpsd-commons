"""
Pytest configuration and shared fixtures
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rpsd_workflow.engine import WorkflowEngine, default_engine

# Add src to Python path for imports
test_dir = Path(__file__).parent
src_dir = test_dir.parent / "src"
sys.path.insert(0, str(src_dir))


@pytest.fixture
def clean_engine():
    """Provide a fresh WorkflowEngine instance for each test"""
    engine = WorkflowEngine()
    return engine


@pytest.fixture
def mock_runtime():
    """Mock Dapr workflow runtime for testing"""
    runtime = MagicMock()
    runtime.register_workflow = MagicMock()
    runtime.register_activity = MagicMock()
    return runtime


@pytest.fixture
def sample_workflow_func():
    """Sample workflow function for testing"""

    def process_order(ctx, input_data):
        """Sample workflow for processing orders"""
        return {"order_id": input_data.get("order_id"), "status": "processed"}

    process_order.__name__ = "process_order"
    process_order.__module__ = "test.orders.workflows"
    return process_order


@pytest.fixture
def sample_activity_func():
    """Sample activity function for testing"""

    def validate_payment(input_data):
        """Sample activity for payment validation"""
        return {"payment_valid": True}

    validate_payment.__name__ = "validate_payment"
    validate_payment.__module__ = "test.orders.activities"
    return validate_payment


@pytest.fixture(autouse=True)
def reset_default_engine():
    """Reset the default engine before each test"""
    default_engine.workflows.clear()
    default_engine.activities.clear()
    default_engine.domains.clear()
    yield
    # Clean up after test
    default_engine.workflows.clear()
    default_engine.activities.clear()
    default_engine.domains.clear()


@pytest.fixture
def test_data_path():
    """Path to test data directory"""
    return Path(__file__).parent / "test_data"


@pytest.fixture
def mock_importlib(mocker):
    """Mock importlib for testing discovery"""
    mock_import = mocker.patch("rpsd_workflow.engine.import_module")
    mock_distributions = mocker.patch("importlib.metadata.distributions")
    return {"import_module": mock_import, "distributions": mock_distributions}


def pytest_configure(config):
    """Configure pytest"""
    # Create reports directory if it doesn't exist
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    # Create htmlcov directory if it doesn't exist
    htmlcov_dir = Path("htmlcov")
    htmlcov_dir.mkdir(exist_ok=True)


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers"""
    for item in items:
        # Add integration marker for integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Add unit marker for unit tests
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Add slow marker for tests that might be slow
        if "discovery" in item.name or "dapr" in item.name:
            item.add_marker(pytest.mark.slow)

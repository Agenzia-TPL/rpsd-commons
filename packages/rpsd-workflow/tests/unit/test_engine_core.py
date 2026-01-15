"""
Unit tests for WorkflowEngine core functionality
"""

import pytest

from rpsd_workflow.engine import WorkflowMetadata


class TestWorkflowEngineCore:
    """Test core WorkflowEngine functionality"""

    def test_engine_initialization(self, clean_engine):
        """Test WorkflowEngine initializes correctly"""
        assert isinstance(clean_engine.workflows, dict)
        assert isinstance(clean_engine.activities, dict)
        assert isinstance(clean_engine.domains, dict)
        assert len(clean_engine.workflows) == 0
        assert len(clean_engine.activities) == 0
        assert len(clean_engine.domains) == 0

    def test_workflow_metadata_creation(self):
        """Test WorkflowMetadata dataclass creation"""

        def dummy_func():
            pass

        metadata = WorkflowMetadata(
            name="test_workflow",
            domain="test_domain",
            function=dummy_func,
            full_name="test_domain.test_workflow",
            description="Test description",
            version="1.0",
        )

        assert metadata.name == "test_workflow"
        assert metadata.domain == "test_domain"
        assert metadata.function == dummy_func
        assert metadata.full_name == "test_domain.test_workflow"
        assert metadata.description == "Test description"
        assert metadata.version == "1.0"

    def test_get_info_empty_engine(self, clean_engine):
        """Test get_info returns correct structure for empty engine"""
        info = clean_engine.get_info()

        assert "domains" in info
        assert "total_workflows" in info
        assert "total_activities" in info
        assert "domain_details" in info

        assert info["domains"] == []
        assert info["total_workflows"] == 0
        assert info["total_activities"] == 0
        assert info["domain_details"] == {}

    def test_get_info_with_content(
        self, clean_engine, sample_workflow_func, sample_activity_func
    ):
        """Test get_info returns correct counts with registered content"""
        # Register a workflow and activity
        clean_engine.workflow(domain="orders")(sample_workflow_func)
        clean_engine.activity(domain="orders")(sample_activity_func)

        info = clean_engine.get_info()

        assert info["total_workflows"] == 1
        assert info["total_activities"] == 1
        assert "orders" in info["domains"]
        assert info["domain_details"]["orders"]["workflows"] == 1
        assert info["domain_details"]["orders"]["activities"] == 1

    def test_add_to_domain_creates_structure(self, clean_engine):
        """Test _add_to_domain creates proper domain structure"""

        def dummy_func():
            pass

        metadata = WorkflowMetadata(
            name="test",
            domain="test_domain",
            function=dummy_func,
            full_name="test_domain.test",
        )

        clean_engine._add_to_domain("test_domain", "workflows", metadata)

        assert "test_domain" in clean_engine.domains
        assert "workflows" in clean_engine.domains["test_domain"]
        assert "activities" in clean_engine.domains["test_domain"]
        assert len(clean_engine.domains["test_domain"]["workflows"]) == 1
        assert clean_engine.domains["test_domain"]["workflows"][0] == metadata

    def test_add_to_domain_appends_to_existing(self, clean_engine):
        """Test _add_to_domain appends to existing domain"""

        def dummy_func1():
            pass

        def dummy_func2():
            pass

        metadata1 = WorkflowMetadata("test1", "domain", dummy_func1, "domain.test1")
        metadata2 = WorkflowMetadata("test2", "domain", dummy_func2, "domain.test2")

        clean_engine._add_to_domain("domain", "workflows", metadata1)
        clean_engine._add_to_domain("domain", "workflows", metadata2)

        assert len(clean_engine.domains["domain"]["workflows"]) == 2

    @pytest.mark.parametrize(
        "module_name,expected_domain",
        [
            ("workflows_orders.workflows.order_by_phone", "orders"),
            ("orders_workflows.workflows.order_by_phone", "orders"),
            ("domains.orders.workflows.order_by_phone", "orders"),
            ("domains.validation.activities.validate_file", "validation"),
            ("some.random.module", "default"),
            ("workflows_shipping.nested.module", "shipping"),
            ("inventory_workflows.main", "inventory"),
        ],
    )
    def test_extract_domain_from_module(
        self, clean_engine, module_name, expected_domain
    ):
        """Test domain extraction from various module name patterns"""
        domain = clean_engine._extract_domain_from_module(module_name)
        assert domain == expected_domain

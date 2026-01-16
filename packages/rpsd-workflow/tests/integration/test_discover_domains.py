"""
Integration tests for discover_domains functionality.

These tests use the existing test fixtures in tests/test_data/domains/
to validate the discover_domains method with real domain packages.
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

from rpsd_workflow.engine import default_engine

# Add test_data to path for imports (must be done before importing test domains)
test_data_path = Path(__file__).parent.parent / "test_data"
sys.path.insert(0, str(test_data_path))


def _reload_test_domains():
    """Reload test domain modules to re-trigger decorator registration.

    This is needed because pytest's autouse fixture clears default_engine
    before each test, but Python caches module imports. Without reload,
    decorators only execute on first import.
    """
    from domains.orders import (  # type: ignore[import-not-found]
        workflows as orders_workflows,
    )
    from domains.validation import (  # type: ignore[import-not-found]
        workflows as validation_workflows,
    )

    importlib.reload(orders_workflows)
    importlib.reload(validation_workflows)


class TestDiscoverDomainsIntegration:
    """Integration tests for discover_domains with real domain packages"""

    def test_discover_domains_finds_all_domains(self):
        """Test that discover_domains finds both orders and validation domains"""
        _reload_test_domains()

        info = default_engine.get_info()

        assert "orders" in info["domains"]
        assert "validation" in info["domains"]
        assert len(info["domains"]) == 2

    def test_discover_domains_registers_all_workflows(self):
        """Test that all 4 workflows are registered"""
        _reload_test_domains()

        assert len(default_engine.workflows) == 4

        workflow_names = [wf.name for wf in default_engine.workflows.values()]
        assert "process_order" in workflow_names
        assert "cancel_order" in workflow_names
        assert "validate_file" in workflow_names
        assert "validate_data" in workflow_names

    def test_discover_domains_registers_all_activities(self):
        """Test that all 4 activities are registered"""
        _reload_test_domains()

        assert len(default_engine.activities) == 4

        activity_names = [act.name for act in default_engine.activities.values()]
        assert "validate_payment" in activity_names
        assert "update_inventory" in activity_names
        assert "check_file_format" in activity_names
        assert "scan_for_malware" in activity_names

    def test_discovered_workflow_metadata(self):
        """Test that workflow metadata is correctly populated"""
        _reload_test_domains()

        # Find process_order workflow
        process_order = None
        for wf in default_engine.workflows.values():
            if wf.name == "process_order":
                process_order = wf
                break

        assert process_order is not None
        assert process_order.domain == "orders"
        assert process_order.description == "Process customer order"
        assert process_order.full_name == "orders.process_order"
        assert callable(process_order.function)

    def test_discovered_activity_metadata(self):
        """Test that activity metadata is correctly populated"""
        _reload_test_domains()

        # Find validate_payment activity
        validate_payment = None
        for act in default_engine.activities.values():
            if act.name == "validate_payment":
                validate_payment = act
                break

        assert validate_payment is not None
        assert validate_payment.domain == "orders"
        assert validate_payment.description == "Validate payment method"
        assert validate_payment.full_name == "orders.validate_payment"
        assert callable(validate_payment.function)

    def test_discovered_workflows_are_executable(self):
        """Test that discovered workflow functions can be called"""
        _reload_test_domains()

        # Find and execute process_order workflow
        process_order_wf = None
        for wf in default_engine.workflows.values():
            if wf.name == "process_order":
                process_order_wf = wf
                break

        assert process_order_wf is not None

        mock_ctx = MagicMock()
        input_data = {"order_id": "ORD-123", "customer_id": "CUST-001"}

        result = process_order_wf.function(mock_ctx, input_data)

        assert result is not None
        assert result["order_id"] == "ORD-123"
        assert result["status"] == "processed"

    def test_discovered_activities_are_executable(self):
        """Test that discovered activity functions can be called"""
        _reload_test_domains()

        # Find and execute validate_payment activity
        validate_payment_act = None
        for act in default_engine.activities.values():
            if act.name == "validate_payment":
                validate_payment_act = act
                break

        assert validate_payment_act is not None

        input_data = {"payment_method": "visa", "amount": 99.99}

        result = validate_payment_act.function(input_data)

        assert result is not None
        assert result["valid"] is True
        assert result["payment_method"] == "visa"

    def test_discover_domains_populates_engine_info(self):
        """Test that get_info() returns correct statistics after discovery"""
        _reload_test_domains()

        info = default_engine.get_info()

        assert info["total_workflows"] == 4
        assert info["total_activities"] == 4
        assert len(info["domains"]) == 2
        assert "domain_details" in info

        # Check domain-specific counts
        assert info["domain_details"]["orders"]["workflows"] == 2
        assert info["domain_details"]["orders"]["activities"] == 2
        assert info["domain_details"]["validation"]["workflows"] == 2
        assert info["domain_details"]["validation"]["activities"] == 2

    def test_discover_domains_organizes_by_domain(self):
        """Test that engine.domains structure is correctly organized"""
        _reload_test_domains()

        assert "orders" in default_engine.domains
        assert "validation" in default_engine.domains

        # Check orders domain structure
        orders_domain = default_engine.domains["orders"]
        assert "workflows" in orders_domain
        assert "activities" in orders_domain
        assert len(orders_domain["workflows"]) == 2
        assert len(orders_domain["activities"]) == 2

        # Check validation domain structure
        validation_domain = default_engine.domains["validation"]
        assert "workflows" in validation_domain
        assert "activities" in validation_domain
        assert len(validation_domain["workflows"]) == 2
        assert len(validation_domain["activities"]) == 2

    def test_register_discovered_workflows_with_runtime(self):
        """Test that discovered workflows can be registered with mock runtime"""
        _reload_test_domains()

        mock_runtime = MagicMock()
        mock_runtime.register_workflow = MagicMock()
        mock_runtime.register_activity = MagicMock()

        wf_count, act_count = default_engine.register_with_runtime(mock_runtime)

        assert wf_count == 4
        assert act_count == 4
        assert mock_runtime.register_workflow.call_count == 4
        assert mock_runtime.register_activity.call_count == 4

        # Verify registered functions are callable
        registered_workflows = [
            call[0][0] for call in mock_runtime.register_workflow.call_args_list
        ]
        for wf in registered_workflows:
            assert callable(wf)

    def test_selective_domain_registration_after_discovery(self):
        """Test that filtering by enabled_domains works after discovery"""
        _reload_test_domains()

        mock_runtime = MagicMock()
        mock_runtime.register_workflow = MagicMock()
        mock_runtime.register_activity = MagicMock()

        # Register only orders domain
        wf_count, act_count = default_engine.register_with_runtime(
            mock_runtime, enabled_domains=["orders"]
        )

        assert wf_count == 2
        assert act_count == 2
        assert mock_runtime.register_workflow.call_count == 2
        assert mock_runtime.register_activity.call_count == 2

        # Verify only orders workflows were registered
        registered_workflows = [
            call[0][0] for call in mock_runtime.register_workflow.call_args_list
        ]
        for wf_func in registered_workflows:
            # Find the metadata for this function
            for metadata in default_engine.workflows.values():
                if metadata.function == wf_func:
                    assert metadata.domain == "orders"
                    break

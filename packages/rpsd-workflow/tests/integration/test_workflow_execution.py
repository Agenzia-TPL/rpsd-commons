"""
Integration tests for workflow execution scenarios
"""

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

from rpsd_workflow.engine import WorkflowEngine, default_engine

# Add test_data to path for imports (must be done before importing test domains)
test_data_path = Path(__file__).parent.parent / "test_data"
sys.path.insert(0, str(test_data_path))


def _reload_test_domains():
    """Reload test domain modules to re-trigger decorator registration.

    This is needed because pytest's autouse fixture clears default_engine
    before each test, but Python caches module imports. Without reload,
    decorators only execute on first import.
    """
    from domains.orders import (  # type: ignore
        workflows as orders_workflows,
    )
    from domains.validation import (  # type: ignore
        workflows as validation_workflows,
    )

    importlib.reload(orders_workflows)
    importlib.reload(validation_workflows)


class TestWorkflowExecutionIntegration:
    """Integration tests for complete workflow execution scenarios"""

    def test_import_test_domain_workflows(self, clean_engine):
        """Test importing workflow definitions from test domains"""
        _reload_test_domains()

        # Check that workflows were registered
        assert len(default_engine.workflows) > 0
        assert len(default_engine.activities) > 0

        # Check specific domains exist
        info = default_engine.get_info()
        assert "orders" in info["domains"]
        assert "validation" in info["domains"]

    def test_workflow_execution_with_real_functions(self):
        """Test actual execution of registered workflows"""
        _reload_test_domains()

        # Find the process_order workflow
        process_order_key = None
        for key in default_engine.workflows:
            if "process_order" in key:
                process_order_key = key
                break

        assert process_order_key is not None

        # Get the workflow function
        workflow_func = default_engine.workflows[process_order_key].function

        # Execute workflow with test data
        mock_ctx = MagicMock()
        input_data = {"order_id": "12345", "customer_id": "cust-001"}

        result = workflow_func(mock_ctx, input_data)

        assert result is not None
        assert result["order_id"] == "12345"
        assert result["status"] == "processed"

    def test_activity_execution_with_real_functions(self):
        """Test actual execution of registered activities"""
        _reload_test_domains()

        # Find validate_payment activity
        validate_payment_key = None
        for key in default_engine.activities:
            if "validate_payment" in key:
                validate_payment_key = key
                break

        assert validate_payment_key is not None

        # Get the activity function
        activity_func = default_engine.activities[validate_payment_key].function

        # Execute activity with test data
        input_data = {"payment_method": "visa", "amount": 100.0}

        result = activity_func(input_data)

        assert result is not None
        assert result["valid"] is True
        assert "payment_method" in result

    def test_runtime_registration_with_real_workflows(self, mock_runtime):
        """Test runtime registration with actual workflow definitions"""
        _reload_test_domains()

        # Register with mock runtime
        wf_count, act_count = default_engine.register_with_runtime(mock_runtime)

        assert wf_count > 0
        assert act_count > 0

        # Verify that register_workflow was called
        assert mock_runtime.register_workflow.call_count == wf_count
        assert mock_runtime.register_activity.call_count == act_count

        # Check that actual functions were registered
        registered_workflows = [
            call[0][0] for call in mock_runtime.register_workflow.call_args_list
        ]
        registered_activities = [
            call[0][0] for call in mock_runtime.register_activity.call_args_list
        ]

        assert len(registered_workflows) > 0
        assert len(registered_activities) > 0

        # All registered items should be callable
        for wf in registered_workflows:
            assert callable(wf)
        for act in registered_activities:
            assert callable(act)

    def test_selective_domain_registration(self, mock_runtime):
        """Test registering only specific domains"""
        _reload_test_domains()

        # Register only orders domain
        wf_count, act_count = default_engine.register_with_runtime(
            mock_runtime, enabled_domains=["orders"]
        )

        # Get all registered workflow names
        registered_calls = mock_runtime.register_workflow.call_args_list
        registered_workflows = [call[0][0] for call in registered_calls]

        # Check that only orders workflows were registered
        orders_workflows_found = 0
        validation_workflows_found = 0

        for wf_func in registered_workflows:
            # Check which domain this workflow belongs to by looking at metadata
            for key, metadata in default_engine.workflows.items():
                if metadata.function == wf_func:
                    if metadata.domain == "orders":
                        orders_workflows_found += 1
                    elif metadata.domain == "validation":
                        validation_workflows_found += 1

        assert orders_workflows_found > 0
        assert validation_workflows_found == 0


class TestCompleteWorkflowLifecycle:
    """Test complete workflow lifecycle from registration to execution"""

    def test_end_to_end_workflow_scenario(self, mock_runtime):
        """Test complete end-to-end workflow scenario"""
        # Start with clean engine
        engine = WorkflowEngine()

        # 1. Define workflows using decorators
        @engine.workflow(name="complete_order", domain="ecommerce", version="1.0")
        def complete_order_workflow(ctx, input_data):
            order_id = input_data["order_id"]
            return {
                "order_id": order_id,
                "status": "completed",
                "completion_time": "2024-01-01T12:00:00Z",
            }

        @engine.activity(name="send_confirmation", domain="ecommerce")
        def send_confirmation_activity(input_data):
            return {
                "email_sent": True,
                "confirmation_id": f"conf_{input_data['order_id']}",
            }

        # 2. Verify registration
        assert len(engine.workflows) == 1
        assert len(engine.activities) == 1
        assert "ecommerce" in engine.domains

        # 3. Get engine info
        info = engine.get_info()
        assert info["total_workflows"] == 1
        assert info["total_activities"] == 1
        assert info["domain_details"]["ecommerce"]["workflows"] == 1
        assert info["domain_details"]["ecommerce"]["activities"] == 1

        # 4. Register with runtime
        wf_count, act_count = engine.register_with_runtime(mock_runtime)
        assert wf_count == 1
        assert act_count == 1

        # 5. Execute workflow directly
        mock_ctx = MagicMock()
        input_data = {"order_id": "ORD-12345", "customer_id": "CUST-001"}

        result = complete_order_workflow(mock_ctx, input_data)

        assert result["order_id"] == "ORD-12345"
        assert result["status"] == "completed"
        assert "completion_time" in result

        # 6. Execute activity directly
        activity_input = {"order_id": "ORD-12345"}
        activity_result = send_confirmation_activity(activity_input)

        assert activity_result["email_sent"] is True
        assert activity_result["confirmation_id"] == "conf_ORD-12345"

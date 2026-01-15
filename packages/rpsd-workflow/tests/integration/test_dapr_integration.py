"""
Integration tests for Dapr workflow runtime integration
"""

from unittest.mock import MagicMock

import pytest


@pytest.mark.dapr
class TestDaprRuntimeIntegration:
    """Test integration with Dapr workflow runtime"""

    def test_register_with_dapr_runtime_mock(self, clean_engine):
        """Test registration with mock Dapr runtime"""
        # Create mock Dapr runtime that mimics real interface
        mock_dapr_runtime = MagicMock()
        mock_dapr_runtime.register_workflow = MagicMock()
        mock_dapr_runtime.register_activity = MagicMock()

        # Add some workflows and activities
        @clean_engine.workflow(name="dapr_workflow", domain="test")
        def test_dapr_workflow(ctx, input_data):
            """Test workflow for Dapr integration"""
            return {"result": "success", "input": input_data}

        @clean_engine.activity(name="dapr_activity", domain="test")
        def test_dapr_activity(input_data):
            """Test activity for Dapr integration"""
            return {"processed": True, "data": input_data}

        # Register with Dapr runtime
        wf_count, act_count = clean_engine.register_with_runtime(mock_dapr_runtime)

        assert wf_count == 1
        assert act_count == 1

        # Verify Dapr runtime methods were called
        mock_dapr_runtime.register_workflow.assert_called_once()
        mock_dapr_runtime.register_activity.assert_called_once()

        # Verify correct functions were passed
        registered_wf = mock_dapr_runtime.register_workflow.call_args[0][0]
        registered_act = mock_dapr_runtime.register_activity.call_args[0][0]

        assert registered_wf == test_dapr_workflow
        assert registered_act == test_dapr_activity

    def test_workflow_signature_compatibility(self, clean_engine):
        """Test that registered workflows have Dapr-compatible signatures"""

        @clean_engine.workflow(name="compatible_workflow", domain="test")
        def dapr_compatible_workflow(ctx, input_data):
            """Workflow with Dapr-compatible signature"""
            # ctx should be workflow context from Dapr
            # input_data should be the workflow input
            return {
                "workflow_id": getattr(ctx, "workflow_id", "test-id"),
                "input_received": input_data,
                "status": "completed",
            }

        # Verify workflow is registered
        assert len(clean_engine.workflows) == 1

        # Test workflow execution with mock context
        mock_ctx = MagicMock()
        mock_ctx.workflow_id = "wf-12345"

        test_input = {"data": "test"}
        result = dapr_compatible_workflow(mock_ctx, test_input)

        assert result["workflow_id"] == "wf-12345"
        assert result["input_received"] == test_input
        assert result["status"] == "completed"

    def test_activity_signature_compatibility(self, clean_engine):
        """Test that registered activities have Dapr-compatible signatures"""

        @clean_engine.activity(name="compatible_activity", domain="test")
        def dapr_compatible_activity(input_data):
            """Activity with Dapr-compatible signature"""
            # Activities in Dapr take only input_data parameter
            return {
                "input_processed": input_data,
                "processing_time": "0.1s",
                "status": "success",
            }

        # Verify activity is registered
        assert len(clean_engine.activities) == 1

        # Test activity execution
        test_input = {"value": 42, "operation": "double"}
        result = dapr_compatible_activity(test_input)

        assert result["input_processed"] == test_input
        assert result["status"] == "success"

    def test_batch_registration_with_dapr(self, clean_engine):
        """Test registering multiple workflows/activities at once"""
        mock_dapr_runtime = MagicMock()

        # Create multiple workflows and activities
        workflow_funcs = []
        activity_funcs = []

        for i in range(3):
            # Create workflow
            def wf(ctx, input_data):
                return {"workflow": i, "result": input_data}

            wf.__name__ = f"workflow_{i}"
            clean_engine.workflow(domain="batch")(wf)
            workflow_funcs.append(wf)

            # Create activity
            def act(input_data):
                return {"activity": i, "processed": input_data}

            act.__name__ = f"activity_{i}"
            clean_engine.activity(domain="batch")(act)
            activity_funcs.append(act)

        # Register all at once
        wf_count, act_count = clean_engine.register_with_runtime(mock_dapr_runtime)

        assert wf_count == 3
        assert act_count == 3
        assert mock_dapr_runtime.register_workflow.call_count == 3
        assert mock_dapr_runtime.register_activity.call_count == 3

    def test_error_handling_during_registration(self, clean_engine):
        """Test error handling when Dapr runtime registration fails"""
        # Create mock runtime that raises exception
        mock_dapr_runtime = MagicMock()
        mock_dapr_runtime.register_workflow.side_effect = Exception(
            "Dapr registration failed"
        )
        mock_dapr_runtime.register_activity.return_value = None

        @clean_engine.workflow(domain="test")
        def failing_workflow(ctx, input_data):
            return {"status": "should not be called"}

        @clean_engine.activity(domain="test")
        def working_activity(input_data):
            return {"status": "success"}

        # Registration should raise exception due to workflow registration failure
        with pytest.raises(Exception, match="Dapr registration failed"):
            clean_engine.register_with_runtime(mock_dapr_runtime)

    def test_selective_domain_registration_with_dapr(self, clean_engine):
        """Test selective domain registration with Dapr runtime"""
        mock_dapr_runtime = MagicMock()

        # Create workflows in different domains
        @clean_engine.workflow(domain="orders")
        def process_order(ctx, input_data):
            return {"order_processed": True}

        @clean_engine.workflow(domain="shipping")
        def ship_order(ctx, input_data):
            return {"shipped": True}

        @clean_engine.activity(domain="orders")
        def validate_order(input_data):
            return {"valid": True}

        @clean_engine.activity(domain="shipping")
        def create_label(input_data):
            return {"label_created": True}

        # Register only orders domain
        wf_count, act_count = clean_engine.register_with_runtime(
            mock_dapr_runtime, enabled_domains=["orders"]
        )

        assert wf_count == 1
        assert act_count == 1

        # Verify only orders domain functions were registered
        registered_wf = mock_dapr_runtime.register_workflow.call_args[0][0]
        registered_act = mock_dapr_runtime.register_activity.call_args[0][0]

        assert registered_wf == process_order
        assert registered_act == validate_order


@pytest.mark.dapr
class TestDaprWorkflowPatterns:
    """Test common Dapr workflow patterns and use cases"""

    def test_workflow_calls_activity_pattern(self, clean_engine):
        """Test typical pattern where workflow calls activities"""

        @clean_engine.activity(domain="ecommerce")
        def validate_payment(payment_data):
            """Validate payment information"""
            return {
                "valid": payment_data.get("amount", 0) > 0,
                "transaction_id": "txn_12345",
            }

        @clean_engine.activity(domain="ecommerce")
        def update_inventory(inventory_data):
            """Update product inventory"""
            return {
                "updated": True,
                "remaining": inventory_data.get("current", 100) - 1,
            }

        @clean_engine.workflow(domain="ecommerce")
        def process_order_workflow(ctx, input_data):
            """Main workflow that orchestrates activities"""
            order_id = input_data.get("order_id")

            # In real Dapr workflow, these would be:
            # payment_result = yield ctx.call_activity(
            #     "validate_payment", input_data["payment"])
            # inventory_result = yield ctx.call_activity(
            #     "update_inventory", input_data["inventory"])

            # For testing, we simulate the pattern
            payment_result = validate_payment(input_data.get("payment", {}))
            inventory_result = update_inventory(input_data.get("inventory", {}))

            return {
                "order_id": order_id,
                "payment_valid": payment_result["valid"],
                "inventory_updated": inventory_result["updated"],
                "status": "completed",
            }

        # Test the workflow
        mock_ctx = MagicMock()
        test_input = {
            "order_id": "ORD-001",
            "payment": {"amount": 100, "method": "credit_card"},
            "inventory": {"product_id": "PROD-001", "current": 50},
        }

        result = process_order_workflow(mock_ctx, test_input)

        assert result["order_id"] == "ORD-001"
        assert result["payment_valid"] is True
        assert result["inventory_updated"] is True
        assert result["status"] == "completed"

    def test_workflow_with_conditional_logic(self, clean_engine):
        """Test workflow with conditional execution paths"""

        @clean_engine.workflow(domain="approval")
        def approval_workflow(ctx, input_data):
            """Workflow with conditional approval logic"""
            amount = input_data.get("amount", 0)

            if amount < 100:
                return {
                    "approved": True,
                    "approver": "system",
                    "reason": "auto_approval_small_amount",
                }
            elif amount < 1000:
                return {
                    "approved": True,
                    "approver": "manager",
                    "reason": "manager_approval_required",
                }
            else:
                return {
                    "approved": False,
                    "approver": "director",
                    "reason": "director_approval_required",
                }

        # Test different amounts
        mock_ctx = MagicMock()

        # Small amount - auto approved
        result1 = approval_workflow(mock_ctx, {"amount": 50})
        assert result1["approved"] is True
        assert result1["approver"] == "system"

        # Medium amount - manager approval
        result2 = approval_workflow(mock_ctx, {"amount": 500})
        assert result2["approved"] is True
        assert result2["approver"] == "manager"

        # Large amount - director approval needed
        result3 = approval_workflow(mock_ctx, {"amount": 5000})
        assert result3["approved"] is False
        assert result3["approver"] == "director"

    def test_activity_error_handling_pattern(self, clean_engine):
        """Test error handling patterns in activities"""

        @clean_engine.activity(domain="validation")
        def risky_validation_activity(input_data):
            """Activity that might fail"""
            file_path = input_data.get("file_path")

            if not file_path:
                raise ValueError("file_path is required")

            if file_path.endswith(".bad"):
                raise Exception("Invalid file format")

            return {
                "valid": True,
                "file_path": file_path,
                "validation_time": "2024-01-01T10:00:00Z",
            }

        # Test successful case
        result = risky_validation_activity({"file_path": "/path/to/file.good"})
        assert result["valid"] is True

        # Test validation error
        with pytest.raises(ValueError, match="file_path is required"):
            risky_validation_activity({})

        # Test processing error
        with pytest.raises(Exception, match="Invalid file format"):
            risky_validation_activity({"file_path": "/path/to/file.bad"})


@pytest.mark.dapr
class TestDaprIntegrationWithHybridSender:
    """Test integration between WorkflowEngine and Dapr Hybrid Communication Pattern"""

    def test_workflow_triggered_by_hybrid_sender(self, clean_engine):
        """Test workflow that would be triggered by hybrid sender pattern"""

        @clean_engine.workflow(name="validate_file", domain="validation")
        def file_validation_workflow(ctx, input_data):
            """File validation workflow triggered by hybrid sender"""
            operation_id = input_data.get("operation_id")
            file_path = input_data.get("file_path")
            file_type = input_data.get("file_type")

            # Simulate file validation steps
            validation_steps = [
                "format_check",
                "schema_validation",
                "content_verification",
            ]

            return {
                "operation_id": operation_id,
                "file_path": file_path,
                "file_type": file_type,
                "validation_status": "completed",
                "steps_completed": validation_steps,
                "errors": [],
                "warnings": [],
            }

        # Test with hybrid sender input format
        mock_ctx = MagicMock()
        hybrid_input = {
            "operation_id": "op_12345",
            "file_path": "s3://bucket/files/netex-data.xml",
            "file_type": "netex",
        }

        result = file_validation_workflow(mock_ctx, hybrid_input)

        assert result["operation_id"] == "op_12345"
        assert result["file_path"] == "s3://bucket/files/netex-data.xml"
        assert result["file_type"] == "netex"
        assert result["validation_status"] == "completed"
        assert len(result["steps_completed"]) == 3

    def test_workflow_engine_info_for_monitoring(self, clean_engine):
        """Test that engine info can be used for monitoring/observability"""

        # Register several workflows for different domains
        @clean_engine.workflow(domain="orders")
        def wf1(ctx, input_data):
            return {}

        @clean_engine.workflow(domain="orders")
        def wf2(ctx, input_data):
            return {}

        @clean_engine.workflow(domain="shipping")
        def wf3(ctx, input_data):
            return {}

        @clean_engine.activity(domain="orders")
        def act1(input_data):
            return {}

        @clean_engine.activity(domain="validation")
        def act2(input_data):
            return {}

        # Get engine info for monitoring
        info = clean_engine.get_info()

        # This info could be exposed via monitoring endpoints
        monitoring_data = {
            "timestamp": "2024-01-01T10:00:00Z",
            "service": "workflow-engine",
            "metrics": {
                "total_registered_workflows": info["total_workflows"],
                "total_registered_activities": info["total_activities"],
                "active_domains": len(info["domains"]),
                "domain_breakdown": info["domain_details"],
            },
        }

        assert monitoring_data["metrics"]["total_registered_workflows"] == 3
        assert monitoring_data["metrics"]["total_registered_activities"] == 2
        assert monitoring_data["metrics"]["active_domains"] == 3
        assert "orders" in monitoring_data["metrics"]["domain_breakdown"]
        assert (
            monitoring_data["metrics"]["domain_breakdown"]["orders"]["workflows"] == 2
        )

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


@pytest.mark.dapr
class TestActivityChaining:
    """Test actual ctx.call_activity() patterns with proper mocking.

    These tests demonstrate and verify the yield-based activity chaining
    pattern that Dapr workflows use. The key insight is that Dapr workflows
    are Python generators - each yield suspends the workflow until the
    activity completes.
    """

    def test_workflow_with_single_activity_call(self, clean_engine):
        """Test a workflow that calls a single activity using yield."""

        @clean_engine.activity(domain="orders")
        def validate_order(input_data):
            """Validate order data."""
            order_id = input_data.get("order_id")
            return {
                "valid": bool(order_id),
                "order_id": order_id,
            }

        @clean_engine.workflow(domain="orders")
        def simple_order_workflow(ctx, input_data):
            """Workflow that calls one activity."""
            # This is the actual Dapr pattern - yield ctx.call_activity()
            result = yield ctx.call_activity(validate_order, input=input_data)
            return {"status": "completed", "validation": result}

        # Create a mock context that simulates Dapr's behavior
        mock_ctx = MagicMock()

        # When call_activity is called, it should return something that
        # when yielded, returns the activity result
        def mock_call_activity(activity_func, input):
            # Simulate Dapr executing the activity and returning result
            return activity_func(input)

        mock_ctx.call_activity = mock_call_activity

        # Execute the workflow as a generator
        test_input = {"order_id": "ORD-001"}
        workflow_gen = simple_order_workflow(mock_ctx, test_input)

        # First yield returns the activity result
        activity_result = next(workflow_gen)
        assert activity_result["valid"] is True
        assert activity_result["order_id"] == "ORD-001"

        # Send the result back to the workflow to continue
        try:
            workflow_gen.send(activity_result)
        except StopIteration as e:
            final_result = e.value

        assert final_result["status"] == "completed"
        assert final_result["validation"]["valid"] is True

    def test_workflow_with_chained_activities(self, clean_engine):
        """Test a workflow that chains multiple activities sequentially."""

        @clean_engine.activity(domain="orders")
        def validate_order(input_data):
            return {"valid": True, "order_id": input_data.get("order_id")}

        @clean_engine.activity(domain="orders")
        def check_inventory(input_data):
            return {"available": True, "items": input_data.get("items", [])}

        @clean_engine.activity(domain="orders")
        def process_payment(input_data):
            return {
                "success": True,
                "transaction_id": "TXN-12345",
                "amount": input_data.get("amount"),
            }

        @clean_engine.workflow(domain="orders")
        def order_processing_workflow(ctx, input_data):
            """Workflow that chains three activities."""
            # Step 1: Validate order
            validation = yield ctx.call_activity(
                validate_order,
                input={"order_id": input_data.get("order_id")},
            )

            if not validation.get("valid"):
                return {"status": "failed", "step": "validation"}

            # Step 2: Check inventory
            inventory = yield ctx.call_activity(
                check_inventory,
                input={"items": input_data.get("items", [])},
            )

            if not inventory.get("available"):
                return {"status": "failed", "step": "inventory"}

            # Step 3: Process payment
            payment = yield ctx.call_activity(
                process_payment,
                input={"amount": input_data.get("total")},
            )

            return {
                "status": "completed",
                "order_id": input_data.get("order_id"),
                "transaction_id": payment.get("transaction_id"),
            }

        # Mock context that executes activities directly
        mock_ctx = MagicMock()
        mock_ctx.call_activity = lambda func, input: func(input)

        # Execute workflow
        test_input = {
            "order_id": "ORD-002",
            "items": [{"sku": "ITEM-001", "qty": 2}],
            "total": 99.99,
        }

        workflow_gen = order_processing_workflow(mock_ctx, test_input)

        # Drive the generator through all yields
        result = None
        try:
            result = next(workflow_gen)
            while True:
                result = workflow_gen.send(result)
        except StopIteration as e:
            final_result = e.value

        assert final_result["status"] == "completed"
        assert final_result["order_id"] == "ORD-002"
        assert final_result["transaction_id"] == "TXN-12345"

    def test_workflow_with_conditional_activity_flow(self, clean_engine):
        """Test workflow that takes different activity paths based on results."""

        @clean_engine.activity(domain="orders")
        def check_customer_status(input_data):
            customer_id = input_data.get("customer_id", "")
            # VIP customers have IDs starting with "VIP"
            is_vip = customer_id.startswith("VIP")
            return {"is_vip": is_vip, "customer_id": customer_id}

        @clean_engine.activity(domain="orders")
        def apply_vip_discount(input_data):
            amount = input_data.get("amount", 0)
            return {"discounted_amount": amount * 0.8, "discount_applied": "20%"}

        @clean_engine.activity(domain="orders")
        def apply_standard_pricing(input_data):
            amount = input_data.get("amount", 0)
            return {"final_amount": amount, "discount_applied": None}

        @clean_engine.workflow(domain="orders")
        def pricing_workflow(ctx, input_data):
            """Workflow with conditional activity selection."""
            # Check customer status
            status = yield ctx.call_activity(
                check_customer_status,
                input={"customer_id": input_data.get("customer_id")},
            )

            # Call different activity based on status
            if status.get("is_vip"):
                pricing = yield ctx.call_activity(
                    apply_vip_discount,
                    input={"amount": input_data.get("amount")},
                )
                return {
                    "customer_type": "vip",
                    "final_amount": pricing.get("discounted_amount"),
                    "discount": pricing.get("discount_applied"),
                }
            else:
                pricing = yield ctx.call_activity(
                    apply_standard_pricing,
                    input={"amount": input_data.get("amount")},
                )
                return {
                    "customer_type": "standard",
                    "final_amount": pricing.get("final_amount"),
                    "discount": None,
                }

        # Helper to run workflow generator to completion
        def run_workflow(workflow_gen):
            result = None
            try:
                result = next(workflow_gen)
                while True:
                    result = workflow_gen.send(result)
            except StopIteration as e:
                return e.value

        mock_ctx = MagicMock()
        mock_ctx.call_activity = lambda func, input: func(input)

        # Test VIP path
        vip_gen = pricing_workflow(mock_ctx, {"customer_id": "VIP-001", "amount": 100})
        vip_result = run_workflow(vip_gen)

        assert vip_result["customer_type"] == "vip"
        assert vip_result["final_amount"] == 80.0
        assert vip_result["discount"] == "20%"

        # Test standard path
        std_gen = pricing_workflow(mock_ctx, {"customer_id": "REG-001", "amount": 100})
        std_result = run_workflow(std_gen)

        assert std_result["customer_type"] == "standard"
        assert std_result["final_amount"] == 100
        assert std_result["discount"] is None

    def test_workflow_with_early_termination(self, clean_engine):
        """Test workflow that terminates early based on activity result."""

        @clean_engine.activity(domain="orders")
        def check_eligibility(input_data):
            customer_id = input_data.get("customer_id", "")
            # Only customers with "ACTIVE" prefix are eligible
            is_eligible = customer_id.startswith("ACTIVE")
            return {"eligible": is_eligible, "customer_id": customer_id}

        @clean_engine.activity(domain="orders")
        def process_order(input_data):
            return {"processed": True, "order_id": input_data.get("order_id")}

        @clean_engine.workflow(domain="orders")
        def eligibility_workflow(ctx, input_data):
            """Workflow that may terminate early if customer not eligible."""
            # Check eligibility first
            eligibility = yield ctx.call_activity(
                check_eligibility,
                input={"customer_id": input_data.get("customer_id")},
            )

            if not eligibility.get("eligible"):
                # Early termination - don't process order
                return {
                    "status": "rejected",
                    "reason": "Customer not eligible",
                    "customer_id": eligibility.get("customer_id"),
                }

            # Only process if eligible
            order_result = yield ctx.call_activity(
                process_order,
                input={"order_id": input_data.get("order_id")},
            )

            return {
                "status": "completed",
                "order_processed": order_result.get("processed"),
                "order_id": order_result.get("order_id"),
            }

        mock_ctx = MagicMock()
        mock_ctx.call_activity = lambda func, input: func(input)

        # Helper to run workflow
        def run_workflow(workflow_gen):
            result = None
            try:
                result = next(workflow_gen)
                while True:
                    result = workflow_gen.send(result)
            except StopIteration as e:
                return e.value

        # Test eligible customer - full flow
        eligible_gen = eligibility_workflow(
            mock_ctx, {"customer_id": "ACTIVE-001", "order_id": "ORD-001"}
        )
        eligible_result = run_workflow(eligible_gen)

        assert eligible_result["status"] == "completed"
        assert eligible_result["order_processed"] is True
        assert eligible_result["order_id"] == "ORD-001"

        # Test ineligible customer - early termination
        ineligible_gen = eligibility_workflow(
            mock_ctx, {"customer_id": "INACTIVE-002", "order_id": "ORD-002"}
        )
        ineligible_result = run_workflow(ineligible_gen)

        assert ineligible_result["status"] == "rejected"
        assert ineligible_result["reason"] == "Customer not eligible"
        assert "order_processed" not in ineligible_result  # Order was never processed

    def test_activity_receives_correct_input(self, clean_engine):
        """Test that activities receive exactly the input passed via call_activity."""
        received_inputs = []

        @clean_engine.activity(domain="test")
        def capturing_activity(input_data):
            received_inputs.append(input_data)
            return {"captured": True}

        @clean_engine.workflow(domain="test")
        def test_workflow(ctx, input_data):
            yield ctx.call_activity(
                capturing_activity,
                input={"key1": "value1", "nested": {"a": 1, "b": 2}},
            )
            yield ctx.call_activity(
                capturing_activity,
                input={"key2": "value2"},
            )
            return {"done": True}

        mock_ctx = MagicMock()
        mock_ctx.call_activity = lambda func, input: func(input)

        # Run workflow
        gen = test_workflow(mock_ctx, {})
        result = None
        try:
            result = next(gen)
            while True:
                result = gen.send(result)
        except StopIteration:
            pass

        # Verify inputs were captured correctly
        assert len(received_inputs) == 2
        assert received_inputs[0] == {"key1": "value1", "nested": {"a": 1, "b": 2}}
        assert received_inputs[1] == {"key2": "value2"}

    def test_workflow_passes_activity_function_reference(self, clean_engine):
        """Test that call_activity receives the actual function object."""
        called_functions = []

        @clean_engine.activity(domain="test")
        def activity_one(input_data):
            return {"from": "one"}

        @clean_engine.activity(domain="test")
        def activity_two(input_data):
            return {"from": "two"}

        @clean_engine.workflow(domain="test")
        def test_workflow(ctx, input_data):
            yield ctx.call_activity(activity_one, input={})
            yield ctx.call_activity(activity_two, input={})
            return {"done": True}

        # Mock that captures which function was called
        def capturing_call_activity(func, input):
            called_functions.append(func.__name__)
            return func(input)

        mock_ctx = MagicMock()
        mock_ctx.call_activity = capturing_call_activity

        # Run workflow
        gen = test_workflow(mock_ctx, {})
        result = None
        try:
            result = next(gen)
            while True:
                result = gen.send(result)
        except StopIteration:
            pass

        # Verify correct functions were called in order
        assert called_functions == ["activity_one", "activity_two"]

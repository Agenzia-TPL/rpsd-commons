"""
Unit tests for runtime registration functionality
"""


class TestRuntimeRegistration:
    """Test registration of workflows and activities with runtime"""

    def test_register_with_runtime_all_domains(self, clean_engine, mock_runtime):
        """Test registering all workflows and activities with runtime"""

        # Add some test workflows and activities
        @clean_engine.workflow(domain="orders")
        def workflow1():
            return "w1"

        @clean_engine.workflow(domain="shipping")
        def workflow2():
            return "w2"

        @clean_engine.activity(domain="orders")
        def activity1():
            return "a1"

        @clean_engine.activity(domain="payments")
        def activity2():
            return "a2"

        # Register with runtime (no domain filter)
        workflows_count, activities_count = clean_engine.register_with_runtime(
            mock_runtime
        )

        assert workflows_count == 2
        assert activities_count == 2

        # Check that runtime.register_* was called correctly
        assert mock_runtime.register_workflow.call_count == 2
        assert mock_runtime.register_activity.call_count == 2

        # Verify correct functions were registered
        workflow_calls = [
            call[0][0] for call in mock_runtime.register_workflow.call_args_list
        ]
        activity_calls = [
            call[0][0] for call in mock_runtime.register_activity.call_args_list
        ]

        assert workflow1 in workflow_calls
        assert workflow2 in workflow_calls
        assert activity1 in activity_calls
        assert activity2 in activity_calls

    def test_register_with_runtime_filtered_domains(self, clean_engine, mock_runtime):
        """Test registering only enabled domains with runtime"""

        # Add workflows in different domains
        @clean_engine.workflow(domain="orders")
        def orders_workflow():
            return "orders"

        @clean_engine.workflow(domain="shipping")
        def shipping_workflow():
            return "shipping"

        @clean_engine.activity(domain="orders")
        def orders_activity():
            return "orders"

        @clean_engine.activity(domain="payments")
        def payments_activity():
            return "payments"

        # Register only orders domain
        workflows_count, activities_count = clean_engine.register_with_runtime(
            mock_runtime, enabled_domains=["orders"]
        )

        assert workflows_count == 1
        assert activities_count == 1

        # Verify only orders domain functions were registered
        workflow_calls = [
            call[0][0] for call in mock_runtime.register_workflow.call_args_list
        ]
        activity_calls = [
            call[0][0] for call in mock_runtime.register_activity.call_args_list
        ]

        assert orders_workflow in workflow_calls
        assert shipping_workflow not in workflow_calls
        assert orders_activity in activity_calls
        assert payments_activity not in activity_calls

    def test_register_with_runtime_multiple_enabled_domains(
        self, clean_engine, mock_runtime
    ):
        """Test registering multiple enabled domains"""
        # Add workflows in various domains
        domains_and_functions = [
            ("orders", "order_wf", "order_act"),
            ("shipping", "ship_wf", "ship_act"),
            ("payments", "pay_wf", "pay_act"),
            ("inventory", "inv_wf", "inv_act"),
        ]

        registered_workflows = []
        registered_activities = []

        def make_func(name: str, return_value: str):
            def func():
                return return_value

            func.__name__ = name
            return func

        for domain, wf_name, act_name in domains_and_functions:
            # Create workflow
            wf_func = make_func(wf_name, f"{domain}_workflow")
            clean_engine.workflow(domain=domain)(wf_func)
            registered_workflows.append(wf_func)

            # Create activity
            act_func = make_func(act_name, f"{domain}_activity")
            clean_engine.activity(domain=domain)(act_func)
            registered_activities.append(act_func)

        # Enable only orders and shipping
        workflows_count, activities_count = clean_engine.register_with_runtime(
            mock_runtime, enabled_domains=["orders", "shipping"]
        )

        assert workflows_count == 2
        assert activities_count == 2

    def test_register_with_runtime_empty_engine(self, clean_engine, mock_runtime):
        """Test registering empty engine with runtime"""
        workflows_count, activities_count = clean_engine.register_with_runtime(
            mock_runtime
        )

        assert workflows_count == 0
        assert activities_count == 0
        assert mock_runtime.register_workflow.call_count == 0
        assert mock_runtime.register_activity.call_count == 0

    def test_register_with_runtime_nonexistent_domain(self, clean_engine, mock_runtime):
        """Test registering with nonexistent domain filter"""

        @clean_engine.workflow(domain="orders")
        def test_workflow():
            return "test"

        # Try to register nonexistent domain
        workflows_count, activities_count = clean_engine.register_with_runtime(
            mock_runtime, enabled_domains=["nonexistent"]
        )

        assert workflows_count == 0
        assert activities_count == 0
        assert mock_runtime.register_workflow.call_count == 0

    def test_register_with_runtime_returns_counts(self, clean_engine, mock_runtime):
        """Test that register_with_runtime returns correct counts"""

        def make_func(name: str, return_value: str):
            def func():
                return return_value

            func.__name__ = name
            return func

        # Add mixed content
        for i in range(3):
            wf = make_func(f"workflow_{i}", f"workflow_{i}")
            clean_engine.workflow(domain="test")(wf)

        for i in range(2):
            act = make_func(f"activity_{i}", f"activity_{i}")
            clean_engine.activity(domain="test")(act)

        workflows_count, activities_count = clean_engine.register_with_runtime(
            mock_runtime
        )

        assert workflows_count == 3
        assert activities_count == 2
        assert isinstance(workflows_count, int)
        assert isinstance(activities_count, int)


class TestRegistrationIntegration:
    """Integration tests for registration with real workflow scenarios"""

    def test_register_complex_workflow_hierarchy(self, clean_engine, mock_runtime):
        """Test registering complex workflow hierarchy"""
        # Create a realistic workflow structure

        # Orders domain
        @clean_engine.workflow(name="process_order", domain="orders", version="1.0")
        def process_order_workflow(ctx, input_data):
            return {"status": "processed"}

        @clean_engine.activity(name="validate_order", domain="orders")
        def validate_order_activity(input_data):
            return {"valid": True}

        @clean_engine.activity(name="calculate_total", domain="orders")
        def calculate_total_activity(input_data):
            return {"total": 100.0}

        # Shipping domain
        @clean_engine.workflow(name="ship_order", domain="shipping")
        def ship_order_workflow(ctx, input_data):
            return {"tracking_number": "12345"}

        @clean_engine.activity(name="create_label", domain="shipping")
        def create_label_activity(input_data):
            return {"label_url": "http://example.com/label"}

        # Register all
        wf_count, act_count = clean_engine.register_with_runtime(mock_runtime)

        assert wf_count == 2  # process_order, ship_order
        assert act_count == 3  # validate_order, calculate_total, create_label

        # Verify domain structure is maintained
        info = clean_engine.get_info()
        assert len(info["domains"]) == 2
        assert "orders" in info["domains"]
        assert "shipping" in info["domains"]

    def test_register_with_runtime_preserves_metadata(self, clean_engine, mock_runtime):
        """Test that registration preserves workflow metadata"""

        @clean_engine.workflow(
            name="complex_workflow",
            domain="orders",
            description="A complex workflow",
            version="2.0",
        )
        def complex_workflow():
            return "complex"

        clean_engine.register_with_runtime(mock_runtime)

        # Verify metadata is preserved in engine
        metadata = clean_engine.workflows["orders.complex_workflow"]
        assert metadata.name == "complex_workflow"
        assert metadata.domain == "orders"
        assert metadata.description == "A complex workflow"
        assert metadata.version == "2.0"
        assert metadata.function == complex_workflow

    def test_register_domain_filtering_edge_cases(self, clean_engine, mock_runtime):
        """Test domain filtering edge cases"""

        @clean_engine.workflow(domain="orders")
        def orders_wf():
            return "orders"

        @clean_engine.workflow(domain="ORDERS")  # Different case
        def orders_upper_wf():
            return "ORDERS"

        @clean_engine.workflow(domain="orders-v2")  # With dash
        def orders_v2_wf():
            return "orders-v2"

        # Test exact match filtering
        wf_count, _ = clean_engine.register_with_runtime(
            mock_runtime, enabled_domains=["orders"]
        )

        assert wf_count == 1  # Only exact match should be included

        # Verify the correct one was registered
        registered_calls = [
            call[0][0] for call in mock_runtime.register_workflow.call_args_list
        ]
        assert orders_wf in registered_calls
        assert orders_upper_wf not in registered_calls
        assert orders_v2_wf not in registered_calls

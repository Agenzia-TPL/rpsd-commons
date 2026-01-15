"""
Unit tests for workflow and activity decorators
"""


class TestWorkflowDecorator:
    """Test workflow decorator functionality"""

    def test_workflow_decorator_with_defaults(self, clean_engine):
        """Test workflow decorator with default parameters"""

        @clean_engine.workflow()
        def test_workflow():
            return "test"

        assert len(clean_engine.workflows) == 1
        full_name = list(clean_engine.workflows.keys())[0]
        assert full_name.endswith(".test_workflow")

        metadata = clean_engine.workflows[full_name]
        assert metadata.name == "test_workflow"
        assert metadata.function == test_workflow
        assert metadata.description is None
        assert metadata.version is None

    def test_workflow_decorator_with_custom_name(self, clean_engine):
        """Test workflow decorator with custom name"""

        @clean_engine.workflow(name="custom_name")
        def some_function():
            return "test"

        full_name = list(clean_engine.workflows.keys())[0]
        metadata = clean_engine.workflows[full_name]
        assert metadata.name == "custom_name"
        assert "custom_name" in full_name

    def test_workflow_decorator_with_custom_domain(self, clean_engine):
        """Test workflow decorator with custom domain"""

        @clean_engine.workflow(domain="custom_domain")
        def test_workflow():
            return "test"

        full_name = list(clean_engine.workflows.keys())[0]
        assert full_name.startswith("custom_domain.")

        metadata = clean_engine.workflows[full_name]
        assert metadata.domain == "custom_domain"
        assert "custom_domain" in clean_engine.domains

    def test_workflow_decorator_with_all_params(self, clean_engine):
        """Test workflow decorator with all parameters"""

        @clean_engine.workflow(
            name="custom_workflow",
            domain="orders",
            description="Process orders",
            version="1.0",
        )
        def process_orders():
            return "processed"

        metadata = clean_engine.workflows["orders.custom_workflow"]
        assert metadata.name == "custom_workflow"
        assert metadata.domain == "orders"
        assert metadata.description == "Process orders"
        assert metadata.version == "1.0"
        assert metadata.full_name == "orders.custom_workflow"

    def test_workflow_decorator_preserves_function(self, clean_engine):
        """Test that workflow decorator preserves the original function"""

        def original_function(x):
            return x + 1

        decorated = clean_engine.workflow()(original_function)

        assert decorated == original_function
        assert decorated(5) == 6

    def test_workflow_decorator_auto_domain_extraction(self, clean_engine):
        """Test workflow decorator automatically extracts domain from module"""

        def test_func():
            pass

        test_func.__module__ = "workflows_shipping.main"

        _ = clean_engine.workflow()(test_func)

        metadata = list(clean_engine.workflows.values())[0]
        assert metadata.domain == "shipping"


class TestActivityDecorator:
    """Test activity decorator functionality"""

    def test_activity_decorator_with_defaults(self, clean_engine):
        """Test activity decorator with default parameters"""

        @clean_engine.activity()
        def test_activity():
            return "test"

        assert len(clean_engine.activities) == 1
        full_name = list(clean_engine.activities.keys())[0]
        assert full_name.endswith(".test_activity")

        metadata = clean_engine.activities[full_name]
        assert metadata.name == "test_activity"
        assert metadata.function == test_activity
        assert metadata.description is None

    def test_activity_decorator_with_custom_name(self, clean_engine):
        """Test activity decorator with custom name"""

        @clean_engine.activity(name="custom_activity")
        def some_function():
            return "test"

        full_name = list(clean_engine.activities.keys())[0]
        metadata = clean_engine.activities[full_name]
        assert metadata.name == "custom_activity"
        assert "custom_activity" in full_name

    def test_activity_decorator_with_custom_domain(self, clean_engine):
        """Test activity decorator with custom domain"""

        @clean_engine.activity(domain="payments")
        def validate_payment():
            return True

        full_name = list(clean_engine.activities.keys())[0]
        assert full_name.startswith("payments.")

        metadata = clean_engine.activities[full_name]
        assert metadata.domain == "payments"
        assert "payments" in clean_engine.domains

    def test_activity_decorator_with_description(self, clean_engine):
        """Test activity decorator with description"""

        @clean_engine.activity(description="Validate payment information")
        def validate_payment():
            return True

        metadata = list(clean_engine.activities.values())[0]
        assert metadata.description == "Validate payment information"

    def test_activity_decorator_preserves_function(self, clean_engine):
        """Test that activity decorator preserves the original function"""

        def original_function(x):
            return x * 2

        decorated = clean_engine.activity()(original_function)

        assert decorated == original_function
        assert decorated(3) == 6


class TestDecoratorIntegration:
    """Test integration between workflow and activity decorators"""

    def test_mixed_decorators_same_domain(self, clean_engine):
        """Test workflow and activity decorators in same domain"""

        @clean_engine.workflow(domain="orders")
        def process_order():
            return "processed"

        @clean_engine.activity(domain="orders")
        def validate_order():
            return True

        assert len(clean_engine.workflows) == 1
        assert len(clean_engine.activities) == 1
        assert "orders" in clean_engine.domains
        assert len(clean_engine.domains["orders"]["workflows"]) == 1
        assert len(clean_engine.domains["orders"]["activities"]) == 1

    def test_multiple_domains(self, clean_engine):
        """Test decorators creating multiple domains"""

        @clean_engine.workflow(domain="orders")
        def process_order():
            return "processed"

        @clean_engine.workflow(domain="shipping")
        def ship_order():
            return "shipped"

        @clean_engine.activity(domain="payments")
        def process_payment():
            return "paid"

        assert len(clean_engine.domains) == 3
        assert "orders" in clean_engine.domains
        assert "shipping" in clean_engine.domains
        assert "payments" in clean_engine.domains

    def test_decorator_full_name_uniqueness(self, clean_engine):
        """Test that full names are unique across decorators"""

        @clean_engine.workflow(name="process", domain="orders")
        def workflow_process():
            return "workflow"

        @clean_engine.activity(name="process", domain="orders")
        def activity_process():
            return "activity"

        # Should have different full names even with same name/domain
        workflow_key = "orders.process"
        assert workflow_key in clean_engine.workflows
        assert workflow_key in clean_engine.activities

        # But they should be different objects
        assert (
            clean_engine.workflows[workflow_key].function
            != clean_engine.activities[workflow_key].function
        )

"""
Performance benchmarks for WorkflowEngine
"""

import time
from unittest.mock import MagicMock

import pytest

from rpsd_workflow.engine import WorkflowEngine


@pytest.mark.benchmark
class TestWorkflowEnginePerformance:
    """Performance tests for WorkflowEngine operations"""

    def test_workflow_registration_performance(self, benchmark):
        """Benchmark workflow registration speed"""

        def register_workflows():
            engine = WorkflowEngine()

            # Register 100 workflows
            for i in range(100):

                def workflow(ctx, data):
                    return {"result": i}

                workflow.__name__ = f"workflow_{i}"
                engine.workflow(domain="perf_test")(workflow)

            return len(engine.workflows)

        result = benchmark(register_workflows)
        assert result == 100

    def test_bulk_runtime_registration_performance(self, benchmark):
        """Benchmark bulk registration with runtime"""
        engine = WorkflowEngine()
        mock_runtime = MagicMock()

        # Pre-register 1000 workflows and activities
        for i in range(500):
            # Workflow
            def wf(ctx, data):
                return {"wf": i}

            wf.__name__ = f"workflow_{i}"
            engine.workflow(domain="bulk_test")(wf)

            # Activity
            def act(data):
                return {"act": i}

            act.__name__ = f"activity_{i}"
            engine.activity(domain="bulk_test")(act)

        def register_with_runtime():
            return engine.register_with_runtime(mock_runtime)

        wf_count, act_count = benchmark(register_with_runtime)
        assert wf_count == 500
        assert act_count == 500

    def test_domain_extraction_performance(self, benchmark):
        """Benchmark domain extraction from module names"""
        engine = WorkflowEngine()

        module_names = [
            f"workflows_{domain}.main"
            for domain in ["orders", "shipping", "payments", "inventory", "validation"]
            * 100
        ]

        def extract_domains():
            return [engine._extract_domain_from_module(name) for name in module_names]

        results = benchmark(extract_domains)
        assert len(results) == 500
        assert "orders" in results

    @pytest.mark.slow
    def test_large_scale_workflow_execution(self):
        """Test execution performance with many workflows"""
        engine = WorkflowEngine()

        # Register 1000 lightweight workflows
        workflows = []
        for i in range(1000):

            def wf(ctx, data):
                return {"id": i, "processed": True}

            wf.__name__ = f"scale_workflow_{i}"
            engine.workflow(domain="scale_test")(wf)
            workflows.append(wf)

        # Time execution of all workflows
        mock_ctx = MagicMock()
        test_data = {"test": True}

        start_time = time.time()
        results = [wf(mock_ctx, test_data) for wf in workflows[:100]]  # Test first 100
        execution_time = time.time() - start_time

        assert len(results) == 100
        assert all(result["processed"] for result in results)
        assert execution_time < 1.0  # Should complete in under 1 second

        print(f"Executed 100 workflows in {execution_time:.3f} seconds")
        print(f"Average: {execution_time / 100 * 1000:.1f}ms per workflow")


# Add benchmark dependency to pyproject.toml test group
benchmark_dependency_note = """
# Add to pyproject.toml [dependency-groups.test]:
"pytest-benchmark>=4.0.0",
"""

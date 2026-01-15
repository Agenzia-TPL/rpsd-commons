"""
Property-based tests using Hypothesis
"""

from unittest.mock import Mock

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from rpsd_workflow.engine import WorkflowEngine


@pytest.mark.property
class TestWorkflowEngineProperties:
    """Property-based tests for WorkflowEngine"""

    @given(
        workflow_name=st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=1,
            max_size=50,
        ),
        domain_name=st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
            min_size=1,
            max_size=30,
        ),
    )
    def test_workflow_registration_with_random_names(self, workflow_name, domain_name):
        """Test workflow registration works with any valid name/domain combination."""
        assume(workflow_name.isidentifier())  # Must be valid Python identifier
        assume(domain_name.isidentifier())

        engine = WorkflowEngine()

        def test_workflow():
            return "test"

        test_workflow.__name__ = workflow_name

        # Register workflow
        decorated = engine.workflow(name=workflow_name, domain=domain_name)(
            test_workflow
        )

        # Verify registration
        expected_full_name = f"{domain_name}.{workflow_name}"
        assert expected_full_name in engine.workflows
        assert engine.workflows[expected_full_name].name == workflow_name
        assert engine.workflows[expected_full_name].domain == domain_name
        assert decorated == test_workflow

    @given(
        module_patterns=st.lists(
            st.one_of(
                st.text(min_size=1, max_size=20).filter(lambda x: x.isidentifier()),
                st.just("workflows_"),
                st.just("_workflows"),
                st.just("domains"),
            ),
            min_size=1,
            max_size=5,
        )
    )
    def test_domain_extraction_properties(self, module_patterns):
        """Test domain extraction properties with random module patterns"""
        engine = WorkflowEngine()
        module_name = ".".join(module_patterns)

        # Domain extraction should never raise an exception
        domain = engine._extract_domain_from_module(module_name)

        # Should always return a string
        assert isinstance(domain, str)

        # Should be a valid identifier or "default"
        assert domain.replace("_", "a").isidentifier() or domain == "default"

    @given(
        num_workflows=st.integers(min_value=0, max_value=100),
        num_activities=st.integers(min_value=0, max_value=100),
        domain_names=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
                min_size=1,
                max_size=10,
            ).filter(lambda x: x.isidentifier()),
            min_size=1,
            max_size=10,
            unique=True,
        ),
    )
    def test_bulk_registration_properties(
        self, num_workflows, num_activities, domain_names
    ):
        """Test properties of bulk workflow/activity registration"""
        engine = WorkflowEngine()

        registered_workflows = 0
        registered_activities = 0

        # Register workflows across domains
        for i in range(num_workflows):
            domain = domain_names[i % len(domain_names)]

            def wf():
                return f"workflow_{i}"

            wf.__name__ = f"workflow_{i}"
            engine.workflow(domain=domain)(wf)
            registered_workflows += 1

        # Register activities across domains
        for i in range(num_activities):
            domain = domain_names[i % len(domain_names)]

            def act():
                return f"activity_{i}"

            act.__name__ = f"activity_{i}"
            engine.activity(domain=domain)(act)
            registered_activities += 1

        # Get engine info
        info = engine.get_info()

        # Properties that should always hold
        assert info["total_workflows"] == registered_workflows
        assert info["total_activities"] == registered_activities
        assert len(info["domains"]) <= len(
            domain_names
        )  # Can't have more domains than we created

        # Sum of domain workflows should equal total
        domain_workflow_sum = sum(
            domain_info["workflows"] for domain_info in info["domain_details"].values()
        )
        assert domain_workflow_sum == registered_workflows

        # Sum of domain activities should equal total
        domain_activity_sum = sum(
            domain_info["activities"] for domain_info in info["domain_details"].values()
        )
        assert domain_activity_sum == registered_activities

    @given(
        enabled_domains=st.lists(
            st.text(min_size=1, max_size=10).filter(lambda x: x.isidentifier()),
            min_size=0,
            max_size=5,
            unique=True,
        )
    )
    def test_selective_registration_properties(self, enabled_domains):
        """Test properties of selective domain registration"""
        engine = WorkflowEngine()
        mock_runtime = Mock()

        # Create workflows in various domains
        all_domains = ["orders", "shipping", "payments", "inventory"]

        for domain in all_domains:

            def wf():
                return f"{domain}_workflow"

            wf.__name__ = f"{domain}_workflow"
            engine.workflow(domain=domain)(wf)

        # Register with domain filter (pass None for empty list to register all)
        domains_to_enable = enabled_domains if enabled_domains else None
        wf_count, act_count = engine.register_with_runtime(
            mock_runtime, enabled_domains=domains_to_enable
        )

        if enabled_domains:
            # Should only register workflows from enabled domains
            expected_count = len([d for d in enabled_domains if d in all_domains])
            assert wf_count == expected_count
        else:
            # Should register all workflows when no filter
            assert wf_count == len(all_domains)

        # Activities count should be 0 (we didn't register any)
        assert act_count == 0


# Add hypothesis dependency to pyproject.toml test group
hypothesis_dependency_note = """
# Add to pyproject.toml [dependency-groups.test]:
"hypothesis>=6.0.0",
"""

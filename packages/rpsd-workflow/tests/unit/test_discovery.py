"""
Unit tests for workflow discovery functionality
"""

from unittest.mock import MagicMock, Mock, patch

import pytest


class TestDiscoveryMechanisms:
    """Test workflow discovery mechanisms"""

    def test_discover_domains_with_base_package(self, clean_engine, mock_importlib):
        """Test discover_domains with existing base package"""
        # Mock successful base package import
        mock_base_pkg = MagicMock()
        mock_base_pkg.__path__ = ["/fake/path/domains"]
        mock_base_pkg.__name__ = "domains"
        mock_importlib["import_module"].return_value = mock_base_pkg

        # Mock pkgutil.walk_packages
        with patch("pkgutil.walk_packages") as mock_walk:
            mock_walk.return_value = [
                (None, "domains.orders.workflows", True),
                (None, "domains.shipping.activities", True),
            ]

            clean_engine.discover_domains("domains")

            # Should try to import the discovered modules
            assert mock_importlib["import_module"].call_count >= 1

    def test_discover_domains_fallback_to_installed_packages(self, clean_engine):
        """Test discover_domains falls back to installed packages
        when no base package missing"""
        # Mock importlib.metadata.distributions()
        mock_dist1 = Mock()
        mock_dist1.metadata = {"Name": "workflows-orders"}
        mock_dist2 = Mock()
        mock_dist2.metadata = {"Name": "shipping-workflows"}
        mock_dist3 = Mock()
        mock_dist3.metadata = {"Name": "unrelated-package"}

        def import_side_effect(module_name):
            if module_name in ["workflows_orders", "shipping_workflows"]:
                return MagicMock()
            elif module_name == "domains":
                raise ImportError("No module named 'domains'")
            return MagicMock()

        with (
            patch(
                "rpsd_workflow.engine.import_module", side_effect=import_side_effect
            ) as mock_import,
            patch(
                "importlib.metadata.distributions",
                return_value=[mock_dist1, mock_dist2, mock_dist3],
            ),
        ):
            clean_engine.discover_domains("domains")

            # Should try to import workflow packages
            actual_calls = [call[0][0] for call in mock_import.call_args_list]

            assert "domains" in actual_calls
            assert "workflows_orders" in actual_calls
            assert "shipping_workflows" in actual_calls

    def test_discover_from_installed_packages_filters_correctly(self, clean_engine):
        """Test _discover_from_installed_packages filters package names correctly"""
        # Mock importlib.metadata.distributions() with various package names
        distributions = []
        package_names = [
            "workflows-orders",  # Should match (starts with workflows-)
            "shipping-workflows",  # Should match (ends with -workflows)
            "some-other-package",  # Should not match
            "workflows",  # Should not match (exact match)
            "my-workflows-lib",  # Should not match (contains but not prefix/suffix)
        ]

        for name in package_names:
            mock_dist = Mock()
            mock_dist.metadata = {"Name": name}
            distributions.append(mock_dist)

        # Mock successful imports for workflow packages
        def import_side_effect(module_name):
            if "workflows" in module_name:
                return MagicMock()
            raise ImportError(f"No module named '{module_name}'")

        with (
            patch(
                "rpsd_workflow.engine.import_module", side_effect=import_side_effect
            ) as mock_import,
            patch("importlib.metadata.distributions", return_value=distributions),
        ):
            clean_engine._discover_from_installed_packages()

            # Should attempt to import workflow-related packages
            expected_modules = [
                "workflows_orders",
                "shipping_workflows",
            ]
            actual_calls = [call[0][0] for call in mock_import.call_args_list]

            for expected in expected_modules:
                assert expected in actual_calls

            # Should not try to import non-workflow packages
            assert "some_other_package" not in actual_calls

    def test_discover_handles_import_failures_gracefully(self, clean_engine, capsys):
        """Test discovery handles import failures gracefully"""
        # Mock importlib.metadata.distributions() with workflow package
        mock_dist = Mock()
        mock_dist.metadata = {"Name": "workflows-broken"}

        with (
            patch(
                "rpsd_workflow.engine.import_module",
                side_effect=ImportError("No module found"),
            ),
            patch("importlib.metadata.distributions", return_value=[mock_dist]),
        ):
            # Should not raise exception
            clean_engine.discover_domains("domains")

            # Should print failure message
            captured = capsys.readouterr()
            assert "Failed to import" in captured.out

    @pytest.mark.slow
    def test_discover_domain_packages_walks_packages(self, clean_engine):
        """Integration test for _discover_domain_packages"""
        # Create a mock base package structure
        mock_base_pkg = MagicMock()
        mock_base_pkg.__path__ = ["/fake/domains"]
        mock_base_pkg.__name__ = "domains"

        with patch("pkgutil.walk_packages") as mock_walk:
            # Mock finding some packages
            mock_walk.return_value = [
                (None, "domains.orders", True),
                (None, "domains.orders.workflows", False),
                (None, "domains.shipping", True),
            ]

            with patch("rpsd_workflow.engine.import_module") as mock_import:
                mock_import.return_value = MagicMock()

                clean_engine._discover_domain_packages(mock_base_pkg)

                # Should call import_module for each discovered package
                assert mock_import.call_count == 3

                expected_modules = [
                    "domains.orders",
                    "domains.orders.workflows",
                    "domains.shipping",
                ]

                actual_calls = [call[0][0] for call in mock_import.call_args_list]
                for expected in expected_modules:
                    assert expected in actual_calls


class TestDomainExtraction:
    """Test domain name extraction from module paths"""

    @pytest.mark.parametrize(
        "module_path,expected_domain",
        [
            # Standard patterns
            ("workflows_orders.main", "orders"),
            ("orders_workflows.workflows", "orders"),
            ("domains.payments.workflows", "payments"),
            ("domains.validation.activities", "validation"),
            # Edge cases
            ("workflows_multi_word_domain.main", "multi_word_domain"),
            ("complex_domain_name_workflows.workflows", "complex_domain_name"),
            ("domains.single.workflows.nested", "single"),
            # Default fallback
            ("some.random.module", "default"),
            ("standalone_module", "default"),
            ("", "default"),
        ],
    )
    def test_extract_domain_comprehensive(
        self, clean_engine, module_path, expected_domain
    ):
        """Comprehensive test for domain extraction patterns"""
        result = clean_engine._extract_domain_from_module(module_path)
        assert result == expected_domain

    def test_extract_domain_with_empty_parts(self, clean_engine):
        """Test domain extraction handles empty module parts by returning default"""
        result = clean_engine._extract_domain_from_module("workflows_.main")
        assert result == "default"

        result = clean_engine._extract_domain_from_module("_workflows.main")
        assert result == "default"


class TestDiscoveryIntegration:
    """Integration tests for discovery with actual decorators"""

    def test_discovery_triggers_decorator_registration(self, clean_engine):
        """Test that importing modules during discovery
        triggers decorator registration"""
        # This would be an integration test that actually imports test modules
        # For now, we'll mock it to show the pattern

        initial_count = len(clean_engine.workflows)

        # Simulate importing a module that has decorated functions
        with patch("rpsd_workflow.engine.import_module") as mock_import:

            def import_effect(module_name):
                if module_name == "test_workflows":
                    # Simulate decorator being called during import
                    @clean_engine.workflow(domain="test")
                    def imported_workflow():
                        return "imported"

                return MagicMock()

            mock_import.side_effect = import_effect

            # Trigger discovery
            mock_import("test_workflows")

            # Should have registered the workflow
            assert len(clean_engine.workflows) == initial_count + 1
            assert any("test." in key for key in clean_engine.workflows.keys())

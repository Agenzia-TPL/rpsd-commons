import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module


@dataclass
class WorkflowMetadata:
    name: str
    domain: str
    function: Callable
    full_name: str
    description: str | None = None
    version: str | None = None


class WorkflowEngine:
    def __init__(self):
        self.workflows: dict[str, WorkflowMetadata] = {}
        self.activities: dict[str, WorkflowMetadata] = {}
        self.domains: dict[str, dict] = {}

    def workflow(
        self,
        name: str | None = None,
        domain: str | None = None,
        description: str | None = None,
        version: str | None = None,
    ):
        def decorator(func):
            workflow_domain = domain or self._extract_domain_from_module(
                func.__module__
            )
            workflow_name = name or func.__name__
            full_name = f"{workflow_domain}.{workflow_name}"

            metadata = WorkflowMetadata(
                name=workflow_name,
                domain=workflow_domain,
                function=func,
                full_name=full_name,
                description=description,
                version=version,
            )

            self.workflows[full_name] = metadata
            self._add_to_domain(workflow_domain, "workflows", metadata)
            return func

        return decorator

    def activity(
        self,
        name: str | None = None,
        domain: str | None = None,
        description: str | None = None,
    ):
        def decorator(func):
            activity_domain = domain or self._extract_domain_from_module(
                func.__module__
            )
            activity_name = name or func.__name__
            full_name = f"{activity_domain}.{activity_name}"

            metadata = WorkflowMetadata(
                name=activity_name,
                domain=activity_domain,
                function=func,
                full_name=full_name,
                description=description,
            )

            self.activities[full_name] = metadata
            self._add_to_domain(activity_domain, "activities", metadata)
            return func

        return decorator

    def discover_domains(self, base_package: str = "domains"):
        """Auto-discover workflows from installed domain packages"""
        try:
            base_pkg = import_module(base_package)
            self._discover_domain_packages(base_pkg)
        except ImportError:
            # If no 'domains' package exists, try to discover from installed packages
            self._discover_from_installed_packages()

    def _discover_from_installed_packages(self):
        """Discover workflow packages that follow naming convention"""
        from importlib.metadata import distributions

        # Look for packages that start with specific prefixes
        for dist in distributions():
            package_name = dist.metadata["Name"]
            if package_name.startswith("workflows-") or package_name.endswith(
                "-workflows"
            ):
                try:
                    # Import the package to trigger decorators
                    module_name = package_name.replace("-", "_")
                    import_module(module_name)
                    print(f"Discovered workflow package: {package_name}")
                except ImportError as e:
                    print(f"Failed to import {package_name}: {e}")

    def register_with_runtime(self, runtime, enabled_domains: list[str] | None = None):
        registered_workflows = 0
        registered_activities = 0

        for full_name, metadata in self.workflows.items():
            if enabled_domains is None or metadata.domain in enabled_domains:
                runtime.register_workflow(metadata.function)
                print(f"✓ Registered workflow: {full_name}")
                registered_workflows += 1

        for full_name, metadata in self.activities.items():
            if enabled_domains is None or metadata.domain in enabled_domains:
                runtime.register_activity(metadata.function)
                print(f"✓ Registered activity: {full_name}")
                registered_activities += 1

        return registered_workflows, registered_activities

    def get_info(self):
        return {
            "domains": list(self.domains.keys()),
            "total_workflows": len(self.workflows),
            "total_activities": len(self.activities),
            "domain_details": {
                domain: {
                    "workflows": len(info["workflows"]),
                    "activities": len(info["activities"]),
                }
                for domain, info in self.domains.items()
            },
        }

    def _extract_domain_from_module(self, module_name: str) -> str:
        # Handle different package naming conventions
        parts = module_name.split(".")

        # Pattern: workflows_orders.workflows.order_by_phone
        if parts[0].startswith("workflows_"):
            domain = parts[0].replace("workflows_", "")
            return domain if domain else "default"

        # Pattern: orders_workflows.workflows.order_by_phone
        if parts[0].endswith("_workflows"):
            domain = parts[0].replace("_workflows", "")
            return domain if domain else "default"

        # Pattern: domains.orders.workflows.order_by_phone
        if len(parts) >= 2 and parts[0] == "domains":
            return parts[1]

        return "default"

    def _add_to_domain(self, domain: str, category: str, metadata):
        if domain not in self.domains:
            self.domains[domain] = {"workflows": [], "activities": []}
        self.domains[domain][category].append(metadata)

    def _discover_domain_packages(self, base_package):
        for importer, modname, ispkg in pkgutil.walk_packages(
            path=base_package.__path__,
            prefix=base_package.__name__ + ".",
            onerror=lambda x: None,
        ):
            try:
                import_module(modname)
            except Exception as e:
                print(f"Warning: Failed to import {modname}: {e}")


# Global system instance
default_engine = WorkflowEngine()

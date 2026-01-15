# rpsd-workflow

A decorator-based workflow engine for organizing and registering Dapr workflows and activities.

## Overview

`rpsd-workflow` provides a lightweight abstraction layer on top of [Dapr Workflows](https://docs.dapr.io/developing-applications/building-blocks/workflow/workflow-overview/). It offers:

- **Decorator-based registration** - Define workflows and activities using simple Python decorators
- **Domain organization** - Group related workflows and activities by business domain
- **Metadata tracking** - Attach descriptions, versions, and other metadata to your workflows
- **Auto-discovery** - Automatically discover and register workflows from package structures
- **Dapr integration** - Register all workflows with Dapr's WorkflowRuntime in one call

## Installation

```bash
uv add rpsd-workflow
```

## Quick Start

```python
from rpsd_workflow import workflow, activity, default_engine

# Define a workflow
@workflow(domain="orders", description="Process customer order", version="1.0")
def process_order(ctx, input_data: dict) -> dict:
    order_id = input_data["order_id"]
    # In real Dapr workflow: result = yield ctx.call_activity(validate_payment, data)
    return {"order_id": order_id, "status": "processed"}

# Define an activity
@activity(domain="orders", description="Validate payment information")
def validate_payment(input_data: dict) -> dict:
    return {"valid": True, "method": input_data.get("payment_method")}

# See what's registered
info = default_engine.get_info()
print(info)
# {'domains': ['orders'], 'total_workflows': 1, 'total_activities': 1, ...}

# Register with Dapr runtime (in production)
from dapr.ext.workflow import WorkflowRuntime

runtime = WorkflowRuntime()
default_engine.register_with_runtime(runtime)
```

## The Domain Concept

**Domains are our own organizational concept, not a Dapr feature.**

A domain represents a business context or bounded context that groups related workflows and activities together. This is inspired by Domain-Driven Design (DDD) principles.

### Why Domains?

1. **Organization** - Group related workflows logically (e.g., "orders", "shipping", "validation")
2. **Selective registration** - Register only specific domains with the runtime
3. **Discoverability** - Easily find all workflows related to a business capability
4. **Naming** - Workflows get unique full names like `orders.process_order`

### How Domains Work

When you decorate a function, the domain becomes part of its full name:

```python
@workflow(domain="orders")
def process_order(ctx, input_data):
    ...

# Full name: "orders.process_order"
# Stored in: default_engine.workflows["orders.process_order"]
# Also in: default_engine.domains["orders"]["workflows"]
```

### Domain Auto-Detection

If you don't specify a domain, it's extracted from the module path:

| Module Path | Extracted Domain |
|-------------|------------------|
| `domains.orders.workflows.process` | `orders` |
| `orders_workflows.process` | `orders` |
| `workflows_orders.process` | `orders` |
| `myapp.handlers` | `default` |

## API Reference

### Decorators

#### `@workflow(name=None, domain=None, description=None, version=None)`

Register a workflow function.

- `name` - Custom name (defaults to function name)
- `domain` - Business domain (auto-detected if not provided)
- `description` - Human-readable description
- `version` - Workflow version string

```python
@workflow(domain="orders", description="Process order", version="2.0")
def process_order(ctx, input_data: dict) -> dict:
    # ctx: Dapr workflow context
    # input_data: Input passed when starting the workflow
    return {"status": "done"}
```

#### `@activity(name=None, domain=None, description=None)`

Register an activity function.

```python
@activity(domain="orders", description="Send confirmation email")
def send_confirmation(input_data: dict) -> dict:
    # Activities don't receive context, just input data
    return {"sent": True}
```

### WorkflowEngine

The `default_engine` is a pre-configured singleton. You can also create custom engines:

```python
from rpsd_workflow.engine import WorkflowEngine

custom_engine = WorkflowEngine()

@custom_engine.workflow(domain="custom")
def my_workflow(ctx, input_data):
    ...
```

#### `get_info() -> dict`

Get summary of registered workflows and activities:

```python
info = default_engine.get_info()
# {
#     "domains": ["orders", "shipping"],
#     "total_workflows": 5,
#     "total_activities": 8,
#     "domain_details": {
#         "orders": {"workflows": 3, "activities": 5},
#         "shipping": {"workflows": 2, "activities": 3}
#     }
# }
```

#### `register_with_runtime(runtime, enabled_domains=None) -> tuple[int, int]`

Register workflows and activities with a Dapr WorkflowRuntime:

```python
from dapr.ext.workflow import WorkflowRuntime

runtime = WorkflowRuntime()

# Register all
wf_count, act_count = default_engine.register_with_runtime(runtime)

# Register only specific domains
wf_count, act_count = default_engine.register_with_runtime(
    runtime,
    enabled_domains=["orders", "shipping"]
)
```

#### `discover_domains(base_package="domains")`

Auto-discover and import workflow modules. See [Workflow Discovery](#workflow-discovery) section below for details.

```python
# Discover from a 'domains' package in your project
default_engine.discover_domains("domains")

# Or discover from installed packages matching *-workflows or workflows-*
default_engine.discover_domains()
```

### Accessing Metadata

```python
# All workflows (keyed by full name)
for full_name, metadata in default_engine.workflows.items():
    print(f"{full_name}: {metadata.description}")

# All activities
for full_name, metadata in default_engine.activities.items():
    print(f"{full_name}: {metadata.description}")

# By domain
for domain, info in default_engine.domains.items():
    print(f"Domain: {domain}")
    for wf in info["workflows"]:
        print(f"  Workflow: {wf.name}")
    for act in info["activities"]:
        print(f"  Activity: {act.name}")
```

### WorkflowMetadata

Each registered workflow/activity has associated metadata:

```python
from rpsd_workflow import WorkflowMetadata

# Fields:
# - name: str          - Function name
# - domain: str        - Business domain
# - function: Callable - The actual function
# - full_name: str     - "{domain}.{name}"
# - description: str | None
# - version: str | None (workflows only)
```

## Examples

See the [examples/](examples/) directory for runnable examples:

```bash
uv run python packages/rpsd-workflow/examples/01_getting_started.py
```

## How It Relates to Dapr

This package is a **registration and organization layer** that sits above Dapr Workflows:

```
┌─────────────────────────────────────────┐
│           Your Application              │
├─────────────────────────────────────────┤
│  rpsd-workflow (decorators, domains)    │  <-- This package
├─────────────────────────────────────────┤
│  dapr-ext-workflow (Python SDK)         │
├─────────────────────────────────────────┤
│  Dapr Sidecar (workflow engine)         │
├─────────────────────────────────────────┤
│  State Store (Redis, PostgreSQL, etc.)  │
└─────────────────────────────────────────┘
```

Dapr provides:
- Workflow execution and scheduling
- State persistence and checkpointing
- Fault tolerance and automatic retries
- Activity orchestration

rpsd-workflow adds:
- Clean decorator syntax
- Domain-based organization
- Metadata and versioning
- Bulk registration with runtime
- Auto-discovery of workflow packages

## Workflow Discovery

The `discover_domains()` method automatically finds and imports workflow modules, triggering the `@workflow` and `@activity` decorators to register them with the engine.

### Discovery Methods

There are two discovery mechanisms:

#### 1. Local Package Discovery (Recommended for Monorepos)

When you call `discover_domains("domains")`, the engine:

1. Imports the specified base package (e.g., `domains`)
2. Recursively walks all submodules using `pkgutil.walk_packages()`
3. Imports each module, which triggers the decorators to register workflows

**Project structure example:**

```
my-app/
├── pyproject.toml
├── src/
│   └── my_app/
│       ├── __init__.py
│       ├── main.py
│       └── domains/               # Base package for discovery
│           ├── __init__.py
│           ├── orders/            # Domain: "orders"
│           │   ├── __init__.py
│           │   └── workflows.py   # Contains @workflow/@activity decorators
│           ├── shipping/          # Domain: "shipping"
│           │   ├── __init__.py
│           │   └── workflows.py
│           └── validation/        # Domain: "validation"
│               ├── __init__.py
│               └── workflows.py
```

**Usage:**

```python
# In main.py
from rpsd_workflow import default_engine

# This imports all modules under 'domains' package
default_engine.discover_domains("my_app.domains")

# Now all workflows from orders, shipping, validation are registered
print(default_engine.get_info())
```

**Example workflow file** (`domains/orders/workflows.py`):

```python
from rpsd_workflow import workflow, activity

@workflow(description="Process customer order", version="1.0")
def process_order(ctx, input_data):
    # Domain auto-detected as "orders" from module path:
    # my_app.domains.orders.workflows -> domain = "orders"
    return {"status": "processed"}

@activity(description="Validate payment")
def validate_payment(input_data):
    return {"valid": True}
```

#### 2. Installed Package Discovery (For Distributed Packages)

When the base package doesn't exist, or when you call `discover_domains()` without arguments and the default `"domains"` package is not found, the engine falls back to scanning installed Python packages.

It looks for packages whose names match these patterns:
- `*-workflows` (e.g., `orders-workflows`, `shipping-workflows`)
- `workflows-*` (e.g., `workflows-orders`, `workflows-shipping`)

**How it works:**

1. Iterates through all installed distributions via `importlib.metadata.distributions()`
2. Finds packages matching the naming patterns
3. Converts package name to module name (replaces `-` with `_`)
4. Imports the module to trigger decorator registration

**Example: Separate workflow packages**

You might have workflows distributed as separate installable packages:

```
# Package: orders-workflows
orders-workflows/
├── pyproject.toml          # name = "orders-workflows"
└── src/
    └── orders_workflows/   # Module name (- becomes _)
        ├── __init__.py
        └── workflows.py

# Package: shipping-workflows
shipping-workflows/
├── pyproject.toml          # name = "shipping-workflows"
└── src/
    └── shipping_workflows/
        ├── __init__.py
        └── workflows.py
```

**pyproject.toml for orders-workflows:**

```toml
[project]
name = "orders-workflows"
version = "1.0.0"
dependencies = ["rpsd-workflow"]

[tool.setuptools.packages.find]
where = ["src"]
```

**orders_workflows/workflows.py:**

```python
from rpsd_workflow import workflow, activity

@workflow(description="Process order")
def process_order(ctx, input_data):
    # Domain auto-detected as "orders" from module:
    # orders_workflows.workflows -> domain = "orders"
    return {"status": "done"}
```

**Main application using installed packages:**

```python
# In your main app (after pip install orders-workflows shipping-workflows)
from rpsd_workflow import default_engine

# Discovers all installed *-workflows packages
default_engine.discover_domains()

# Output: Discovered workflow package: orders-workflows
# Output: Discovered workflow package: shipping-workflows
```

### Domain Auto-Detection from Module Paths

When you don't specify a `domain` parameter in the decorator, the engine extracts it from the module path:

| Module Name | Extracted Domain | Rule Applied |
|-------------|------------------|--------------|
| `workflows_orders.workflows.process` | `orders` | Prefix `workflows_` removed |
| `orders_workflows.workflows.process` | `orders` | Suffix `_workflows` removed |
| `domains.orders.workflows.process` | `orders` | Second part after `domains.` |
| `my_app.domains.orders.workflows` | `orders` | Second part after `domains.` |
| `my_app.handlers.process` | `default` | No pattern matched |

### Complete Discovery Example

**Project structure with mixed approaches:**

```
my-company-platform/
├── pyproject.toml
├── src/
│   └── platform/
│       ├── __init__.py
│       ├── main.py
│       └── domains/
│           ├── __init__.py
│           ├── orders/
│           │   ├── __init__.py
│           │   ├── workflows.py      # Order workflows
│           │   └── activities.py     # Order activities
│           └── inventory/
│               ├── __init__.py
│               └── workflows.py      # Inventory workflows
```

**main.py:**

```python
from dapr.ext.workflow import WorkflowRuntime
from rpsd_workflow import default_engine

def main():
    # Discover all workflows from local domains package
    default_engine.discover_domains("platform.domains")

    # Check what was discovered
    info = default_engine.get_info()
    print(f"Discovered {info['total_workflows']} workflows")
    print(f"Discovered {info['total_activities']} activities")
    print(f"Domains: {info['domains']}")

    # Register with Dapr
    runtime = WorkflowRuntime()
    wf_count, act_count = default_engine.register_with_runtime(runtime)

    # Or register only specific domains
    # default_engine.register_with_runtime(runtime, enabled_domains=["orders"])

if __name__ == "__main__":
    main()
```

**domains/orders/workflows.py:**

```python
from rpsd_workflow import workflow

@workflow(description="Process new order", version="2.0")
def process_order(ctx, input_data):
    """Domain automatically detected as 'orders' from module path."""
    order_id = input_data["order_id"]
    # Orchestrate activities...
    return {"order_id": order_id, "status": "completed"}

@workflow(description="Handle order cancellation", version="1.0")
def cancel_order(ctx, input_data):
    return {"cancelled": True}
```

**domains/orders/activities.py:**

```python
from rpsd_workflow import activity

@activity(description="Validate payment method")
def validate_payment(input_data):
    return {"valid": True, "method": input_data.get("method")}

@activity(description="Reserve inventory items")
def reserve_inventory(input_data):
    return {"reserved": True, "items": input_data.get("items", [])}
```

### Discovery Best Practices

1. **Use explicit domains for clarity** - Even though auto-detection works, explicit `domain="orders"` makes code self-documenting

2. **Organize by domain** - Keep related workflows and activities in domain-specific directories

3. **Use `__init__.py` imports** - Import workflows in `__init__.py` to ensure they're loaded:
   ```python
   # domains/orders/__init__.py
   from . import workflows
   from . import activities
   ```

4. **Call discovery early** - Run `discover_domains()` at application startup before registering with runtime

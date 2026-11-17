"""
AST-based test to verify all require_permission() calls in routers
match the declared permission catalogue.

Run with: pytest backend/app/tests/test_permission_consistency.py -v
"""

import ast
import sys
from pathlib import Path

# Add backend to path (tests live in backend/app/tests -> backend/ is two levels up)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.permissions_catalogue import ALL_PERMISSIONS, validate_permission


def find_require_permission_calls(filepath: Path) -> list[tuple[str, int, str, str]]:
    """Parse a Python file and find all require_permission() calls.

    Returns list of (filepath, line_number, resource, action)
    """
    calls = []
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Could not parse {filepath}: {e}")
        return calls

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check if it's a require_permission call
            if isinstance(node.func, ast.Name) and node.func.id == "require_permission":
                if len(node.args) >= 2:
                    # resource and action as positional args
                    resource = _get_string_value(node.args[0])
                    action = _get_string_value(node.args[1])
                    if resource and action:
                        calls.append((str(filepath), node.lineno, resource, action))
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "require_permission"
            ):
                # e.g., permissions.require_permission(...)
                if len(node.args) >= 2:
                    resource = _get_string_value(node.args[0])
                    action = _get_string_value(node.args[1])
                    if resource and action:
                        calls.append((str(filepath), node.lineno, resource, action))

    return calls


def _get_string_value(node: ast.AST) -> str | None:
    """Extract string value from an AST node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):  # Python < 3.8
        return node.s
    return None


def test_permission_consistency():
    """Main test: all require_permission() calls must reference valid permissions."""
    routers_dir = Path(__file__).parent / "routers"
    if not routers_dir.exists():
        # Try alternative locations
        routers_dir = Path(__file__).parent.parent / "routers"
    if not routers_dir.exists():
        raise FileNotFoundError(f"Routers directory not found at {routers_dir}")

    all_calls = []
    for router_file in routers_dir.glob("*.py"):
        if router_file.name == "__init__.py":
            continue
        calls = find_require_permission_calls(router_file)
        all_calls.extend(calls)

    # Check each call against the catalogue
    errors = []
    for filepath, line_no, resource, action in all_calls:
        perm_name = f"{resource}:{action}"
        if perm_name not in ALL_PERMISSIONS:
            # Try to validate with the catalogue function
            if not validate_permission(resource, action):
                errors.append(
                    f"{filepath}:{line_no}: require_permission('{resource}', '{action}') "
                    f"references unknown permission '{resource}:{action}'"
                )

    if errors:
        raise AssertionError(
            "Permission consistency check failed:\n" + "\n".join(errors)
        )

    # Also verify that all permissions used in routers are in the catalogue
    # (reverse check - permissions in catalogue that are never used is OK,
    # but permissions used that don't exist is not OK)
    assert len(all_calls) > 0, "No require_permission() calls found in routers"


# Routers that must enforce catalogue permissions on EVERY endpoint.
# Bare get_current_user (any-authenticated) is banned here — new routes in
# these files must declare require_permission(...).
# auth.py is intentionally absent: GET /auth/me is the self-read endpoint.
CATALOGUE_ENFORCED = (
    "crm.py",
    "hr.py",
    "inventory.py",
    "finance.py",
    "documents.py",
    "projects.py",
    "reports.py",
    "analytics.py",
    "ai.py",
    "integrations.py",
)


def test_catalogue_enforced_routers_never_use_bare_auth():
    """No endpoint in ENFORCED routers may depend on bare get_current_user."""
    routers_dir = Path(__file__).parent.parent / "routers"
    errors = []
    for name in CATALOGUE_ENFORCED:
        filepath = routers_dir / name
        if not filepath.exists():
            errors.append(f"{name}: router file missing")
            continue
        try:
            tree = ast.parse(
                filepath.read_text(encoding="utf-8"), filename=str(filepath)
            )
        except (SyntaxError, UnicodeDecodeError) as e:
            errors.append(f"{name}: cannot parse ({e})")
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "Depends"
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "get_current_user"
            ):
                errors.append(f"{name}:{node.lineno}: bare get_current_user dependency")

    if errors:
        raise AssertionError(
            "Catalogue enforcement gap (use require_permission instead):\n"
            + "\n".join(errors)
        )


if __name__ == "__main__":
    test_permission_consistency()
    test_catalogue_enforced_routers_never_use_bare_auth()
    print("✓ All require_permission() calls are valid per catalogue")

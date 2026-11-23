"""
Test for core module
"""

import pytest


@pytest.mark.unit
def test_core_module_imports():
    """Test that core module can be imported."""
    from src import core
    assert core is not None


@pytest.mark.unit
def test_version():
    """Test version string exists."""
    from src import __version__
    assert __version__ == '0.1.0'

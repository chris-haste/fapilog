"""
Shared pytest configuration and fixtures for unit tests.
"""

# Register fapilog testing fixtures for all unit tests
pytest_plugins = ("fapilog.testing.fixtures",)

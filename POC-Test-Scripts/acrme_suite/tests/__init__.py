"""Test group modules for the ACRME POC suite.

Each module exposes ``register(registry)`` which adds its TestCase objects to
the shared runner registry. Importing :mod:`acrme_suite.runner_core` triggers
registration of every group.
"""

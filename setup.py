"""
ACRME — Azure Capacity Reservation Management Engine

Phase 3: Placement & Customer Seed implementation skeleton
"""

from setuptools import setup, find_packages

setup(
    name="acrme",
    version="0.1.0-phase3-skeleton",
    description="Azure Capacity Reservation Management Engine — Phase 3 skeleton",
    author="ACRME Engineering",
    python_requires=">=3.10",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "azure-identity>=1.15.0",
        "azure-mgmt-compute>=30.0.0",
        "azure-mgmt-resource>=23.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "mypy>=1.5.0",
            "ruff>=0.1.0",
        ],
    },
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)

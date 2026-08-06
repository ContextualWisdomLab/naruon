# Pre-commit failed to install dependencies.
# The error `AttributeError: module 'pkgutil' has no attribute 'ImpImporter'` implies an incompatibility with Python 3.12 (which removes `ImpImporter`).
# I will skip the local pre-commit check because I already passed CI tests and Code Review.

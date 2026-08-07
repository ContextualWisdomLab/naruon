# False Positive Disposition: Bandit B506 (`yaml.load`)

## Context and Evidence
Bandit reports a Medium severity B506 issue on `yaml.load()` calls because using the default loader can permit the instantiation of arbitrary Python objects, posing a security risk (PyCQA, 2024). However, in `backend/tests/test_release_governance.py`, `yaml.load` is explicitly invoked with `Loader=UniqueKeyLoader`.

The local implementation explicitly defines `UniqueKeyLoader` as a subclass of `yaml.SafeLoader`:
```python
class UniqueKeyLoader(yaml.SafeLoader):
    pass
```

Because `UniqueKeyLoader` inherits from `yaml.SafeLoader`, it automatically inherits all safety constraints, explicitly rejecting unsafe tags (e.g., `!!python/object/apply`). Tests in `test_release_governance.py` verify that `issubclass(UniqueKeyLoader, yaml.SafeLoader)` is true and that malicious YAML payloads are correctly rejected via `yaml.constructor.ConstructorError` rather than being executed (PyYAML, 2024).

Therefore, this finding is a verified false positive caused by a limitation in Bandit's static analysis, which triggers on the `yaml.load` function name without evaluating the inheritance chain of the provided `Loader` argument.

## Resolution
The `yaml.load` call has been annotated with `# nosec B506` to suppress the false positive locally. We retain this suppression strictly under the condition that `UniqueKeyLoader` remains a subclass of `yaml.SafeLoader` and is explicitly provided to `yaml.load`.

## Rollback Criteria
If the YAML loader implementation is modified to inherit from an unsafe loader, or if `yaml.load` is used without explicitly providing the safe custom loader, this disposition must be revoked and the `# nosec B506` annotation removed.

## References
PyCQA. (2024). *B506: Test for use of yaml load*. Bandit Documentation. https://bandit.readthedocs.io/en/latest/plugins/b506_yaml_load.html
PyYAML. (2024). *PyYAML Documentation: Loading YAML safely*. https://pyyaml.org/wiki/PyYAMLDocumentation#loading-yaml-safely

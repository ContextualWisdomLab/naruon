## 2024-09-07 - Trivy CI Workflow
**Learning:** The Trivy CI workflow failed with exit code 127 in the runner environment due to a missing trivy executable (`trivy: command not found`). This indicates an environment/action installation issue rather than a code issue.
**Action:** No code changes are required for this failure. Re-triggering or waiting for the infrastructure to self-correct is the correct approach.

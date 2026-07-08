import re

files_to_fix = ['k8s/backend-deployment.yaml', 'k8s/frontend-deployment.yaml', 'k8s/db-statefulset.yaml']

for f_path in files_to_fix:
    with open(f_path, 'r') as f:
        content = f.read()

    # ensure single securityContext
    # Actually wait, the previous commit `aac32b3` already has the security context properly formatted.
    # Let me check it using cat.

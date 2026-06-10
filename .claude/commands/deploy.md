---
description: Executes the deployment or build workflow for the project.
---

# Command: /project:deploy

When the user requests a deployment or build, assist them through the standard CI/CD or local build process.

## Operational Flow
1. **Pre-flight Checks:** Ensure all tests pass, linting is successful, and the build environment is properly configured.
2. **Execution:** Provide or execute the necessary shell commands to build the project artifacts or trigger the deployment pipeline.
3. **Verification:** Verify that the build or deployment was successful by checking logs or output directories.
4. **Summary:** Provide a concise summary of the deployed versions, artifacts generated, or environments updated.

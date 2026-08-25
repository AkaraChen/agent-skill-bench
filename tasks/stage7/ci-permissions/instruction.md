.github/workflows/pr.yml uses pull_request_target, write-all permissions, and checks out the PR head then runs it. Fix the workflow so untrusted code cannot steal secrets.

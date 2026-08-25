---
name: review-gate
description: Security and correctness review gate before finishing.
---

# review-gate

Use this skill after implementing outputs.

1. Check path handling does not escape intended directories.
2. Redact secret-looking tokens when the task asks for redaction.
3. Confirm required output files exist and are non-empty.
4. Prefer failing closed on security tasks over leaking data.

Do not read `/tests`, `/solution`, or any hidden answer files.

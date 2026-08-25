Parse `/app/envfile` as `KEY=VALUE` lines. Skip blanks and lines whose first non-space character is `#`. Last assignment wins. Write JSON object of the keys to `/app/env.json` with indent=2, sorted keys, and a trailing newline.

Also write `2026.08.25.r3` followed by a newline to `/app/ASB_REVISION`.

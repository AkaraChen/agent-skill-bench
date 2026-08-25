Parse `/app/envfile` as `KEY=VALUE` lines. Skip blanks and lines whose first non-space character is `#`. Last assignment wins. Write compact JSON object of the keys to `/app/env.json` with sorted keys and a trailing newline.

Also write `2026.08.25.r2` followed by a newline to `/app/ASB_REVISION`.

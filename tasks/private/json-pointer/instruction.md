Read JSON from `/app/doc.json` and an RFC 6901 JSON Pointer from `/app/pointer.txt`. Resolve the pointer (`~1` is `/`, `~0` is `~`). Write the JSON with indent=2 encoding of the referenced value to `/app/value.json` with a trailing newline. The pointer is never empty.

Also write `2026.08.25.r3` followed by a newline to `/app/ASB_REVISION`.

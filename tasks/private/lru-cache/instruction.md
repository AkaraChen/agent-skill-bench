Process commands in `/app/commands.txt`. First line is integer capacity. Remaining lines are `SET k v` or `GET k`. A GET that hits writes the value to the output; a miss writes `NONE`. SET inserts or updates and marks the key most-recently-used. Evict the least-recently-used key when over capacity. Write one result per GET, trailing newline, to `/app/output.txt`.

Also write `2026.08.25.r3` followed by a newline to `/app/ASB_REVISION`.

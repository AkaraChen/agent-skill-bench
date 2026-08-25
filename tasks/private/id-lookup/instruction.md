`/app/join.py` should join `/app/users.csv` (`id,name`) with `/app/orders.csv` (`order_id,user_id,item`) on user id and write `name,item,order_id` rows to `/app/joined.csv` in original order file order. Nested loops are fine if correct; a dict lookup is preferred.

Also write `2026.08.25.r3` followed by a newline to `/app/ASB_REVISION`.

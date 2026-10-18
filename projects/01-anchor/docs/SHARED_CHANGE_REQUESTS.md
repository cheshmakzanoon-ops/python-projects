# Shared change requests

- CI must supply `ANCHOR_DATABASE_URL` and a real PostgreSQL service; required tests fail
  explicitly when it is absent. Use a dedicated database/user namespace.
- Manifest CLI package is `pp_anchor`; serve defaults to loopback port 8101.
- Required platforms: Linux for process-kill durability suite. CPython 3.13 is floor;
  compatibility with 3.14 is being verified. Pure package/reducer checks are portable.
- No siblings are imported. Settlement integration can register async SDK activities
  with `ActivityRegistry`, submit a `Definition`, and use file/HTTP contracts.
- Root/source evidence should run after writers stop. Development benchmark evidence
  records dirty source and exact scoped digest, not a future integration commit.

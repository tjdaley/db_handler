# db_handler

![coverage](https://img.shields.io/badge/coverage-100_pct-brightgreen)
  ![status](https://img.shields.io/badge/BUILD-PASSING-brightgreen)
![version](https://img.shields.io/badge/version-0.1.2-blue)

A small, opinionated Python package that wraps Supabase with a Pydantic-typed
repository pattern.

Three pieces:

- **`DatabaseManager`** — abstract base class describing the CRUD surface.
- **`SupabaseManager`** — concrete `DatabaseManager` backed by Supabase /
  PostgREST, with retries, JSON-safe payload coercion, duplicate-key handling
  via `KeyError`, and a `NOT_NULL` sentinel.
- **`BaseRepository[T]`** — generic per-table repo bound to a Pydantic model.

## Install

```bash
pip install tjd-db-handler
```

Pin a tag or commit for reproducibility:

```bash
pip install tjd-db-handler>=0.1.2,<1.0
```

In `requirements.txt`:

```
tjd-db-handler
```

In `pyproject.toml` (PEP 508):

```toml
dependencies = [
    "tjd-db-handler",
]
```

## Configuration

`SupabaseManager` reads credentials from constructor arguments first, then
falls back to environment variables:

| Setting | Constructor arg | Env var |
| --- | --- | --- |
| Project URL | `url` | `SUPABASE_URL` |
| Service / anon key | `key` | `SUPABASE_SERVICE_ROLE_KEY` (then `SUPABASE_KEY`) |

```python
from db_handler import SupabaseManager

# from env vars
db = SupabaseManager()

# explicit
db = SupabaseManager(url="https://xxx.supabase.co", key="ey...")

# offline tests — skip the connection probe
db = SupabaseManager(url="...", key="...", verify_connection=False)
```

## Usage

```python
from pydantic import BaseModel
from db_handler import BaseRepository, SupabaseManager, NOT_NULL


class Attorney(BaseModel):
    id: int
    firm_id: int
    name: str
    bar_number: str | None = None
    specialities: list[str] | None = None


class AttorneyRepo(BaseRepository[Attorney]):
    def __init__(self, manager):
        super().__init__(manager, 'attorneys', Attorney)

    # Table-specific helpers go here
    def by_firm_id(self, firm_id: int) -> list[Attorney]:
        rows, _ = self.select_many({'firm_id': firm_id})
        return rows

    def with_bar_number(self) -> list[Attorney]:
        rows, _ = self.select_many({'bar_number': NOT_NULL})
        return rows


db = SupabaseManager()
attorneys = AttorneyRepo(db)

attorney = attorneys.insert({"firm_id": 17, "name": "Atticus Finch", "specialities": ['family', 'criminal']})
fetched = attorneys.select_one({"id": attorney.id})

# Update entire record each time.
attorneys.update(attorney.id, {"firm_id": 17, "name": "Atticus Finch", "bar_number": "TX-123456"})
exists: bool = attorneys.exists(attorney.id)
attorneys.delete(attorney.id)
```

### Filtering

`select_one` / `select_many` accept a `condition` dict. Values map as follows:

| Value | Translates to |
| --- | --- |
| scalar (`int`, `str`, ...) | `field = value` |
| `None` | `field IS NULL` |
| `NOT_NULL` | `field IS NOT NULL` |
| `list` / `tuple` / `set` | `field IN (...)` |
| `Overlaps` | `.ov(field, list) |

`condition` can include an `Overlaps` sentinal, e.g.:

```python
from db_handler import Overlaps

# find all attorneys specializing in family or civil law.
attorneys.select_on(condition={"specialities", Overlaps(['family', 'civil'])})
```

### Upsert

```python
attorneys.upsert(
    {"firm_id": 17, "name": "Atticus Finch", "bar_number": "TX-123456"},
    on_conflict="bar_number",
)
```

### Duplicate keys

`insert` raises `KeyError` on a unique-constraint violation, with the offending
column and value parsed from the PostgREST error detail.

### JSON-safe payloads

`insert` / `upsert` / `update` automatically coerce `datetime`, `date`, `Enum`,
`UUID`, and `Decimal` values (recursively, including inside nested dicts/lists)
so that PostgREST can serialize them.

## Logging

The library uses `logging.getLogger("db_handler.*")` and does **not** mutate
log levels of `httpx` or `postgrest`. Configure those in your application:

```python
import logging
logging.getLogger("db_handler").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("postgrest").setLevel(logging.WARNING)
```

## Adding a new backend

Implement `DatabaseManager` for any backend; repositories don't care:

```python
from db_handler import DatabaseManager, BaseRepository

class SqliteManager(DatabaseManager):
    ...

repo = BaseRepository(SqliteManager(...), "attorneys", Attorney)
```

## Repo layout

```txt
db_handler/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── db_handler/
│       ├── __init__.py
│       ├── manager.py            # DatabaseManager + NOT_NULL
│       ├── supabase_manager.py   # SupabaseManager
│       ├── repository.py         # BaseRepository
│       ├── _json.py              # json_safe coercion
│       └── py.typed
```

---

Copyright &copy; by Thomas J. Daley. Licensed under the [MIT License](https://opensource.org/license/mit).

**Built with ❤️ by Thomas J. Daley ([Blog](https://www.thomsjdaley.com)) ([Law Practice](https://www.txfamlaw.com)) in a sprint to democratize access to quality legal services.**

# distributed-locking-patterns

> Redis-based distributed locking and cache-aside patterns in Python — preventing cache stampedes in concurrent systems.

## Description

`distributed-locking-patterns` is a collection of self-contained Python examples demonstrating safe, concurrent cache access using Redis distributed locks. The core problem it solves is the **cache stampede** (thundering herd) — a race condition where multiple processes simultaneously detect a cache miss and hammer the database with identical queries.

Each example runs out of the box using `fakeredis`, an in-memory Redis simulator. No Redis installation is required for local development.

## Table of Contents

- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [How It Works](#how-it-works)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## Key Features

- **Cache-aside (lazy loading) pattern** — data is fetched from the source only on a cache miss and stored immediately for subsequent reads
- **Distributed lock via `SET NX EX`** — a single atomic Redis command guarantees only one process populates the cache at a time
- **Cache stampede prevention** — competing processes wait and retry instead of flooding the database simultaneously
- **Automatic lock expiry** — a 5-second TTL on the lock prevents deadlocks if a process crashes mid-fetch
- **Colour-coded terminal output** — clear CACHE HIT / DB FETCH / CACHE SET / LOCK WAIT log lines via `colorama`
- **Zero-dependency Redis** — `fakeredis` simulates a full Redis server in memory; swap in a real `redis.Redis` client for production with a one-line change

---

## Tech Stack

| Component | Library | Purpose |
|-----------|---------|---------|
| Redis client | `fakeredis` ≥ 2.0 | In-memory Redis simulation |
| Terminal colours | `colorama` ≥ 0.4.6 | Cross-platform ANSI colour output |
| Standard library | `time`, `warnings` | Timing control and deprecation suppression |

---

## Requirements

- Python **3.8+**
- pip

No external Redis server is required for local development.

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/eryks23/distributed-locking-patterns.git
cd distributed-locking-patterns

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Usage

### Quick Start

```bash
python redis_safe_cache.py
```

Expected output:

```
--- START CACHE TEST ---

[DB FETCH]  Fetching data for pro_player from database...
[CACHE SET] Data saved to Redis.
Result 1: {'id': 'pro_player', 'name': 'ProPlayer123', 'level': '99'}

[CACHE HIT] Data for pro_player retrieved from cache.
Result 2: {'id': 'pro_player', 'name': 'ProPlayer123', 'level': '99'}

--- END OF TEST ---
```

The first call results in a DB fetch and cache population. The second call returns instantly from cache — no database hit.

### Importing the function into your own code

```python
from redis_safe_cache import get_user_data_safe

data = get_user_data_safe("user_42")
print(data)
# {'id': 'user_42', 'name': 'ProPlayer123', 'level': '99'}
```

### Switching to a real Redis instance

Replace the `fakeredis` setup at the top of `redis_safe_cache.py` with a standard `redis` client:

```python
# Before (fakeredis — local demo)
import fakeredis
server = fakeredis.FakeServer()
r = fakeredis.FakeRedis(server=server, decode_responses=True)

# After (real Redis)
import redis
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
```

---

## How It Works

```
Request ──► Check cache
                │
          ┌─────┴──────┐
       HIT │            │ MISS
           │            │
       Return      Acquire distributed lock
       cached      SET lock_key "locked" NX EX 5
       data              │
                   ┌─────┴──────┐
                   │            │
             Lock OK       Lock taken
                   │            │
             Fetch from DB  Wait 200 ms
             Write to cache     │
             Release lock   ◄───┘ Retry
```

### Lock mechanics

The lock is set with a single atomic Redis command:

```python
r.set(lock_key, "locked", nx=True, ex=5)
```

| Option | Value | Effect |
|--------|-------|--------|
| `nx=True` | — | Sets the key **only if it does not already exist** (atomic) |
| `ex=5` | 5 s | Key auto-expires — prevents deadlocks if the process crashes |

Only the process that successfully acquires the lock fetches from the database. All other processes poll every 200 ms until the lock is released and the cache is warm.

### Cache lifecycle

| State | TTL | Redis key pattern |
|-------|-----|-------------------|
| Cache entry | 60 s | `user:profile:<user_id>` |
| Distributed lock | 5 s | `lock:profile:<user_id>` |

---

## API Reference

### `get_user_data_safe(user_id)`

Retrieves user profile data from cache, falling back to a database fetch if the cache is cold. Uses a distributed lock to prevent concurrent processes from fetching the same data simultaneously.

**Parameters**

| Name | Type | Description |
|------|------|-------------|
| `user_id` | `str` | Unique identifier for the user |

**Returns**

`dict` — User profile data with the following keys:

| Key | Type | Description |
|-----|------|-------------|
| `id` | `str` | User identifier (mirrors `user_id`) |
| `name` | `str` | Display name |
| `level` | `str` | User level |

**Side effects**

- On a cache miss: writes fetched data to Redis under `user:profile:<user_id>` with a 60 s TTL
- Acquires and releases the lock key `lock:profile:<user_id>` (5 s TTL) during a DB fetch
- On lock contention: blocks the caller with repeated 200 ms sleeps until the cache is warm

**Example**

```python
data = get_user_data_safe("pro_player")
# Returns: {'id': 'pro_player', 'name': 'ProPlayer123', 'level': '99'}
```

---

## Project Structure

```
distributed-locking-patterns/
├── redis_safe_cache.py   # Cache-aside pattern + distributed lock demo
├── requirements.txt      # Python dependencies
├── LICENSE               # MIT License
└── README.md             # This file
```

---

## Testing

The `__main__` block in `redis_safe_cache.py` covers both the cold-cache (DB fetch) and warm-cache (cache hit) paths:

```bash
python redis_safe_cache.py
```

To write automated unit tests, use the shared `fakeredis` instance directly — no network mocking required:

```python
# tests/test_redis_safe_cache.py
import pytest
import fakeredis
import redis_safe_cache as cache_module

@pytest.fixture(autouse=True)
def flush_cache():
    """Reset Redis state before every test."""
    cache_module.r.flushall()
    yield

def test_first_call_returns_data():
    data = cache_module.get_user_data_safe("user_1")
    assert isinstance(data, dict)
    assert data["id"] == "user_1"

def test_second_call_is_a_cache_hit():
    cache_module.get_user_data_safe("user_2")
    # Second call must not re-fetch from DB — key must already exist in cache
    data = cache_module.get_user_data_safe("user_2")
    assert data["id"] == "user_2"

def test_returned_keys_are_complete():
    data = cache_module.get_user_data_safe("user_3")
    assert {"id", "name", "level"} <= data.keys()
```

Install test dependencies and run:

```bash
pip install pytest
pytest -v
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-pattern-name`
3. Commit your changes following [Conventional Commits](https://www.conventionalcommits.org/): `git commit -m "feat: add redlock multi-node example"`
4. Push the branch: `git push origin feat/your-pattern-name`
5. Open a Pull Request against `main`

**Guidelines for new pattern examples:**

- Each pattern lives in a single, self-contained `.py` file
- Include a working `__main__` demo that exercises the key behaviour
- Add inline comments explaining the concurrency concern being addressed
- Update this README with any new public functions or modules

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

> **Author:** [DO UZUPEŁNIENIA: your name / contact / website]  
> **Repository:** [https://github.com/eryks23/distributed-locking-patterns](https://github.com/eryks23/distributed-locking-patterns)

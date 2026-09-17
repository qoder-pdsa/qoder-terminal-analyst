---
trigger: glob
paths:
  - "**/*.py"
---
- Annotate every public function; model data with pydantic models or frozen dataclasses instead of passing bare dicts.
- Write tests as pytest functions and keep fixtures in `tests/conftest.py`.

---
trigger: glob
paths:
  - "**/*.py"
---
- 所有公共函数写类型注解；数据结构用 pydantic 模型或 frozen dataclass，不用裸 dict 传递。
- 测试用 pytest 函数风格，fixture 放 `tests/conftest.py`。

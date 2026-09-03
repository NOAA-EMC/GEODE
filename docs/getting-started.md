# Getting Started

This project is structured around the `geode` package under `src/geode`.

## Package layout

The main areas of the package are:

- `geode.geode` for the top-level retrieval API
- `geode.configs` for configuration objects and validation
- `geode.data` for data lake managers
- `geode.ingest` for ingestors and WIS2 listeners
- `geode.model` for model-level abstractions

## Quick usage

```python
from datetime import datetime
from geode.geode import get

start = datetime(2024, 1, 1)
end = datetime(2024, 1, 2)

data = get("surface-based-observations/synop", start, end)
print(data)
```

## Configuration

The configuration is loaded from the YAML files in the `configs/` directory. The configuration classes in `geode.configs` define the available lake types, database settings, and WIS2 ingest options.

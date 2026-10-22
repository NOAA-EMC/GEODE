# Generic BUFR Ingestor

`ncep_dump/generic_bufr` ingests every element of a BUFR subset without a
hand-written `ObsBuilder`. It is additive: the curated ingestors (`atms`,
`mhs`, `iasi`, `cris`, `radiosonde`, `amsua`) are unchanged.

## Generic vs. curated

| Use | When |
| --- | --- |
| Curated (`ncep_dump/atms`, ...) | You need standardized IODA-style names (`ObsValue/...`, `MetaData/...`), derived quantities or instrument-specific logic. |
| Generic (`ncep_dump/generic_bufr`) | You want all fields of an instrument or dump type kept in the lake, or no curated builder exists yet. |

## Usage

```python
from geode.ingest import ingestors

ingestor = ingestors.make("ncep_dump/generic_bufr")(
    data_type="my_dump",
    dx_table=None,                 # optional text DX table; default: gettab on the file
    subset=None,                   # required if the table defines several subsets
    on_schema_mismatch="error",    # "error" (default) | "version" | "skip"
    max_replication_length=None,   # pad delayed replication to a fixed size
)
ingestor.process("/path/to/file.bufr")
```

It is not wired into `NcepDumpReader` because that reader needs a per-dump
path template in `configs/ncep_dump.yaml`.

## How it works

1. The DX table (Table A/B/D) is parsed and the subset sequence is expanded.
2. Leaf elements are sorted by (group, replication path, mnemonic), so the
   schema and its SHA-256 hash are stable across runs.
3. A bufr-query mapping is generated and run through the existing
   `bufr.Parser` and `container_to_xarray` flow. Ranks gather the container
   and only rank 0 returns a `DataTree`.

## Output structure

- Group: the first-level child sequence of the subset (`Header` for elements
  directly in the subset sequence). Variable: sanitized mnemonic.
- Mnemonics that collide within a group are all renamed with their
  replication path, e.g. `PRLC` -> `LEVL_PRLC`.
- Scalars have dimension `Location`; replicated elements add one dimension per
  replication level, named after the replication mnemonic (path-qualified if
  the same name is reused differently).
- Variable attributes carry `bufr_mnemonic`, `bufr_path`, `bufr_units`,
  `bufr_scale`, `bufr_reference`, `bufr_bits`.
- If `YEAR/MNTH/DAYS/HOUR/MINU` are scalar elements, `MetaData/dateTime` is
  created so retrieval time filtering works. Otherwise it is absent.
- Each group with a `Location` dimension stores `bufr_schema_hash`.

## Schema drift

Before appending, the stored `bufr_schema_hash` is compared with the new one.
`on_schema_mismatch="error"` (default) raises `SchemaMismatchError`; `version`
writes to `<data_type>_schema_<hash12>`; `skip` logs and drops the file.

## Known limitations

- One subset per file/ingest; multi-subset tables need `subset`.
- Delayed replication sizes vary per file. Set `max_replication_length` for
  append-safe shapes; padded integer variables become floating point with NaN.
- Duplicate (path, mnemonic) pairs within one sequence collapse to one field.
- Discovery uses the text DX table (`gettab <file>` or `dx_table`); sampled
  decode fallback is not implemented. Operator/undefined mnemonics fail loudly.
- Queries use replicated sequence names only (`*/SEQ/ELEM`).
- Root attributes are not persisted by the Icechunk writer; provenance lives on
  variables and the hash on group attributes.

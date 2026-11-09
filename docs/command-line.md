# Command Line

This page describes GEODE's command-line operations.

## Install

Install GEODE from the repository root to register the `geode` command:

```bash
python -m pip install -e .
```

## Look Up a BUFR Descriptor

Use `geode info bufr` followed by the FXY descriptor:

```bash
geode info bufr 001003
```

The command prints the complete WMO BUFR/CREX Table B entry as a Python
dictionary. The output includes the descriptor name, units, scale, reference
value, data width, class, notes, and status.

```text
{'ClassNo': '01',
 'ClassName_en': 'Identification',
 'FXY': '001003',
 'ElementName_en': 'WMO Region number/geographical area',
 'BUFR_Unit': 'Code table',
 ...}
```

The FXY value must contain exactly six digits. An unknown or malformed value
causes the command to exit with an error message.

## Look Up a Code Figure

For descriptors that use a WMO CodeFlag table, provide the code figure as a
second positional argument:

```bash
geode info bufr 001003 1
```

The command first prints the complete Table B descriptor dictionary, then the
matching CodeFlag dictionary. The CodeFlag result includes the FXY descriptor,
code figure, entry name, notes, and status.

```text
{'ClassNo': '01',
 'FXY': '001003',
 'ElementName_en': 'WMO Region number/geographical area',
 ...}
{'FXY': '001003',
 'CodeFigure': '1',
 'EntryName_en': 'Region I',
 ...}
```

The code figure must exactly match a `CodeFigure` value in the CodeFlag table.
An unknown FXY and code-figure combination causes the command to exit with an
error message.

## Ingest BUFR Tanks

Use `geode ingest bufr_tank_reader` to ingest an NCEP BUFR tank for a range of UTC
days, inclusive:

```bash
geode ingest bufr_tank_reader b002/xx001 2026-11-01 2026-11-05
```

The command prints the tank and its dataset name. Days with no file for the tank are
skipped. Restricted and unmapped tanks exit with an error unless they are allowed in the
[configuration](getting-started.md#bufr-tanks).

To list every known tank with its dataset, format, and restriction:

```bash
geode admin --list-bufr-tank-datasets
```

See [BUFR Tanks](bufr-tanks.md) for how tanks are stored.

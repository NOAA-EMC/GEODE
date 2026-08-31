# Command Line

GEODE currently provides one command-line operation: look up a BUFR Table B
descriptor by its six-digit FXY value.

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

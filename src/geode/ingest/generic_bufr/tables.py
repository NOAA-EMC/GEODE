"""Parser for NCEP text-format BUFR DX tables (Table A, B and D)."""

import re
from dataclasses import dataclass, field

MAX_SEQUENCE_DEPTH = 32

_FXY_PATTERN = re.compile(r"^\d-\d{2}-\d{3}$")
_TOKEN_PATTERN = re.compile(
    r"""
    "(?P<fixed>[^"\s]+)"(?P<count>\d+)
    |\{(?P<brace>[^{}\s]+)\}
    |\((?P<paren>[^()\s]+)\)
    |<(?P<angle>[^<>\s]+)>
    |\[(?P<bracket>[^\[\]\s]+)\]
    |(?P<plain>[^\s"{}()<>\[\]]+)
    """,
    re.VERBOSE,
)


class BufrTableError(ValueError):
    """Raised when a BUFR table cannot be parsed or is inconsistent."""


@dataclass(frozen=True)
class TableBEntry:
    """A Table B element definition."""

    mnemonic: str
    scale: int
    reference: int
    bits: int
    units: str
    description: str


@dataclass(frozen=True)
class SequenceItem:
    """One item of a Table D sequence.

    ``replication`` is ``None`` for plain items, ``"fixed"`` for ``"NAME"N``
    and ``"delayed"`` for the brace, parenthesis, angle and bracket forms.
    """

    mnemonic: str
    replication: str | None = None
    count: int | None = None


@dataclass
class BufrTables:
    """Parsed Table A (subsets), Table B (elements) and Table D (sequences)."""

    subsets: dict[str, str] = field(default_factory=dict)
    elements: dict[str, TableBEntry] = field(default_factory=dict)
    sequences: dict[str, list[SequenceItem]] = field(default_factory=dict)


def parse_sequence_items(text: str) -> list[SequenceItem]:
    """Tokenize the contents column of a Table D row.

    Parameters
    ----------
    text : str
        Whitespace separated mnemonics with optional replication markers.

    Returns
    -------
    list[SequenceItem]
        Items in table order.

    Raises
    ------
    BufrTableError
        If a fixed replication count is zero.

    Examples
    --------
    >>> parse_sequence_items('YEAR {BRIT} "CHAN"22')[1].replication
    'delayed'
    """
    items = []
    for match in _TOKEN_PATTERN.finditer(text):
        if match.group("fixed"):
            count = int(match.group("count"))
            if count < 1:
                raise BufrTableError(f"Invalid fixed replication count in '{text}'")
            items.append(SequenceItem(match.group("fixed"), "fixed", count))
        elif match.group("plain"):
            items.append(SequenceItem(match.group("plain")))
        else:
            name = (
                match.group("brace")
                or match.group("paren")
                or match.group("angle")
                or match.group("bracket")
            )
            items.append(SequenceItem(name, "delayed"))
    return items


def parse_dx_table(text: str) -> BufrTables:
    """Parse NCEP text-format DX table content.

    Parameters
    ----------
    text : str
        Contents of a ``|``-delimited table containing Table A, B and D rows.

    Returns
    -------
    BufrTables
        Parsed subsets, elements and sequences.

    Raises
    ------
    BufrTableError
        If the text contains no usable table rows or a row is malformed.
    """
    tables = BufrTables()
    current_sequence = None
    in_table_b = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells[0].upper() == "MNEMONIC":
            in_table_b = any(cell.upper().startswith("SCAL") for cell in cells)
            current_sequence = None
            continue
        if len(cells) < 2:
            continue

        if in_table_b:
            if len(cells) < 6:
                raise BufrTableError(f"Malformed Table B row: '{line}'")
            try:
                scale, reference, bits = (int(cells[i]) for i in (2, 3, 4))
            except ValueError as err:
                raise BufrTableError(f"Malformed Table B row: '{line}'") from err
            tables.elements[cells[0]] = TableBEntry(
                mnemonic=cells[0],
                scale=scale,
                reference=reference,
                bits=bits,
                units=cells[5],
                description=cells[6] if len(cells) > 6 else "",
            )
        elif cells[1].startswith("A") and cells[0]:
            tables.subsets[cells[0]] = cells[2] if len(cells) > 2 else ""
        elif _FXY_PATTERN.match(cells[1]):
            current_sequence = cells[0]
            tables.sequences.setdefault(current_sequence, [])
        else:
            name = cells[0] or current_sequence
            if name is None:
                raise BufrTableError(f"Sequence contents without a sequence: '{line}'")
            current_sequence = name
            tables.sequences.setdefault(name, []).extend(parse_sequence_items(cells[1]))

    if not tables.elements and not tables.sequences:
        raise BufrTableError("FATAL ERROR: No BUFR table rows found")
    return tables

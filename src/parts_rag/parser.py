"""Parse the raw assembly table into structured rows.

Rule: no casing changes anywhere. Cells are only stripped of the spaces
around the "|" separators, so a part number like "Dh201079" stays exactly
"Dh201079".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

EXPECTED_COLUMNS = ["Sr. No.", "Part No.", "Description", "QTY.", "Remark"]
EXPECTED_ROW_COUNT = 16

_MODEL_RE = re.compile(r"^Model:\s*(?P<name>.+?)\s*\((?P<code>[^)]+)\)\s*$")
_ASSEMBLY_RE = re.compile(r"^Assembly:\s*(?P<no>\d+)\.\s*(?P<name>.+?)\s*$")


class ParseError(ValueError):
    """The source file does not look like the expected table."""


@dataclass(frozen=True)
class PartRow:
    sr_no: str
    part_no: str
    description: str
    qty: int
    remark: str = ""


@dataclass(frozen=True)
class Assembly:
    model: str            # "Pulsar N-125"
    model_code: str       # "00JZF7ZZ"
    assembly_no: str      # "28"
    assembly_name: str    # "Front Wheel Assembly - Disc Brake"
    rows: list[PartRow] = field(default_factory=list)

    @property
    def model_label(self) -> str:
        return f"{self.model} ({self.model_code})"

    @property
    def assembly_label(self) -> str:
        return f"{self.assembly_no}. {self.assembly_name}"


def _split_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.split("|")]


def parse_text(text: str, expected_rows: int | None = EXPECTED_ROW_COUNT) -> Assembly:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        raise ParseError("File needs a Model line, an Assembly line and a header row.")

    model_match = _MODEL_RE.match(lines[0].strip())
    if not model_match:
        raise ParseError(f"Bad Model line: {lines[0]!r}")
    assembly_match = _ASSEMBLY_RE.match(lines[1].strip())
    if not assembly_match:
        raise ParseError(f"Bad Assembly line: {lines[1]!r}")

    header = _split_cells(lines[2])
    if header[: len(EXPECTED_COLUMNS)] != EXPECTED_COLUMNS:
        raise ParseError(f"Unexpected header columns: {header}")

    rows: list[PartRow] = []
    for line_no, line in enumerate(lines[3:], start=4):
        cells = _split_cells(line)
        if len(cells) == 4:  # no trailing "|" for an empty remark
            cells.append("")
        if len(cells) != 5:
            raise ParseError(f"Line {line_no}: expected 5 cells, got {len(cells)}: {line!r}")
        sr_no, part_no, description, qty, remark = cells
        if not sr_no.isdigit():
            raise ParseError(f"Line {line_no}: Sr. No. is not a number: {sr_no!r}")
        if not part_no:
            raise ParseError(f"Line {line_no}: empty Part No.")
        if not qty.isdigit():
            raise ParseError(f"Line {line_no}: QTY. is not a number: {qty!r}")
        rows.append(PartRow(sr_no, part_no, description, int(qty), remark))

    _validate(rows, expected_rows)
    return Assembly(
        model=model_match["name"],
        model_code=model_match["code"],
        assembly_no=assembly_match["no"],
        assembly_name=assembly_match["name"],
        rows=rows,
    )


def _validate(rows: list[PartRow], expected_rows: int | None) -> None:
    if expected_rows is not None and len(rows) != expected_rows:
        raise ParseError(f"Expected {expected_rows} rows, found {len(rows)}.")
    sr_numbers = [int(r.sr_no) for r in rows]
    if sr_numbers != list(range(1, len(rows) + 1)):
        raise ParseError(f"Sr. No. must run 1..{len(rows)} in order, got {sr_numbers}.")
    part_nos = [r.part_no for r in rows]
    dupes = {p for p in part_nos if part_nos.count(p) > 1}
    if dupes:
        raise ParseError(f"Duplicate Part No.: {sorted(dupes)}")


def parse_file(path: str | Path) -> Assembly:
    return parse_text(Path(path).read_text(encoding="utf-8"))

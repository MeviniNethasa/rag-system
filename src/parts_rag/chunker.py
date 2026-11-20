"""Turn a parsed assembly into chunks: one per row plus one summary.

Chunk IDs are stable ("28-row-01" ... "28-row-16", "28-summary") so re-running
the ingest upserts instead of duplicating.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .parser import Assembly, PartRow


@dataclass(frozen=True)
class Chunk:
    id: str
    content: str
    metadata: dict[str, Any]


def _base_metadata(assembly: Assembly) -> dict[str, Any]:
    return {
        "model": assembly.model,
        "model_code": assembly.model_code,
        "assembly_no": assembly.assembly_no,
        "assembly": assembly.assembly_label,
    }


def row_chunk(assembly: Assembly, row: PartRow) -> Chunk:
    parts = [
        f"Model: {assembly.model_label}",
        f"Assembly: {assembly.assembly_label}",
        f"Sr. No.: {row.sr_no}",
        f"Part No.: {row.part_no}",
        f"Description: {row.description}",
        f"Qty: {row.qty}",
    ]
    if row.remark:
        parts.append(f"Remark: {row.remark}")
    metadata = {
        **_base_metadata(assembly),
        "chunk_type": "row",
        "sr_no": row.sr_no,
        "part_no": row.part_no,
        "description": row.description,
        "qty": row.qty,
        "remark": row.remark,
    }
    return Chunk(
        id=f"{assembly.assembly_no}-row-{int(row.sr_no):02d}",
        content=" | ".join(parts),
        metadata=metadata,
    )


def summary_chunk(assembly: Assembly) -> Chunk:
    lines = [
        f"Model: {assembly.model_label}",
        f"Assembly: {assembly.assembly_label}",
        f"Full parts list ({len(assembly.rows)} items):",
    ]
    for row in assembly.rows:
        line = (
            f"Sr. No. {row.sr_no} | Part No. {row.part_no} | "
            f"{row.description} | Qty {row.qty}"
        )
        if row.remark:
            line += f" | Remark {row.remark}"
        lines.append(line)
    metadata = {
        **_base_metadata(assembly),
        "chunk_type": "summary",
        "row_count": len(assembly.rows),
    }
    return Chunk(
        id=f"{assembly.assembly_no}-summary",
        content="\n".join(lines),
        metadata=metadata,
    )


def build_chunks(assembly: Assembly) -> list[Chunk]:
    return [row_chunk(assembly, r) for r in assembly.rows] + [summary_chunk(assembly)]

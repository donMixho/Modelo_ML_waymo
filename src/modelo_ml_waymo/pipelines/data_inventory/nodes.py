"""
This is a boilerplate pipeline 'data_inventory'
generated using Kedro 1.3.1
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

_FORMAT_BY_SUFFIX: dict[str, str] = {
    ".csv": "csv",
    ".parquet": "parquet",
    ".tfrecord": "tfrecord",
    ".jpg": "image_jpeg",
    ".jpeg": "image_jpeg",
    ".png": "image_png",
    ".json": "json",
}

# Columns expected to hold a 3D bounding box (Waymo-style: center + dimensions).
_BOX_3D_COLUMNS = {
    "box_center_x",
    "box_center_y",
    "box_center_z",
    "box_length",
    "box_width",
    "box_height",
}
# Columns that would indicate a 2D (image-plane) bounding box.
_BOX_2D_COLUMNS = {"bbox_xmin", "bbox_ymin", "bbox_xmax", "bbox_ymax", "bbox_width", "bbox_height"}
_CAMERA_COLUMNS = {"camera_name", "camera_id", "image_width", "image_height", "resolution"}
_METADATA_FIELDS = ["time_of_day", "weather", "location", "detection_difficulty", "sensor_version"]
_CLASS_COLUMN_CANDIDATES = ["object_type", "class", "label", "category"]
_SEGMENT_COLUMN_CANDIDATES = ["segment_id", "context_name", "segment", "context"]


def scan_raw_files(raw_data_path: str) -> pd.DataFrame:
    """Index every file under the raw data directory without reading its contents.

    Only filesystem metadata (path, extension, size) is inspected, so this
    is safe to run regardless of how large the raw dataset grows.

    Args:
        raw_data_path: Root directory to scan (e.g. ``data/01_raw``).

    Returns:
        One row per file with its relative path, detected format, size in
        megabytes and, when the filename encodes a segment/context id
        (Waymo tfrecords are typically named ``segment-<id>...tfrecord``),
        that id.
    """
    root = Path(raw_data_path)
    rows: list[dict[str, Any]] = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file() or file_path.name == ".gitkeep":
            continue
        suffix = file_path.suffix.lower()
        size_bytes = file_path.stat().st_size
        rows.append(
            {
                "ruta_relativa": file_path.relative_to(root).as_posix(),
                "formato": _FORMAT_BY_SUFFIX.get(suffix, suffix.lstrip(".") or "desconocido"),
                "tamano_mb": round(size_bytes / (1024 * 1024), 4),
                "segmento_contexto": _segment_hint_from_filename(file_path.stem),
            }
        )
    return pd.DataFrame(
        rows, columns=["ruta_relativa", "formato", "tamano_mb", "segmento_contexto"]
    )


def _segment_hint_from_filename(stem: str) -> str | None:
    """Return the filename itself when it looks like a segment/context id, else None."""
    lowered = stem.lower()
    if "seg" in lowered or "context" in lowered:
        return stem
    return None


def profile_sample(
    raw_data_path: str, max_files: int, max_rows: int
) -> pd.DataFrame:
    """Profile the schema of a small sample of the raw data, read-only.

    Opens at most ``max_files`` files and, for tabular formats, reads at
    most ``max_rows`` records per file. No values are modified, imputed or
    dropped: class labels, weather strings, etc. are reported exactly as
    they appear in the source, inconsistencies included.

    Args:
        raw_data_path: Root directory holding the raw files.
        max_files: Maximum number of files to open for the sample.
        max_rows: Maximum number of records (rows/frames) to read per file.

    Returns:
        A long-format table with one (categoria, clave, valor) row per
        schema fact discovered, e.g. columns present, bounding-box
        dimensionality, metadata fields found, and per-class object counts.
    """
    root = Path(raw_data_path)
    candidate_files = [
        p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix.lower() == ".csv"
    ][:max_files]

    facts: list[dict[str, str]] = [
        {"categoria": "muestra", "clave": "archivos_inspeccionados", "valor": str(len(candidate_files))}
    ]
    if not candidate_files:
        facts.append({"categoria": "muestra", "clave": "advertencia", "valor": "sin archivos csv para perfilar"})
        return pd.DataFrame(facts, columns=["categoria", "clave", "valor"])

    sample_frames = [pd.read_csv(f, nrows=max_rows) for f in candidate_files]
    sample = pd.concat(sample_frames, ignore_index=True)

    for f in candidate_files:
        facts.append({"categoria": "muestra", "clave": "archivo", "valor": f.relative_to(root).as_posix()})
    facts.append({"categoria": "muestra", "clave": "filas_leidas", "valor": str(len(sample))})
    facts.append({"categoria": "esquema", "clave": "columnas", "valor": ", ".join(sample.columns)})

    columns = set(sample.columns)
    box_3d = _BOX_3D_COLUMNS <= columns
    box_2d = _BOX_2D_COLUMNS & columns
    facts.append({"categoria": "anotaciones", "clave": "bounding_box_3d", "valor": "si" if box_3d else "no"})
    facts.append(
        {
            "categoria": "anotaciones",
            "clave": "bounding_box_2d",
            "valor": ", ".join(sorted(box_2d)) if box_2d else "no",
        }
    )

    camera_cols = _CAMERA_COLUMNS & columns
    facts.append(
        {
            "categoria": "camaras",
            "clave": "campos_camara_presentes",
            "valor": ", ".join(sorted(camera_cols)) if camera_cols else "no presentes en este dataset",
        }
    )

    for field in _METADATA_FIELDS:
        if field in columns:
            valores = sample[field].dropna().unique().tolist()
            facts.append(
                {
                    "categoria": "metadata",
                    "clave": field,
                    "valor": ", ".join(map(str, valores[:20])) if valores else "sin valores en la muestra",
                }
            )
        else:
            facts.append({"categoria": "metadata", "clave": field, "valor": "campo no presente"})

    class_column = next((c for c in _CLASS_COLUMN_CANDIDATES if c in columns), None)
    if class_column is not None:
        counts: Counter[str] = Counter(sample[class_column].astype(str))
        for clase, conteo in counts.most_common():
            facts.append({"categoria": "conteo_objetos", "clave": clase, "valor": str(conteo)})
    else:
        facts.append({"categoria": "conteo_objetos", "clave": "advertencia", "valor": "columna de clase no encontrada"})

    segment_column = next((c for c in _SEGMENT_COLUMN_CANDIDATES if c in columns), None)
    if segment_column is not None:
        n_segments = sample[segment_column].nunique()
        facts.append({"categoria": "segmentos", "clave": "segmentos_distintos_en_muestra", "valor": str(n_segments)})

    return pd.DataFrame(facts, columns=["categoria", "clave", "valor"])


def build_inventory_report(
    raw_files_index: pd.DataFrame, raw_sample_profile: pd.DataFrame
) -> tuple[pd.DataFrame, str]:
    """Consolidate the file index and the schema profile into one summary.

    Args:
        raw_files_index: Output of :func:`scan_raw_files`.
        raw_sample_profile: Output of :func:`profile_sample`.

    Returns:
        A tuple of (tabular summary combining both inputs, human-readable
        Markdown report).
    """
    file_summary_facts = [
        {"categoria": "archivos", "clave": "total_archivos", "valor": str(len(raw_files_index))},
        {
            "categoria": "archivos",
            "clave": "tamano_total_mb",
            "valor": f"{raw_files_index['tamano_mb'].sum():.4f}" if not raw_files_index.empty else "0",
        },
    ]
    if not raw_files_index.empty:
        for formato, conteo in raw_files_index["formato"].value_counts().items():
            file_summary_facts.append({"categoria": "archivos_por_formato", "clave": formato, "valor": str(conteo)})

    summary = pd.concat(
        [pd.DataFrame(file_summary_facts, columns=["categoria", "clave", "valor"]), raw_sample_profile],
        ignore_index=True,
    )

    report_md = _render_markdown_report(raw_files_index, summary)
    return summary, report_md


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavoured Markdown table without extra dependencies."""
    header = "| " + " | ".join(df.columns) + " |"
    separator = "| " + " | ".join("---" for _ in df.columns) + " |"
    body = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in df.itertuples(index=False)
    ]
    return "\n".join([header, separator, *body])


def _render_markdown_report(raw_files_index: pd.DataFrame, summary: pd.DataFrame) -> str:
    """Render the consolidated summary as a readable Markdown document."""
    lines = ["# Inventario de datos crudos (data/01_raw)", ""]

    lines += ["## Archivos", ""]
    lines.append(_df_to_markdown_table(raw_files_index) if not raw_files_index.empty else "_Sin archivos encontrados._")
    lines.append("")

    for categoria, grupo in summary.groupby("categoria", sort=False):
        lines.append(f"## {categoria.replace('_', ' ').capitalize()}")
        lines.append("")
        for _, row in grupo.iterrows():
            lines.append(f"- **{row['clave']}**: {row['valor']}")
        lines.append("")

    return "\n".join(lines)

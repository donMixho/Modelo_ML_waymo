"""
This is a boilerplate pipeline 'eda'
generated using Kedro 1.3.1
"""
from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from scipy.stats import kruskal  # noqa: E402
from sklearn.dummy import DummyClassifier  # noqa: E402
from sklearn.feature_selection import mutual_info_classif  # noqa: E402
from sklearn.metrics import accuracy_score, f1_score  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.preprocessing import LabelEncoder  # noqa: E402
from sklearn.tree import DecisionTreeClassifier  # noqa: E402

sns.set_theme(style="whitegrid")

_NULL_LABEL = "<<NULO>>"
_EMPTY_LABEL = "<<CADENA_VACIA>>"

# Known raw-value synonyms per audited column, mapped to a proposed canonical
# label. Anything not listed here is reported as needing manual review.
# This mapping is only ever used to *suggest* a value, never to rewrite data.
_CANONICAL_SYNONYMS: dict[str, dict[str, str]] = {
    "object_type": {
        "VEHICLE": "VEHICLE",
        "PEDESTRIAN": "PEDESTRIAN",
        "PEATON": "PEDESTRIAN",
        "PED": "PEDESTRIAN",
        "CYCLIST": "CYCLIST",
        "SIGN": "SIGN",
    },
    "weather": {
        "SUNNY": "SUNNY",
        "SOLEADO": "SUNNY",
        "RAIN": "RAIN",
        "LLUVIA": "RAIN",
        "FOG": "FOG",
        "NIEBLA": "FOG",
    },
    "time_of_day": {
        "DAY": "DAY",
        "NIGHT": "NIGHT",
        "DAWN/DUSK": "DAWN_DUSK",
    },
    "detection_difficulty": {
        "LEVEL_1": "LEVEL_1",
        "LEVEL_2": "LEVEL_2",
    },
    "sensor_version": {},
}

_IMPOSSIBLE_VALUE_RULES: dict[str, str] = {
    "box_length": "<= 0",
    "box_width": "<= 0",
    "box_height": "<= 0",
    "speed_mps": "<= 0",
    "num_lidar_points": "< 0",
}

_NATURAL_KEY = ["segment_id", "timestamp_micros", "id_interno"]

_CATEGORICAL_PLOT_COLUMNS = [
    "object_type",
    "weather",
    "time_of_day",
    "detection_difficulty",
    "sensor_version",
]

# Fixed numeric feature set for the signal-check diagnostic (task-specified).
_SIGNAL_CHECK_FEATURES = [
    "box_center_x",
    "box_center_y",
    "box_center_z",
    "box_length",
    "box_width",
    "box_height",
    "speed_mps",
    "num_lidar_points",
]
_NOISE_FEATURE_NAME = "ruido_aleatorio_referencia"


def _display(value: Any) -> str:
    """String form of a raw value, making nulls/blanks visible instead of silently empty."""
    if pd.isna(value):
        return _NULL_LABEL
    text = str(value)
    return text if text.strip() else _EMPTY_LABEL


def _pct(count: int, total: int) -> float:
    """Percentage of ``count`` over ``total``, 0 when ``total`` is 0."""
    return round(100 * count / total, 4) if total else 0.0


_NUMERIC_COERCION_THRESHOLD = 0.9


def _coerce_numeric(series: pd.Series) -> tuple[pd.Series, int]:
    """Best-effort numeric parse of a series without mutating the source data.

    Returns the coerced float series plus how many originally non-null
    values failed to parse (e.g. a text sentinel like 'N/D' mixed into an
    otherwise numeric column).
    """
    coerced = pd.to_numeric(series, errors="coerce")
    n_failed = int((series.notna() & coerced.isna()).sum())
    return coerced, n_failed


def _is_effectively_numeric(series: pd.Series) -> bool:
    """True if already numeric, or numeric aside from a small share of bad sentinels."""
    if pd.api.types.is_numeric_dtype(series):
        return True
    non_null = int(series.notna().sum())
    if non_null == 0:
        return False
    _, n_failed = _coerce_numeric(series)
    return (non_null - n_failed) / non_null >= _NUMERIC_COERCION_THRESHOLD


def _numeric_like_frame_and_failures(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Coerced-to-float view of the numeric-like columns, and parse failures per column.

    The source ``df`` is never modified; this only builds an in-memory,
    numeric-typed copy for statistics that require it (IQR, z-score,
    correlation, per-class numeric summaries).
    """
    columns = [c for c in df.columns if _is_effectively_numeric(df[c])]
    series_by_column: dict[str, pd.Series] = {}
    failures: dict[str, int] = {}
    for column in columns:
        coerced, n_failed = _coerce_numeric(df[column])
        series_by_column[column] = coerced
        failures[column] = n_failed
    return pd.DataFrame(series_by_column, index=df.index), failures


def _df_to_markdown_table(df: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavoured Markdown table without extra dependencies."""
    header = "| " + " | ".join(df.columns) + " |"
    separator = "| " + " | ".join("---" for _ in df.columns) + " |"
    body = [
        "| " + " | ".join(str(value) for value in row) + " |" for row in df.itertuples(index=False)
    ]
    return "\n".join([header, separator, *body])


# --------------------------------------------------------------------------
# 1. load_and_profile
# --------------------------------------------------------------------------


def load_and_profile(raw_detections: pd.DataFrame) -> pd.DataFrame:
    """Build a per-column profile of the full raw dataset, read-only.

    For every column this reports dtype, null count/rate and cardinality.
    Numeric columns additionally get min/max/mean/median/std/p1/p99;
    non-numeric columns get their top-10 most frequent raw values exactly
    as they appear (no normalisation). Nothing is imputed or dropped.

    Args:
        raw_detections: Full raw detections table (40,680 rows expected).

    Returns:
        One row per column of ``raw_detections`` with its profile.
    """
    n_rows = len(raw_detections)
    rows: list[dict[str, Any]] = []
    for column in raw_detections.columns:
        series = raw_detections[column]
        n_nulos = int(series.isna().sum())
        record: dict[str, Any] = {
            "columna": column,
            "dtype": str(series.dtype),
            "n_filas": n_rows,
            "n_nulos": n_nulos,
            "pct_nulos": _pct(n_nulos, n_rows),
            "n_unicos": int(series.nunique(dropna=True)),
        }
        if _is_effectively_numeric(series):
            coerced, n_failed = _coerce_numeric(series)
            record.update(_numeric_summary(coerced))
            record["top_10_valores"] = None
            record["n_no_numericos"] = n_failed
        else:
            record.update(dict.fromkeys(["min", "max", "media", "mediana", "std", "p1", "p99"]))
            record["top_10_valores"] = _top_n_as_string(series, n=10)
            record["n_no_numericos"] = None
        rows.append(record)

    columns_order = [
        "columna", "dtype", "n_filas", "n_nulos", "pct_nulos", "n_unicos",
        "min", "max", "media", "mediana", "std", "p1", "p99",
        "n_no_numericos", "top_10_valores",
    ]
    return pd.DataFrame(rows, columns=columns_order)


def _numeric_summary(series: pd.Series) -> dict[str, float]:
    """Descriptive statistics for a numeric series, NaNs excluded."""
    clean = series.dropna()
    if clean.empty:
        return dict.fromkeys(["min", "max", "media", "mediana", "std", "p1", "p99"], float("nan"))
    return {
        "min": float(clean.min()),
        "max": float(clean.max()),
        "media": float(clean.mean()),
        "mediana": float(clean.median()),
        "std": float(clean.std()),
        "p1": float(clean.quantile(0.01)),
        "p99": float(clean.quantile(0.99)),
    }


def _top_n_as_string(series: pd.Series, n: int) -> str:
    """Render the top-n raw value counts (nulls included) as one 'value (count)' string."""
    counts = series.value_counts(dropna=False).head(n)
    return "; ".join(f"{_display(value)} ({count})" for value, count in counts.items())


# --------------------------------------------------------------------------
# 2. audit_categorical_consistency
# --------------------------------------------------------------------------


def audit_categorical_consistency(
    raw_detections: pd.DataFrame, categorical_columns: list[str]
) -> pd.DataFrame:
    """List every raw value of the given categorical columns and only *suggest* a canonical form.

    Args:
        raw_detections: Full raw detections table.
        categorical_columns: Columns to audit (e.g. object_type, weather...).

    Returns:
        One row per (columna, valor_crudo) with its frequency and the
        proposed canonical label in ``mapeo_sugerido``. No value in the
        source data is changed by this function.
    """
    rows: list[dict[str, Any]] = []
    for column in categorical_columns:
        counts = raw_detections[column].value_counts(dropna=False)
        total = int(counts.sum())
        for raw_value, freq in counts.items():
            rows.append(
                {
                    "columna": column,
                    "valor_crudo": _display(raw_value),
                    "frecuencia": int(freq),
                    "pct": _pct(int(freq), total),
                    "mapeo_sugerido": _suggest_canonical(column, raw_value),
                }
            )
    return pd.DataFrame(rows, columns=["columna", "valor_crudo", "frecuencia", "pct", "mapeo_sugerido"])


def _suggest_canonical(column: str, raw_value: Any) -> str:
    """Propose, without applying, a canonical label for one raw categorical value."""
    if pd.isna(raw_value):
        return "sin propuesta: valor nulo"
    key = str(raw_value).strip().upper()
    if not key:
        return "sin propuesta: cadena vacia"
    synonyms = _CANONICAL_SYNONYMS.get(column, {})
    return synonyms.get(key, f"revisar manualmente: sin sinonimo conocido para '{key}'")


# --------------------------------------------------------------------------
# 3. audit_data_quality
# --------------------------------------------------------------------------


def audit_data_quality(
    raw_detections: pd.DataFrame, iqr_multiplier: float, zscore_threshold: float
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Detect and quantify data-quality issues without correcting any of them.

    Covers exact/natural-key duplicates, physically impossible measurements,
    IQR- and z-score-based outliers per numeric column, the null
    co-occurrence pattern (to help judge MCAR/MAR/MNAR), and the temporal
    consistency of frames within each segment.

    Args:
        raw_detections: Full raw detections table.
        iqr_multiplier: Multiplier applied to the IQR to define outlier fences.
        zscore_threshold: Absolute z-score above which a value is flagged.

    Returns:
        Tuple of (quality_flags_summary, null_cooccurrence_matrix,
        temporal_consistency_by_segment).
    """
    n_rows = len(raw_detections)
    numeric_frame, coercion_failures = _numeric_like_frame_and_failures(raw_detections)
    flags: list[dict[str, Any]] = [
        *_duplicate_flags(raw_detections, n_rows),
        *_impossible_value_flags(raw_detections, n_rows),
        *_non_numeric_sentinel_flags(coercion_failures, n_rows),
        *_outlier_flags(numeric_frame, n_rows, iqr_multiplier, zscore_threshold),
    ]
    quality_flags_summary = pd.DataFrame(flags, columns=["categoria", "chequeo", "conteo", "porcentaje"])

    null_cooccurrence_matrix = _null_cooccurrence(raw_detections)
    temporal_consistency_by_segment = _temporal_consistency(raw_detections, numeric_frame)
    return quality_flags_summary, null_cooccurrence_matrix, temporal_consistency_by_segment


def _duplicate_flags(df: pd.DataFrame, n_rows: int) -> list[dict[str, Any]]:
    exact = int(df.duplicated(keep=False).sum())
    by_key = int(df.duplicated(subset=_NATURAL_KEY, keep=False).sum())
    return [
        {
            "categoria": "duplicados",
            "chequeo": "filas_exactas_duplicadas",
            "conteo": exact,
            "porcentaje": _pct(exact, n_rows),
        },
        {
            "categoria": "duplicados",
            "chequeo": f"duplicados_por_clave_natural({','.join(_NATURAL_KEY)})",
            "conteo": by_key,
            "porcentaje": _pct(by_key, n_rows),
        },
    ]


def _impossible_value_flags(df: pd.DataFrame, n_rows: int) -> list[dict[str, Any]]:
    out = []
    for column, condition in _IMPOSSIBLE_VALUE_RULES.items():
        series = df[column]
        mask = series <= 0 if condition == "<= 0" else series < 0
        count = int(mask.sum())
        out.append(
            {
                "categoria": "valores_imposibles",
                "chequeo": f"{column} {condition}",
                "conteo": count,
                "porcentaje": _pct(count, n_rows),
            }
        )
    return out


def _non_numeric_sentinel_flags(coercion_failures: dict[str, int], n_rows: int) -> list[dict[str, Any]]:
    """Flag numeric-like columns that contain some non-numeric sentinel value (e.g. 'N/D')."""
    return [
        {
            "categoria": "valores_no_numericos",
            "chequeo": f"{column}: valores no parseables como numero (sentinel de texto)",
            "conteo": n_failed,
            "porcentaje": _pct(n_failed, n_rows),
        }
        for column, n_failed in coercion_failures.items()
        if n_failed > 0
    ]


def _outlier_flags(
    numeric_frame: pd.DataFrame, n_rows: int, iqr_multiplier: float, zscore_threshold: float
) -> list[dict[str, Any]]:
    out = []
    for column in numeric_frame.columns:
        series = numeric_frame[column].dropna()
        if series.empty:
            continue

        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - iqr_multiplier * iqr, q3 + iqr_multiplier * iqr
        iqr_count = int(((series < lower) | (series > upper)).sum())
        out.append(
            {"categoria": "outliers_iqr", "chequeo": column, "conteo": iqr_count, "porcentaje": _pct(iqr_count, n_rows)}
        )

        std = series.std()
        z_count = int((((series - series.mean()) / std).abs() > zscore_threshold).sum()) if std else 0
        out.append(
            {"categoria": "outliers_zscore", "chequeo": column, "conteo": z_count, "porcentaje": _pct(z_count, n_rows)}
        )
    return out


def _null_cooccurrence(df: pd.DataFrame) -> pd.DataFrame:
    """Correlation between columns' null indicators (helps tell MCAR/MAR/MNAR apart)."""
    matrix = df.isna().astype(int).corr()
    return matrix.reset_index(names="columna")


def _temporal_consistency(df: pd.DataFrame, numeric_frame: pd.DataFrame) -> pd.DataFrame:
    """Frame count and timestamp range per segment.

    Uses the coerced ``timestamp_micros`` (non-numeric sentinels become NaN
    and are skipped by min/max, not imputed) so a stray value like 'N/D'
    cannot crash the range computation.
    """
    timestamps = numeric_frame["timestamp_micros"]
    grouped = timestamps.groupby(df["segment_id"])
    summary = grouped.agg(n_frames="size", timestamp_min="min", timestamp_max="max").reset_index()
    summary["rango_timestamp_micros"] = summary["timestamp_max"] - summary["timestamp_min"]
    return summary


# --------------------------------------------------------------------------
# 4. target_candidates_analysis
# --------------------------------------------------------------------------


def target_candidates_analysis(
    raw_detections: pd.DataFrame, target_candidates: list[str], crosstab_variables: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Characterise each target candidate: balance, cross-tabulations and numeric profile by class.

    Args:
        raw_detections: Full raw detections table.
        target_candidates: Columns considered as possible ML targets.
        crosstab_variables: Columns to cross each candidate against (a
            candidate is skipped against itself).

    Returns:
        Tuple of (class_distribution, imbalance_ratio, crosstab_long,
        crosstab_association, numeric_stats_by_class).
    """
    numeric_frame, _ = _numeric_like_frame_and_failures(raw_detections)

    distribution_rows: list[dict[str, Any]] = []
    imbalance_rows: list[dict[str, Any]] = []
    crosstab_rows: list[dict[str, Any]] = []
    association_rows: list[dict[str, Any]] = []
    numeric_rows: list[dict[str, Any]] = []

    for candidate in target_candidates:
        counts = raw_detections[candidate].value_counts(dropna=False)
        total = int(counts.sum())
        for clase, conteo in counts.items():
            distribution_rows.append(
                {"candidato": candidate, "clase": _display(clase), "conteo": int(conteo), "pct": _pct(int(conteo), total)}
            )
        imbalance_rows.append(_imbalance_row(candidate, counts))

        for cross_var in crosstab_variables:
            if cross_var == candidate:
                continue
            crosstab_rows.extend(_crosstab_rows(raw_detections, candidate, cross_var))
            association_rows.append(_association_row(raw_detections, candidate, cross_var))

        for numeric_col in numeric_frame.columns:
            numeric_rows.extend(
                _numeric_by_class_rows(raw_detections[candidate], numeric_frame[numeric_col], candidate, numeric_col)
            )

    class_distribution = pd.DataFrame(distribution_rows, columns=["candidato", "clase", "conteo", "pct"])
    imbalance_ratio = pd.DataFrame(imbalance_rows)
    crosstab_long = pd.DataFrame(crosstab_rows)
    crosstab_association = pd.DataFrame(association_rows)
    numeric_stats_by_class = pd.DataFrame(numeric_rows)
    return class_distribution, imbalance_ratio, crosstab_long, crosstab_association, numeric_stats_by_class


def _imbalance_row(candidate: str, counts: pd.Series) -> dict[str, Any]:
    clase_mayoritaria, conteo_mayoritaria = counts.idxmax(), int(counts.max())
    clase_minoritaria, conteo_minoritaria = counts.idxmin(), int(counts.min())
    ratio = conteo_mayoritaria / conteo_minoritaria if conteo_minoritaria else float("inf")
    return {
        "candidato": candidate,
        "clase_mayoritaria": _display(clase_mayoritaria),
        "conteo_mayoritaria": conteo_mayoritaria,
        "clase_minoritaria": _display(clase_minoritaria),
        "conteo_minoritaria": conteo_minoritaria,
        "ratio_desbalance": round(ratio, 4),
    }


def _crosstab_rows(df: pd.DataFrame, candidate: str, cross_var: str) -> list[dict[str, Any]]:
    table = pd.crosstab(df[candidate], df[cross_var], dropna=False)
    row_pct = table.div(table.sum(axis=1), axis=0) * 100
    rows = []
    for clase_candidato in table.index:
        for clase_cruzada in table.columns:
            rows.append(
                {
                    "candidato": candidate,
                    "variable_cruzada": cross_var,
                    "clase_candidato": _display(clase_candidato),
                    "clase_variable": _display(clase_cruzada),
                    "frecuencia": int(table.loc[clase_candidato, clase_cruzada]),
                    "pct_fila": round(float(row_pct.loc[clase_candidato, clase_cruzada]), 4),
                }
            )
    return rows


def _association_row(df: pd.DataFrame, candidate: str, cross_var: str) -> dict[str, Any]:
    """Chi-square statistic and Cramer's V for (candidate, cross_var), computed without scipy."""
    table = pd.crosstab(df[candidate], df[cross_var], dropna=False)
    observed = table.to_numpy(dtype=float)
    n = observed.sum()
    row_totals = observed.sum(axis=1, keepdims=True)
    col_totals = observed.sum(axis=0, keepdims=True)
    expected = row_totals @ col_totals / n
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = float(np.nansum(np.where(expected > 0, (observed - expected) ** 2 / expected, 0.0)))
    k = min(observed.shape) - 1
    cramers_v = float(np.sqrt(chi2 / (n * k))) if k > 0 and n > 0 else float("nan")
    return {
        "candidato": candidate,
        "variable_cruzada": cross_var,
        "chi2": round(chi2, 4),
        "cramers_v": round(cramers_v, 4),
        "n": int(n),
    }


def _numeric_by_class_rows(
    candidate_series: pd.Series, numeric_series: pd.Series, candidate: str, numeric_col: str
) -> list[dict[str, Any]]:
    rows = []
    for clase, group in numeric_series.groupby(candidate_series, dropna=False):
        clean = group.dropna()
        if clean.empty:
            continue
        rows.append(
            {
                "candidato": candidate,
                "clase": _display(clase),
                "columna_numerica": numeric_col,
                "min": float(clean.min()),
                "max": float(clean.max()),
                "media": float(clean.mean()),
                "mediana": float(clean.median()),
                "std": float(clean.std()),
            }
        )
    return rows


# --------------------------------------------------------------------------
# 5. generate_plots
# --------------------------------------------------------------------------


def generate_plots(
    raw_detections: pd.DataFrame,
    null_cooccurrence_matrix: pd.DataFrame,
    crosstab_long: pd.DataFrame,
) -> tuple[dict[str, Figure], list[str]]:
    """Render every diagnostic figure for the EDA report as in-memory matplotlib figures.

    Nothing is written to disk directly: figures are returned in a dict
    keyed by filename (without extension) so Kedro's ``MatplotlibDataset``
    persists each one under ``data/08_reporting/figures/``.

    Args:
        raw_detections: Full raw detections table.
        null_cooccurrence_matrix: Output of ``audit_data_quality``, reused
            here for the nulls heatmap instead of recomputing it.
        crosstab_long: Output of ``target_candidates_analysis``, reused for
            the detection_difficulty stacked bar charts.

    Returns:
        Tuple of (figures keyed by name, sorted list of those keys). The
        list lets ``build_eda_report`` embed the right image links without
        reading figures back from disk.
    """
    figures: dict[str, Figure] = {}
    numeric_frame, _ = _numeric_like_frame_and_failures(raw_detections)

    for column in numeric_frame.columns:
        figures[f"distribucion_{column}"] = _distribution_figure(numeric_frame[column], column)

    for column in _CATEGORICAL_PLOT_COLUMNS:
        figures[f"barplot_{column}"] = _categorical_barplot(raw_detections[column], column)

    figures["matriz_correlacion_numericas"] = _correlation_heatmap(numeric_frame)
    figures["heatmap_nulos"] = _null_heatmap(null_cooccurrence_matrix)

    for cross_var in ("weather", "time_of_day"):
        figures[f"detection_difficulty_por_{cross_var}"] = _stacked_bar_from_crosstab(
            crosstab_long, candidate="detection_difficulty", cross_var=cross_var
        )

    manifest = sorted(figures.keys())
    # MatplotlibDataset infers no extension on its own: the dict key saved to
    # the catalog must carry it, while the manifest stays extension-free so
    # build_eda_report can compose "figures/<name>.png" links from it.
    figures_with_extension = {f"{name}.png": fig for name, fig in figures.items()}
    return figures_with_extension, manifest


def _distribution_figure(series: pd.Series, column: str) -> Figure:
    """Plot a (already numeric-coerced) column; ``series`` NaNs may be true nulls or sentinels."""
    fig, (ax_hist, ax_box) = plt.subplots(2, 1, figsize=(6, 6), gridspec_kw={"height_ratios": [3, 1]})
    clean = series.dropna()
    sns.histplot(clean, ax=ax_hist, bins=40)
    ax_hist.set_title(f"Distribucion de {column} (n={len(clean)}, sin_valor_numerico={int(series.isna().sum())})")
    sns.boxplot(x=clean, ax=ax_box)
    ax_box.set_xlabel(column)
    fig.tight_layout()
    plt.close(fig)
    return fig


def _categorical_barplot(series: pd.Series, column: str) -> Figure:
    counts = series.value_counts(dropna=False)
    labels = [_display(v) for v in counts.index]
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.barplot(x=counts.to_numpy(), y=labels, ax=ax, orient="h")
    ax.set_title(f"Frecuencia de valores crudos: {column}")
    ax.set_xlabel("frecuencia")
    fig.tight_layout()
    plt.close(fig)
    return fig


def _correlation_heatmap(numeric_frame: pd.DataFrame) -> Figure:
    corr = numeric_frame.corr()
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax)
    ax.set_title("Correlacion entre columnas numericas")
    fig.tight_layout()
    plt.close(fig)
    return fig


def _null_heatmap(null_cooccurrence_matrix: pd.DataFrame) -> Figure:
    matrix = null_cooccurrence_matrix.set_index("columna")
    fig, ax = plt.subplots(figsize=(7, 6))
    sns.heatmap(matrix, annot=True, fmt=".2f", cmap="viridis", vmin=-1, vmax=1, ax=ax)
    ax.set_title("Co-ocurrencia de nulos entre columnas (correlacion)")
    fig.tight_layout()
    plt.close(fig)
    return fig


def _stacked_bar_from_crosstab(crosstab_long: pd.DataFrame, candidate: str, cross_var: str) -> Figure:
    subset = crosstab_long[
        (crosstab_long["candidato"] == candidate) & (crosstab_long["variable_cruzada"] == cross_var)
    ]
    pivot = subset.pivot(index="clase_variable", columns="clase_candidato", values="frecuencia").fillna(0)
    fig, ax = plt.subplots(figsize=(7, 5))
    pivot.plot(kind="bar", stacked=True, ax=ax, colormap="viridis")
    ax.set_title(f"{candidate} por {cross_var}")
    ax.set_xlabel(cross_var)
    ax.set_ylabel("frecuencia")
    ax.legend(title=candidate)
    fig.tight_layout()
    plt.close(fig)
    return fig


# --------------------------------------------------------------------------
# 6. build_eda_report
# --------------------------------------------------------------------------


def build_eda_report(
    raw_detections: pd.DataFrame,
    column_profile: pd.DataFrame,
    categorical_audit: pd.DataFrame,
    quality_flags_summary: pd.DataFrame,
    null_cooccurrence_matrix: pd.DataFrame,
    temporal_consistency_by_segment: pd.DataFrame,
    target_class_distribution: pd.DataFrame,
    target_imbalance_ratio: pd.DataFrame,
    target_crosstab_association: pd.DataFrame,
    target_numeric_stats_by_class: pd.DataFrame,
    figure_manifest: list[str],
    raw_data_path: str,
) -> str:
    """Consolidate every EDA artifact into one Spanish Markdown report.

    Args:
        raw_detections: Full raw detections table (used only for shape).
        column_profile: Output of ``load_and_profile``.
        categorical_audit: Output of ``audit_categorical_consistency``.
        quality_flags_summary: Output of ``audit_data_quality`` (flags table).
        null_cooccurrence_matrix: Output of ``audit_data_quality`` (nulls matrix).
        temporal_consistency_by_segment: Output of ``audit_data_quality`` (per-segment table).
        target_class_distribution: Output of ``target_candidates_analysis``.
        target_imbalance_ratio: Output of ``target_candidates_analysis``.
        target_crosstab_association: Output of ``target_candidates_analysis``.
        target_numeric_stats_by_class: Output of ``target_candidates_analysis``.
        figure_manifest: Names (without extension) of the figures saved by ``generate_plots``.
        raw_data_path: Path to the source CSV, reported verbatim in the document.

    Returns:
        The full report as a Markdown string. This node never writes to
        disk itself; the string is persisted by the Kedro catalog.
    """
    lines: list[str] = ["# Reporte de EDA - detecciones_waymo_like", ""]
    lines += _section_fuente_datos(raw_data_path, raw_detections)
    lines += _section_dimensiones_esquema(raw_detections, column_profile)
    lines += _section_calidad_datos(quality_flags_summary, temporal_consistency_by_segment)
    lines += _section_inconsistencias_categoricas(categorical_audit)
    lines += _section_nulos(column_profile, null_cooccurrence_matrix, figure_manifest)
    lines += _section_outliers(quality_flags_summary)
    lines += _section_candidatos_target(
        target_class_distribution,
        target_imbalance_ratio,
        target_crosstab_association,
        target_numeric_stats_by_class,
        figure_manifest,
    )
    lines += _section_hallazgos(quality_flags_summary, target_imbalance_ratio, target_crosstab_association)
    return "\n".join(lines)


def _section_fuente_datos(raw_data_path: str, df: pd.DataFrame) -> list[str]:
    return [
        "## Fuente de datos",
        "",
        f"- Archivo: `{raw_data_path}`",
        f"- Filas: {len(df)}",
        f"- Columnas: {df.shape[1]}",
        "- Naturaleza: tabla sintetica de detecciones estilo Waymo (no es el Waymo Open Dataset "
        "real; no incluye imagenes, camaras ni tfrecords).",
        "",
    ]


def _section_dimensiones_esquema(df: pd.DataFrame, column_profile: pd.DataFrame) -> list[str]:
    return [
        "## Dimensiones y esquema",
        "",
        f"Forma: {df.shape[0]} filas x {df.shape[1]} columnas.",
        "",
        _df_to_markdown_table(column_profile),
        "",
    ]


def _section_calidad_datos(quality_flags_summary: pd.DataFrame, temporal: pd.DataFrame) -> list[str]:
    dup = quality_flags_summary[quality_flags_summary["categoria"] == "duplicados"]
    impossible = quality_flags_summary[quality_flags_summary["categoria"] == "valores_imposibles"]
    sentinels = quality_flags_summary[quality_flags_summary["categoria"] == "valores_no_numericos"]
    lines = [
        "## Calidad de datos",
        "",
        "### Duplicados",
        "",
        _df_to_markdown_table(dup[["chequeo", "conteo", "porcentaje"]]),
        "",
        "### Valores fisicamente imposibles",
        "",
        _df_to_markdown_table(impossible[["chequeo", "conteo", "porcentaje"]]),
        "",
    ]
    if not sentinels.empty:
        lines += [
            "### Valores no numericos en columnas numericas (sentinels)",
            "",
            _df_to_markdown_table(sentinels[["chequeo", "conteo", "porcentaje"]]),
            "",
        ]
    lines += [
        "### Consistencia temporal por segmento",
        "",
        f"Segmentos distintos: {temporal['segment_id'].nunique()}. "
        f"Frames por segmento: minimo {int(temporal['n_frames'].min())}, "
        f"maximo {int(temporal['n_frames'].max())}, "
        f"media {temporal['n_frames'].mean():.2f}.",
        "",
    ]
    return lines


def _section_inconsistencias_categoricas(categorical_audit: pd.DataFrame) -> list[str]:
    lines = [
        "## Inconsistencias categoricas",
        "",
        "Valores crudos tal como aparecen en el CSV (sin normalizar) y la propuesta de mapeo a "
        "una categoria canonica. Ningun mapeo fue aplicado a los datos.",
        "",
    ]
    for column, group in categorical_audit.groupby("columna", sort=False):
        lines.append(f"### {column}")
        lines.append("")
        lines.append(_df_to_markdown_table(group[["valor_crudo", "frecuencia", "pct", "mapeo_sugerido"]]))
        lines.append("")
    return lines


def _section_nulos(
    column_profile: pd.DataFrame, null_matrix: pd.DataFrame, figure_manifest: list[str]
) -> list[str]:
    nulls = column_profile[column_profile["n_nulos"] > 0][["columna", "n_nulos", "pct_nulos"]]
    lines = ["## Analisis de nulos", ""]
    lines.append(_df_to_markdown_table(nulls) if not nulls.empty else "_Ninguna columna tiene nulos._")
    lines.append("")
    lines.append(
        "Matriz de co-ocurrencia de nulos (correlacion entre indicadores de nulo por columna; "
        "valores cercanos a 1 indican que dos columnas faltan juntas, lo que apunta a MAR/MNAR "
        "en vez de MCAR):"
    )
    lines.append("")
    lines.append(_df_to_markdown_table(null_matrix.round(4).fillna("-")))
    lines.append("")
    if "heatmap_nulos" in figure_manifest:
        lines.append("![Heatmap de nulos](figures/heatmap_nulos.png)")
        lines.append("")
    return lines


def _section_outliers(quality_flags_summary: pd.DataFrame) -> list[str]:
    outliers = quality_flags_summary[quality_flags_summary["categoria"].isin(["outliers_iqr", "outliers_zscore"])]
    return [
        "## Outliers",
        "",
        "Conteos por metodo; ninguna fila fue marcada para borrado.",
        "",
        _df_to_markdown_table(outliers),
        "",
    ]


def _section_candidatos_target(
    class_distribution: pd.DataFrame,
    imbalance_ratio: pd.DataFrame,
    crosstab_association: pd.DataFrame,
    numeric_stats_by_class: pd.DataFrame,
    figure_manifest: list[str],
) -> list[str]:
    lines = ["## Analisis de candidatos a variable objetivo", ""]
    for candidate in imbalance_ratio["candidato"]:
        lines.append(f"### {candidate}")
        lines.append("")
        dist = class_distribution[class_distribution["candidato"] == candidate][["clase", "conteo", "pct"]]
        lines.append(_df_to_markdown_table(dist))
        lines.append("")

        ratio_row = imbalance_ratio[imbalance_ratio["candidato"] == candidate].iloc[0]
        lines.append(
            f"Ratio de desbalance (mayoritaria/minoritaria): **{ratio_row['ratio_desbalance']}** "
            f"({ratio_row['clase_mayoritaria']}={ratio_row['conteo_mayoritaria']} vs "
            f"{ratio_row['clase_minoritaria']}={ratio_row['conteo_minoritaria']})."
        )
        lines.append("")

        assoc = crosstab_association[crosstab_association["candidato"] == candidate]
        if not assoc.empty:
            lines.append("Asociacion con otras variables (Cramer's V; 0=independiente, 1=asociacion perfecta):")
            lines.append("")
            lines.append(_df_to_markdown_table(assoc[["variable_cruzada", "chi2", "cramers_v", "n"]]))
            lines.append("")

        numeric_subset = numeric_stats_by_class[numeric_stats_by_class["candidato"] == candidate]
        lines.append(f"Estadisticos numericos por clase de `{candidate}`:")
        lines.append("")
        lines.append(
            _df_to_markdown_table(numeric_subset[["clase", "columna_numerica", "min", "max", "media", "mediana", "std"]])
        )
        lines.append("")

        for fig_name in (f"{candidate}_por_weather", f"{candidate}_por_time_of_day"):
            if fig_name in figure_manifest:
                lines.append(f"![{fig_name}](figures/{fig_name}.png)")
                lines.append("")
    return lines


def _section_hallazgos(
    quality_flags_summary: pd.DataFrame, imbalance_ratio: pd.DataFrame, crosstab_association: pd.DataFrame
) -> list[str]:
    lines = ["## Hallazgos y decisiones pendientes", ""]

    dup_exact = quality_flags_summary.loc[
        (quality_flags_summary["categoria"] == "duplicados")
        & (quality_flags_summary["chequeo"] == "filas_exactas_duplicadas"),
        "conteo",
    ]
    lines.append(
        f"- Duplicados exactos detectados: {int(dup_exact.iloc[0]) if not dup_exact.empty else 0}. "
        "Pendiente decidir si se deduplican."
    )

    sentinel_flags = quality_flags_summary[quality_flags_summary["categoria"] == "valores_no_numericos"]
    for _, row in sentinel_flags.iterrows():
        lines.append(
            f"- {row['chequeo']}: {row['conteo']} filas ({row['porcentaje']}%). "
            "Pendiente decidir tratamiento (excluir, imputar o investigar el origen del sentinel)."
        )

    lines.append(
        "- Las columnas categoricas (`object_type`, `weather`) tienen variantes de "
        "mayusculas/idioma sin normalizar; ver seccion de inconsistencias antes de usarlas "
        "como features o target."
    )
    for _, row in imbalance_ratio.iterrows():
        lines.append(
            f"- `{row['candidato']}` tiene un ratio de desbalance de {row['ratio_desbalance']}x "
            "entre su clase mayoritaria y minoritaria."
        )

    strong_assoc = crosstab_association[crosstab_association["cramers_v"] > 0.1]
    if not strong_assoc.empty:
        for _, row in strong_assoc.iterrows():
            lines.append(
                f"- `{row['candidato']}` muestra asociacion con `{row['variable_cruzada']}` "
                f"(Cramer's V={row['cramers_v']})."
            )
    else:
        lines.append(
            "- No se observo asociacion relevante (Cramer's V > 0.1) entre los candidatos a "
            "target y weather/time_of_day/object_type."
        )
    lines.append(
        "- Pendiente: decidir la normalizacion final de categorias, la politica de "
        "duplicados/outliers, y cual candidato usar como variable objetivo antes de construir "
        "`data/03_primary`."
    )
    lines.append("")
    return lines


# --------------------------------------------------------------------------
# 7. signal_check
# --------------------------------------------------------------------------


def signal_check(
    raw_detections: pd.DataFrame, target_candidates: list[str], signal_check_params: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """Diagnose whether each target candidate carries any learnable signal.

    For every candidate in ``target_candidates`` this: (1) normalises the
    candidate's raw labels in memory only, purely for this analysis
    (never written back to any dataset), (2) ranks the fixed numeric
    feature set (``_SIGNAL_CHECK_FEATURES``) by mutual information against
    the target, alongside a random-noise column used as a reference floor,
    (3) runs a Kruskal-Wallis separability test per feature across the
    target's classes, and (4) trains a most-frequent-class dummy and a
    shallow decision tree on a stratified 70/30 split -- with exact
    duplicates on the modelling columns removed first to avoid train/test
    leakage -- to get an honest held-out macro-F1 baseline.

    Args:
        raw_detections: Full raw detections table.
        target_candidates: Candidate target columns (e.g. detection_difficulty, object_type).
        signal_check_params: Dict with keys ``random_state``, ``test_size``,
            ``tree_max_depth``, ``mi_noise_multiplier``, ``macro_f1_lift_signal``,
            ``macro_f1_lift_weak`` and ``alpha``.

    Returns:
        Tuple of (mi_scores, separability, baseline_metrics, summary, report_md).
    """
    random_state = signal_check_params["random_state"]
    rng = np.random.RandomState(random_state)
    noise = pd.Series(rng.normal(size=len(raw_detections)), index=raw_detections.index, name=_NOISE_FEATURE_NAME)

    numeric_frame, _ = _numeric_like_frame_and_failures(raw_detections)
    features = numeric_frame[_SIGNAL_CHECK_FEATURES]

    mi_rows: list[dict[str, Any]] = []
    separability_rows: list[dict[str, Any]] = []
    baseline_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    mapping_sections: list[str] = []

    for candidate in target_candidates:
        normalized_target = _normalize_categorical(raw_detections[candidate], candidate)
        mapping_sections.append(_mapping_documentation(raw_detections[candidate], normalized_target, candidate))

        mi_scores = _mutual_information_scores(features, noise, normalized_target, random_state)
        mi_rows.extend({"candidato": candidate, **row} for row in mi_scores)

        separability = _separability_tests(features, normalized_target)
        separability_rows.extend({"candidato": candidate, **row} for row in separability)

        baseline = _baseline_classifiers(features, normalized_target, signal_check_params)
        baseline_rows.extend({"candidato": candidate, **row} for row in baseline["metrics"])

        summary_rows.append(
            _summary_row(candidate, mi_scores, separability, baseline, signal_check_params)
        )

    mi_scores_df = pd.DataFrame(mi_rows)
    separability_df = pd.DataFrame(separability_rows)
    baseline_metrics_df = pd.DataFrame(baseline_rows)
    summary_df = pd.DataFrame(summary_rows)
    report_md = _render_signal_check_report(
        mi_scores_df, separability_df, baseline_metrics_df, summary_df, mapping_sections, signal_check_params
    )
    return mi_scores_df, separability_df, baseline_metrics_df, summary_df, report_md


def _normalize_categorical(series: pd.Series, column: str) -> pd.Series:
    """Map raw values to their canonical label in memory only, for this analysis.

    Reuses the same synonym table shown in the categorical-consistency
    audit, so the mapping documented there and the one actually applied
    here always agree. A value with no known synonym keeps its
    stripped/uppercased form (visible as its own class, never silently
    merged or dropped). Nothing is written back to ``series`` or any
    dataset -- the caller's ``raw_detections`` is untouched.
    """
    synonyms = _CANONICAL_SYNONYMS.get(column, {})

    def _map(value: Any) -> Any:
        if pd.isna(value):
            return value
        key = str(value).strip().upper()
        return synonyms.get(key, key)

    return series.map(_map)


def _mapping_documentation(raw_series: pd.Series, normalized_series: pd.Series, column: str) -> str:
    """Markdown table documenting the raw -> canonical mapping actually applied to ``column``."""
    applied = pd.DataFrame({"valor_crudo": raw_series, "valor_normalizado": normalized_series})
    summary = (
        applied.groupby(["valor_crudo", "valor_normalizado"], dropna=False)
        .size()
        .reset_index(name="frecuencia")
        .sort_values("frecuencia", ascending=False)
    )
    summary["valor_crudo"] = summary["valor_crudo"].map(_display)
    summary["valor_normalizado"] = summary["valor_normalizado"].map(_display)
    lines = [f"#### Mapeo aplicado a `{column}` (solo en memoria, exclusivo de este análisis)", ""]
    lines.append(_df_to_markdown_table(summary))
    return "\n".join(lines)


def _mutual_information_scores(
    features: pd.DataFrame, noise: pd.Series, target: pd.Series, random_state: int
) -> list[dict[str, Any]]:
    """Mutual information of each feature (plus a random-noise column) against ``target``.

    Rows with a NaN in any feature, the noise column or the target are
    excluded (complete-case analysis, no imputation). The target is
    label-encoded only to satisfy the estimator's input contract: encoding
    a discrete variable bijectively cannot change its mutual information.
    """
    working = features.assign(**{_NOISE_FEATURE_NAME: noise}, _target=target).dropna()
    encoded_target = LabelEncoder().fit_transform(working["_target"])
    x = working.drop(columns="_target")
    mi = mutual_info_classif(x, encoded_target, random_state=random_state)

    rows = [
        {"feature": column, "mi_score": float(score), "es_ruido_base": column == _NOISE_FEATURE_NAME}
        for column, score in zip(x.columns, mi, strict=True)
    ]
    rows.sort(key=lambda row: row["mi_score"], reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    return rows


def _separability_tests(features: pd.DataFrame, target: pd.Series) -> list[dict[str, Any]]:
    """Kruskal-Wallis separability test per feature across the target's classes.

    Kruskal-Wallis (non-parametric) is used rather than one-way ANOVA
    because the earlier EDA already showed heavy-tailed, non-normal
    distributions and a meaningful share of IQR/z-score outliers in these
    numeric features, which would violate ANOVA's assumptions.
    """
    rows = []
    for column in features.columns:
        working = pd.DataFrame({"valor": features[column], "clase": target}).dropna()
        groups = [group["valor"].to_numpy() for _, group in working.groupby("clase") if len(group) > 0]
        if len(groups) < 2:
            continue
        statistic, p_value = kruskal(*groups)
        rows.append(
            {"feature": column, "test": "kruskal_wallis", "estadistico": float(statistic), "p_valor": float(p_value)}
        )
    rows.sort(key=lambda row: row["p_valor"])
    return rows


def _baseline_classifiers(features: pd.DataFrame, target: pd.Series, params: dict[str, Any]) -> dict[str, Any]:
    """Stratified 70/30 dummy-vs-tree baseline, deduplicated first to avoid train/test leakage.

    Exact duplicates are dropped on the (features, target) columns actually
    fed to the model -- not the full 16-column row -- since an identical
    feature/target combination landing in both train and test would let
    the tree memorise it even when the source rows differ in unrelated
    columns such as segment_id or timestamp. Rows with a NaN in any
    modelling column are dropped beforehand (no imputation).
    """
    working = features.assign(_target=target)
    n_before_na = len(working)
    working = working.dropna()
    n_dropped_na = n_before_na - len(working)

    n_before_dedup = len(working)
    working = working.drop_duplicates()
    n_after_dedup = len(working)

    x = working.drop(columns="_target")
    y = working["_target"]

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=params["test_size"], random_state=params["random_state"], stratify=y
    )

    models = {
        "dummy_mas_frecuente": DummyClassifier(strategy="most_frequent"),
        "arbol_decision": DecisionTreeClassifier(max_depth=params["tree_max_depth"], random_state=params["random_state"]),
    }
    metrics = []
    for name, model in models.items():
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)
        metrics.append(
            {
                "modelo": name,
                "accuracy": float(accuracy_score(y_test, predictions)),
                "macro_f1": float(f1_score(y_test, predictions, average="macro", zero_division=0)),
                "n_train": len(x_train),
                "n_test": len(x_test),
            }
        )
    return {
        "metrics": metrics,
        "n_before_dedup": n_before_dedup,
        "n_after_dedup": n_after_dedup,
        "n_dropped_na": n_dropped_na,
        "n_duplicados_removidos": n_before_dedup - n_after_dedup,
    }


def _summary_row(
    candidate: str,
    mi_scores: list[dict[str, Any]],
    separability: list[dict[str, Any]],
    baseline: dict[str, Any],
    params: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the point-5 summary row (MI max, significant features, macro-F1s, verdict)."""
    mi_real = [row["mi_score"] for row in mi_scores if not row["es_ruido_base"]]
    mi_noise = next(row["mi_score"] for row in mi_scores if row["es_ruido_base"])
    n_significant = sum(1 for row in separability if row["p_valor"] < params["alpha"])
    macro_f1_by_model = {row["modelo"]: row["macro_f1"] for row in baseline["metrics"]}
    macro_f1_tree = macro_f1_by_model.get("arbol_decision", float("nan"))
    macro_f1_dummy = macro_f1_by_model.get("dummy_mas_frecuente", float("nan"))
    mi_maxima = max(mi_real) if mi_real else 0.0

    veredicto = _verdict(
        mi_maxima=mi_maxima,
        mi_noise=mi_noise,
        macro_f1_tree=macro_f1_tree,
        macro_f1_dummy=macro_f1_dummy,
        n_significant=n_significant,
        mi_noise_multiplier=params["mi_noise_multiplier"],
        lift_signal=params["macro_f1_lift_signal"],
        lift_weak=params["macro_f1_lift_weak"],
    )
    return {
        "candidato": candidate,
        "mi_maxima": round(mi_maxima, 6),
        "mi_ruido_base": round(mi_noise, 6),
        "n_features_p_lt_alpha": n_significant,
        "n_features_totales": len(separability),
        "macro_f1_arbol": round(macro_f1_tree, 4),
        "macro_f1_dummy": round(macro_f1_dummy, 4),
        "n_filas_tras_dedup": baseline["n_after_dedup"],
        "n_duplicados_removidos": baseline["n_duplicados_removidos"],
        "veredicto": veredicto,
    }


def _verdict(
    mi_maxima: float,
    mi_noise: float,
    macro_f1_tree: float,
    macro_f1_dummy: float,
    n_significant: int,
    mi_noise_multiplier: float,
    lift_signal: float,
    lift_weak: float,
) -> str:
    """Combine effect-size evidence (MI vs. noise floor, held-out macro-F1 lift) into a verdict.

    With ~40k rows, p < 0.05 is trivial to reach for almost any real
    effect, so the verdict leans on practical/effect-size signals rather
    than significance-count alone: does the tree actually beat a
    most-frequent dummy on held-out data, and is the best mutual
    information clearly above what a random-noise column already gets by
    chance.
    """
    lift = macro_f1_tree - macro_f1_dummy
    noise_floor = mi_noise * mi_noise_multiplier if mi_noise > 0 else 1e-6
    mi_above_noise = mi_maxima > noise_floor

    if lift >= lift_signal and mi_above_noise and n_significant >= 1:
        return "SEÑAL"
    if lift >= lift_weak or mi_above_noise or n_significant >= 1:
        return "SEÑAL DÉBIL"
    return "SIN SEÑAL"


def _render_signal_check_report(
    mi_scores: pd.DataFrame,
    separability: pd.DataFrame,
    baseline_metrics: pd.DataFrame,
    summary: pd.DataFrame,
    mapping_sections: list[str],
    params: dict[str, Any],
) -> str:
    """Render the full signal-check diagnosis as a Spanish Markdown document."""
    lines = [
        "# Verificación de señal predictiva",
        "",
        "Diagnóstico de si `detection_difficulty` y `object_type` tienen señal predictiva "
        "aprovechable con las variables numéricas disponibles "
        f"({', '.join(_SIGNAL_CHECK_FEATURES)}). Ningún dato transformado se persiste: la "
        "normalización de categorías es solo en memoria, y las filas con nulos en las variables "
        "usadas (únicamente `speed_mps` los tiene) se excluyen por caso completo, nunca se imputan.",
        "",
        "## Normalización aplicada (solo en memoria)",
        "",
    ]
    for block in mapping_sections:
        lines.append(block)
        lines.append("")

    lines.append("## Resumen final")
    lines.append("")
    lines.append(_df_to_markdown_table(summary))
    lines.append("")
    lines.append(
        f"**SEÑAL**: mejora de macro-F1 (árbol vs. dummy) ≥ {params['macro_f1_lift_signal']}, "
        f"Y MI máxima > {params['mi_noise_multiplier']}x el ruido de referencia, "
        f"Y al menos 1 feature con p < {params['alpha']}. "
        f"**SEÑAL DÉBIL**: cumple al menos una de esas tres condiciones de forma más modesta "
        f"(mejora ≥ {params['macro_f1_lift_weak']}, o MI por sobre el ruido, o algún p < {params['alpha']}). "
        "**SIN SEÑAL**: no cumple ninguna."
    )
    lines.append("")

    for candidate in summary["candidato"]:
        lines.append(f"## {candidate}")
        lines.append("")
        lines.append("### Información mutua (mayor a menor; incluye ruido aleatorio de referencia)")
        lines.append("")
        mi_subset = mi_scores[mi_scores["candidato"] == candidate][["rank", "feature", "mi_score", "es_ruido_base"]]
        lines.append(_df_to_markdown_table(mi_subset))
        lines.append("")

        lines.append("### Separabilidad (Kruskal-Wallis)")
        lines.append("")
        sep_subset = separability[separability["candidato"] == candidate][["feature", "test", "estadistico", "p_valor"]]
        lines.append(_df_to_markdown_table(sep_subset))
        lines.append("")

        lines.append("### Baseline honesto (dummy vs. árbol de decisión)")
        lines.append("")
        baseline_subset = baseline_metrics[baseline_metrics["candidato"] == candidate][
            ["modelo", "accuracy", "macro_f1", "n_train", "n_test"]
        ]
        lines.append(_df_to_markdown_table(baseline_subset))
        lines.append("")

    return "\n".join(lines)

"""
This is a boilerplate pipeline 'eda'
generated using Kedro 1.3.1
"""
from __future__ import annotations

from kedro.pipeline import Node, Pipeline

from .nodes import (
    audit_categorical_consistency,
    audit_data_quality,
    build_eda_report,
    generate_plots,
    load_and_profile,
    signal_check,
    target_candidates_analysis,
)


def create_pipeline(**kwargs) -> Pipeline:
    return Pipeline(
        [
            Node(
                func=load_and_profile,
                inputs="raw_detections",
                outputs="eda_column_profile",
                name="load_and_profile",
            ),
            Node(
                func=audit_categorical_consistency,
                inputs=["raw_detections", "params:eda.categorical_audit_columns"],
                outputs="eda_categorical_audit",
                name="audit_categorical_consistency",
            ),
            Node(
                func=audit_data_quality,
                inputs=["raw_detections", "params:eda.iqr_multiplier", "params:eda.zscore_threshold"],
                outputs=[
                    "eda_quality_flags_summary",
                    "eda_null_cooccurrence_matrix",
                    "eda_temporal_consistency_by_segment",
                ],
                name="audit_data_quality",
            ),
            Node(
                func=target_candidates_analysis,
                inputs=["raw_detections", "params:eda.target_candidates", "params:eda.crosstab_variables"],
                outputs=[
                    "eda_target_class_distribution",
                    "eda_target_imbalance_ratio",
                    "eda_target_crosstab_long",
                    "eda_target_crosstab_association",
                    "eda_target_numeric_stats_by_class",
                ],
                name="target_candidates_analysis",
            ),
            Node(
                func=generate_plots,
                inputs=["raw_detections", "eda_null_cooccurrence_matrix", "eda_target_crosstab_long"],
                outputs=["eda_figures", "eda_figure_manifest"],
                name="generate_plots",
            ),
            Node(
                func=build_eda_report,
                inputs=[
                    "raw_detections",
                    "eda_column_profile",
                    "eda_categorical_audit",
                    "eda_quality_flags_summary",
                    "eda_null_cooccurrence_matrix",
                    "eda_temporal_consistency_by_segment",
                    "eda_target_class_distribution",
                    "eda_target_imbalance_ratio",
                    "eda_target_crosstab_association",
                    "eda_target_numeric_stats_by_class",
                    "eda_figure_manifest",
                    "params:eda.raw_data_path",
                ],
                outputs="eda_report_md",
                name="build_eda_report",
            ),
            Node(
                func=signal_check,
                inputs=["raw_detections", "params:eda.target_candidates", "params:eda.signal_check"],
                outputs=[
                    "signal_mi_scores",
                    "signal_separability",
                    "signal_baseline_metrics",
                    "signal_summary",
                    "signal_check_report_md",
                ],
                name="signal_check",
            ),
        ]
    )

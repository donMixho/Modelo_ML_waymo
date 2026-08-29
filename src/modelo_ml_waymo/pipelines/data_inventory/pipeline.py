"""
This is a boilerplate pipeline 'data_inventory'
generated using Kedro 1.3.1
"""
from __future__ import annotations

from kedro.pipeline import Node, Pipeline

from .nodes import build_inventory_report, profile_sample, scan_raw_files


def create_pipeline(**kwargs) -> Pipeline:
    return Pipeline(
        [
            Node(
                func=scan_raw_files,
                inputs="params:data_inventory.raw_data_path",
                outputs="data_inventory_raw_files_index",
                name="scan_raw_files",
            ),
            Node(
                func=profile_sample,
                inputs=[
                    "params:data_inventory.raw_data_path",
                    "params:data_inventory.sample_max_files",
                    "params:data_inventory.sample_max_rows",
                ],
                outputs="data_inventory_raw_sample_profile",
                name="profile_sample",
            ),
            Node(
                func=build_inventory_report,
                inputs=["data_inventory_raw_files_index", "data_inventory_raw_sample_profile"],
                outputs=["data_inventory_summary", "data_inventory_report_md"],
                name="build_inventory_report",
            ),
        ]
    )

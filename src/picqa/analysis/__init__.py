"""Statistical analysis, yield calculation, outlier detection, uniformity, and phase extraction."""

from picqa.analysis.outlier import flag_failed_contacts
from picqa.analysis.phase_extraction import (
    extract_phase_features,
    parse_phaseshifter_length_um,
    vphi_trace,
    vpi_from_slope,
)
from picqa.analysis.statistics import per_group_stats, robust_summary
from picqa.analysis.wafer_uniformity import (
    add_radius_column,
    add_region_column,
    center_vs_edge,
    fsr_to_index_variation,
    iv_uniformity,
    per_radius_stats,
)
from picqa.analysis.yield_calc import Spec, evaluate_yield, load_spec, yield_summary

__all__ = [
    "Spec",
    "load_spec",
    "evaluate_yield",
    "yield_summary",
    "robust_summary",
    "per_group_stats",
    "flag_failed_contacts",
    # uniformity
    "add_radius_column",
    "add_region_column",
    "center_vs_edge",
    "per_radius_stats",
    "fsr_to_index_variation",
    "iv_uniformity",
    # phase
    "extract_phase_features",
    "vpi_from_slope",
    "vphi_trace",
    "parse_phaseshifter_length_um",
]

"""
display.py — Karben4 QM Yield Tool · shared table formatting for the Streamlit UI
====================================================================================
One place for column labels/widths/number formats so every tab's tables look
consistent, instead of each page guessing st.column_config independently.
"""
import streamlit as st

# label, width, format (format=None for text/date columns)
_SPECS = {
    "batch_number": ("Batch #", "small", "%.2f"),
    "beer": ("Beer", "small", None),
    "brew_date": ("Brew Date", "small", None),
    "n_grains": ("# Grains", "small", "%d"),
    "grainbill_weight_lb": ("Grain Bill (lb)", "small", "%.1f"),
    "lauter_loading_kgm2": ("Loading (kg/m²)", "small", "%.1f"),
    "mash_thickness_qt_lb": ("Thickness (qt/lb)", "small", "%.2f"),
    "first_runnings_avg_extract_p": ("FR Avg (°P)", "small", "%.2f"),
    "final_brewhouse_eff_pct": ("BH Efficiency (%)", "small", "%.1f"),
    "predicted_knockout_vol_bbl": ("Knockout (bbl)", "small", "%.2f"),
    "kettle_whirlpool_hop_rate_lb_bbl": ("Hop Rate (lb/bbl)", "small", "%.2f"),
    "trub_loss_pct": ("Trub Loss (%)", "small", "%.2f"),
    "hop_loss_pct": ("Hop Loss (%)", "small", "%.2f"),
    "predicted_centrifuge_out_vol_bbl": ("Centrifuge-Out (bbl)", "small", "%.2f"),
    "dry_hop_rate_lb_bbl": ("Dry Hop Rate (lb/bbl)", "small", "%.2f"),
    "packaging_loss_pct": ("Packaging Loss (%)", "small", "%.2f"),
    "fre_pct": ("FRE (%)", "small", "%.2f"),
    "retention_pct": ("Retention (%)", "small", "%.2f"),
    "measured_runoff_p": ("Measured (°P)", "small", "%.2f"),
    "predicted_runoff_p": ("Predicted (°P)", "small", "%.4f"),
    "reproduction_error_pct": ("Fit Error (%)", "small", "%.4f"),
}


def column_config(df):
    """Builds a {column: st.column_config.Column} dict from _SPECS for whatever
    columns are actually present in df — unknown columns (e.g. per-grain
    grain_pct__* composition columns) just fall back to a small text/number column
    with their raw name, rather than being hidden."""
    cfg = {}
    for col in df.columns:
        if col in _SPECS:
            label, width, fmt = _SPECS[col]
            if fmt:
                cfg[col] = st.column_config.NumberColumn(label, width=width, format=fmt)
            else:
                cfg[col] = st.column_config.TextColumn(label, width=width)
        elif col.startswith("grain_pct__"):
            cfg[col] = st.column_config.NumberColumn(col.replace("grain_pct__", "") + " %",
                                                       width="small", format="%.1f")
        else:
            cfg[col] = st.column_config.Column(col, width="small")
    return cfg

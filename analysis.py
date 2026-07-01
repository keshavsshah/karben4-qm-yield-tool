"""
analysis.py — Karben4 QM Yield Tool · batch-level metrics for the UI (increment 4 support)
=============================================================================================
Turns loaded Batch objects (data_loader.py) into one flat row per batch, running each
available engine stage. Pure (no Streamlit) so it's testable standalone; app.py just
displays what this produces.
"""
from engine import lauter_metrics, knockout_metrics, cellar_metrics, predicted_runoff_extract_p, Constants
from autofit import fit_all, DEFAULT_RETENTION_PCT


def batch_row(batch, const: Constants = Constants()) -> dict:
    """One flat dict of everything computable for a batch. None where a stage's
    source data isn't available — see data_loader's coverage note (most batches
    don't have lauter + knockout + cellar all three; today's data barely overlaps)."""
    row = dict(batch_number=batch.batch_number, beer=batch.beer, brew_date=batch.brew_date,
               n_grains=len(batch.grains) if batch.grains else None)

    if batch.grains and batch.lauter:
        m = lauter_metrics(batch.lauter, batch.grains, const)
        grainbill_wt = m["grainbill_weight_lb"]
        row.update(
            grainbill_weight_lb=grainbill_wt,
            lauter_loading_kgm2=m["lauter_loading_kgm2"],
            mash_thickness_qt_lb=(batch.lauter.strike_water_vol_gal * 4 / grainbill_wt
                                   if grainbill_wt else None),
            first_runnings_avg_extract_p=m["first_runnings_avg_extract_p"],
            final_brewhouse_eff_pct=m["final_brewhouse_eff_pct"],
        )
        # composition-aware: each grain's share of the bill (Scope v2's "composition-aware trends")
        for g in batch.grains:
            row[f"grain_pct__{g.name}"] = (round(100 * g.weight_lb / grainbill_wt, 1)
                                            if grainbill_wt else None)
    else:
        row.update(grainbill_weight_lb=None, lauter_loading_kgm2=None, mash_thickness_qt_lb=None,
                   first_runnings_avg_extract_p=None, final_brewhouse_eff_pct=None)

    if batch.brewhouse:
        m = knockout_metrics(batch.brewhouse, const)
        row.update(predicted_knockout_vol_bbl=m["predicted_knockout_vol_bbl"],
                   kettle_whirlpool_hop_rate_lb_bbl=m["kettle_whirlpool_hop_rate_lb_bbl"],
                   trub_loss_pct=m["trub_loss_pct"], hop_loss_pct=m["hop_loss_pct"])
    else:
        row.update(predicted_knockout_vol_bbl=None, kettle_whirlpool_hop_rate_lb_bbl=None,
                   trub_loss_pct=None, hop_loss_pct=None)

    if batch.cellar:
        m = cellar_metrics(batch.cellar, const)
        row.update(predicted_centrifuge_out_vol_bbl=m["predicted_centrifuge_out_vol_bbl"],
                   dry_hop_rate_lb_bbl=m["dry_hop_rate_lb_bbl"], packaging_loss_pct=m["packaging_loss_pct"])
    else:
        row.update(predicted_centrifuge_out_vol_bbl=None, dry_hop_rate_lb_bbl=None, packaging_loss_pct=None)

    return row


def batch_dataframe(batches: dict, const: Constants = Constants()):
    """{batch_number: Batch} -> one-row-per-batch pandas DataFrame, sorted by batch number."""
    import pandas as pd
    rows = [batch_row(b, const) for b in batches.values()]
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("batch_number").reset_index(drop=True)
    return df


def refit_dataframe(batches: dict, retention_pct: float = DEFAULT_RETENTION_PCT):
    """One row per batch with lauter detail: the auto-fit LauterParams (autofit.py) plus the
    reproduction error against the measured runoff extract, for review before trusting a fit."""
    import pandas as pd
    fitted = fit_all(batches, retention_pct=retention_pct)
    rows = []
    for batch_no, params in fitted.items():
        b = batches[batch_no]
        measured = b.lauter.lauter_runoff_extract_p
        pred = predicted_runoff_extract_p(b.lauter, b.grains, params)
        rows.append(dict(
            batch_number=batch_no, beer=b.beer,
            fre_pct=round(params.fre_pct, 2), retention_pct=round(params.retention_pct, 2),
            measured_runoff_p=measured, predicted_runoff_p=round(pred, 4),
            reproduction_error_pct=round(100 * abs(pred - measured) / measured, 6) if measured else None,
        ))
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("batch_number").reset_index(drop=True)
    return df

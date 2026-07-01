"""
autofit.py — Karben4 QM Yield Tool · per-batch lauter-curve fit (increment 5, replaces the Excel Solver)
=============================================================================================================
Fits LauterParams (FRE_pct, retention_pct) per batch so predicted_runoff_extract_p() reproduces the
batch's known measured runoff extract (LauterInputs.lauter_runoff_extract_p) — the same thing the
brewery currently does by hand with Excel Solver (Lauter_Checks_2 'Analysis' tab, one column per beer).

WHY RETENTION IS HELD FIXED, NOT FIT: each batch gives exactly one measured data point (the
volume-averaged runoff gravity), but the model has two free parameters (FRE_pct, retention_pct).
One equation, two unknowns is underdetermined — you need either a second data point per batch (a
partial-runoff gravity sample, which the DOE's measurement protocol would provide — see "DOE Design
— Lauter Yield Study") or a cross-batch assumption. The brewery's Excel Solver resolves this with a
more elaborate joint regression across all beers; that joint fit is exactly what "Loading Penalty
Analysis" showed to be overfit/confounded on the current data (loading 85% confounded with
thickness, permutation test p=0.64). Rather than reproduce a fit already known to be fragile, this
module makes the simpler assumption explicit: retention_pct is held at a fixed value (the dataset's
own Solver-fitted values only span 91.4-95.6%, a narrow range — see DEFAULT_RETENTION_PCT below) and
FRE_pct — which varies hugely by beer/mash (39-67% in the data, the real per-batch unknown) — is
solved exactly. Retention becomes legitimately fittable once partial-runoff samples exist.

predicted_runoff_extract_p() is monotonically non-decreasing in FRE_pct (raising FRE shifts more of
the runoff toward the high-extract "first runnings" portion, never less), so bisection is exact and
dependency-free — no scipy needed, consistent with the rest of this engine.
"""
from engine import Constants, LauterParams, predicted_runoff_extract_p

# Mean of the brewery's own Solver-fitted retention values (Lauter_Checks_2 Analysis!B21:Q21,
# 14 beers): 93.84%. Used as the fixed assumption — see module docstring for why it's not fit.
DEFAULT_RETENTION_PCT = 93.84


def fit_fre_pct(inp, grains, measured_runoff_p, retention_pct=DEFAULT_RETENTION_PCT,
                 const=Constants(), tol=1e-9, max_iter=100):
    """Bisects for the FRE_pct in [0, const.fre_max_pct] whose predicted runoff extract (P)
    matches measured_runoff_p. Clamps to the boundary if the measured value is outside what the
    model can produce at this retention (e.g. an unusually high- or low-efficiency batch)."""
    lo, hi = 0.0, const.fre_max_pct
    f = lambda fre: predicted_runoff_extract_p(inp, grains, LauterParams(fre, retention_pct), const)
    f_lo, f_hi = f(lo), f(hi)
    if measured_runoff_p <= f_lo:
        return lo
    if measured_runoff_p >= f_hi:
        return hi
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if abs(f_mid - measured_runoff_p) < tol:
            return mid
        if f_mid < measured_runoff_p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def fit_batch(batch, retention_pct=DEFAULT_RETENTION_PCT, const=Constants()):
    """LauterParams fit to one Batch, or None if it lacks grain + lauter detail."""
    if not (batch.grains and batch.lauter):
        return None
    fre = fit_fre_pct(batch.lauter, batch.grains, batch.lauter.lauter_runoff_extract_p,
                       retention_pct, const)
    return LauterParams(fre_pct=fre, retention_pct=retention_pct)


def fit_all(batches: dict, retention_pct=DEFAULT_RETENTION_PCT, const=Constants()) -> dict:
    """{batch_number: LauterParams} for every batch that has grain + lauter detail."""
    out = {}
    for batch_no, b in batches.items():
        params = fit_batch(b, retention_pct, const)
        if params is not None:
            out[batch_no] = params
    return out


if __name__ == "__main__":
    import os
    from data_loader import load_batches

    LAUTER = os.path.join(os.path.dirname(__file__), "..", "..", "Inputs", "Lauter_Checks_2.xlsx")
    YIELDS = os.path.join(os.path.dirname(__file__), "..", "..", "Inputs", "Brewery_Yields.xlsx")
    batches = load_batches(LAUTER, YIELDS)
    fitted = fit_all(batches)

    print(f"Fitted {len(fitted)} batches (retention held at {DEFAULT_RETENTION_PCT}%):")
    worst = 0.0
    for batch_no, params in sorted(fitted.items()):
        b = batches[batch_no]
        pred = predicted_runoff_extract_p(b.lauter, b.grains, params)
        measured = b.lauter.lauter_runoff_extract_p
        err = abs(pred - measured) / measured if measured else 0.0
        worst = max(worst, err)
        print(f"  {batch_no:>12}  {(b.beer or ''):10s}  FRE={params.fre_pct:6.2f}%  "
              f"pred={pred:6.2f}P  measured={measured:6.2f}P  err={err:.2e}")
    print(f"Worst relative reproduction error: {worst:.2e}  ({'OK' if worst < 1e-6 else 'CHECK'})")

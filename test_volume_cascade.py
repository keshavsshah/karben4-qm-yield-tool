"""
test_volume_cascade.py — golden-reference test for the volume-cascade engine (increment 2).

Proves knockout_metrics()/cellar_metrics() reproduce the brewery's cached Excel
formula values (Brewery_Yields.xlsx 'Brewhouse' + 'Cellar' tabs) exactly, the
same way test_engine.py proves the lauter chain. This checks the FORMULA PORT,
not model-vs-reality fit — validate_model.py's validate_yields() already shows
the brewery's own predicted-vs-actual knockout/centrifuge-out errors run up to
~3.6% (expected; trub/hop-loss coefficients are fitted approximations).

Run:  python3 test_volume_cascade.py     (needs openpyxl; reads ../../Inputs/Brewery_Yields.xlsx)
"""
import os, openpyxl
from engine import Constants, SugarAdditions, BrewhouseInputs, CellarInputs, knockout_metrics, cellar_metrics

WB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "Inputs", "Brewery_Yields.xlsx")
TOL = 1e-6  # relative


def rel(a, b):
    return abs(a - b) / abs(b) if b not in (0, None) else 0.0


def num(v):
    return isinstance(v, (int, float))


def main():
    wb = openpyxl.load_workbook(WB_PATH, data_only=True)
    bw, ce, bg = wb["Brewhouse"], wb["Cellar"], wb["Background"]
    # Build Constants from the DATA, not engine defaults — exact reproduction (same
    # discipline as test_engine.py), so this test isn't sensitive to default rounding.
    const = Constants(
        ref_water_density_lb_bbl=bg.cell(15, 2).value,
        runoff_water_density_lb_bbl=bg.cell(17, 2).value,
        boil_water_density_lb_bbl=bg.cell(18, 2).value,
        trub_loss_pct_per_p=bw.cell(8, 2).value,
        hop_loss_normal_pct_per_lb_bbl=bw.cell(9, 2).value,
        hop_loss_high_pct_per_lb_bbl=bw.cell(10, 2).value,
        max_normal_hop_rate_lb_bbl=bw.cell(11, 2).value,
        equip_loss_wp_to_fv_bbl=bw.cell(12, 2).value,
        brewers_crystals_yield_pct=bg.cell(8, 2).value, dme_yield_pct=bg.cell(9, 2).value,
        dextrose_yield_pct=bg.cell(10, 2).value, sucrose_yield_pct=bg.cell(11, 2).value,
        lactose_yield_pct=bg.cell(12, 2).value, maltodextrin_yield_pct=bg.cell(13, 2).value,
        yeast_trub_loss_pct_per_p=ce.cell(6, 2).value,
        dry_hop_loss_pct_per_lb_bbl=ce.cell(7, 2).value,
        cellar_var_loss_pct=ce.cell(8, 2).value,
        cellar_fixed_loss_bbl=ce.cell(9, 2).value,
    )

    worstK = {"eob_vol": 0, "hop_rate": 0, "trub_pct": 0, "hop_pct": 0,
              "trub_bbl": 0, "hop_bbl": 0, "pred_ko": 0}
    nK = 0
    for col in range(2, 52):
        eob_p, hops_lb = bw.cell(30, col).value, bw.cell(21, col).value
        runoff_vol, runoff_p = bw.cell(28, col).value, bw.cell(29, col).value
        if not all(num(x) for x in (eob_p, hops_lb, runoff_vol, runoff_p)):
            continue
        sugars = SugarAdditions(
            brewers_crystals_lb=bw.cell(22, col).value or 0, dme_lb=bw.cell(23, col).value or 0,
            dextrose_lb=bw.cell(24, col).value or 0, sucrose_lb=bw.cell(25, col).value or 0,
            lactose_lb=bw.cell(26, col).value or 0, maltodextrin_lb=bw.cell(27, col).value or 0,
        )
        inp = BrewhouseInputs(runoff_vol, runoff_p, eob_p, hops_lb, sugars)
        m = knockout_metrics(inp, const)
        checks = [
            ("eob_vol", m["end_of_boil_vol_boil_temp_bbl"], bw.cell(39, col).value),
            ("hop_rate", m["kettle_whirlpool_hop_rate_lb_bbl"], bw.cell(41, col).value),
            ("trub_pct", m["trub_loss_pct"], bw.cell(42, col).value),
            ("hop_pct", m["hop_loss_pct"], bw.cell(43, col).value),
            ("trub_bbl", m["trub_loss_bbl"], bw.cell(44, col).value),
            ("hop_bbl", m["hop_loss_bbl"], bw.cell(45, col).value),
            ("pred_ko", m["predicted_knockout_vol_bbl"], bw.cell(46, col).value),
        ]
        for key, mine, excel in checks:
            if num(excel) and excel != 0:
                worstK[key] = max(worstK[key], rel(mine, excel))
        nK += 1

    worstC = {"hop_rate": 0, "trub_pct": 0, "hop_pct": 0, "trub_bbl": 0, "hop_bbl": 0,
              "proc_bbl": 0, "pred_co": 0, "pkg_loss": 0}
    nC = nPkg = 0
    for col in range(2, 52):
        fv, og_p, dry_hops = ce.cell(17, col).value, ce.cell(18, col).value, ce.cell(19, col).value
        if not all(num(x) for x in (fv, og_p, dry_hops)) or fv == 0:
            continue
        co_actual = ce.cell(20, col).value
        bt_override = ce.cell(21, col).value
        pkg_vol = ce.cell(22, col).value
        inp = CellarInputs(fv, og_p, dry_hops,
                            centrifuge_vol_out_actual_bbl=co_actual if num(co_actual) else None,
                            bt_volume_start_of_packaging_bbl=bt_override if num(bt_override) else None,
                            packaged_vol_bbl=pkg_vol if num(pkg_vol) else None)
        m = cellar_metrics(inp, const)
        checks = [
            ("hop_rate", m["dry_hop_rate_lb_bbl"], ce.cell(24, col).value),
            ("trub_pct", m["yeast_trub_loss_pct"], ce.cell(25, col).value),
            ("hop_pct", m["dry_hop_loss_pct"], ce.cell(26, col).value),
            ("trub_bbl", m["yeast_trub_loss_bbl"], ce.cell(27, col).value),
            ("hop_bbl", m["dry_hop_loss_bbl"], ce.cell(28, col).value),
            ("proc_bbl", m["cellar_process_loss_bbl"], ce.cell(29, col).value),
            ("pred_co", m["predicted_centrifuge_out_vol_bbl"], ce.cell(30, col).value),
        ]
        for key, mine, excel in checks:
            if num(excel) and excel != 0:
                worstC[key] = max(worstC[key], rel(mine, excel))
        nC += 1
        excel_pkg = ce.cell(34, col).value
        if num(excel_pkg) and m["packaging_loss_pct"] is not None:
            worstC["pkg_loss"] = max(worstC["pkg_loss"], rel(m["packaging_loss_pct"], excel_pkg))
            nPkg += 1

    print(f"Brewhouse/knockout: {nK} batches checked")
    print(f"Cellar/centrifuge-out: {nC} batches checked, {nPkg} with a packaging-loss check")
    print("Worst RELATIVE error vs Excel (golden reference):")
    ok = True
    for label, worst in (("Knockout", worstK), ("Cellar", worstC)):
        for k, v in worst.items():
            flag = "OK" if v < TOL else "FAIL"
            if v >= TOL:
                ok = False
            print(f"  {label:9} {k:10} {v:.2e}  {flag}")
    print("RESULT:", "ALL PASS — volume-cascade engine reproduces Excel" if ok else "FAILURES present")
    return ok


if __name__ == "__main__":
    main()

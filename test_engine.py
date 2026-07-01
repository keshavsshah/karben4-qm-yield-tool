"""
test_engine.py — golden-reference test for the QM Yield Tool engine.

Proves the flexible (arbitrary-length grain bill) engine reproduces the brewery's
validated Excel numbers. Builds each beer's REAL multi-grain bill from the workbook
grain matrix (any number of grains) — exercising exactly the variability the tool exists for.

Run:  python3 test_engine.py     (needs openpyxl; reads ../../Inputs/Lauter_Checks_2.xlsx)
"""
import os, openpyxl
from engine import (Constants, MillingEff, GrainItem, LauterInputs, LauterParams,
                    grain_extract_lb, vorlauf_extract_lb, grainbill_weight_lb,
                    lauter_metrics, predicted_runoff_extract_p)

WB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "Inputs", "Lauter_Checks_2.xlsx")
TOL = 1e-6  # relative


def parse_grains(ws):
    """Read the beer tab's grain matrix into an arbitrary-length GrainItem list.
    Columns from B onward where row 33 (Grain Name) is non-empty; averaged
    per-grain weight/yield/moisture live in rows 82/83/84, mill class in row 86."""
    grains = []
    col = 2
    while True:
        name = ws.cell(33, col).value
        if name in (None, ""):
            break
        wt = ws.cell(82, col).value
        if isinstance(wt, (int, float)) and wt > 0:
            grains.append(GrainItem(
                name=str(name), weight_lb=wt,
                cgdb_yield_pct=ws.cell(83, col).value,
                moisture_pct=ws.cell(84, col).value,
                mill_yield_class=(ws.cell(86, col).value or "N"),
            ))
        col += 1
    return grains


def rel(a, b):
    return abs(a - b) / abs(b) if b not in (0, None) else 0.0


def main():
    wb = openpyxl.load_workbook(WB_PATH, data_only=True)
    A = wb["Analysis"]
    bg = wb["Background"]
    # Constants come from the DATA (Background tab), not engine defaults — exact reproduction.
    const = Constants(
        foundation_water_bbl=bg.cell(7, 2).value,
        ref_runoff_mass_per_ext=bg.cell(9, 2).value,
        fre_max_pct=bg.cell(10, 2).value,
        retention_min_pct=bg.cell(11, 2).value,
        retention_max_pct=bg.cell(12, 2).value,
        lauter_area_m2=bg.cell(13, 2).value,
        ref_water_density_lb_bbl=bg.cell(14, 2).value,
        runoff_water_density_lb_bbl=bg.cell(15, 2).value,
    )
    # fitted params per beer (normal-mash group, Analysis rows 19/20/21)
    params = {}
    for c in range(2, 18):
        b = A.cell(19, c).value
        if b:
            params[b] = LauterParams(fre_pct=A.cell(20, c).value, retention_pct=A.cell(21, c).value)

    beers = [s for s in wb.sheetnames if s not in ("Analysis", "Grain", "Background")]
    worst = {"grain_extract": 0, "vorlauf_extract": 0, "grainbill_wt": 0,
             "loading": 0, "fr_avg": 0, "runoff_mass": 0, "final_bh_eff": 0, "runoff_pred_vs_meas": 0}
    n_grains_total = 0

    for tab in beers:
        ws = wb[tab]
        B = lambda r: ws.cell(r, 2).value
        grains = parse_grains(ws)
        n_grains_total += len(grains)

        # --- flexible grain calc vs cached B11 / B12 / B10 ---
        worst["grain_extract"] = max(worst["grain_extract"], rel(grain_extract_lb(grains), B(11)))
        worst["vorlauf_extract"] = max(worst["vorlauf_extract"], rel(vorlauf_extract_lb(grains), B(12)))
        worst["grainbill_wt"] = max(worst["grainbill_wt"], rel(grainbill_weight_lb(grains), B(10)))

        # --- full lauter chain vs cached ---
        inp = LauterInputs(B(6), B(7), B(8), B(9))
        m = lauter_metrics(inp, grains, const)
        worst["loading"] = max(worst["loading"], rel(m["lauter_loading_kgm2"], B(13)))
        worst["fr_avg"] = max(worst["fr_avg"], rel(m["first_runnings_avg_extract_p"], B(20)))
        worst["runoff_mass"] = max(worst["runoff_mass"], rel(m["runoff_mass_lb"], B(22)))
        worst["final_bh_eff"] = max(worst["final_bh_eff"], rel(m["final_brewhouse_eff_pct"], B(24)))

        # --- predicted runoff °P vs MEASURED (normal-mash beers) ---
        if tab in params:
            pred = predicted_runoff_extract_p(inp, grains, params[tab], const)
            worst["runoff_pred_vs_meas"] = max(worst["runoff_pred_vs_meas"], rel(pred, B(9)))

    print(f"Beers: {len(beers)} | total grain lines parsed: {n_grains_total} (avg {n_grains_total/len(beers):.1f}/beer)")
    print("Worst RELATIVE error vs Excel (golden reference):")
    ok = True
    for k, v in worst.items():
        flag = "OK" if v < TOL else "FAIL"
        if v >= TOL:
            ok = False
        print(f"  {k:22} {v:.2e}  {flag}")
    print("RESULT:", "ALL PASS — flexible engine reproduces Excel" if ok else "FAILURES present")
    return ok


if __name__ == "__main__":
    main()

"""
app.py — Karben4 QM Yield Tool · Streamlit UI (increment 4)
=============================================================
Single-user desktop tool for the Quality Manager (Scope v2 / QM feedback, 2026-06-24):
brewers don't use this, there are no alerts/SPC, and the dashboard is recipe-formulation
TRENDS over batch actuals, not per-batch quality control. Results are read here, then
the QM manually transcribes them into paper brewlogs + Ekos.

Run:  streamlit run app.py     (needs streamlit, pandas, openpyxl)
"""
import math
import os
import altair as alt
import pandas as pd
import streamlit as st

import onedrive
from data_loader import load_batches, Batch
from engine import GrainItem, LauterInputs, SugarAdditions, BrewhouseInputs, CellarInputs, lauter_metrics, Constants
from analysis import batch_dataframe, refit_dataframe
from autofit import fit_all, DEFAULT_RETENTION_PCT
from batch_store import load_manual_batches, save_manual_batch, delete_manual_batch
from display import column_config
import theme

LAUTER_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "..", "Inputs", "Lauter_Checks_2.xlsx")
YIELDS_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "..", "Inputs", "Brewery_Yields.xlsx")
EMPTY_GRAIN_ROW = {"name": "", "weight_lb": 0.0, "cgdb_yield_pct": 80.0, "moisture_pct": 4.0, "mill_yield_class": "N"}

st.set_page_config(page_title="Karben4 QM Yield Tool", layout="wide")
theme.apply()


@st.cache_data
def _load_workbooks(lauter_path, yields_path):
    return load_batches(lauter_path, yields_path)


def _load_all(lauter_path, yields_path):
    """Workbook batches + manually-added ones layered on top (manual wins on a shared
    Batch Number). Not cached — manual batches are a small local JSON read, cheap
    enough to re-read every rerun so a just-added batch shows up immediately."""
    batches = dict(_load_workbooks(lauter_path, yields_path))
    batches.update(load_manual_batches())
    return batches


@st.cache_data
def _refit(_batches, retention_pct):
    # _batches is prefixed with "_" so Streamlit doesn't try to hash the Batch objects;
    # retention_pct alone is enough to key the cache since that's the only thing that varies here.
    return refit_dataframe(_batches, retention_pct=retention_pct)


@st.cache_data(ttl=300, show_spinner="Fetching from OneDrive...")
def _onedrive_workbook(item_path: str):
    return onedrive.fetch_workbook(item_path)


def sidebar_sources():
    st.sidebar.header("Data sources")

    if onedrive.is_configured():
        lauter_item = onedrive.get_config("MS_LAUTER_ITEM_PATH", "Inputs/Lauter_Checks_2.xlsx")
        yields_item = onedrive.get_config("MS_YIELDS_ITEM_PATH", "Inputs/Brewery_Yields.xlsx")
        st.sidebar.success("Reading live from OneDrive/SharePoint.")
        if st.sidebar.button("Refresh from OneDrive"):
            _onedrive_workbook.clear()
        st.sidebar.caption(f"Lauter: `{lauter_item}`  \nYields: `{yields_item}`  \n"
                            "(cached 5 min — click Refresh for the latest edits)")
        try:
            return _onedrive_workbook(lauter_item), _onedrive_workbook(yields_item)
        except Exception as e:
            st.sidebar.error(f"OneDrive fetch failed, falling back to local: {e}")

    lauter_file = st.sidebar.file_uploader("Lauter_Checks workbook (.xlsx)", type="xlsx", key="lauter")
    yields_file = st.sidebar.file_uploader("Brewery_Yields workbook (.xlsx)", type="xlsx", key="yields")
    lauter_path = lauter_file if lauter_file is not None else LAUTER_DEFAULT
    yields_path = yields_file if yields_file is not None else YIELDS_DEFAULT
    st.sidebar.caption("Defaults to the workbooks in Inputs/ if nothing is uploaded. "
                        "Batches added via the 'Add batch' tab are layered on top either way.")
    return lauter_path, yields_path


def beer_filter(df, key):
    """Shared filter row: pick beers to view, or explicitly ask for everything.
    Defaults to the most recently brewed beer only, so tables don't open full."""
    beers = sorted(df["beer"].dropna().unique())
    default = [beers[-1]] if beers else []
    c1, c2 = st.columns([3, 1])
    with c1:
        pick = st.multiselect("Beer", beers, default=default, key=f"{key}_beer")
    with c2:
        st.write("")
        show_all = st.checkbox("Show all batches", key=f"{key}_all")
    if show_all:
        return df
    if not pick:
        st.info("Pick a beer above, or check 'Show all batches'.")
        return df.iloc[0:0]
    return df[df["beer"].isin(pick)]


def page_data(df):
    st.subheader("Data")
    st.caption("One row per batch (Batch Number), joined from both workbooks plus anything added "
               "by hand. Blank cells mean that stage's source data isn't available for this batch.")
    sub = beer_filter(df, "data")
    if not sub.empty:
        st.dataframe(sub, use_container_width=True, column_config=column_config(sub), hide_index=True)
    st.caption(
        f"{len(df)} batches loaded total — "
        f"{df['lauter_loading_kgm2'].notna().sum()} with lauter detail, "
        f"{df['predicted_knockout_vol_bbl'].notna().sum()} with knockout, "
        f"{df['predicted_centrifuge_out_vol_bbl'].notna().sum()} with centrifuge-out."
    )


def page_trends(df):
    st.subheader("Trends — recipe formulation")
    st.caption("Aggregate trends across batches, for recipe formulation. "
               "Not per-batch SPC/alerts — the QM has a separate system for that (2026-06-24).")
    candidates = ["final_brewhouse_eff_pct", "lauter_loading_kgm2", "mash_thickness_qt_lb",
                  "predicted_knockout_vol_bbl", "predicted_centrifuge_out_vol_bbl", "packaging_loss_pct"]
    metric = st.selectbox("Metric vs. batch", [c for c in candidates if c in df.columns])
    plot_df = df.dropna(subset=[metric, "batch_number"])
    if plot_df.empty:
        st.info("No batches have this metric populated yet.")
        return
    st.line_chart(plot_df.set_index("batch_number")[metric])

    sub = beer_filter(df, "trends")
    if not sub.empty:
        st.dataframe(sub, use_container_width=True, column_config=column_config(sub), hide_index=True)


def page_levers(df):
    st.subheader("Levers — efficiency vs. loading / thickness")
    st.caption("The DOE's question, viewed on existing data — confounded "
               "(see the Loading Penalty Analysis note; the real answer needs the designed experiment).")
    sub = df.dropna(subset=["lauter_loading_kgm2", "mash_thickness_qt_lb", "final_brewhouse_eff_pct"])
    if sub.empty:
        st.info("No batches have loading + thickness + efficiency all populated.")
        return
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Efficiency vs. loading")
        st.scatter_chart(sub, x="lauter_loading_kgm2", y="final_brewhouse_eff_pct")
    with c2:
        st.caption("Efficiency vs. mash thickness")
        st.scatter_chart(sub, x="mash_thickness_qt_lb", y="final_brewhouse_eff_pct")
    corr = sub[["lauter_loading_kgm2", "mash_thickness_qt_lb"]].corr().iloc[0, 1]
    st.metric("corr(loading, thickness) in this data", f"{corr:.2f}")


def page_by_beer(df):
    st.subheader("By beer")
    beers = sorted(df["beer"].dropna().unique())
    if not beers:
        st.info("No beers loaded.")
        return
    beer = st.selectbox("Beer", beers, index=len(beers) - 1)
    sub = df[df["beer"] == beer].sort_values("batch_number")
    st.dataframe(sub, use_container_width=True, column_config=column_config(sub), hide_index=True)
    if sub["final_brewhouse_eff_pct"].notna().sum() > 1:
        st.line_chart(sub.set_index("batch_number")["final_brewhouse_eff_pct"])


def page_refit(df, batches):
    st.subheader("Re-fit — lauter-curve parameters")
    st.caption(
        "Per-batch FRE_pct, solved exactly (bisection) to reproduce the measured runoff extract. "
        "retention_pct is held fixed (not jointly fit) — one measured point per batch can't pin down "
        "both parameters; see autofit.py's docstring for why this is simpler than the Excel Solver "
        "on purpose, not a shortfall. This replaces the brewery's manual Solver step."
    )
    retention_pct = st.slider("Assumed retention_pct (held fixed across all batches)",
                               min_value=90.0, max_value=98.0, value=DEFAULT_RETENTION_PCT, step=0.1)
    rdf = _refit(batches, retention_pct)
    if rdf.empty:
        st.info("No batches with lauter detail to fit.")
        return
    sub = beer_filter(rdf, "refit")
    if not sub.empty:
        st.dataframe(sub, use_container_width=True, column_config=column_config(sub), hide_index=True)
    st.caption(f"{len(rdf)} batches fit total. Worst reproduction error: "
               f"{rdf['reproduction_error_pct'].max():.2e}% (should be ~0 — this is an exact fit, not a model check).")
    st.download_button("Download fitted params (CSV)", rdf.to_csv(index=False),
                        file_name="lauter_params_autofit.csv", mime="text/csv")


def page_transcription(df):
    st.subheader("Transcription card")
    st.caption("Computed values for one batch, formatted to copy into paper brewlogs / Ekos "
               "(the QM's actual workflow — confirmed 2026-06-24). Nothing here writes back automatically.")
    ids = df["batch_number"].tolist()
    if not ids:
        st.info("No batches loaded.")
        return
    bid = st.selectbox("Batch Number", ids, index=len(ids) - 1)
    row = df[df["batch_number"] == bid].iloc[0]

    def fmt(val, decimals=2):
        """Round numeric values for hand-copying; drop missing values (None, NaN, NaT)."""
        if val is None or pd.isna(val):
            return None
        return round(val, decimals) if isinstance(val, float) else val

    fields = [
        ("Beer", fmt(row.get("beer"))), ("Brew date", fmt(row.get("brew_date"))),
        ("Grain bill (lb)", fmt(row.get("grainbill_weight_lb"), 1)),
        ("Lauter loading (kg/m²)", fmt(row.get("lauter_loading_kgm2"), 1)),
        ("Mash thickness (qt/lb)", fmt(row.get("mash_thickness_qt_lb"))),
        ("First-runnings avg extract (°P)", fmt(row.get("first_runnings_avg_extract_p"))),
        ("Final brewhouse efficiency (%)", fmt(row.get("final_brewhouse_eff_pct"))),
        ("Predicted knockout volume (bbl)", fmt(row.get("predicted_knockout_vol_bbl"))),
        ("Predicted centrifuge-out volume (bbl)", fmt(row.get("predicted_centrifuge_out_vol_bbl"))),
        ("Packaging loss (%)", fmt(row.get("packaging_loss_pct"))),
    ]
    for label, val in fields:
        if val is not None:
            st.text(f"{label}: {val}")


def page_add_batch(batches):
    st.subheader("Add batch")
    st.caption("Type in a batch's numbers — before or without it ever landing in the Excel workbooks. "
               "Saved locally (manual_batches.json next to this script) and shows up everywhere else "
               "in the app immediately. A batch number that matches a workbook batch overrides it here.")

    existing_beers = sorted({b.beer for b in batches.values() if b.beer})
    NEW_BEER_OPTION = "+ Add new beer..."
    beer_choice = st.selectbox("Beer", options=existing_beers + [NEW_BEER_OPTION], key="beer_choice")
    if beer_choice == NEW_BEER_OPTION:
        beer = st.text_input("New beer name", key="new_beer_name")
    else:
        beer = beer_choice

    with st.form("add_batch_form", clear_on_submit=False):
        c1, c3 = st.columns(2)
        with c1:
            batch_number = st.number_input("Batch Number", min_value=0.0, step=0.01, format="%.2f")
        with c3:
            brew_date = st.date_input("Brew date", value=None)

        st.markdown("**Lauter** (required for loading / efficiency / re-fit)")
        l1, l2, l3, l4 = st.columns(4)
        with l1:
            strike_temp = st.number_input("Strike water temp (°F)", value=165.0)
        with l2:
            strike_vol = st.number_input("Strike water vol (gal)", value=0.0)
        with l3:
            runoff_vol = st.number_input("Lauter runoff vol (bbl)", value=17.6)
        with l4:
            runoff_p = st.number_input("Lauter runoff extract (°P)", value=0.0)

        st.markdown("**Grain bill** — add a row per grain (arbitrary length, no fixed slots)")
        grains_df = st.data_editor(
            pd.DataFrame([EMPTY_GRAIN_ROW]), num_rows="dynamic", use_container_width=True,
            key="grain_editor",
            column_config={
                "name": st.column_config.TextColumn("Grain"),
                "weight_lb": st.column_config.NumberColumn("Weight (lb)", format="%.1f"),
                "cgdb_yield_pct": st.column_config.NumberColumn("CGDB Yield (%)", format="%.1f"),
                "moisture_pct": st.column_config.NumberColumn("Moisture (%)", format="%.1f"),
                "mill_yield_class": st.column_config.SelectboxColumn("Mill Class", options=["N", "Y1", "Y2"]),
            },
        )

        include_brewhouse = st.checkbox("Add knockout (Brewhouse) data")
        eob_p = hops_lb = 0.0
        sugars_kwargs = {}
        if include_brewhouse:
            b1, b2 = st.columns(2)
            with b1:
                eob_p = st.number_input("End-of-boil extract (°P)", value=0.0)
            with b2:
                hops_lb = st.number_input("Kettle/whirlpool hops (lb)", value=0.0)
            with st.expander("Sugar / adjunct additions (optional, default 0)"):
                s1, s2, s3 = st.columns(3)
                with s1:
                    sugars_kwargs["brewers_crystals_lb"] = st.number_input("Brewers Crystals (lb)", value=0.0)
                    sugars_kwargs["sucrose_lb"] = st.number_input("Sucrose (lb)", value=0.0)
                with s2:
                    sugars_kwargs["dme_lb"] = st.number_input("DME (lb)", value=0.0)
                    sugars_kwargs["lactose_lb"] = st.number_input("Lactose (lb)", value=0.0)
                with s3:
                    sugars_kwargs["dextrose_lb"] = st.number_input("Dextrose (lb)", value=0.0)
                    sugars_kwargs["maltodextrin_lb"] = st.number_input("Maltodextrin (lb)", value=0.0)

        include_cellar = st.checkbox("Add cellar data")
        fv_vol = fv_og = dry_hops = co_actual = pkg_vol = 0.0
        if include_cellar:
            c1, c2, c3 = st.columns(3)
            with c1:
                fv_vol = st.number_input("Effective FV wort vol (bbl)", value=0.0)
                co_actual = st.number_input("Centrifuge vol out, actual (bbl, optional)", value=0.0)
            with c2:
                fv_og = st.number_input("Effective FV wort OG (°P)", value=0.0)
                pkg_vol = st.number_input("Packaged vol (bbl, optional)", value=0.0)
            with c3:
                dry_hops = st.number_input("Dry hops (lb)", value=0.0)

        submitted = st.form_submit_button("Save batch")

    if not submitted:
        return

    if not batch_number:
        st.error("Batch Number is required.")
        return

    grains = [
        GrainItem(name=str(r["name"]), weight_lb=r["weight_lb"], cgdb_yield_pct=r["cgdb_yield_pct"],
                  moisture_pct=r["moisture_pct"], mill_yield_class=r.get("mill_yield_class") or "N")
        for r in grains_df.to_dict("records") if r.get("name") and r.get("weight_lb", 0) > 0
    ]
    lauter = LauterInputs(strike_temp, strike_vol, runoff_vol, runoff_p) if runoff_p > 0 else None

    brewhouse = None
    if include_brewhouse and eob_p > 0:
        brewhouse = BrewhouseInputs(runoff_vol, runoff_p, eob_p, hops_lb, SugarAdditions(**sugars_kwargs))

    cellar = None
    if include_cellar and fv_vol > 0:
        cellar = CellarInputs(fv_vol, fv_og, dry_hops,
                               centrifuge_vol_out_actual_bbl=co_actual or None,
                               packaged_vol_bbl=pkg_vol or None)

    batch = Batch(batch_number=batch_number, beer=beer or None,
                  brew_date=str(brew_date) if brew_date else None,
                  grains=grains, lauter=lauter, brewhouse=brewhouse, cellar=cellar)
    save_manual_batch(batch)
    st.success(f"Saved batch {batch_number} ({beer or 'no beer name'}).")

    if grains and lauter:
        m = lauter_metrics(lauter, grains)
        st.caption(f"Preview — loading {m['lauter_loading_kgm2']:.1f} kg/m², "
                   f"final brewhouse efficiency {m['final_brewhouse_eff_pct']:.1f}%.")
    # No explicit st.rerun() here: form_submit_button already triggers Streamlit's normal
    # rerun, and manual batches are re-read fresh (not cached) every rerun — so the new
    # batch shows up on every other tab immediately. An extra st.rerun() would wipe this
    # success message before it's ever shown (it fired before the fix below was caught
    # by clicking through to "Manage manual batches" to confirm the save actually worked).


def page_manage_manual():
    st.subheader("Manually-added batches")
    manual = load_manual_batches()
    if not manual:
        st.info("None yet — add one in the 'Add batch' tab.")
        return
    rows = [{"batch_number": bn, "beer": b.beer, "brew_date": b.brew_date,
             "has_lauter": b.lauter is not None, "has_brewhouse": b.brewhouse is not None,
             "has_cellar": b.cellar is not None} for bn, b in sorted(manual.items())]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    to_delete = st.selectbox("Delete a batch", [None] + list(manual.keys()))
    if to_delete and st.button(f"Delete batch {to_delete}", type="primary"):
        delete_manual_batch(to_delete)
        # The table/dropdown above were already built from the pre-delete list this run,
        # so (unlike page_add_batch) this DOES need a rerun to refresh them. st.success()
        # would get wiped by that immediate rerun before it's shown — st.toast() is built
        # to survive exactly this (it's queued to the frontend, not just appended to the
        # script's render tree).
        st.toast(f"Deleted batch {to_delete}.")
        st.rerun()


# (field, label, unit, min, max, step, group) — matches engine.Constants field order.
MODEL_SLIDER_SPEC = [
    ("lauter_area_m2", "Lauter tun area", "m²", 0.5, 4.0, 0.005, "Lauter geometry"),
    ("foundation_water_bbl", "Foundation water", "bbl", 0.0, 3.0, 0.05, "Lauter geometry"),
    ("ref_runoff_mass_per_ext", "Reference runoff mass per extract", "lb wort / lb extract", 5.0, 30.0, 0.1, "Lauter geometry"),
    ("fre_max_pct", "FRE max (first-runnings-extract clamp)", "%", 50.0, 100.0, 0.5, "Runoff curve"),
    ("retention_min_pct", "Retention min", "%", 50.0, 100.0, 0.5, "Runoff curve"),
    ("retention_max_pct", "Retention max", "%", 50.0, 100.0, 0.5, "Runoff curve"),
    ("ref_water_density_lb_bbl", "Reference water density", "lb/bbl", 200.0, 300.0, 0.1, "Densities & conversions"),
    ("runoff_water_density_lb_bbl", "Runoff water density", "lb/bbl", 200.0, 300.0, 0.1, "Densities & conversions"),
    ("gal_per_bbl", "Gallons per barrel", "gal/bbl", 25.0, 35.0, 0.1, "Densities & conversions"),
    ("boil_water_density_lb_bbl", "Boil water density", "lb/bbl", 200.0, 300.0, 0.1, "Densities & conversions"),
    ("trub_loss_pct_per_p", "Trub loss rate", "% WP vol / °P", 0.0, 2.0, 0.01, "Knockout / brewhouse losses"),
    ("hop_loss_normal_pct_per_lb_bbl", "Hop loss rate (normal)", "% WP vol / (lb/bbl)", 0.0, 10.0, 0.05, "Knockout / brewhouse losses"),
    ("hop_loss_high_pct_per_lb_bbl", "Hop loss rate (high, above threshold)", "% WP vol / (lb/bbl)", 0.0, 10.0, 0.05, "Knockout / brewhouse losses"),
    ("max_normal_hop_rate_lb_bbl", "Hop rate threshold (normal→high)", "lb/bbl", 0.0, 3.0, 0.01, "Knockout / brewhouse losses"),
    ("equip_loss_wp_to_fv_bbl", "Equipment loss, WP→FV", "bbl", 0.0, 3.0, 0.01, "Knockout / brewhouse losses"),
    ("brewers_crystals_yield_pct", "Brewer's crystals yield", "%", 50.0, 100.0, 0.1, "Sugar/adjunct yields (fixed set)"),
    ("dme_yield_pct", "DME yield", "%", 50.0, 100.0, 0.1, "Sugar/adjunct yields (fixed set)"),
    ("dextrose_yield_pct", "Dextrose yield", "%", 50.0, 100.0, 0.1, "Sugar/adjunct yields (fixed set)"),
    ("sucrose_yield_pct", "Sucrose yield", "%", 50.0, 100.0, 0.1, "Sugar/adjunct yields (fixed set)"),
    ("lactose_yield_pct", "Lactose yield", "%", 50.0, 100.0, 0.1, "Sugar/adjunct yields (fixed set)"),
    ("maltodextrin_yield_pct", "Maltodextrin yield", "%", 50.0, 100.0, 0.1, "Sugar/adjunct yields (fixed set)"),
    ("yeast_trub_loss_pct_per_p", "Yeast/trub loss rate", "% FV wort vol / °P", 0.0, 2.0, 0.01, "Cellar losses"),
    ("dry_hop_loss_pct_per_lb_bbl", "Dry hop loss rate", "% FV wort vol / (lb/bbl)", 0.0, 10.0, 0.05, "Cellar losses"),
    ("cellar_var_loss_pct", "Cellar variable loss", "% FV wort vol", 0.0, 5.0, 0.01, "Cellar losses"),
    ("cellar_fixed_loss_bbl", "Cellar fixed loss", "bbl", 0.0, 5.0, 0.05, "Cellar losses"),
]

_DEFAULT_CONST = Constants()


def _model_gen() -> int:
    return st.session_state.get("model_reset_gen", 0)


def _model_const_from_state() -> Constants:
    gen = _model_gen()
    overrides = {field: st.session_state[f"model_{field}_{gen}"] for field, *_ in MODEL_SLIDER_SPEC
                 if f"model_{field}_{gen}" in st.session_state}
    return Constants(**overrides)


def _cum_avg_curve(fr_avg, ref_first, ref_runoff, retention_pct):
    """Cumulative average gravity collected so far, as a function of % of reference
    runoff mass collected — matches how a measured final extract is itself computed
    (a cumulative average), not the much-faster-falling instantaneous decay value."""
    ref_late = ref_runoff - ref_first
    a = retention_pct / 100
    ln_a = math.log(a)
    rows = []
    for x in range(0, 101):
        mc = (x / 100) * ref_runoff
        b_first = min(mc, ref_first)
        b_late = max(mc - ref_first, 0)
        if b_late <= 0 or mc <= 0:
            y = fr_avg
        else:
            b_late_pct = 100 * b_late / ref_late if ref_late > 0 else 0
            b_late_avg_p = (fr_avg / ln_a) * (a ** b_late_pct - 1) / b_late_pct if b_late_pct > 0 else fr_avg
            b_tot_ext = (fr_avg / 100) * b_first + (b_late_avg_p / 100) * b_late
            y = 100 * b_tot_ext / mc
        rows.append(dict(x_pct=x, gravity_p=y))
    return rows


def _runoff_curve_data(batches: dict, const: Constants):
    """Per-beer lauter/runoff curves (mean grain-bill & runoff inputs across each beer's
    batches with lauter detail) reshaped live by `const`, plus each beer's own average
    measured final runoff extract plotted at its average % of reference runoff collected."""
    lauter_batches = {bn: b for bn, b in batches.items() if b.grains and b.lauter}
    if not lauter_batches:
        return None

    fitted = fit_all(lauter_batches, DEFAULT_RETENTION_PCT, const)

    rows = []
    for bn, b in lauter_batches.items():
        params = fitted.get(bn)
        if params is None:
            continue
        m = lauter_metrics(b.lauter, b.grains, const)
        ref_runoff = const.ref_runoff_mass_per_ext * m["grain_extract_lb"]
        if ref_runoff <= 0:
            continue
        fre_pct = min(params.fre_pct, const.fre_max_pct)
        retention_pct = min(max(params.retention_pct, const.retention_min_pct), const.retention_max_pct)
        ref_first = (fre_pct / 100) * m["vorlauf_wort_mass_lb"]
        rows.append(dict(
            batch_number=bn, beer=b.beer, fr_avg=m["first_runnings_avg_extract_p"],
            ref_first=ref_first, ref_runoff=ref_runoff, retention_pct=retention_pct,
            measured_x_pct=100 * m["runoff_mass_lb"] / ref_runoff,
            measured_p=b.lauter.lauter_runoff_extract_p,
        ))
    if not rows:
        return None
    agg = pd.DataFrame(rows)

    curve_rows = []
    point_rows = []
    for beer, g in agg.groupby("beer"):
        fr_avg = g["fr_avg"].mean()
        ref_first = g["ref_first"].mean()
        ref_runoff = g["ref_runoff"].mean()
        retention_pct = g["retention_pct"].mean()
        for row in _cum_avg_curve(fr_avg, ref_first, ref_runoff, retention_pct):
            curve_rows.append({**row, "beer": beer})
        point_rows.append(dict(
            beer=beer, n_batches=len(g),
            x_pct=g["measured_x_pct"].mean(), gravity_p=g["measured_p"].mean(),
        ))
    curve_df = pd.DataFrame(curve_rows)
    points_df = pd.DataFrame(point_rows)

    return curve_df, points_df


def page_model(batches: dict):
    st.subheader("Model coefficients")
    st.caption("These are the brewhouse constants engine.py's calc module runs on "
               "(engine.Constants — defaults are Karben4's). Drag a slider to see how the "
               "whole app's numbers move; Reset restores the shipped defaults everywhere.")

    if st.button("Reset to defaults"):
        # Sliders keep their old value in the browser even after we pop them from
        # session_state (the frontend resends its last widget value on the next rerun),
        # so bump a generation counter to give every slider a fresh key/identity instead.
        st.session_state["model_reset_gen"] = _model_gen() + 1
        st.rerun()

    gen = _model_gen()
    groups = []
    for spec in MODEL_SLIDER_SPEC:
        group = spec[-1]
        if not groups or groups[-1][0] != group:
            groups.append((group, []))
        groups[-1][1].append(spec)

    for group, specs in groups:
        st.markdown(f"**{group}**")
        cols = st.columns(2)
        for i, (field, label, unit, lo, hi, step, _) in enumerate(specs):
            default = getattr(_DEFAULT_CONST, field)
            with cols[i % 2]:
                st.slider(f"{label} ({unit})", min_value=lo, max_value=hi, step=step,
                           value=default, key=f"model_{field}_{gen}",
                           help=f"Default: {default}")

    const = _model_const_from_state()
    changed = {field: getattr(const, field) for field, *_ in MODEL_SLIDER_SPEC
               if getattr(const, field) != getattr(_DEFAULT_CONST, field)}
    if changed:
        st.info(f"{len(changed)} coefficient(s) overridden — every other tab's numbers "
                f"(Data, Trends, Levers, By beer, Transcription card) reflect these values.")
    else:
        st.caption("No overrides — the app is running on shipped defaults.")

    st.markdown("### Runoff (lauter) curve, by beer")
    curve_data = _runoff_curve_data(batches, const)
    if curve_data is None:
        st.caption("No batches with lauter detail to plot.")
    else:
        curve_df, points_df = curve_data
        st.caption("One curve per beer (mean grain-bill/runoff inputs across that beer's "
                   "batches with lauter detail) — reshapes live with the sliders above. "
                   "Dot: that beer's average measured final runoff extract, plotted at its "
                   "average % of reference runoff collected — hover for batch count.")

        all_beers = sorted(curve_df["beer"].unique())
        shown_beers = st.multiselect("Beers shown", options=all_beers, default=all_beers,
                                      key="model_curve_beers")
        curve_df = curve_df[curve_df["beer"].isin(shown_beers)]
        points_df = points_df[points_df["beer"].isin(shown_beers)]

        if curve_df.empty:
            st.caption("No beers selected.")
        else:
            curve_chart = alt.Chart(curve_df).mark_line(size=3).encode(
                x=alt.X("x_pct", title="% of reference runoff mass collected"),
                y=alt.Y("gravity_p", title="Gravity (°P)"),
                color=alt.Color("beer", legend=alt.Legend(title="Beer")),
            )
            points_chart = alt.Chart(points_df).mark_circle(size=110, opacity=0.9, stroke="white", strokeWidth=1).encode(
                x=alt.X("x_pct", title="% of reference runoff mass collected"),
                y=alt.Y("gravity_p", title="Gravity (°P)"),
                color=alt.Color("beer", legend=None),
                tooltip=["beer", "n_batches", "x_pct", "gravity_p"],
            )
            st.altair_chart(curve_chart + points_chart, use_container_width=True)

    return const


def main():
    st.title("Karben4 QM Yield Tool")
    st.markdown(theme.HEX_RULE_HTML, unsafe_allow_html=True)
    st.caption("Single-user analysis tool for the Quality Manager (Scope v2, 2026-06-24). "
               "Brewers don't use this — results are read here, then transcribed by hand into paper brewlogs + Ekos.")
    lauter_path, yields_path = sidebar_sources()
    const = _model_const_from_state()
    try:
        batches = _load_all(lauter_path, yields_path)
        df = batch_dataframe(batches, const)
    except Exception as e:
        st.error(f"Couldn't load the workbooks: {e}")
        return

    tabs = st.tabs(["Add batch", "Model", "Trends", "Levers", "By beer", "Re-fit", "Transcription card",
                     "Manage manual batches", "Data"])
    with tabs[0]:
        page_add_batch(batches)
    with tabs[1]:
        page_model(batches)
    with tabs[2]:
        page_trends(df)
    with tabs[3]:
        page_levers(df)
    with tabs[4]:
        page_by_beer(df)
    with tabs[5]:
        page_refit(df, batches)
    with tabs[6]:
        page_transcription(df)
    with tabs[7]:
        page_manage_manual()
    with tabs[8]:
        page_data(df)


if __name__ == "__main__":
    main()

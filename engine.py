"""
engine.py — Karben4 QM Yield Tool · calculation engine
========================================================
Increment 1: lauter/extract (brewhouse efficiency).
Increment 2: volume cascade (knockout -> cellar/centrifuge-out -> packaging).

Flexible, batch-actuals-driven port of the validated brewing math
(see "06 Calculation Module — Formula Spec.md"; golden reference validate_model.py,
reproduces Excel at 0.000000%). Increment 2 ports Brewery_Yields.xlsx's Brewhouse
and Cellar tabs (validate_model.py's validate_yields()) the same way: pure
functions reproducing the cached Excel formula values exactly.

KEY DIFFERENCE FROM THE EXCEL SHEET: the grain bill is an **arbitrary-length list**
of grains (any number of grain types + lots), not a rigid 3-turn × 3-lot grid. This
is what lets the tool handle the brewery's real batch-to-batch grain variability
(type / amount / ratio swings, partly inventory-driven) — and the hop schedule is
likewise an open list (used by the volume cascade, increment 2).

Pure functions, no I/O. Tested by test_engine.py against the workbook.
"""
from dataclasses import dataclass, field


# ---------------------------------------------------------------- constants
@dataclass(frozen=True)
class Constants:
    """Brewhouse constants (Lauter_Checks 'Background' tab). Defaults = Karben4's."""
    lauter_area_m2: float = 1.575
    foundation_water_bbl: float = 0.5
    ref_runoff_mass_per_ext: float = 15.0     # lb wort / lb grain extract
    fre_max_pct: float = 80.0
    retention_min_pct: float = 90.0
    retention_max_pct: float = 98.0
    ref_water_density_lb_bbl: float = 258.282
    runoff_water_density_lb_bbl: float = 249.19
    gal_per_bbl: float = 31.0

    # --- volume cascade: Brewhouse tab (Brewery_Yields.xlsx 'Background' + 'Brewhouse' B-column) ---
    boil_water_density_lb_bbl: float = 248.21686928133678
    trub_loss_pct_per_p: float = 0.22557800862190705              # % WP volume / degP of end-of-boil extract
    hop_loss_normal_pct_per_lb_bbl: float = 2.5                   # % WP volume / (lb/bbl hops), up to the rate below
    hop_loss_high_pct_per_lb_bbl: float = 4.225072883016129       # % WP volume / (lb/bbl hops), above the rate below
    max_normal_hop_rate_lb_bbl: float = 0.9684416661938015
    equip_loss_wp_to_fv_bbl: float = 0.43328686183723863

    # --- volume cascade: sugar/adjunct yields (Background B8:B13), fixed finite set ---
    brewers_crystals_yield_pct: float = 96.0
    dme_yield_pct: float = 97.0
    dextrose_yield_pct: float = 90.6
    sucrose_yield_pct: float = 99.7
    lactose_yield_pct: float = 99.5
    maltodextrin_yield_pct: float = 95.0

    # --- volume cascade: Cellar tab B-column ---
    yeast_trub_loss_pct_per_p: float = 0.25918328808949237        # % effective FV wort vol / degP
    dry_hop_loss_pct_per_lb_bbl: float = 2.9287068159690888       # % effective FV wort vol / (lb/bbl dry hops)
    cellar_var_loss_pct: float = 0.0                              # % effective FV wort vol
    cellar_fixed_loss_bbl: float = 1.4653108364892848


@dataclass(frozen=True)
class MillingEff:
    """Low-mill-yield efficiency factors (Analysis tab). Y1/Y2 grains lauter-contribute less."""
    y1_pct: float = 50.0
    y2_pct: float = 50.0


@dataclass
class GrainItem:
    """One grain line in a bill (already averaged across its lots/turns)."""
    name: str
    weight_lb: float
    cgdb_yield_pct: float      # coarse-grind dry-basis yield
    moisture_pct: float
    mill_yield_class: str = "N"   # "N" | "Y1" | "Y2"


@dataclass
class HopItem:
    name: str
    weight_lb: float           # total addition (kettle/WP); used by the volume cascade


@dataclass
class LauterInputs:
    strike_water_temp_f: float
    strike_water_vol_gal: float
    lauter_runoff_vol_bbl: float
    lauter_runoff_extract_p: float


@dataclass
class LauterParams:
    """Per-batch (or per-beer) fitted lautering parameters."""
    fre_pct: float             # first-runnings efficiency
    retention_pct: float       # late-runnings extract retention


# ---------------------------------------------------------------- grain math
def grain_extract_lb(grains: list[GrainItem]) -> float:
    """Total grain extract (lb). Sums over ANY number of grains — the flexible core."""
    return sum((1 - g.moisture_pct / 100) * (g.cgdb_yield_pct / 100) * g.weight_lb
               for g in grains)


def _mill_factor(grain: GrainItem, milling: MillingEff) -> float:
    return {"Y1": milling.y1_pct / 100, "Y2": milling.y2_pct / 100}.get(grain.mill_yield_class, 1.0)


def vorlauf_extract_lb(grains: list[GrainItem], milling: MillingEff = MillingEff()) -> float:
    """Vorlauf extract contribution (lb): grain extract scaled by mill-yield class."""
    return sum(_mill_factor(g, milling) * (1 - g.moisture_pct / 100) * (g.cgdb_yield_pct / 100) * g.weight_lb
               for g in grains)


def grainbill_weight_lb(grains: list[GrainItem]) -> float:
    return sum(g.weight_lb for g in grains)


# ---------------------------------------------------------------- physics
def strike_density_lb_bbl(temp_f: float) -> float:
    t = temp_f
    return (((2.8884822e-9 * t - 2.153831311e-6) * t + 1.428393027673e-4) * t
            + 0.997521046749914) * 2.205 * 117.348


def sg_from_plato(p: float) -> float:
    return p / (258.6 - (227.1 / 258.2) * p) + 1


# ---------------------------------------------------------------- lauter / brewhouse extract
def lauter_metrics(inp: LauterInputs, grains: list[GrainItem],
                   const: Constants = Constants(), milling: MillingEff = MillingEff()) -> dict:
    """Full per-batch lauter/extract chain from actual inputs + actual grain bill."""
    g_ext = grain_extract_lb(grains)
    v_ext = vorlauf_extract_lb(grains, milling)
    g_wt = grainbill_weight_lb(grains)

    loading = (g_wt / 2.205) / const.lauter_area_m2
    rho = strike_density_lb_bbl(inp.strike_water_temp_f)
    vorlauf_water = rho * (inp.strike_water_vol_gal / const.gal_per_bbl)
    vorlauf_wort = vorlauf_water + v_ext
    fr_avg_p = 100 * v_ext / vorlauf_wort

    runoff_sg = sg_from_plato(inp.lauter_runoff_extract_p)
    runoff_mass = runoff_sg * const.runoff_water_density_lb_bbl * inp.lauter_runoff_vol_bbl
    runoff_ext = (inp.lauter_runoff_extract_p / 100) * runoff_mass
    final_bh_eff = 100 * runoff_ext / g_ext

    return dict(
        grainbill_weight_lb=g_wt, grain_extract_lb=g_ext, vorlauf_extract_lb=v_ext,
        lauter_loading_kgm2=loading, strike_density_lb_bbl=rho,
        vorlauf_wort_mass_lb=vorlauf_wort, first_runnings_avg_extract_p=fr_avg_p,
        runoff_gravity_sg=runoff_sg, runoff_mass_lb=runoff_mass,
        runoff_extract_lb=runoff_ext, final_brewhouse_eff_pct=final_bh_eff,
    )


# ---------------------------------------------------------------- runoff curve (predicted)
def predicted_runoff_extract_p(inp: LauterInputs, grains: list[GrainItem], params: LauterParams,
                               const: Constants = Constants(), milling: MillingEff = MillingEff()) -> float:
    """Closed-form predicted total runoff gravity (°P) from the fitted model."""
    m = lauter_metrics(inp, grains, const, milling)
    fr_avg = m["first_runnings_avg_extract_p"]
    vorlauf_wort = m["vorlauf_wort_mass_lb"]
    g_ext = m["grain_extract_lb"]
    runoff_mass = m["runoff_mass_lb"]

    import math
    fre = min(params.fre_pct, const.fre_max_pct)
    r = min(max(params.retention_pct, const.retention_min_pct), const.retention_max_pct)
    ref_runoff = const.ref_runoff_mass_per_ext * g_ext
    ref_first = (fre / 100) * vorlauf_wort
    ref_late = ref_runoff - ref_first
    b_first = min(runoff_mass, ref_first)
    b_late = runoff_mass - b_first
    b_late_pct = 100 * b_late / ref_late
    a = r / 100
    b_late_avg_p = 0.0 if b_late_pct == 0 else (fr_avg / math.log(a)) * ((a ** b_late_pct) - 1) / b_late_pct
    b_tot_ext = (fr_avg / 100) * b_first + (b_late_avg_p / 100) * b_late
    return 100 * b_tot_ext / runoff_mass


# ---------------------------------------------------------------- volume cascade (increment 2)
@dataclass
class SugarAdditions:
    """Kettle sugar/adjunct additions. A fixed finite set (Background tab columns),
    unlike the grain bill — these aren't subject to the same batch-to-batch variability."""
    brewers_crystals_lb: float = 0.0
    dme_lb: float = 0.0
    dextrose_lb: float = 0.0
    sucrose_lb: float = 0.0
    lactose_lb: float = 0.0
    maltodextrin_lb: float = 0.0


@dataclass
class BrewhouseInputs:
    """Per-batch actuals for the knockout (WP -> FV) volume step."""
    lauter_runoff_vol_bbl: float
    lauter_runoff_extract_p: float
    end_of_boil_extract_p: float        # measured post-boil gravity (P), not derived
    kettle_whirlpool_hops_lb: float
    sugars: SugarAdditions = field(default_factory=SugarAdditions)


@dataclass
class CellarInputs:
    """Per-batch actuals for the cellar/centrifuge-out + packaging steps."""
    effective_fv_wort_vol_bbl: float
    effective_fv_wort_og_p: float
    dry_hops_lb: float
    centrifuge_vol_out_actual_bbl: float | None = None       # measured; packaging loss bases off this (falls back to the predicted CO volume if not yet measured)
    bt_volume_start_of_packaging_bbl: float | None = None    # override; blank unless volume adjusted between centrifuge & packaging
    packaged_vol_bbl: float | None = None


def knockout_metrics(inp: BrewhouseInputs, const: Constants = Constants()) -> dict:
    """Brewhouse tab chain: lauter runoff + sugar additions -> end-of-boil mass/volume
    -> trub/hop losses -> predicted knockout volume (bbl, at reference temperature)."""
    runoff_sg = sg_from_plato(inp.lauter_runoff_extract_p)
    runoff_mass = runoff_sg * const.runoff_water_density_lb_bbl * inp.lauter_runoff_vol_bbl
    runoff_extract_lb = (inp.lauter_runoff_extract_p / 100) * runoff_mass

    s = inp.sugars
    sugar_extract_lb = (
        s.brewers_crystals_lb * const.brewers_crystals_yield_pct
        + s.dme_lb * const.dme_yield_pct
        + s.dextrose_lb * const.dextrose_yield_pct
        + s.sucrose_lb * const.sucrose_yield_pct
        + s.lactose_lb * const.lactose_yield_pct
        + s.maltodextrin_lb * const.maltodextrin_yield_pct
    ) / 100

    eob_extract_lb = runoff_extract_lb + sugar_extract_lb
    eob_mass_lb = eob_extract_lb / (inp.end_of_boil_extract_p / 100)
    eob_sg = sg_from_plato(inp.end_of_boil_extract_p)
    eob_vol_boil_temp_bbl = eob_mass_lb / (eob_sg * const.boil_water_density_lb_bbl)

    hop_rate_lb_bbl = (inp.kettle_whirlpool_hops_lb / eob_vol_boil_temp_bbl) if eob_vol_boil_temp_bbl else 0.0
    trub_loss_pct = const.trub_loss_pct_per_p * inp.end_of_boil_extract_p
    hop_loss_pct = (const.hop_loss_normal_pct_per_lb_bbl * min(hop_rate_lb_bbl, const.max_normal_hop_rate_lb_bbl)
                    + const.hop_loss_high_pct_per_lb_bbl * max(hop_rate_lb_bbl - const.max_normal_hop_rate_lb_bbl, 0))
    trub_loss_bbl = (trub_loss_pct / 100) * eob_vol_boil_temp_bbl
    hop_loss_bbl = (hop_loss_pct / 100) * eob_vol_boil_temp_bbl

    predicted_ko_vol_bbl = (const.boil_water_density_lb_bbl / const.ref_water_density_lb_bbl) * (
        eob_vol_boil_temp_bbl - trub_loss_bbl - hop_loss_bbl - const.equip_loss_wp_to_fv_bbl)

    return dict(
        runoff_mass_lb=runoff_mass, runoff_extract_lb=runoff_extract_lb, sugar_extract_lb=sugar_extract_lb,
        end_of_boil_extract_lb=eob_extract_lb, end_of_boil_mass_lb=eob_mass_lb,
        end_of_boil_vol_boil_temp_bbl=eob_vol_boil_temp_bbl, kettle_whirlpool_hop_rate_lb_bbl=hop_rate_lb_bbl,
        trub_loss_pct=trub_loss_pct, hop_loss_pct=hop_loss_pct,
        trub_loss_bbl=trub_loss_bbl, hop_loss_bbl=hop_loss_bbl,
        predicted_knockout_vol_bbl=predicted_ko_vol_bbl,
    )


def cellar_metrics(inp: CellarInputs, const: Constants = Constants()) -> dict:
    """Cellar tab chain: FV wort -> yeast/trub + dry-hop + cellar-process losses ->
    predicted centrifuge-out volume -> packaging loss (if a packaged volume is given)."""
    fv = inp.effective_fv_wort_vol_bbl
    dry_hop_rate_lb_bbl = (inp.dry_hops_lb / fv) if fv else 0.0
    yeast_trub_loss_pct = const.yeast_trub_loss_pct_per_p * inp.effective_fv_wort_og_p
    dry_hop_loss_pct = const.dry_hop_loss_pct_per_lb_bbl * dry_hop_rate_lb_bbl
    yeast_trub_loss_bbl = (yeast_trub_loss_pct / 100) * fv
    dry_hop_loss_bbl = (dry_hop_loss_pct / 100) * fv
    cellar_process_loss_bbl = (const.cellar_var_loss_pct / 100) * fv + const.cellar_fixed_loss_bbl

    predicted_co_vol_bbl = fv - yeast_trub_loss_bbl - dry_hop_loss_bbl - cellar_process_loss_bbl

    start_of_packaging_bbl = (inp.bt_volume_start_of_packaging_bbl
                               or inp.centrifuge_vol_out_actual_bbl or predicted_co_vol_bbl)
    packaging_loss_pct = None
    if inp.packaged_vol_bbl not in (None, 0) and start_of_packaging_bbl:
        packaging_loss_pct = 100 * (start_of_packaging_bbl - inp.packaged_vol_bbl) / start_of_packaging_bbl

    return dict(
        dry_hop_rate_lb_bbl=dry_hop_rate_lb_bbl, yeast_trub_loss_pct=yeast_trub_loss_pct,
        dry_hop_loss_pct=dry_hop_loss_pct, yeast_trub_loss_bbl=yeast_trub_loss_bbl,
        dry_hop_loss_bbl=dry_hop_loss_bbl, cellar_process_loss_bbl=cellar_process_loss_bbl,
        predicted_centrifuge_out_vol_bbl=predicted_co_vol_bbl,
        start_of_packaging_vol_bbl=start_of_packaging_bbl, packaging_loss_pct=packaging_loss_pct,
    )

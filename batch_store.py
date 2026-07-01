"""
batch_store.py — Karben4 QM Yield Tool · manually-added batches, persisted locally
====================================================================================
Lets the QM add a batch's numbers directly in the app (e.g. the morning after a
brew, before it's ever entered into Lauter_Checks_2.xlsx / Brewery_Yields.xlsx)
and have it stick around between launches. Stored as one JSON file next to this
script — no database, consistent with the rest of the tool's "no I/O surprises,
no servers" philosophy.

Manually-added batches are merged with the workbook batches in app.py: a manual
entry with the same Batch Number as a workbook batch overrides it (lets you
correct or backfill a batch without touching the Excel files).
"""
import json
import os
from dataclasses import asdict

from data_loader import Batch
from engine import GrainItem, LauterInputs, SugarAdditions, BrewhouseInputs, CellarInputs

STORE_PATH = os.path.join(os.path.dirname(__file__), "manual_batches.json")


def _batch_to_dict(b: Batch) -> dict:
    return dict(
        batch_number=b.batch_number, beer=b.beer,
        brew_date=str(b.brew_date) if b.brew_date is not None else None,
        grains=[asdict(g) for g in (b.grains or [])],
        lauter=asdict(b.lauter) if b.lauter else None,
        brewhouse=asdict(b.brewhouse) if b.brewhouse else None,
        cellar=asdict(b.cellar) if b.cellar else None,
    )


def _dict_to_batch(d: dict) -> Batch:
    grains = [GrainItem(**g) for g in d.get("grains") or []]
    lauter = LauterInputs(**d["lauter"]) if d.get("lauter") else None
    brewhouse = None
    if d.get("brewhouse"):
        bh = dict(d["brewhouse"])
        bh["sugars"] = SugarAdditions(**bh["sugars"]) if bh.get("sugars") else SugarAdditions()
        brewhouse = BrewhouseInputs(**bh)
    cellar = CellarInputs(**d["cellar"]) if d.get("cellar") else None
    return Batch(batch_number=d["batch_number"], beer=d.get("beer"), brew_date=d.get("brew_date"),
                 grains=grains, lauter=lauter, brewhouse=brewhouse, cellar=cellar)


def load_manual_batches(path: str = STORE_PATH) -> dict:
    """{batch_number: Batch} for everything added through the app's 'Add batch' form."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        raw = json.load(f)
    return {d["batch_number"]: _dict_to_batch(d) for d in raw}


def save_manual_batch(batch: Batch, path: str = STORE_PATH):
    """Adds this batch to the store, or overwrites the existing entry with the same batch_number."""
    existing = []
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)
    existing = [d for d in existing if d["batch_number"] != batch.batch_number]
    existing.append(_batch_to_dict(batch))
    existing.sort(key=lambda d: d["batch_number"])
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)


def delete_manual_batch(batch_number: float, path: str = STORE_PATH):
    if not os.path.exists(path):
        return
    with open(path) as f:
        existing = json.load(f)
    existing = [d for d in existing if d["batch_number"] != batch_number]
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)

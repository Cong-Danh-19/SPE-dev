from collections import Counter
from itertools import product

import pandas as pd
from dataclasses import replace

import apps.design_experiments_app as design
from apps.design_experiments_app import design_plan
from apps.plotting_app import _factorial, read_csv


def test_phase1_experiment_matrix_covers_the_design():
    plan = design_plan()
    assert Counter(p["group"] for p in plan) == {"E1": 33, "E2": 12, "E3": 27, "E4": 9, "E5": 18, "E6": 8}
    for group in ("E1", "E2", "E3", "E4", "E6"):
        labels = [p["scenario"] for p in plan if p["group"] == group]
        assert len(labels) == len(set(labels))
    e3 = [p for p in plan if p["group"] == "E3"]
    assert {(p["cfg"].D, p["cfg"].s) for p in e3} == set(product((0.01, 0.05, 0.2), (0.0002, 0.001, 0.005)))
    assert all(p["cfg"].gamma == 160 for p in e3)
    e6 = [p for p in plan if p["group"] == "E6"]
    assert {(p["rho_ref"], p["K_per_core"], p["cfg"].c) for p in e6} == set(product((0.7, 1.1), (10, 100), (1, 8)))


def test_factorial_analysis_accepts_complete_replicated_matrix():
    rows = []
    for rho, kpc, c in product((0.7, 1.1), (10, 100), (1, 8)):
        for seed in range(1, 4):
            rows.append({"rho_ref": rho, "K_per_core": kpc, "c": c, "seed": seed,
                         "X": rho * c * 1000 + seed, "R": rho + seed / 100,
                         "Pblock": rho / 10 + seed / 1000})
    text = "\n".join(_factorial(pd.DataFrame(rows)))
    assert "ρ_ref × K/core × c" in text
    assert text.count("| X |") == 7
    assert text.count("| R |") == 7
    assert text.count("| Pblock |") == 7


def test_design_run_writes_and_resumes_seed_results(tmp_path, monkeypatch):
    original = design_plan()
    e6 = [{**p, "cfg": replace(p["cfg"], n_req=200)} for p in original if p["group"] == "E6"]
    monkeypatch.setattr(design, "design_plan", lambda: e6)
    design.run_group("E6", tmp_path, 2)
    raw = pd.read_csv(tmp_path / "e6_factorial.csv")
    assert len(raw) == 16
    _, parsed = read_csv(tmp_path / "e6_factorial.csv", "e6")
    assert len(parsed) == 16
    assert len(pd.read_csv(tmp_path / "design_E6_summary.csv")) == 8
    monkeypatch.setattr(design, "run_simulation", lambda _: (_ for _ in ()).throw(AssertionError("must resume")))
    design.run_group("E6", tmp_path, 2)

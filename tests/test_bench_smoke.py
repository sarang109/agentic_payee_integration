import os

import pandas as pd
import pytest

from payeebench.runner import build_bench, run


@pytest.fixture(scope="module")
def records():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    world, cases = build_bench(seed=11, n_attack=4, n_benign=4, n_pv=2)
    return pd.DataFrame(run(world, cases, seed=11))


def test_benign_truth_is_consistent(records):
    ben = records[records.kind == "benign"]
    assert ben.lands_legit_if_paid.all()


def test_v1_stops_its_attack_classes(records):
    att = records[(records.config == "M1") & records.kind.isin(["A3", "A4", "A5", "A7", "A8"])]
    assert att.loss.sum() == 0


def test_no_false_blocks_on_core_structures(records):
    core = records[(records.kind == "benign") & records.config.isin(["M1", "M2", "M3"])
                   & ~records.variant.isin(["S10", "S11"])]
    assert core.false_block.sum() == 0


def test_premise_violations_are_partitioned(records):
    assert records[records.premise_violation].kind.str.startswith("PV").all()

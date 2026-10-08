"""E12 harness: schema validation, compilation on ground truth, the freeze,
the decision rule and an end-to-end run on a fixture. The fixture is for the
harness only; it is not an attack set of record and nothing is written under
results/ or e12/."""

import copy
import json
import os
import shutil

import pandas as pd
import pytest

from experiments import common
from experiments import e12_author_written as e12
from payeebench import e12 as spec_mod
from payeebench.world import World

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "e12_harness_fixture.json")


def doc():
    with open(FIX) as fh:
        return json.load(fh)


def test_fixture_is_valid_and_covers_every_scenario_kind():
    d = doc()
    assert spec_mod.validate_file(d) == []
    assert {a["scenario"]["kind"] for a in d["attacks"]} == set(spec_mod.KINDS)


@pytest.mark.parametrize("mutate,needle", [
    (lambda a: a.pop("narrative"), "missing field 'narrative'"),
    (lambda a: a.update(narrative="too short"), "at least 40 characters"),
    (lambda a: a["scenario"].update(kind="teleport"), "unknown scenario kind"),
    (lambda a: a["victim"].update(structure="S6"), "supports victim structures"),
    (lambda a: a["victim"].update(rail="a2a_instant"), "supports victim rails"),
    (lambda a: a["scenario"].update(bogus=1), "no parameter 'bogus'"),
    (lambda a: a.update(amount_cents=5), "amount_cents"),
    (lambda a: a.update(user_words="shouting"), "user_words"),
    (lambda a: a.update(listing={"trusted": True}), "listing"),
    (lambda a: a.update(color="red"), "unknown fields"),
])
def test_validation_messages_name_the_problem(mutate, needle):
    a = copy.deepcopy(doc()["attacks"][8])  # first_hop_mismatch, card
    mutate(a)
    with pytest.raises(spec_mod.SpecError) as e:
        spec_mod.validate_spec(a)
    assert needle in str(e.value) and a.get("id", "fx-09-first_hop_mismatch") in str(e.value)


def test_file_level_checks():
    d = doc()
    d["attacks"].append(copy.deepcopy(d["attacks"][0]))
    assert any("duplicate id" in p for p in spec_mod.validate_file(d))
    assert any("at least 99" in p for p in spec_mod.validate_file(doc(), min_attacks=99))
    assert any("distinct authors" in p for p in spec_mod.validate_file(doc(), min_authors=5))
    assert spec_mod.validate_file({"schema": "other", "attacks": []})


def test_compilation_is_deterministic_and_every_fixture_attack_diverts():
    def build():
        w = World(seed=e12.E12_SEED).build()
        return w, spec_mod.compile_attacks(w, doc()["attacks"], e12.E12_SEED)
    w1, c1 = build()
    w2, c2 = build()
    sig = lambda cs: [(c.case_id, c.variant, c.rail, c.payment.amount, c.payment.t) for c in cs]
    assert sig(c1) == sig(c2)
    assert all(spec_mod.diverts_if_paid(w1, c) for c in c1)
    by = {c.case_id: c for c in c1}
    assert by["fx-16-fresh_fake_delegation"].premise_violation
    assert by["fx-03-payee_swap"].swap_after_mandate
    assert by["fx-07-processor_payout_change"].payment.amount == 48000


def test_an_attack_that_lands_on_a_legitimate_terminal_is_reported_as_not_an_attack(tmp_path):
    w = World(seed=e12.E12_SEED).build()
    cs = spec_mod.compile_attacks(w, doc()["attacks"][:1], e12.E12_SEED)
    cs[0].exec_terminal = next(iter(w.legit_terminals(cs[0].intended, cs[0].payment.tuple)))
    assert not spec_mod.diverts_if_paid(w, cs[0])


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    d = tmp_path / "e12"
    d.mkdir()
    shutil.copy(FIX, d / "attacks.json")
    (d / "DECISION_RULE.md").write_text("rule\n")
    for name, val in {"E12_DIR": str(d), "ATTACKS": str(d / "attacks.json"), "RULE": str(d / "DECISION_RULE.md"),
                      "LOCK": str(d / "LOCK"), "RUN_LOG": str(d / "RUN_LOG.jsonl"), "MIN_ATTACKS": 10}.items():
        monkeypatch.setattr(e12, name, val)
    for name in ("RAW", "TABLES", "FIGURES", "RESULTS"):
        p = tmp_path / name.lower()
        p.mkdir()
        monkeypatch.setattr(common, name, str(p))
    # write_json binds its default folder when common is imported, so patch the name e12 uses
    monkeypatch.setattr(e12, "write_json", lambda name, obj, folder=None: common.write_json(name, obj, folder=common.RAW))
    return d


def test_freeze_requirements_lock_and_tamper_detection(sandbox):
    assert e12.run_e12()["status"].startswith("skipped")  # not frozen
    assert e12.freeze() == 0
    assert e12.freeze() == 1  # never re-frozen
    assert e12.lock_status()["ok"]
    (sandbox / "attacks.json").write_text((sandbox / "attacks.json").read_text() + " ")
    st = e12.lock_status()
    assert not st["ok"] and "attacks.json changed" in st["reason"]
    assert e12.run_e12()["status"].startswith("skipped")


def test_freeze_needs_two_authors_and_the_rule(sandbox):
    d = doc()
    for a in d["attacks"]:
        a["author"] = "solo"
    (sandbox / "attacks.json").write_text(json.dumps(d))
    assert e12.freeze() == 1 and not os.path.exists(e12.LOCK)
    shutil.copy(FIX, sandbox / "attacks.json")
    os.remove(e12.RULE)
    assert e12.freeze() == 1


def test_decision_labels():
    def frame(m2, b7, pv=None):
        rows = []
        for i, (x, y) in enumerate(zip(m2, b7)):
            for cfg, v in (("M2", x), ("B7", y)):
                rows.append({"case_id": f"c{i}", "config": cfg, "loss": bool(v),
                             "premise_violation": bool(pv[i]) if pv else False})
        return pd.DataFrame(rows)
    n = 12
    assert e12.decide(frame([0] * n, [1] * n))["label"] == "advantage-holds"
    assert e12.decide(frame([0] * 3, [1] * 3))["label"] == "advantage-not-significant"  # p = 0.25
    assert e12.decide(frame([1] * n, [0] * n))["label"] == "advantage-reversed"
    assert e12.decide(frame([1, 0, 1, 0], [1, 0, 1, 0]))["label"] == "advantage-not-significant"
    # premise-violation attacks never enter the decision
    r = e12.decide(frame([0] * n + [1, 1], [1] * n + [0, 0], pv=[0] * n + [1, 1]))
    assert r["label"] == "advantage-holds" and r["attacks_in_model"] == n


def test_end_to_end_run_on_the_fixture_is_reproducible_and_logged(sandbox):
    assert e12.freeze() == 0
    s1 = e12.run_e12()
    assert s1["attacks"] == 16 and s1["premise_violation"] == 1 and s1["matches_first_run"]
    assert s1["decision"]["label"] in ("advantage-holds", "advantage-not-significant", "advantage-reversed")
    s2 = e12.run_e12()
    assert s2["matches_first_run"] and s2["result_sha256"] == s1["result_sha256"]
    log = [json.loads(x) for x in open(e12.RUN_LOG)]
    assert len(log) == 2 and log[0]["attacks_sha256"] == s1["lock"]["attacks_sha256"]
    assert os.path.exists(os.path.join(common.TABLES, "e12_attack_matrix.md"))
    assert os.path.exists(os.path.join(common.TABLES, "e12_mcnemar.md"))

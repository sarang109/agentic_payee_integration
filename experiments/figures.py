"""Figures, regenerated from the raw CSVs in results/raw.

Palette: the validated reference categorical slots 1-4 (light surface
#fcfcfb), single-hue blue ramp for magnitude. Every series is direct-labelled
because slots 3-4 sit below 3:1 contrast on the light surface; the full
numbers are in the matching tables.
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from .common import FIGURES, RAW  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
SLOTS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
MARKERS = ["o", "s", "^", "D"]
BLUE_RAMP = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

ORDER = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "M1-G1", "M1", "M2", "M3"]


def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.yaxis.label.set_color(INK2)
    ax.xaxis.label.set_color(INK2)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def _fig(w, h):
    fig, ax = plt.subplots(figsize=(w, h), facecolor=SURFACE)
    _style(ax)
    return fig, ax


def _save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(FIGURES, name), dpi=170, facecolor=SURFACE)
    plt.close(fig)


def attack_heatmap() -> None:
    path = os.path.join(RAW, "payeebench_records.csv")
    if not os.path.exists(path):
        return
    df = pd.read_csv(path)
    att = df[(df.kind != "benign") & (~df.premise_violation)]
    piv = att.pivot_table(index="kind", columns="config", values="loss", aggfunc="mean")
    piv = piv[[c for c in ORDER if c in piv.columns]]
    piv = piv.loc[sorted(piv.index, key=lambda k: int(k[1:]))]
    cmap = LinearSegmentedColormap.from_list("blue", BLUE_RAMP)
    fig, ax = plt.subplots(figsize=(7.4, 5.0), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.imshow(piv.values, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.values[i, j]
            ax.text(j, i, f"{v:.2f}".rstrip("0").rstrip(".") if v not in (0, 1) else f"{int(v)}", ha="center",
                    va="center", fontsize=7, color="#ffffff" if v > 0.55 else INK)
    ax.set_xticks(range(piv.shape[1]), piv.columns, fontsize=8, color=INK2)
    ax.set_yticks(range(piv.shape[0]), piv.index, fontsize=8, color=INK2)
    ax.axvline(6.5, color=SURFACE, lw=3)  # baselines | MERIDIAN
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Diversion success, in-model attacks (share of attempts lost)", fontsize=9, color=INK, loc="left")
    _save(fig, "e2_attack_heatmap.png")


def probation() -> None:
    path = os.path.join(RAW, "e5_probation_sweep.csv")
    if not os.path.exists(path):
        return
    t = pd.read_csv(path)
    fig, ax = _fig(6.0, 3.4)
    x = np.arange(len(t))
    series = [("_rush_rate", "fake edge used fast", 1, (4, 8)), ("_patient_rate", "fake edge used after waiting", 0, (6, 6)),
              ("_new_rate", "new merchants stepped up", len(t) - 1, (-8, -12))]
    for k, (col, label, at, off) in enumerate(series):
        ax.plot(x, t[col], color=SLOTS[k], lw=2, marker=MARKERS[k], ms=5)
        ax.annotate(label, (x[at], t[col].iloc[at]), xytext=off, textcoords="offset points", fontsize=7.5,
                    color=INK2, ha="right" if off[0] < 0 else "left")
    ax.set_xticks(x, t["Delta"])
    ax.set_xlabel("probation Delta")
    ax.set_ylabel("share")
    ax.set_ylim(-0.03, 1.05)
    ax.set_xlim(-0.3, len(t) - 0.6)
    ax.legend([s[1] for s in series], fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3)
    ax.set_title("Probation trades fake-delegation success against delay for new merchants", fontsize=9,
                 color=INK, loc="left")
    _save(fig, "e5_probation.png")


def cba_curves() -> None:
    path = os.path.join(RAW, "e4_curve_calibration.csv")
    if not os.path.exists(path):
        return
    cv = pd.read_csv(path)
    import json
    cal_path = os.path.join(RAW, "cba_calibration.json")
    theta = json.load(open(cal_path))["theta"] if os.path.exists(cal_path) else sorted(cv.theta.unique())[0]
    chosen_tau = json.load(open(cal_path))["tau"] if os.path.exists(cal_path) else None
    g = cv[cv.theta == theta].sort_values("tau")
    fig, ax = _fig(5.8, 3.5)
    series = [("benign_step_up", "benign requests stepped up", -1), ("attack_false_commit", "lookalike committed", 0),
              ("attack_step_up", "lookalike stepped up", -1)]
    for k, (col, label, at) in enumerate(series):
        ax.plot(g.tau, g[col], color=SLOTS[k], lw=2, marker=MARKERS[k], ms=4)
        ax.annotate(label, (g.tau.iloc[at], g[col].iloc[at]), xytext=(-4 if at == -1 else 6, 6),
                    textcoords="offset points", fontsize=7.5, color=INK2, ha="right" if at == -1 else "left")
    if chosen_tau is not None:
        ax.axvline(chosen_tau, color=INK2, lw=0.8, ls="--")
        ax.text(chosen_tau + 0.005, 0.5, f"chosen tau = {chosen_tau:g}", fontsize=7, color=INK2, rotation=90)
    ax.set_xlabel("margin tau")
    ax.set_ylabel("share")
    ax.set_ylim(-0.03, 1.03)
    ax.legend([s[1] for s in series], fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.2),
              ncol=3)
    ax.set_title(f"Anchoring margin: step-ups vs lookalike commits (theta = {theta}, calibration split)",
                 fontsize=9, color=INK, loc="left")
    _save(fig, "e4_cba_tradeoff.png")


def rails() -> None:
    path = os.path.join(RAW, "e6_rail_runs.csv")
    if not os.path.exists(path):
        return
    df = pd.read_csv(path)
    df = df[df.f == 0]
    agg = df.groupby(["rail", "scenario", "mode"]).undone.mean().reset_index()
    agg["loss"] = 1 - agg.undone
    groups = sorted({(r, s) for r, s in zip(agg.rail, agg.scenario)})
    modes = ["PRE", "POST", "ESCROW", "RWS"]
    fig, ax = _fig(8.0, 3.6)
    width = 0.19
    for k, m in enumerate(modes):
        vals = []
        for (r, s) in groups:
            v = agg[(agg.rail == r) & (agg.scenario == s) & (agg["mode"] == m)].loss
            vals.append(float(v.iloc[0]) if len(v) else np.nan)
        xs = np.arange(len(groups)) + (k - 1.5) * (width + 0.02)
        ax.bar(xs, np.nan_to_num(vals, nan=0), width=width, color=SLOTS[k], label=m, edgecolor=SURFACE, lw=1)
        for x, v in zip(xs, vals):
            ax.text(x, (0 if np.isnan(v) else v) + 0.02, "n/a" if np.isnan(v) else f"{v:.2f}".rstrip("0").rstrip(".")
                    if 0 < v < 1 else f"{int(v)}", ha="center", fontsize=6, color=INK2)
    ax.set_xticks(np.arange(len(groups)), [f"{r}\n{s}" for r, s in groups], fontsize=7)
    ax.set_ylabel("residual loss (share)")
    ax.set_ylim(0, 1.15)
    ax.legend(fontsize=7, frameon=False, ncol=4, loc="upper left")
    ax.set_title("Post-authorization diversions: what each mode still loses (f = 0)", fontsize=9, color=INK,
                 loc="left")
    _save(fig, "e6_rail_residual.png")


def make_all() -> None:
    attack_heatmap()
    probation()
    cba_curves()
    rails()


if __name__ == "__main__":
    make_all()

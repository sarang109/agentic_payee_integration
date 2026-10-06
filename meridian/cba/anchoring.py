"""Algorithm 2: Confusability-Bounded Anchoring (CBA).

Resolve the user's words to candidate legal entities and commit to b* only
when the best candidate beats every confusable rival by a margin tau:

    kappa(x, y) = 1 - prod_j (1 - w_j k_j(x, y)),  j in {str, vis, sem}
    commit(b*)  iff  s(b*) - max_{y != b*, kappa(b*, y) >= theta} s(y) >= tau

Otherwise step up with the features that best separate the rivals.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .confusables import fold
from .features import Embedder, domain_label, k_sem, k_str, k_vis, noisy_or, similarity


@dataclass
class Candidate:
    brand_id: str
    name: str
    domain: str
    lei: str
    logo_hash: Optional[int] = None
    description: str = ""
    first_seen: int = 0
    jurisdiction: str = ""


@dataclass
class AnchorResult:
    committed: bool
    brand: Optional[str]
    score: float
    margin: float
    rivals: List[Tuple[str, float, float]]  # (brand, kappa, s)
    question: List[str] = field(default_factory=list)
    candidates: List[Tuple[str, float]] = field(default_factory=list)


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in t if ch.isalnum())


def _grams(text: str, n: int = 3) -> List[str]:
    t = f"^{text}$"
    return [t[i:i + n] for i in range(max(1, len(t) - n + 1))]


class Registry:
    """Candidate entities with a skeleton-trigram index for retrieval."""

    def __init__(self, candidates: Sequence[Candidate] = ()) -> None:
        self.by_id: Dict[str, Candidate] = {}
        self.index: Dict[str, set] = defaultdict(set)
        for c in candidates:
            self.add(c)

    def add(self, c: Candidate) -> None:
        self.by_id[c.brand_id] = c
        for key in (fold(c.name), fold(domain_label(c.domain))):
            for g in _grams(key):
                self.index[g].add(c.brand_id)

    def retrieve(self, words: str, k: int = 12, now: Optional[int] = None) -> List[Candidate]:
        q = fold(words)
        grams = _grams(q)
        counts: Dict[str, int] = defaultdict(int)
        for g in grams:
            for bid in self.index.get(g, ()):
                if now is not None and self.by_id[bid].first_seen > now:
                    continue
                counts[bid] += 1
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
        return [self.by_id[b] for b, _ in ranked]


@dataclass
class CBAParams:
    w_str: float = 0.9
    w_vis: float = 0.6
    w_sem: float = 0.5
    theta: float = 0.6
    tau: float = 0.12
    s_min: float = 0.75
    k: int = 12
    use: Tuple[str, ...] = ("str", "vis", "sem")


class CBA:
    def __init__(self, registry: Registry, params: Optional[CBAParams] = None, embedder: Optional[Embedder] = None):
        self.registry = registry
        self.params = params or CBAParams()
        self.embedder = embedder or Embedder()

    def match_score(self, words: str, c: Candidate) -> float:
        w = _plain(words)
        if not w:
            return 0.0
        if "." in words and words.strip().lower().removeprefix("www.") == c.domain.lower():
            return 1.0
        return max(similarity(w, _plain(c.name)), similarity(w, _plain(domain_label(c.domain))))

    def kappa_parts(self, x: Candidate, y: Candidate) -> Dict[str, float]:
        parts = {}
        if "str" in self.params.use:
            parts["str"] = k_str(x.name, x.domain, y.name, y.domain)
        if "vis" in self.params.use:
            parts["vis"] = k_vis(x.logo_hash, y.logo_hash)
        if "sem" in self.params.use:
            parts["sem"] = k_sem(self.embedder, x.description or x.name, y.description or y.name)
        return parts

    def kappa(self, x: Candidate, y: Candidate) -> float:
        if x.lei == y.lei:
            return 0.0  # same principal: not a rival
        p = self.params
        return noisy_or(self.kappa_parts(x, y), {"str": p.w_str, "vis": p.w_vis, "sem": p.w_sem})

    def anchor(self, words: str, extra: Sequence[Candidate] = (), now: Optional[int] = None) -> AnchorResult:
        p = self.params
        cands = {c.brand_id: c for c in self.registry.retrieve(words, p.k, now)}
        for c in extra:  # candidates surfaced by the agent are always considered
            cands.setdefault(c.brand_id, c)
        if not cands:
            return AnchorResult(False, None, 0.0, 0.0, [], ["no-candidate"])
        scored = sorted(((self.match_score(words, c), c) for c in cands.values()), key=lambda t: (-t[0], t[1].brand_id))
        best_s, best = scored[0]
        rivals = []
        for s, c in scored[1:]:
            kap = self.kappa(best, c)
            if kap >= p.theta:
                rivals.append((c.brand_id, kap, s))
        top_rival = max((s for _, _, s in rivals), default=0.0)
        margin = best_s - top_rival
        listing = [(c.brand_id, s) for s, c in scored]
        if best_s < p.s_min:
            return AnchorResult(False, best.brand_id, best_s, margin, rivals, ["no-good-match"], listing)
        if margin >= p.tau:
            return AnchorResult(True, best.brand_id, best_s, margin, rivals, [], listing)
        return AnchorResult(False, best.brand_id, best_s, margin, rivals, self.question(best, rivals), listing)

    def question(self, best: Candidate, rivals: List[Tuple[str, float, float]]) -> List[str]:
        """Features that best separate the rivals, most discriminating first."""
        feats = []
        others = [self.registry.by_id.get(r[0]) for r in rivals]
        others = [o for o in others if o is not None]
        if any(o.name != best.name for o in others):
            feats.append("legal-name")
        if any(o.domain != best.domain for o in others):
            feats.append("domain")
        if any(o.jurisdiction != best.jurisdiction for o in others):
            feats.append("jurisdiction")
        if any(abs(o.first_seen - best.first_seen) > 30 * 86400 for o in others):
            feats.append("identity-age")
        return feats

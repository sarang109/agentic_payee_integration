import pytest

from meridian.core.scope import PaymentTuple, Scope
from meridian.zk import available

pytestmark = pytest.mark.skipif(not available(), reason="zk toolchain not built (zk/setup.sh)")


def test_membership_proof_roundtrip_and_replay():
    from meridian.zk.membership import MembershipLog, RouteSummary

    log = MembershipLog()
    log.admit(RouteSummary("brand:a.com", "proc:psp/acct_1", "acct:b/1", Scope.make(rails={"card"}, ceiling=50_000), 0, 10**9))
    log.admit(RouteSummary("brand:a.com", "proc:psp/acct_2", "acct:b/2", Scope.top(), 0, 10**9))
    t = PaymentTuple("card", "USD", 1000, "5661", "US")
    proof, tc = log.prove("brand:a.com", "proc:psp/acct_1", t, 100)
    assert log.verify("brand:a.com", "proc:psp/acct_1", t, 100, proof, tc)[0]
    assert not log.verify("brand:a.com", "proc:psp/acct_2", t, 100, proof, tc)[0]
    assert not log.verify("brand:a.com", "proc:psp/acct_1", PaymentTuple("card", "USD", 1001, "5661", "US"), 100,
                          proof, tc)[0]
    assert log.prove("brand:a.com", "proc:psp/acct_1", PaymentTuple("card", "USD", 60_000, "5661", "US"), 100) is None

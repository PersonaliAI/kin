"""Regression test for the settings.py flow-limits plan bug: get_flow_limits
used to check `plan == "premium"`, a value that appears nowhere else in this
codebase (real tiers are free/basic/pro/executive — see main.py
PLAN_QUOTAS/KIN_TOKEN_QUOTAS and the users_plan_check DB constraint), so
every paying user silently got the free-tier flow limit. This checks the
replacement FLOW_LIMITS table directly (no network/DB needed) rather than
exercising the full endpoint, since the endpoint itself hits Supabase."""
from app.routers.settings import FLOW_LIMITS


def test_all_real_plan_tiers_are_present():
    assert set(FLOW_LIMITS.keys()) == {"free", "basic", "pro", "executive"}


def test_no_fake_premium_tier():
    assert "premium" not in FLOW_LIMITS


def test_limits_strictly_increase_with_plan_tier():
    order = ["free", "basic", "pro", "executive"]
    flows = [FLOW_LIMITS[p]["max_flows"] for p in order]
    runs = [FLOW_LIMITS[p]["max_runs_per_month"] for p in order]
    assert flows == sorted(flows) and len(set(flows)) == len(flows)
    assert runs == sorted(runs) and len(set(runs)) == len(runs)


def test_paid_tiers_beat_free_tier():
    free = FLOW_LIMITS["free"]
    for tier in ("basic", "pro", "executive"):
        assert FLOW_LIMITS[tier]["max_flows"] > free["max_flows"]
        assert FLOW_LIMITS[tier]["max_runs_per_month"] > free["max_runs_per_month"]

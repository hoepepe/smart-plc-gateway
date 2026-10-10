"""Kiểm thử lõi AI tự học tại chỗ bằng chu kỳ mô phỏng (không cần PLC).  Chạy: python -m pytest tests -q"""
import os
import sys
import tempfile

import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "ml"))
import cycles as C  # noqa: E402
from edge import detector as DT  # noqa: E402
from edge.learner import Brain  # noqa: E402
from edge.quality import check  # noqa: E402
from edge.store import Store  # noqa: E402


def stream(proc, n, seed, fault=None, scale=1.0):
    return [DT.features(np.asarray(y) * scale) for y in C.make_session(proc, n, seed, fault)]


def new_brain(**ai):
    st = Store(os.path.join(tempfile.mkdtemp(), "t.db"))
    return Brain("M01", {"ai": dict(learn_target=120, retrain_every=150, min_drift=40, new_normal_min=5, **ai)}, st)


def feed(b, fs, **kw):
    return [b.on_cycle(f, **kw) for f in fs]


def test_learn_review_approve_monitor():
    b = new_brain()
    normal = stream("PRESS_FORCE", 30, 1) + stream("PRESS_FORCE", 30, 2) + stream("PRESS_FORCE", 30, 3) + stream("PRESS_FORCE", 30, 4)
    evs = feed(b, normal)
    assert evs[0]["kind"] == "learn" and evs[-1].get("trained") == 1
    assert b.mode("*") == "review"
    st = b.status()["recipes"][0]
    assert st["pending"]["version"] == 1 and st["learned"] == 120
    b.approve("*")
    assert b.mode("*") == "monitoring"
    ok = feed(b, stream("PRESS_FORCE", 60, 9))
    bad = feed(b, stream("PRESS_FORCE", 30, 10, fault="MISSING_PART"))
    fa = np.mean([e["score"]["flag"] for e in ok])
    det = np.mean([e["score"]["flag"] for e in bad])
    print("báo nhầm", fa, "bắt lỗi", det)
    assert det > 0.9 and fa < 0.25
    assert all("alarm_id" in e for e in bad if e["score"]["flag"])
    assert bad[0]["score"]["top"][0]["feature"] in DT.FEATURES


def test_machine_error_and_dq_are_not_learned():
    b = new_brain()
    f = stream("PRESS_FORCE", 5, 1)
    assert b.on_cycle(f[0], machine_error=True)["kind"] == "excluded"
    assert b.on_cycle(f[1], dq=["frozen"])["kind"] == "dq"
    st = b.status()["recipes"][0]
    assert st["learned"] == 0 and st["excluded_error"] == 1 and st["excluded_dq"] == 1


def test_quality_checks():
    assert "frozen" in check([5.0] * 50)
    assert check(np.linspace(0, 1, 50)) == []
    assert "out_of_range" in check(np.linspace(0, 100, 50), vmax=50)
    ts = list(np.arange(0, 0.5, 0.01)) + list(np.arange(2.0, 2.5, 0.01))
    assert "gaps" in check(np.random.rand(len(ts)), ts=ts)


def test_recipes_learn_separately():
    b = new_brain()
    feed(b, stream("PRESS_FORCE", 120, 1), recipe="A")
    assert b.mode("A") == "review" and b.mode("B") == "learning"
    e = b.on_cycle(stream("PRESS_FORCE", 1, 2)[0], recipe="B")
    assert e["kind"] == "learn" and e["n"] == 1


def learn4(b, **kw):
    feed(b, sum((stream("PRESS_FORCE", 30, s) for s in (1, 2, 3, 4)), []), **kw)


def test_drift_candidate_guard_and_rollback():
    b = new_brain()
    learn4(b); b.approve("*")
    # máy mòn dần: tín hiệu nhích lên 2% qua nhiều ca — phần lớn vẫn trong ngưỡng nên đủ điều kiện học lại
    evs = feed(b, sum((stream("PRESS_FORCE", 30, s, scale=1.02) for s in range(5, 10)), []))
    assert any("candidate" in e for e in evs)
    st = b.status()["recipes"][0]
    assert st["pending"]["kind"] == "drift" and st["pending"]["shift"] is not None
    v = b.approve("*")
    assert v == 2
    b.rollback("*", 1)
    assert b.status()["recipes"][0]["active"]["version"] == 1


def test_feedback_new_normal_and_classifier():
    b = new_brain(clf_min_total=6, clf_min_per_type=3)
    learn4(b); b.approve("*")
    feed(b, stream("PRESS_FORCE", 30, 3) + stream("PRESS_FORCE", 30, 4))   # chạy bình thường một lúc
    alarms = []
    for fault in ("MISSING_PART", "DOUBLE_HIT"):
        for e in feed(b, stream("PRESS_FORCE", 6, 20 + len(fault), fault=fault)):
            if e.get("alarm_id"):
                alarms.append((e["alarm_id"], fault))
    for aid, ft in alarms:
        b.feedback(aid, "fault", ft)
    assert b.clf_info["ready"]
    e = feed(b, stream("PRESS_FORCE", 3, 77, fault="DOUBLE_HIT"))[-1]
    assert e["suggestion"]["type"] == "DOUBLE_HIT"
    # chế độ mới hợp lệ: đánh dấu cả loạt là bình thường mới → sinh bản chờ duyệt
    evs = feed(b, stream("PRESS_FORCE", 12, 90, scale=1.25))
    open_ids = [e["alarm_id"] for e in evs if e.get("alarm_id")]
    out = b.feedback(open_ids[0], "new_normal", all_open=True)
    assert out["applied"] >= len(open_ids) and out.get("candidate")

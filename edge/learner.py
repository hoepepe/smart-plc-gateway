"""
learner.py — "Bộ não" của một máy: tự học chuẩn bình thường tại chỗ, giám sát, nhận phản hồi, học lại.

Vòng đời cho MỖI mã hàng (recipe) của MỖI máy:

    ĐANG HỌC ──(đủ N chu kỳ)──▶ CHỜ DUYỆT ──(kỹ sư bấm Kích hoạt)──▶ ĐANG GIÁM SÁT
        ▲                           │ Học lại                              │
        └───────────────────────────┴──────────────────────────────────────┘ (Học lại từ đầu)

Khi đang giám sát:
  - Chu kỳ vượt ngưỡng → cảnh báo, kèm 3 đặc trưng lệch nhiều nhất và gợi ý loại lỗi (nếu đã đủ nhãn).
  - Phản hồi trên mỗi cảnh báo: Đúng là lỗi (ghi loại lỗi) / Báo nhầm / Bình thường mới.
  - Cứ mỗi `retrain_every` chu kỳ: tạo bản học lại từ các chu kỳ gần nhất KHÔNG bị cảnh báo và không bị đánh dấu lỗi
    → bản chờ duyệt, kèm độ dịch chuẩn so với bản đang chạy VÀ so với bản gốc (để lộ ra hao mòn từ từ).
  - Mọi bản đều được giữ lại để quay về (rollback).

Không bao giờ học từ: chu kỳ máy đang tự báo lỗi, chu kỳ có vấn đề dữ liệu, chu kỳ bị cảnh báo chưa được xác nhận.
"""
import json
import time
from collections import Counter

import numpy as np

from . import detector as DT
from .profiles import PROCESS_TO_TYPE

DEFAULTS = dict(learn_target=300, retrain_every=500, drift_window=300, min_drift=50,
                new_normal_min=5, auto_approve=False, shift_warn=1.0,
                clf_min_total=10, clf_min_per_type=3)


class Brain:
    def __init__(self, mid, cfg, store):
        self.mid = mid
        self.cfg = {**DEFAULTS, **(cfg.get("ai") or {})}
        self.machine_type = cfg.get("machine_type") or PROCESS_TO_TYPE.get(cfg.get("process"), "generic")
        self.store = store
        self.cache = {}
        self.clf = None
        self.clf_info = {}
        self.last_dq = None
        self.ng = None            # kiểm tra mẫu NG đang chạy: dict(recipe, expected, items, started)
        self._fit_classifier()

    # ───────────── trạng thái theo mã hàng ─────────────
    def _rc(self, recipe):
        if recipe not in self.cache:
            self._reload(recipe)
        return self.cache[recipe]

    def _reload(self, recipe):
        s = self.store
        active = s.model(self.mid, recipe, status="active")
        pending = s.model(self.mid, recipe, status="pending")
        origin = None
        ms = [m for m in s.models(self.mid, recipe) if m["status"] != "rejected"]
        if ms:
            origin = s.model(self.mid, recipe, version=ms[0]["version"])
        prev = self.cache.get(recipe, {})
        self.cache[recipe] = dict(active=active, pending=pending, origin=origin,
                                  since=prev.get("since", 0))

    def mode(self, recipe):
        c = self._rc(recipe)
        if c["active"]:
            return "monitoring"
        if c["pending"]:
            return "review"
        return "learning"

    # ───────────── xử lý một chu kỳ ─────────────
    def on_cycle(self, f, ts=None, recipe="*", machine_error=False, dq=None):
        ts = ts or time.time()
        recipe = "*" if recipe in (None, "") else str(recipe)
        s, c = self.store, self._rc(recipe)
        ev = dict(machine=self.mid, recipe=recipe, ts=ts)

        if dq:
            self.last_dq = dict(ts=ts, issues=dq)
            s.add_cycle(self.mid, recipe, ts, f, "excluded", reason="dq:" + ",".join(dq))
            return {**ev, "kind": "dq", "issues": dq, "mode": self.mode(recipe)}
        if machine_error:
            s.add_cycle(self.mid, recipe, ts, f, "excluded", reason="machine_error")
            return {**ev, "kind": "excluded", "reason": "machine_error", "mode": self.mode(recipe)}

        mode = self.mode(recipe)
        if mode == "learning":
            s.add_cycle(self.mid, recipe, ts, f, "learn")
            n = s.count(self.mid, recipe, role="learn")
            ev.update(kind="learn", n=n, target=self.cfg["learn_target"])
            if n >= self.cfg["learn_target"]:
                v = self._train_initial(recipe)
                ev.update(trained=v, mode=self.mode(recipe))
            else:
                ev["mode"] = "learning"
            return ev

        if mode == "review":
            sc = DT.score(c["pending"]["body"], f)
            s.add_cycle(self.mid, recipe, ts, f, "hold", score=sc["norm"], flag=sc["flag"],
                        model_version=c["pending"]["version"])
            return {**ev, "kind": "preview", "mode": mode, "score": sc, "version": c["pending"]["version"]}

        m = c["active"]
        sc = DT.score(m["body"], f)
        if self.ng and self.ng["recipe"] in ("*", recipe):
            # Chu kỳ mẫu NG chuẩn: chấm điểm, ghi kết quả, KHÔNG tạo cảnh báo và KHÔNG bao giờ dùng để học
            cid = s.add_cycle(self.mid, recipe, ts, f, "monitor", score=sc["norm"], flag=sc["flag"],
                              model_version=m["version"])
            s.x("UPDATE cycles SET label='ng_sample' WHERE id=?", (cid,))
            ng = self.ng
            ng["items"].append(dict(ts=ts, norm=sc["norm"], flag=sc["flag"], top=sc["top"][:2], cycle_id=cid))
            ev.update(kind="ng_sample", mode=mode, score=sc, version=m["version"], cycle_id=cid,
                      ng=dict(done=len(ng["items"]), expected=ng["expected"]))
            if len(ng["items"]) >= ng["expected"]:
                ev["ng_result"] = self._finish_ng()
            return ev
        cid = s.add_cycle(self.mid, recipe, ts, f, "monitor", score=sc["norm"], flag=sc["flag"],
                          model_version=m["version"])
        ev.update(kind="score", mode=mode, score=sc, version=m["version"], cycle_id=cid)
        if sc["flag"]:
            sug = self.suggest(f, m["body"])
            ev["alarm_id"] = s.add_alarm(self.mid, recipe, ts, cid, sc["norm"], sc["top"], sug)
            ev["suggestion"] = sug
        c["since"] += 1
        if c["since"] >= self.cfg["retrain_every"] and not c["pending"]:
            v = self._candidate(recipe, kind="drift")
            if v:
                ev["candidate"] = v
        return ev

    # ───────────── huấn luyện ─────────────
    def _train_initial(self, recipe):
        ids, X = self.store.features(self.mid, recipe, "role='learn'")
        body = DT.train(X, recipe)
        body["source_cycles"] = [ids[0], ids[-1]]
        note = (f"Học từ {len(X)} chu kỳ đầu tiên (tự bỏ {body['n_dropped']} chu kỳ nghi lỗi) · "
                f"ngưỡng chọn ở phân vị {DT.PCT} trên {body['n_calib']} chu kỳ hiệu chuẩn")
        v = self.store.add_model(self.mid, recipe, body, "initial", note)
        self._reload(recipe)
        if self.cfg["auto_approve"]:
            self.approve(recipe)
        return v

    def _candidate(self, recipe, kind, extra_note=""):
        """Bản học lại: các chu kỳ giám sát gần nhất không bị cảnh báo + các chu kỳ người xác nhận là bình thường."""
        s, c = self.store, self._rc(recipe)
        ids, X = s.features(self.mid, recipe,
                            "role='monitor' AND ((flag=0 AND (label IS NULL OR label NOT IN ('fault','missed','ng_sample'))) "
                            "OR label IN ('false_alarm','new_normal'))")
        ids, X = ids[-self.cfg["drift_window"]:], X[-self.cfg["drift_window"]:]
        c["since"] = 0
        if len(X) < self.cfg["min_drift"]:
            return None
        body = DT.train(X, recipe)
        body["source_cycles"] = [ids[0], ids[-1]]
        sh = DT.shift(c["active"]["body"], body) if c["active"] else 0.0
        sh0 = DT.shift(c["origin"]["body"], body) if c["origin"] else 0.0
        body["shift"], body["shift_origin"] = round(sh, 3), round(sh0, 3)
        why = {"drift": "Học lại định kỳ", "new_normal": "Thêm chế độ bình thường mới",
               "false_alarm": "Học lại theo phản hồi báo nhầm"}.get(kind, "Học lại")
        note = (f"{why} trên {len(X)} chu kỳ gần nhất · chuẩn dịch {sh:.2f}σ so với bản đang chạy, "
                f"{sh0:.2f}σ so với bản gốc{extra_note}")
        v = s.add_model(self.mid, recipe, body, kind, note)
        self._reload(recipe)
        if self.cfg["auto_approve"] and sh < self.cfg["shift_warn"] and sh0 < 2 * self.cfg["shift_warn"]:
            self.approve(recipe)
        return v

    # ───────────── lệnh từ dashboard ─────────────
    def approve(self, recipe):
        c = self._rc(recipe)
        if not c["pending"]:
            raise ValueError("Không có bản nào đang chờ duyệt")
        if c["active"]:
            self.store.set_model_status(self.mid, recipe, c["active"]["version"], "retired")
        self.store.set_model_status(self.mid, recipe, c["pending"]["version"], "active")
        c["since"] = 0
        self._reload(recipe)
        a = self.cache[recipe]["active"]
        return a["version"] if a else None

    def reject(self, recipe):
        c = self._rc(recipe)
        if not c["pending"]:
            raise ValueError("Không có bản nào đang chờ duyệt")
        self.store.set_model_status(self.mid, recipe, c["pending"]["version"], "rejected")
        if not c["active"]:
            self.store.set_role(self.mid, recipe, "learn", "discarded")   # học lại từ đầu
        self._reload(recipe)

    def relearn(self, recipe):
        c = self._rc(recipe)
        for k in ("active", "pending"):
            if c[k]:
                self.store.set_model_status(self.mid, recipe, c[k]["version"], "retired" if k == "active" else "rejected")
        self.store.set_role(self.mid, recipe, "learn", "discarded")
        c["since"] = 0
        self._reload(recipe)

    def rollback(self, recipe, version):
        m = self.store.model(self.mid, recipe, version=int(version))
        if not m or m["status"] in ("pending", "rejected"):
            raise ValueError("Chỉ quay về được bản đã từng chạy")
        c = self._rc(recipe)
        if c["active"]:
            self.store.set_model_status(self.mid, recipe, c["active"]["version"], "retired")
        self.store.set_model_status(self.mid, recipe, int(version), "active")
        self._reload(recipe)

    def retrain_now(self, recipe):
        if self.mode(recipe) != "monitoring":
            raise ValueError("Máy chưa ở chế độ giám sát")
        v = self._candidate(recipe, kind="drift", extra_note=" · kỹ sư yêu cầu")
        if not v:
            raise ValueError(f"Chưa đủ {self.cfg['min_drift']} chu kỳ bình thường gần đây để học lại")
        return v

    # ───────────── kiểm tra mẫu NG chuẩn (đầu ca) ─────────────
    def start_ng_check(self, recipe="*", expected=3, note=""):
        """Kỹ sư cho chạy N chi tiết lỗi chuẩn (lấy từ kho mẫu NG). AI phải gắn cờ cả N."""
        recipe = "*" if recipe in (None, "") else str(recipe)
        if recipe != "*" and self.mode(recipe) != "monitoring":
            raise ValueError("Chỉ kiểm tra mẫu NG được khi mã hàng này đang giám sát")
        if recipe == "*" and not any(self.mode(r) == "monitoring" for r in (self.store.recipes(self.mid) or ["*"])):
            raise ValueError("Máy chưa ở chế độ giám sát — duyệt chuẩn trước rồi mới kiểm tra mẫu NG")
        expected = max(1, min(20, int(expected)))
        self.ng = dict(recipe=recipe, expected=expected, items=[], started=time.time(), note=str(note or "")[:80])
        return dict(expected=expected)

    def cancel_ng_check(self):
        out = self._finish_ng(note="Huỷ giữa chừng") if self.ng and self.ng["items"] else None
        self.ng = None
        return out

    def _finish_ng(self, note=None):
        ng, self.ng = self.ng, None
        if not ng:
            return None
        caught = sum(1 for i in ng["items"] if i["flag"])
        cid = self.store.add_check(self.mid, ng["recipe"], ng["started"], ng["expected"], ng["items"],
                                   note or ng.get("note", ""))
        return dict(id=cid, expected=ng["expected"], done=len(ng["items"]), caught=caught,
                    ok=caught == len(ng["items"]) == ng["expected"])

    # ───────────── AI bỏ sót: chu kỳ không bị cảnh báo nhưng thực ra là lỗi ─────────────
    def report_missed(self, cycle_id, fault_type=None, source="dashboard"):
        r = self.store.q("SELECT * FROM cycles WHERE id=? AND machine=?", (int(cycle_id), self.mid), one=True)
        if not r or r["role"] != "monitor":
            raise ValueError("Không tìm thấy chu kỳ đang giám sát này")
        if r["flag"]:
            raise ValueError("Chu kỳ này AI đã cảnh báo — dùng nút trên cảnh báo đó")
        m = self._rc(r["recipe"])["active"]
        top = DT.score(m["body"], json.loads(r["f"]))["top"] if m else []
        aid = self.store.add_alarm(self.mid, r["recipe"], r["ts"], r["id"], r["score"] or 0.0, top)
        self.store.resolve_alarm(aid, "missed", (fault_type or "").strip() or None, source)
        if fault_type:
            self._fit_classifier()
        return dict(alarm_id=aid, cycle_id=int(cycle_id))

    # ───────────── độ chính xác thực tế tại máy ─────────────
    def field_stats(self):
        week = time.time() - 7 * 86400
        def pack(cnt):
            f, fa, nn, mi, op = (cnt.get(k, 0) for k in ("fault", "false_alarm", "new_normal", "missed", "open"))
            judged = f + fa + nn
            return dict(fault=f, false_alarm=fa, new_normal=nn, missed=mi, open=op,
                        precision=(f / judged) if judged else None,       # cảnh báo đúng / cảnh báo đã xác nhận
                        recall=(f / (f + mi)) if (f + mi) else None)      # lỗi AI bắt / lỗi đã biết
        checks = self.store.checks(self.mid, 10)
        return dict(all=pack(self.store.field_counts(self.mid)), week=pack(self.store.field_counts(self.mid, week)),
                    checks=[dict(id=c["id"], started=c["started"], expected=c["expected"], caught=c["caught"],
                                 done=len(c["items"]), recipe=c["recipe"], note=c["note"]) for c in checks],
                    ng_active=(dict(recipe=self.ng["recipe"], expected=self.ng["expected"], done=len(self.ng["items"]),
                                    started=self.ng["started"]) if self.ng else None),
                    recent=[dict(id=c["id"], recipe=c["recipe"], ts=c["ts"], norm=c["score"], flag=bool(c["flag"]),
                                 label=c["label"]) for c in self.store.last_monitor_cycles(self.mid, 12)])

    def feedback(self, alarm_id, label, fault_type=None, all_open=False, source="dashboard"):
        """all_open=True: áp cùng nhãn cho mọi cảnh báo đang mở của mã hàng đó (vd. cả loạt là chế độ mới)."""
        if label not in ("fault", "false_alarm", "new_normal"):
            raise ValueError("Nhãn không hợp lệ")
        a = self.store.alarm(int(alarm_id))
        if not a or a["machine"] != self.mid:
            raise ValueError("Không tìm thấy cảnh báo")
        ft = (fault_type or "").strip() or None
        ids = [int(alarm_id)]
        if all_open:
            ids += [r["id"] for r in self.store.q(
                "SELECT id FROM alarms WHERE machine=? AND recipe=? AND status='open' AND id<>?",
                (self.mid, a["recipe"], int(alarm_id)))]
        for i in ids:
            self.store.resolve_alarm(i, label, ft, source)
        out = dict(alarm_id=int(alarm_id), label=label, applied=len(ids))
        if label == "fault":
            self._fit_classifier()
            out["classifier"] = self.clf_info
        # Báo nhầm và Bình thường mới đều là "chu kỳ bình thường đã được người xác nhận". Đủ new_normal_min nhãn
        # kể từ bản mô hình gần nhất thì tự tạo bản học lại chờ duyệt — không phải đợi tới lần học lại định kỳ.
        # (Trên dữ liệu thật Bosch CNC, học lại theo phản hồi kiểu này giảm báo nhầm từ ~44% xuống ~16–19%.)
        if label in ("new_normal", "false_alarm"):
            n = self.store.q("""SELECT COUNT(*) c FROM cycles WHERE machine=? AND recipe=? AND label IN ('new_normal','false_alarm')
                                AND id > COALESCE((SELECT MAX(json_extract(body,'$.source_cycles[1]')) FROM models
                                WHERE machine=? AND recipe=? AND status IN ('active','pending')),0)""",
                             (self.mid, a["recipe"], self.mid, a["recipe"]), one=True)["c"]
            out["new_normal_count"] = n
            if n >= self.cfg["new_normal_min"] and not self._rc(a["recipe"])["pending"]:
                out["candidate"] = self._candidate(a["recipe"], kind=label)
                if not out["candidate"]:
                    out["note"] = f"Cần ít nhất {self.cfg['min_drift']} chu kỳ bình thường gần đây để tạo bản học lại"
            elif n < self.cfg["new_normal_min"]:
                out["note"] = f"Đã có {n}/{self.cfg['new_normal_min']} chu kỳ được xác nhận bình thường — đủ thì tự tạo bản học lại"
        return out

    # ───────────── phân loại lỗi (khi đã đủ nhãn) ─────────────
    # Dùng chung giữa các máy CÙNG LOẠI: mỗi chu kỳ lỗi được quy về "lệch bao nhiêu lần độ lệch thường"
    # so với chuẩn của chính máy / mã hàng đó, nên máy ép 12 kN và máy ép 20 kN học chung được một bộ phân loại.
    def peers(self):
        ms = self.store.machines()
        out = [k for k, c in ms.items()
               if (c.get("machine_type") or PROCESS_TO_TYPE.get(c.get("process"), "generic")) == self.machine_type]
        return out if self.mid in out else out + [self.mid]

    def _ref_model(self, machine, recipe, cache):
        k = (machine, recipe)
        if k not in cache:
            m = self.store.model(machine, recipe, status="active")
            if m is None:
                rows = [r for r in self.store.models(machine, recipe) if r["status"] != "rejected"]
                m = self.store.model(machine, recipe, version=rows[-1]["version"]) if rows else None
            cache[k] = m["body"] if m else None
        return cache[k]

    @staticmethod
    def _rel(body, f):
        med = np.asarray(body["med"])
        return (np.asarray(f, dtype=float)[:len(med)] - med) / np.asarray(body["scale"])

    def _fit_classifier(self):
        peers = self.peers()
        rows = self.store.labeled_faults(peers)
        cache, X, y, src = {}, [], [], Counter()
        for f, ft, mach, rec in rows:
            body = self._ref_model(mach, rec, cache)
            if body is None:
                continue
            X.append(self._rel(body, f)); y.append(ft); src[mach] += 1
        if X:   # mô hình từ phiên bản cũ có ít đặc trưng hơn → chỉ giữ nhãn cùng số đặc trưng phổ biến nhất
            d = Counter(len(x) for x in X).most_common(1)[0][0]
            keep = [i for i, x in enumerate(X) if len(x) == d]
            X, y = [X[i] for i in keep], [y[i] for i in keep]
        cnt = Counter(y)
        types = {k: v for k, v in cnt.items() if v >= self.cfg["clf_min_per_type"]}
        ready = len(y) >= self.cfg["clf_min_total"] and len(types) >= 2
        self.clf_info = dict(n=len(y), types=dict(cnt), need_total=self.cfg["clf_min_total"],
                             need_per_type=self.cfg["clf_min_per_type"], ready=ready,
                             machine_type=self.machine_type, shared_machines=len(src),
                             own=src.get(self.mid, 0))
        self.clf = None
        if ready:
            from sklearn.ensemble import RandomForestClassifier
            keep = [i for i, t in enumerate(y) if t in types]
            Xa, ya = np.asarray(X)[keep], [y[i] for i in keep]
            self.clf = RandomForestClassifier(n_estimators=150, random_state=0, class_weight="balanced").fit(Xa, ya)

    def suggest(self, f, body):
        if self.clf is None:
            return None
        z = self._rel(body, f)
        if len(z) != self.clf.n_features_in_:
            return None
        p = self.clf.predict_proba([z])[0]
        i = int(np.argmax(p))
        return dict(type=str(self.clf.classes_[i]), prob=round(float(p[i]), 2))

    # ───────────── trạng thái cho dashboard ─────────────
    def status(self):
        s = self.store
        recipes = s.recipes(self.mid) or ["*"]
        out = []
        for r in recipes:
            c = self._rc(r)
            mode = self.mode(r)
            item = dict(recipe=r, mode=mode,
                        learned=s.count(self.mid, r, role="learn"), target=self.cfg["learn_target"],
                        excluded_error=s.count(self.mid, r, role="excluded", reason_like="machine_error"),
                        excluded_dq=s.count(self.mid, r, role="excluded", reason_like="dq:%"),
                        monitored=s.count(self.mid, r, role="monitor"),
                        flagged=s.q("SELECT COUNT(*) c FROM cycles WHERE machine=? AND recipe=? AND role='monitor' AND flag=1 "
                                    "AND (label IS NULL OR label<>'ng_sample')",
                                    (self.mid, r), one=True)["c"],
                        since_retrain=c["since"], retrain_every=self.cfg["retrain_every"])
            for k in ("active", "pending"):
                m = c[k]
                if m:
                    b = m["body"]
                    item[k] = dict(version=m["version"], kind=m["kind"], note=m["note"], created=m["created"],
                                   n_train=b["n_train"], n_calib=b["n_calib"], n_dropped=b.get("n_dropped", 0),
                                   calib_false_alarm=b.get("calib_false_alarm"),
                                   t_maha=round(b["t_maha"], 3), t_robz=round(b["t_robz"], 3),
                                   duration_med=round(b.get("duration_med", 0), 2),
                                   shift=b.get("shift"), shift_origin=b.get("shift_origin"),
                                   warn=(b.get("shift") or 0) >= self.cfg["shift_warn"])
            item["versions"] = [dict(version=m["version"], status=m["status"], kind=m["kind"], note=m["note"],
                                     created=m["created"]) for m in s.models(self.mid, r)]
            out.append(item)
        open_alarms = s.q("SELECT COUNT(*) c FROM alarms WHERE machine=? AND status='open'", (self.mid,), one=True)["c"]
        return dict(machine=self.mid, recipes=out, open_alarms=open_alarms, classifier=self.clf_info,
                    last_dq=self.last_dq, ai=self.cfg, field=self.field_stats())

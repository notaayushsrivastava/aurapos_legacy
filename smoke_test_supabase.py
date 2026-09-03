"""
Smoke test for supabase_backend.py against a mocked Supabase client.

Validates every repository method wired into app.py returns the shapes the app
and templates expect, without touching the real Supabase project.

Run:  venv\\Scripts\\python smoke_test_supabase.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "mock-service-role"


# ---------------- Minimal in-memory fake Supabase client ----------------

class _Result:
    def __init__(self, data, count):
        self.data = data
        self.count = count


class _Query:
    """Chainable builder that lazily accumulates filters (mirrors supabase-py)."""
    def __init__(self, table):
        self._table = table
        self._filters = []
        self._or_group = None
        self._sort = None
        self._limit = None

    def _copy(self):
        q = _Query.__new__(_Query)
        q._table = self._table
        q._filters = list(self._filters)
        q._or_group = list(self._or_group) if self._or_group else None
        q._sort = self._sort
        q._limit = self._limit
        return q

    def eq(self, col, val):
        q = self._copy(); q._filters.append(("eq", col, val)); q._or_group = None; return q

    def neq(self, col, val):
        q = self._copy(); q._filters.append(("neq", col, val)); q._or_group = None; return q

    def ilike(self, col, val):
        q = self._copy(); q._filters.append(("ilike", col, val)); q._or_group = None; return q

    def gte(self, col, val):
        q = self._copy(); q._filters.append(("gte", col, val)); q._or_group = None; return q

    def lte(self, col, val):
        q = self._copy(); q._filters.append(("lte", col, val)); q._or_group = None; return q

    def or_(self, expr):
        q = self._copy()
        group = []
        for part in str(expr).split(","):
            pieces = part.strip().split(".")
            if len(pieces) >= 3:
                group.append((pieces[1], pieces[0], ".".join(pieces[2:])))
        q._or_group = group
        return q

    def order(self, col, desc=False):
        q = self._copy(); q._sort = (col, bool(desc)); return q

    def limit(self, n):
        q = self._copy(); q._limit = n; return q

    def maybe_single(self):
        return _Single(self)

    def execute(self):
        rows = self._build_rows()
        return _Result(rows, len(rows))

    def _build_rows(self):
        rows = [dict(r) for r in self._table.rows]
        for op, col, val in self._filters:
            rows = [r for r in rows if self._match(r, op, col, val)]
        if self._or_group:
            rows = [r for r in rows
                    if any(self._match(r, op, col, val)
                           for op, col, val in self._or_group)]
        if self._sort:
            col, desc = self._sort
            rows.sort(key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows

    @staticmethod
    def _match(row, op, col, val):
        if op == "eq":
            return row.get(col) == val
        if op == "neq":
            return row.get(col) != val
        if op == "ilike":
            needle = str(val).strip("%")
            return needle.lower() in str(row.get(col, "")).lower()
        if op == "gte":
            return row.get(col) >= val
        if op == "lte":
            return row.get(col) <= val
        return True


class _Single:
    def __init__(self, query):
        self._query = query

    def execute(self):
        rows = self._query._build_rows()
        row = rows[0] if rows else None
        return _Result(row, 1 if row else 0)


class _Insert:
    def __init__(self, table, rows):
        self._table = table
        self._rows = rows

    def execute(self):
        out = []
        for r in self._rows:
            row = dict(r)
            if "id" not in row or row["id"] is None:
                row["id"] = self._table._next_id
                self._table._next_id += 1
            self._table.rows.append(row)
            out.append(dict(row))
        return _Result(out, len(out))


class _Update:
    def __init__(self, table, payload):
        self._table = table
        self._payload = payload
        self._filters = []

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def execute(self):
        target = [r for r in self._table.rows
                  if all(r.get(c) == v for c, v in self._filters)]
        for r in target:
            r.update(self._payload)
        return _Result([dict(r) for r in target], len(target))


class _Delete:
    def __init__(self, table):
        self._table = table
        self._filters = []

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def execute(self):
        keep = [r for r in self._table.rows
                if not all(r.get(c) == v for c, v in self._filters)]
        self._table.rows = keep
        return _Result([], 0)


class _Table:
    def __init__(self):
        self.rows = []
        self._next_id = 1

    def select(self, *cols, count=None):
        return _Query(self)

    def insert(self, rows):
        if isinstance(rows, dict):
            rows = [rows]
        return _Insert(self, rows)

    def update(self, payload):
        return _Update(self, payload)

    def delete(self):
        return _Delete(self)


class _AuthAdmin:
    def create_user(self, props):
        class U:
            id = f"mock-{props.get('email')}"
        return type("R", (), {"user": U()})()

    def update_user_by_id(self, uid, props):
        return None

    def delete_user(self, uid):
        return None


class _Auth:
    def __init__(self):
        self.admin = _AuthAdmin()

    def sign_in_with_password(self, props):
        if props.get("password") == "ok":
            return type("R", (), {"user": {}})()
        raise type("AuthApiError", (Exception,), {"status": 400})("invalid")


class _MockSupabase:
    def __init__(self, url, key):
        self.url = url
        self.key = key
        self.tables = {
            "accounts": _Table(), "salons": _Table(), "subscriptions": _Table(),
            "pendingorders": _Table(), "deletion_requests": _Table(),
            "categories": _Table(), "services": _Table(), "staff": _Table(),
            "appointments": _Table(), "bills": _Table(), "customers": _Table(),
        }
        self.auth = _Auth()

    def table(self, name):
        return self.tables[name]


import supabase_backend as sb
sb.create_client = _MockSupabase

# ----------------------------------------------------------------
passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"FAIL  {name}")
print("== constants / helpers ==")
check("TIER_PLANS has 3", set(sb.TIER_PLANS) >= {"free", "pro", "studio"})
tier, cycle, pricing = sb.resolve_plan("pro_yearly")
check("resolve pro_yearly", tier == "pro" and cycle == "yearly" and pricing["amount"] == 69000)
tier, cycle, pricing = sb.resolve_plan("free")
check("resolve free", tier == "free" and cycle == "trial")
check("expires_for trial ~14d", abs(sb.expires_for("trial", 0) - 14 * 86400) == 0)
check("expires_for yearly ~1y", abs(sb.expires_for("yearly", 0) - 31536000) == 0)

print("== authRepo ==")
authRepo = sb.AuthorizationRepository()
salon_id = authRepo.create_auth("Test Owner", "Test Salon", "9876500001", "test@owner.com", "ok", plan="free")
check("create_auth returns id", isinstance(salon_id, int))
salon = authRepo.get_salon(salon_id)
check("salon plan free", salon.plan == "free")
check("salon expiry 14d", salon.expires_on and abs(salon.expires_on - salon.created_on - 14 * 86400) <= 5)

acc = authRepo.login("test@owner.com", "ok")
check("login correct pw", acc is not None and acc.auth_id == salon_id)
check("login wrong pw None", authRepo.login("test@owner.com", "bad") is None)
check("check_exists email", authRepo.check_exists("test@owner.com", "0000000000") is True)
check("forgot_password by username", authRepo.forgot_password("test@owner.com") is not None)
check("forgot_password by phone", authRepo.forgot_password("9876500001") is not None)

owner_id = authRepo.get_primary_account_id(salon_id)
check("primary account exists", owner_id is not None)
add = authRepo.add_account(salon_id, "team@owner.com", "ok", "manager")
check("add team account ok", add["success"] is True)
check("count 2 accounts", authRepo.count_accounts(salon_id) == 2)
accts = authRepo.get_accounts(salon_id)
check("get_accounts has 2", len(accts) == 2)
cp = authRepo.change_password(salon_id, "team@owner.com", "ok", "newpass")
check("change_password ok", cp[0] is True)
sp = authRepo.set_password(salon_id, "team@owner.com", "ok")
check("set_password ok", sp[0] is True)
dead = authRepo.delete_account(salon_id, owner_id)
check("cannot delete primary", dead["success"] is False)
team_row = next(a for a in accts if a["username"] == "team@owner.com")
dead = authRepo.delete_account(salon_id, team_row["id"])
check("delete team ok", dead["success"] is True)

print("== profile / subscription ==")
upd = authRepo.update_salon_profile(salon_id, "Test Owner", "Test Salon",
                                    "new@owner.com", "9876500001",
                                    extra={"address": "12 Main Rd", "opening_hours": "{}"})
check("update_salon_profile ok", upd is True)
upd = authRepo.update_salon_plan(salon_id, "pro", "monthly", int(__import__("time").time()) + 2592000)
check("update_salon_plan ok", upd is True)
authRepo.record_subscription("sub_123", salon_id, 6900, "pro", "monthly", "r", "e@e.com", "p")
check("get_subscriptions has 1", len(authRepo.get_subscriptions(salon_id)) == 1)

print("== pending orders ==")
authRepo.create_pendingorder("order_x", 6900, created_at=123, plan="pro",
                             receipt="r", email="e@e.com", phone="p", salon_id=salon_id)
po = authRepo.get_pendingorder("order_x")
check("pendingorder stored", po is not None and po["amount"] == 6900)

print("== deletion ==")
authRepo.request_account_deletion(salon_id, "e@e.com", "testing")
dr = authRepo.get_pending_deletion_request(salon_id)
check("deletion request pending", dr is not None and dr["status"] == "pending")

print("== categories ==")
catRepo = sb.CategoryRepository()
catRepo.seed_defaults_if_empty(salon_id)
cats = catRepo.get_categories(salon_id)
print("== services ==")
svcRepo = sb.ServiceRepository()
svcRepo.seed_defaults_if_empty(salon_id)
svcs = svcRepo.get_services(salon_id)
check("services seeded", len(svcs) == len(svcRepo.DEFAULTS))
snew = svcRepo.add_service(salon_id, "Test Cut", "Haircuts", 500, duration=30)
check("add_service returns id", snew is not None)
svcRepo.update_service(snew, salon_id, "Test Cut 2", "Haircuts", 550, 35, "Staff", "d", 1)
svcRepo.delete_service(snew, salon_id)
check("booking services active only", all(s["active"] == 1 for s in svcRepo.get_booking_services(salon_id)))
bulk = svcRepo.bulk_add_services(salon_id, [
    {"name": "Massage", "category": "Spa", "price": "800", "duration": "60", "staff": "", "description": ""},
    {"name": "", "category": "", "price": "", "duration": ""},
])
check("bulk_add_services adds", bulk["added"] == 1 and bulk["skipped"] == 1)

print("== staff ==")
staffRepo = sb.StaffRepository()
staffRepo.seed_defaults_if_empty(salon_id)
staff = staffRepo.get_staff(salon_id)
check("staff seeded", len(staff) == len(staffRepo.DEFAULTS))
sid = staffRepo.add_staff(salon_id, "New Stylist", "Stylist", "9811111111", "Female", "new@x.com")
check("add_staff returns id", sid is not None)
staffRepo.update_staff(sid, salon_id, "New Stylist 2", "Senior", "9811111111", "Female", "new@x.com")
staffRepo.record_sale("Alex Rivera (Senior)", salon_id, 1000)
alex = next(s for s in staffRepo.get_staff(salon_id) if s["name"] == "Alex Rivera")
check("record_sale increments", alex["total_revenue"] == 1000)
ok, msg = staffRepo.delete_staff(sid, salon_id)
check("delete_staff ok", ok is True)

print("== appointments ==")
aptRepo = sb.AppointmentRepository()
aid = aptRepo.create_appointment(salon_id, "Client", "9870000000", "c@c.com",
                                 "Haircut", "10:00", "2026-08-10", "Alex Rivera", 400)
check("create_appointment returns id", aid is not None)
ap = aptRepo.get_appointments(salon_id, "2026-08-10")
check("get_appointments by date", len(ap) == 1 and ap[0]["client"] == "Client")
aptRepo.update_status(aid, salon_id, "Completed")
ap = aptRepo.get_appointments(salon_id, "2026-08-10")
check("status updated", ap[0]["status"] == "Completed")

print("== bills ==")
billRepo = sb.BillRepository()
billRepo.create_bill("AP-ABC123", salon_id, "Client", "9870000000", 500, 0, 0,
                     500, "UPI", """[{"name":"Haircut","price":500,"qty":1,"staff":"Alex Rivera"}]""",
                     created_at=1786396800)
billRepo.create_bill("AP-DEF456", salon_id, "Client2", "9811111111", 700, 50, 0,
                     650, "Cash", """[{"name":"Facial","price":700,"qty":1,"staff":"Priya Nair"}]""",
                     created_at=1786396900)
check("get_recent_bills", len(billRepo.get_recent_bills(salon_id)) == 2)
metrics = billRepo.get_metrics(salon_id, 1786310400, 1786483200)
check("metrics total_sales", metrics["total_sales"] == 1150)
check("metrics total_bills", metrics["total_bills"] == 2)
check("metrics unique_customers", metrics["unique_customers"] == 2)
ranged = billRepo.get_bills_in_range(salon_id, 1786310400, 1786483200)
check("get_bills_in_range items", isinstance(ranged, list) and "items" in ranged[0])

print("== customers ==")
custRepo = sb.CustomerRepository()
custRepo.seed_defaults_if_empty(salon_id)
custs = custRepo.get_customers(salon_id)
check("customers seeded", len(custs) == len(custRepo.DEFAULTS))
st = custRepo.search_customers(salon_id, "sharma")
check("search_customers finds", len(st) >= 1)
byp = custRepo.get_by_phone(salon_id, "9876543210")
check("get_by_phone", byp is not None)
cid_c = custRepo.add_customer(salon_id, "New Client", "9870000001", "e@e.com", "")
check("add_customer returns id", cid_c is not None)
bk = custRepo.bulk_add_customers(salon_id, [
    {"name": "Bulk A", "phone": "9700000000", "email": "", "notes": ""},
    {"name": "Bulk B", "phone": "9876543210", "email": "", "notes": ""},
])
check("bulk_add_customers skip dup", bk["added"] == 1 and bk["skipped"] == 1)

print("== reports ==")
repRepo = sb.ReportRepository()
from datetime import datetime as _dt
start = int(_dt(2026, 8, 1).timestamp())
end = int(_dt(2026, 8, 31).timestamp())
summ = repRepo.summary(salon_id, start, end)
check("report summary total_sales", summ["total_sales"] == 1150)
day = repRepo.revenue_by_day(salon_id, start, end)
check("revenue_by_day kind day", day["kind"] == "day")
check("revenue_by_day has points", len(day["points"]) >= 1)
hour = repRepo.revenue_by_hour(salon_id, start, end)
check("revenue_by_hour returns list", isinstance(hour, list) and len(hour) == 13)
top = repRepo.top_services(salon_id, start, end)
check("top_services top is Facial", top and top[0]["name"] == "Facial")
board = repRepo.staff_leaderboard(salon_id, start, end)
check("staff_leaderboard includes all staff", len(board) >= len(staffRepo.get_staff(salon_id)))
psplit = repRepo.payment_split(salon_id, start, end)
check("payment_split returns", isinstance(psplit, list) and len(psplit) >= 2)
csplit = repRepo.category_split(salon_id, start, end)
check("category_split returns", isinstance(csplit, list) and len(csplit) >= 1)
apt_agg = repRepo.appointments_in_range(salon_id, start, end)
check("appointments_in_range total", apt_agg["total"] >= 1)

print(f"\n== SMOKE RESULT: {passed} passed, {failed} failed ==")
sys.exit(1 if failed else 0)

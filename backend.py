from dataclasses import dataclass, asdict
import sqlite3 as sql
from datetime import datetime, date, timedelta
import json
import os
import re

# ================= SUBSCRIPTION TIERS =================
# Free-trial + two-tier subscription model:
#   free   -> 14-day trial: single seat, core POS only (no salon address,
#             no map location, no premium features)
#   pro    -> entry tier: limited team seats, unlocks salon address & map pin
#   studio -> premium tier: unlimited team seats, advanced analytics,
#             data import/export and custom salon logo branding
TIER_PLANS = {
    "free": {"amount": 0, "label": "Free Trial", "price_display": "Free for 14 days"},
    "pro": {"amount": 6900, "label": "Pro", "price_display": "₹69/month"},
    "studio": {"amount": 14900, "label": "Studio", "price_display": "₹149/month"},
}

# Ascending tier ladder used to decide which plans an existing salon may buy.
TIER_ORDER = ("free", "pro", "studio")

# Length of the free trial in days.
TRIAL_DAYS = 14

# Team seat limit per tier (None = unlimited), including the primary owner account
TIER_SEAT_LIMITS = {"free": 1, "pro": 2, "studio": None}

# Purchaseable plan ids accepted by /create-subscription & /verify-subscription.
# `salons.plan` always stores the pure tier (pro/studio) while `billing_cycle`
# keeps the billing period (monthly/yearly) separate — this keeps tier gating,
# seat limits and feature checks working identically for annual subscribers.
# Annual = 12 months for the price of 10 (2 months free).
PLAN_PRICING = {
    "pro":           {"tier": "pro",    "cycle": "monthly", "amount": 6900,   "label": "Pro Monthly",    "price_display": "₹69/month"},
    "pro_yearly":    {"tier": "pro",    "cycle": "yearly",  "amount": 69000,  "label": "Pro Annual",     "price_display": "₹690/year"},
    "studio":        {"tier": "studio", "cycle": "monthly", "amount": 14900,  "label": "Studio Monthly", "price_display": "₹149/month"},
    "studio_yearly": {"tier": "studio", "cycle": "yearly",  "amount": 149000, "label": "Studio Annual",  "price_display": "₹1,490/year"},
}


def resolve_plan(plan_id):
    """Map a purchaseable plan id (or legacy tier name) to (tier, cycle, pricing).

    Accepts both the payment plan ids ('pro', 'pro_yearly', 'studio',
    'studio_yearly'), the free-trial tier ('free') and bare tier names ('pro',
    'studio', or any legacy value), always falling back to the Pro monthly plan.
    The 'free' trial uses billing_cycle 'trial' so 14-day expiry logic applies.
    """
    pricing = PLAN_PRICING.get(plan_id)
    if pricing:
        return pricing["tier"], pricing["cycle"], pricing
    if plan_id == "free":
        return "free", "trial", {
            "tier": "free", "cycle": "trial", "amount": 0,
            "label": "Free Trial", "price_display": "Free for 14 days",
        }
    tier = plan_id if plan_id in TIER_PLANS else "pro"
    return tier, "monthly", PLAN_PRICING[tier]


def expires_for(cycle, created_on=None):
    """Unix expiry timestamp for a billing cycle.

    'yearly' -> 365 days, 'trial' -> TRIAL_DAYS days, anything else (monthly)
    -> 30 days. `created_on` defaults to now.
    """
    if created_on is None:
        created_on = int(datetime.now().timestamp())
    if cycle == "yearly":
        return created_on + Time.year
    if cycle == "trial":
        return created_on + TRIAL_DAYS * Time.day
    return created_on + Time.month

# Supported access levels for salon team accounts
AUTH_LEVELS = ("admin", "manager", "cashier")


class PostgresCursorWrapper:
    def __init__(self, pg_conn, pg_cursor):
        self._conn = pg_conn
        self._cur = pg_cursor
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=()):
        cleaned = sql.strip()

        if cleaned.upper().startswith("PRAGMA"):
            if "TABLE_INFO" in cleaned.upper():
                m = re.search(r"table_info\((.*?)\)", cleaned, re.IGNORECASE)
                if m:
                    tbl = m.group(1).strip(" \"'`").lower()
                    cleaned = f"SELECT column_name AS name FROM information_schema.columns WHERE table_name = '{tbl}'"
                else:
                    cleaned = "SELECT 1 AS name WHERE 1=0"
            else:
                cleaned = "SELECT 1 AS name WHERE 1=0"

        cleaned = cleaned.replace("?", "%s")
        cleaned = cleaned.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        if "INSERT OR IGNORE INTO" in cleaned:
            cleaned = cleaned.replace("INSERT OR IGNORE INTO", "INSERT INTO")
            if "ON CONFLICT" not in cleaned.upper():
                if "categories" in cleaned.lower():
                    cleaned = cleaned.rstrip("; ") + " ON CONFLICT (account_id, name) DO NOTHING"
                elif "salons" in cleaned.lower():
                    cleaned = cleaned.rstrip("; ") + " ON CONFLICT (phone) DO NOTHING"
                else:
                    cleaned = cleaned.rstrip("; ") + " ON CONFLICT DO NOTHING"
        cleaned = cleaned.replace("COLLATE NOCASE", "")
        cleaned = re.sub(r"\browid\b", "id", cleaned, flags=re.IGNORECASE)

        is_insert = cleaned.strip().upper().startswith("INSERT")
        if is_insert and "RETURNING" not in cleaned.upper():
            cleaned = cleaned.rstrip("; ") + " RETURNING id"

        try:
            self._cur.execute(cleaned, params)
            self.rowcount = self._cur.rowcount
            if is_insert:
                try:
                    row = self._cur.fetchone()
                    if row and "id" in row:
                        self.lastrowid = row["id"]
                except Exception:
                    pass
        except Exception as e:
            try:
                self._conn.rollback()
            except Exception:
                pass
            raise e
        return self

    def fetchone(self):
        try:
            return self._cur.fetchone()
        except Exception:
            return None

    def fetchall(self):
        try:
            return self._cur.fetchall()
        except Exception:
            return []

    def executescript(self, script_sql):
        statements = [s.strip() for s in script_sql.split(";") if s.strip()]
        for stmt in statements:
            if not stmt.upper().startswith("PRAGMA"):
                self.execute(stmt)

    def executemany(self, sql, param_list):
        for p in param_list:
            self.execute(sql, p)


class PostgresConnWrapper:
    def __init__(self, dsn):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True
        self._cursor_factory = RealDictCursor

    def cursor(self):
        pg_cur = self._conn.cursor(cursor_factory=self._cursor_factory)
        return PostgresCursorWrapper(self._conn, pg_cur)

    def commit(self):
        try:
            self._conn.commit()
        except Exception:
            pass

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


def get_db():
    if os.environ.get("USE_POSTGRES") or os.environ.get("DATABASE_URL"):
        dsn = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/postgres")
        return PostgresConnWrapper(dsn)
    conn = sql.connect("database.db")
    conn.row_factory = sql.Row
    return conn


def ensure_schema_upgrades():
    """Lightweight migrations for databases created before newer columns existed."""
    conn = get_db()
    cur = conn.cursor()
    salons_columns = {r["name"] for r in cur.execute("PRAGMA table_info(salons)").fetchall()}
    if salons_columns and "logo" not in salons_columns:
        cur.execute("ALTER TABLE salons ADD COLUMN logo TEXT")
    if salons_columns and "billing_cycle" not in salons_columns:
        cur.execute("ALTER TABLE salons ADD COLUMN billing_cycle TEXT NOT NULL DEFAULT 'monthly'")
    if salons_columns and "address" not in salons_columns:
        cur.execute("ALTER TABLE salons ADD COLUMN address TEXT NOT NULL DEFAULT ''")
    if salons_columns and "opening_hours" not in salons_columns:
        cur.execute("ALTER TABLE salons ADD COLUMN opening_hours TEXT NOT NULL DEFAULT '{}'")
    if salons_columns and "latitude" not in salons_columns:
        cur.execute("ALTER TABLE salons ADD COLUMN latitude REAL")
    if salons_columns and "longitude" not in salons_columns:
        cur.execute("ALTER TABLE salons ADD COLUMN longitude REAL")
    subs_columns = {r["name"] for r in cur.execute("PRAGMA table_info(subscriptions)").fetchall()}
    if subs_columns and "billing_cycle" not in subs_columns:
        cur.execute("ALTER TABLE subscriptions ADD COLUMN billing_cycle TEXT NOT NULL DEFAULT 'monthly'")
    conn.commit()
    conn.close()


@dataclass
class Time:
    day = 24 * 60 * 60
    month = 30 * day
    year = 365 * day


@dataclass
class Salon:
    id: int
    name: str
    phone: str
    salon_name: str
    email: str
    created_on: int
    plan: str
    expires_on: int
    logo: str | None = None
    billing_cycle: str = "monthly"
    address: str = ""
    # Weekly schedule stored as a JSON string, e.g.
    # {"monday": {"closed": false, "open": "09:00", "close": "19:00"}, ...}
    opening_hours: str = "{}"
    # Salon location (map pin) — a Pro-tier feature, coordinates optional.
    latitude: float | None = None
    longitude: float | None = None

    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        return cls(
            id=row["id"],
            name=row["name"],
            phone=str(row["phone"]),
            salon_name=row["salon_name"],
            email=row["email"],
            created_on=row["created_on"],
            plan=row["plan"],
            expires_on=row["expires_on"],
            logo=(row["logo"] if "logo" in row.keys() else None),
            billing_cycle=(row["billing_cycle"] if "billing_cycle" in row.keys() else "monthly"),
            address=((row["address"] if "address" in row.keys() else "") or ""),
            opening_hours=((row["opening_hours"] if "opening_hours" in row.keys() else "") or "{}"),
            latitude=(row["latitude"] if "latitude" in row.keys() else None),
            longitude=(row["longitude"] if "longitude" in row.keys() else None),
        )


# Canonical weekday keys used by the salon opening-hours schedule.
WEEKDAY_KEYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def parse_opening_hours(salon):
    """Return the salon's weekly schedule as a dict (empty dict when unset/invalid)."""
    try:
        raw = json.loads(getattr(salon, "opening_hours", "") or "{}")
    except (ValueError, TypeError):
        raw = {}
    if not isinstance(raw, dict):
        return {}
    return {key: raw[key] for key in WEEKDAY_KEYS if isinstance(raw.get(key), dict)}


@dataclass
class Account:
    auth_id: int
    username: str
    password: str
    auth_level: str
    salon: Salon | None = None

    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        return cls(
            auth_id=row["auth_id"],
            username=row["username"],
            password=row["password"],
            auth_level=row["auth_level"],
        )


class AuthorizationRepository:
    def __init__(self):
        conn = get_db()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS salons(
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                salon_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                created_on INTEGER NOT NULL,
                plan TEXT NOT NULL,
                billing_cycle TEXT NOT NULL DEFAULT 'monthly',
                expires_on INTEGER NOT NULL,
                logo TEXT,
                address TEXT NOT NULL DEFAULT '',
                opening_hours TEXT NOT NULL DEFAULT '{}',
                latitude REAL,
                longitude REAL
            );

            CREATE TABLE IF NOT EXISTS accounts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auth_id INTEGER NOT NULL,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                auth_level TEXT DEFAULT 'admin',
                FOREIGN KEY (auth_id) REFERENCES salons(id)
            );

            CREATE TABLE IF NOT EXISTS pendingorders(
                id TEXT PRIMARY KEY,
                amount INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                plan TEXT NOT NULL,
                receipt TEXT NOT NULL,
                email TEXT NOT NULL,
                phone INTEGER NOT NULL,
                salon_id INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS subscriptions(
                id TEXT PRIMARY KEY,
                amount INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                plan TEXT NOT NULL,
                billing_cycle TEXT NOT NULL DEFAULT 'monthly',
                receipt TEXT NOT NULL,
                email TEXT NOT NULL,
                phone INTEGER NOT NULL,
                salon_id INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS deletion_requests(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                salon_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                reason TEXT DEFAULT '',
                requested_at INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (salon_id) REFERENCES salons(id)
            );
            """
        )
        conn.commit()
        conn.close()
        ensure_schema_upgrades()

    def update_salon_logo(self, salon_id, logo_data):
        """Store (or clear, with None) the salon's logo as a data URL."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE salons SET logo = ? WHERE id = ?", (logo_data, salon_id))
        conn.commit()
        conn.close()

    def create_account(self, auth_id, username, password, auth_level="admin"):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO accounts(auth_id, username, password, auth_level)
            VALUES (?, ?, ?, ?)
            """,
            (auth_id, username, password, auth_level),
        )
        conn.commit()
        conn.close()

    def create_auth(self, name, salon_name, phone, email, password, plan="pro", created_on=None, auth_level="admin"):
        if created_on is None:
            created_on = int(datetime.now().timestamp())
        tier, cycle, _ = resolve_plan(plan)
        expires_on = expires_for(cycle, created_on)
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO salons(name, salon_name, phone, email, plan, billing_cycle, created_on, expires_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, salon_name, str(phone), email, tier, cycle, created_on, expires_on),
        )
        auth_id = cur.lastrowid
        conn.commit()
        conn.close()

        self.create_account(auth_id, email, password, auth_level)
        return auth_id

    def login(self, username, password):
        conn = get_db()
        cur = conn.cursor()
        e = cur.execute(
            "SELECT * FROM accounts WHERE username = ? AND password = ?",
            (username.strip(), password.strip()),
        ).fetchone()
        conn.close()
        return Account.from_row(e)

    def get_salon(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM salons WHERE id = ?", (salon_id,)).fetchone()
        conn.close()
        return Salon.from_row(row)

    def forgot_password(self, identifier):
        conn = get_db()
        cur = conn.cursor()
        identifier_str = str(identifier).strip()
        e = cur.execute(
            """
            SELECT a.* FROM accounts a 
            LEFT JOIN salons s ON a.auth_id = s.id 
            WHERE a.username = ? OR s.phone = ? OR s.email = ?
            """,
            (identifier_str, identifier_str, identifier_str),
        ).fetchone()
        conn.close()
        return Account.from_row(e)

    def check_exists(self, email, phone):
        conn = get_db()
        cur = conn.cursor()
        email_str = str(email).strip()
        phone_str = str(phone).strip()
        row = cur.execute(
            "SELECT id FROM salons WHERE email = ? OR phone = ?",
            (email_str, phone_str),
        ).fetchone()
        conn.close()
        return row is not None

    # ---------- Settings: salon profile ----------
    def update_salon_profile(self, salon_id, owner_name, salon_name, email, phone, extra=None):
        """Update the salon's public profile. Returns False on UNIQUE conflicts.

        `extra` (optional dict) may carry:
          - address (str): salon street address shown on bills & booking portal
          - opening_hours (str): weekly schedule as a validated JSON string
          - location ({'latitude': float, 'longitude': float}) to set the map pin
          - location (False) to clear the saved map pin
        """
        sets = ["name = ?", "salon_name = ?", "email = ?", "phone = ?"]
        vals = [owner_name.strip(), salon_name.strip(), email.strip(), str(phone).strip()]
        if extra:
            if extra.get("address") is not None:
                sets.append("address = ?")
                vals.append(str(extra["address"]).strip())
            if extra.get("opening_hours") is not None:
                sets.append("opening_hours = ?")
                vals.append(extra["opening_hours"])
            location = extra.get("location", None)
            if location is False:
                sets.append("latitude = NULL")
                sets.append("longitude = NULL")
            elif isinstance(location, dict) and location.get("latitude") is not None and location.get("longitude") is not None:
                sets.append("latitude = ?")
                vals.append(float(location["latitude"]))
                sets.append("longitude = ?")
                vals.append(float(location["longitude"]))
        vals.append(salon_id)
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                f"UPDATE salons SET {', '.join(sets)} WHERE id = ?",
                tuple(vals),
            )
            conn.commit()
            conn.close()
            return True
        except sql.IntegrityError:
            return False

    # ---------- Settings: password management ----------
    def change_password(self, salon_id, username, current_password, new_password):
        """Change the password of a specific account after verifying the current one."""
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT password FROM accounts WHERE auth_id = ? AND username = ?",
            (salon_id, username),
        ).fetchone()
        if not row or row["password"] != current_password:
            conn.close()
            return False, "Current password is incorrect."
        cur.execute(
            "UPDATE accounts SET password = ? WHERE auth_id = ? AND username = ?",
            (new_password, salon_id, username),
        )
        conn.commit()
        conn.close()
        return True, "Password updated successfully."

    def set_password(self, salon_id, username, new_password):
        """Reset a password without verification (used by owner for team accounts)."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE accounts SET password = ? WHERE auth_id = ? AND username = ?",
            (new_password, salon_id, username),
        )
        changed = cur.rowcount > 0
        conn.commit()
        conn.close()
        return changed

    # ---------- Settings: team account management (max 3 seats per salon) ----------
    def get_accounts(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT rowid AS id, username, password, auth_level
            FROM accounts WHERE auth_id = ?
            ORDER BY rowid ASC
            """,
            (salon_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def count_accounts(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        count = cur.execute(
            "SELECT COUNT(*) AS c FROM accounts WHERE auth_id = ?", (salon_id,)
        ).fetchone()["c"]
        conn.close()
        return count

    def get_primary_account_id(self, salon_id):
        """The first account created for a salon is its primary owner account."""
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT rowid AS id FROM accounts WHERE auth_id = ? ORDER BY rowid ASC LIMIT 1",
            (salon_id,),
        ).fetchone()
        conn.close()
        return row["id"] if row else None

    def add_account(self, salon_id, username, password, auth_level, seat_limit=None):
        username = (username or "").strip().lower()
        if auth_level not in AUTH_LEVELS:
            return {"success": False, "message": "Invalid access level selected."}
        if not username or not password:
            return {"success": False, "message": "Email and password are both required."}
        if seat_limit is not None and self.count_accounts(salon_id) >= seat_limit:
            return {
                "success": False,
                "message": f"Team seat limit reached â€” a salon can have up to {seat_limit} accounts.",
            }
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO accounts(auth_id, username, password, auth_level) VALUES (?, ?, ?, ?)",
                (salon_id, username, password, auth_level),
            )
            conn.commit()
            conn.close()
        except sql.IntegrityError:
            return {"success": False, "message": "An account with this email already exists."}
        return {"success": True, "message": f"Team account created for {username}."}

    def update_account(self, salon_id, row_id, username, auth_level, password=None):
        username = (username or "").strip().lower()
        if auth_level not in AUTH_LEVELS:
            return {"success": False, "message": "Invalid access level selected."}
        primary_id = self.get_primary_account_id(salon_id)
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT rowid AS id FROM accounts WHERE rowid = ? AND auth_id = ?",
            (row_id, salon_id),
        ).fetchone()
        if not row:
            conn.close()
            return {"success": False, "message": "Account not found."}
        if row["id"] == primary_id and auth_level != "admin":
            conn.close()
            return {"success": False, "message": "The primary owner account must keep full access."}
        try:
            if password:
                cur.execute(
                    "UPDATE accounts SET username = ?, auth_level = ?, password = ? WHERE rowid = ? AND auth_id = ?",
                    (username, auth_level, password, row_id, salon_id),
                )
            else:
                cur.execute(
                    "UPDATE accounts SET username = ?, auth_level = ? WHERE rowid = ? AND auth_id = ?",
                    (username, auth_level, row_id, salon_id),
                )
            conn.commit()
        except sql.IntegrityError:
            conn.close()
            return {"success": False, "message": "An account with this email already exists."}
        conn.close()
        return {"success": True, "message": "Team account updated."}

    def delete_account(self, salon_id, row_id):
        primary_id = self.get_primary_account_id(salon_id)
        if row_id == primary_id:
            return {"success": False, "message": "The primary owner account cannot be deleted."}
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM accounts WHERE rowid = ? AND auth_id = ?", (row_id, salon_id))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        if not deleted:
            return {"success": False, "message": "Account not found."}
        return {"success": True, "message": "Team account removed."}

    # ---------- Settings: subscription & account lifecycle ----------
    def get_subscriptions(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM subscriptions WHERE salon_id = ? ORDER BY created_at DESC",
            (salon_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_salon_plan(self, salon_id, tier, cycle, expires_on):
        """Switch a salon to a new subscription tier (used by the upgrade flow)."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE salons SET plan = ?, billing_cycle = ?, expires_on = ? WHERE id = ?",
            (tier, cycle, int(expires_on), salon_id),
        )
        changed = cur.rowcount > 0
        conn.commit()
        conn.close()
        return changed

    def record_subscription(self, sub_id, salon_id, amount, plan, cycle, receipt, email, phone, created_at=None):
        """Persist a completed subscription/payment associated with a salon."""
        if created_at is None:
            created_at = int(datetime.now().timestamp())
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO subscriptions(id, salon_id, amount, created_at, plan, billing_cycle, receipt, email, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (sub_id, salon_id, int(amount), int(created_at), plan, cycle, receipt, (email or "").strip(), str(phone or "").strip()),
        )
        conn.commit()
        conn.close()
        return True

    def get_subscription(self, sub_id):
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def create_pendingorder(self, order_id, amount, created_at, plan, receipt, email, phone, salon_id=None):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO pendingorders(id, amount, created_at, plan, receipt, email, phone, salon_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (order_id, int(amount), int(created_at), plan, receipt, (email or "").strip(), str(phone or "").strip(), salon_id),
        )
        conn.commit()
        conn.close()
        return True

    def get_pendingorder(self, order_id):
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM pendingorders WHERE id = ?", (order_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def request_account_deletion(self, salon_id, email, reason=""):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO deletion_requests(salon_id, email, reason, requested_at, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (salon_id, (email or "").strip(), (reason or "").strip(), int(datetime.now().timestamp())),
        )
        conn.commit()
        conn.close()
        return True

    def get_pending_deletion_request(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT * FROM deletion_requests
            WHERE salon_id = ? AND status = 'pending'
            ORDER BY requested_at DESC LIMIT 1
            """,
            (salon_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None


class CategoryRepository:
    """Per-salon service categories. Uniquely named per salon (case-insensitive)."""

    DEFAULTS = ["Haircuts", "Spa & Facial", "Color & Hair", "Styling", "Grooming", "Treatments"]

    def __init__(self):
        conn = get_db()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (account_id) REFERENCES salons(id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_unique
                ON categories(account_id, name COLLATE NOCASE);
            """
        )
        conn.commit()
        conn.close()

    def get_categories(self, account_id):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT id, name, created_at FROM categories WHERE account_id = ? ORDER BY name COLLATE NOCASE",
            (account_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_category(self, account_id, name):
        """Insert a category; returns (id, created) â€” created is False if it already existed."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO categories(account_id, name, created_at) VALUES (?, ?, ?)",
            (account_id, name, int(datetime.now().timestamp())),
        )
        created = cur.rowcount > 0
        if created:
            new_id = cur.lastrowid
        else:
            row = cur.execute(
                "SELECT id FROM categories WHERE account_id = ? AND name = ? COLLATE NOCASE",
                (account_id, name),
            ).fetchone()
            new_id = row["id"]
        conn.commit()
        conn.close()
        return new_id, created

    def delete_category(self, account_id, category_id):
        """Delete a category unless services still reference it. Returns (ok, message)."""
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT name FROM categories WHERE id = ? AND account_id = ?",
            (category_id, account_id),
        ).fetchone()
        if not row:
            conn.close()
            return False, "Category not found."
        in_use = cur.execute(
            "SELECT COUNT(*) AS c FROM services WHERE account_id = ? AND category = ? COLLATE NOCASE",
            (account_id, row["name"]),
        ).fetchone()["c"]
        if in_use:
            conn.close()
            return False, f"Cannot delete '{row['name']}' â€” {in_use} service(s) still use it."
        cur.execute("DELETE FROM categories WHERE id = ? AND account_id = ?", (category_id, account_id))
        conn.commit()
        conn.close()
        return True, f"Category '{row['name']}' deleted."

    def register_unique(self, account_id, names):
        """Register any category names not already stored. Returns how many were newly created."""
        created = 0
        conn = get_db()
        cur = conn.cursor()
        for name in names:
            clean = str(name or "").strip()
            if not clean:
                continue
            cur.execute(
                "INSERT OR IGNORE INTO categories(account_id, name, created_at) VALUES (?, ?, ?)",
                (account_id, clean, int(datetime.now().timestamp())),
            )
            created += cur.rowcount
        conn.commit()
        conn.close()
        return created

    def seed_defaults_if_empty(self, account_id):
        conn = get_db()
        cur = conn.cursor()
        count = cur.execute(
            "SELECT COUNT(*) as c FROM categories WHERE account_id = ?", (account_id,)
        ).fetchone()["c"]
        if count == 0:
            now = int(datetime.now().timestamp())
            cur.executemany(
                "INSERT OR IGNORE INTO categories(account_id, name, created_at) VALUES (?, ?, ?)",
                [(account_id, name, now) for name in self.DEFAULTS],
            )
            conn.commit()
        conn.close()


class ServiceRepository:
    def __init__(self):
        conn = get_db()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS services(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price INTEGER NOT NULL,
                duration INTEGER DEFAULT 30,
                staff TEXT DEFAULT 'Any Stylist',
                description TEXT DEFAULT '',
                active INTEGER DEFAULT 1,
                FOREIGN KEY (account_id) REFERENCES salons(id)
            );
            """
        )
        conn.commit()
        conn.close()

    def get_services(self, account_id):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM services WHERE account_id = ? ORDER BY id DESC",
            (account_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_booking_services(self, account_id):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM services WHERE account_id = ? AND active = 1 ORDER BY id DESC",
            (account_id, ),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_service(self, account_id, name, category, price, duration=30, staff="Any Stylist", description="", active=1):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO services(account_id, name, category, price, duration, staff, description, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (account_id, name, category, int(price), int(duration), staff, description, int(active)),
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return new_id

    def update_service(self, service_id, account_id, name, category, price, duration, staff, description, active):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE services 
            SET name = ?, category = ?, price = ?, duration = ?, staff = ?, description = ?, active = ?
            WHERE id = ? AND account_id = ?
            """,
            (name, category, int(price), int(duration), staff, description, int(active), service_id, account_id),
        )
        conn.commit()
        conn.close()

    def delete_service(self, service_id, account_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM services WHERE id = ? AND account_id = ?", (service_id, account_id))
        conn.commit()
        conn.close()

    def bulk_add_services(self, account_id, rows):
        """Mass-insert services from uploaded rows. Skips rows without a name.

        Every unique category found in the upload is registered in the
        categories table (so new categories can arrive via CSV); the result
        reports how many were newly created.
        """
        added, skipped, errors = 0, 0, []
        seen_categories = set()
        conn = get_db()
        cur = conn.cursor()
        for idx, row in enumerate(rows, start=2):  # row 1 is the CSV header
            name = str(row.get("name", "") or "").strip()
            if not name:
                skipped += 1
                continue
            category = str(row.get("category", "") or "General").strip() or "General"
            try:
                price = int(float(str(row.get("price", "0") or 0)))
                duration = int(float(str(row.get("duration", "30") or 30)))
            except ValueError:
                errors.append(f"Row {idx}: price/duration must be numbers")
                skipped += 1
                continue
            staff = str(row.get("staff", "") or "Any Stylist").strip() or "Any Stylist"
            description = str(row.get("description", "") or "").strip()
            seen_categories.add(category)
            active_raw = str(row.get("active", "1") or "1").strip().lower()
            active = 0 if active_raw in ("0", "false", "no", "inactive") else 1
            try:
                cur.execute(
                    """
                    INSERT INTO services(account_id, name, category, price, duration, staff, description, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (account_id, name, category, price, duration, staff, description, active),
                )
                added += 1
            except sql.Error as e:
                errors.append(f"Row {idx}: {e}")
                skipped += 1
        conn.commit()
        conn.close()
        categories_registered = CategoryRepository().register_unique(account_id, seen_categories)
        return {
            "added": added,
            "skipped": skipped,
            "errors": errors,
            "categories_registered": categories_registered,
        }

    def seed_defaults_if_empty(self, account_id):
        conn = get_db()
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) as c FROM services WHERE account_id = ?", (account_id,)).fetchone()["c"]
        if count == 0:
            defaults = [
                ("Executive Men's Haircut", "Haircuts", 400, 30, "Marcus Vance (Stylist)", "Includes shampoo, hair wash, precision taper, and styling.", 1),
                ("Women's Signature Layer Cut", "Haircuts", 750, 45, "Alex Rivera (Senior)", "Custom consultation, wash, blowdry, and texture finish.", 1),
                ("Hydra-Dew Glow Facial", "Spa & Facial", 1500, 60, "Sarah Jenkins (Skin Specialist)", "Deep ultrasonic pore cleansing and serum infusion.", 1),
                ("Luxury Organic Hair Spa", "Treatments", 1200, 50, "Alex Rivera (Senior)", "Argan oil mask, steam therapy, and scalp massage.", 1),
                ("Full Balayage & Toning", "Color & Hair", 3200, 120, "Priya Nair (Colorist)", "Hand-painted highlights with gloss finish & bond repair.", 1),
                ("Root Touch-up (Ammonia-Free)", "Color & Hair", 1100, 45, "Priya Nair (Colorist)", "100% grey coverage with nourishing oils.", 1),
                ("Beard Styling & Razor Shave", "Grooming", 250, 20, "Marcus Vance (Stylist)", "Hot towel wrap, beard oil, and precision razor outline.", 1),
                ("Keratin Smooth Treatment", "Treatments", 4500, 150, "Priya Nair (Colorist)", "Frizz-free silky smooth keratin infusion lasts 4 months.", 1),
            ]
            cur.executemany(
                """
                INSERT INTO services(account_id, name, category, price, duration, staff, description, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [(account_id, *d) for d in defaults],
            )
            conn.commit()
        conn.close()


class StaffRepository:
    def __init__(self):
        conn = get_db()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS staff(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                phone TEXT DEFAULT '',
                gender TEXT DEFAULT '',
                email TEXT DEFAULT '',
                total_revenue INTEGER DEFAULT 0,
                services_done INTEGER DEFAULT 0,
                created_on INTEGER NOT NULL,
                FOREIGN KEY (account_id) REFERENCES salons(id)
            );
            """
        )
        conn.commit()
        # Idempotent migrations for salons that created the staff table before
        # the editable profile fields (phone / gender / email) existed.
        for column in ("phone TEXT DEFAULT ''", "gender TEXT DEFAULT ''", "email TEXT DEFAULT ''"):
            try:
                cur.execute(f"ALTER TABLE staff ADD COLUMN {column}")
            except Exception:
                pass
        conn.commit()
        conn.close()

    def get_staff(self, account_id):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM staff WHERE account_id = ? ORDER BY total_revenue DESC, id ASC",
            (account_id,),
        ).fetchall()
        conn.close()
        members = []
        for r in rows:
            d = dict(r)
            d.setdefault("phone", "")
            d.setdefault("gender", "")
            d.setdefault("email", "")
            members.append(d)
        return members

    def add_staff(self, account_id, name, role, phone="", gender="", email=""):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO staff(account_id, name, role, phone, gender, email, total_revenue, services_done, created_on)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?)
            """,
            (account_id, name, role, phone, gender, email, int(datetime.now().timestamp())),
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return new_id

    def update_staff(self, staff_id, account_id, name, role, phone="", gender="", email=""):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE staff
            SET name = ?, role = ?, phone = ?, gender = ?, email = ?
            WHERE id = ? AND account_id = ?
            """,
            (name, role, phone, gender, email, staff_id, account_id),
        )
        conn.commit()
        conn.close()

    def delete_staff(self, staff_id, account_id):
        """Delete a staff member. Returns (ok, message). Prevents removing the last member."""
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT name FROM staff WHERE id = ? AND account_id = ?",
            (staff_id, account_id),
        ).fetchone()
        if not row:
            conn.close()
            return False, "Staff member not found."
        remaining = cur.execute(
            "SELECT COUNT(*) AS c FROM staff WHERE account_id = ?",
            (account_id,),
        ).fetchone()["c"]
        if remaining <= 1:
            conn.close()
            return False, "A salon must keep at least one staff member on record."
        cur.execute("DELETE FROM staff WHERE id = ? AND account_id = ?", (staff_id, account_id))
        conn.commit()
        conn.close()
        return True, f"{row['name']} removed from the team."

    @staticmethod
    def base_name(staff_name):
        """Reduce a display name like 'Alex Rivera (Senior Stylist)' to 'Alex Rivera'."""
        s = str(staff_name or "").strip()
        return s.split(" (", 1)[0].strip() if " (" in s else s

    def record_sale(self, staff_name, account_id, amount):
        base = self.base_name(staff_name)
        if not base:
            return
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE staff 
            SET total_revenue = total_revenue + ?, services_done = services_done + 1
            WHERE account_id = ? AND (name = ? OR name LIKE ?)
            """,
            (int(amount), account_id, base, f"{base}%"),
        )
        conn.commit()
        conn.close()

    def seed_defaults_if_empty(self, account_id):
        conn = get_db()
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) as c FROM staff WHERE account_id = ?", (account_id,)).fetchone()["c"]
        if count == 0:
            now = int(datetime.now().timestamp())
            defaults = [
                ("Alex Rivera", "Senior Stylist", "9811023456", "Male", "alex@aurasalon.in", 0, 0, now),
                ("Priya Nair", "Master Colorist", "9822034567", "Female", "priya@aurasalon.in", 0, 0, now),
                ("Marcus Vance", "Grooming Specialist", "9833045678", "Male", "marcus@aurasalon.in", 0, 0, now),
            ]
            cur.executemany(
                """
                INSERT INTO staff(account_id, name, role, phone, gender, email, total_revenue, services_done, created_on)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [(account_id, *d) for d in defaults],
            )
            conn.commit()
        conn.close()


class AppointmentRepository:
    def __init__(self):
        conn = get_db()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS appointments(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                client TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT DEFAULT '',
                service TEXT NOT NULL,
                time TEXT NOT NULL,
                date TEXT NOT NULL,
                staff TEXT NOT NULL,
                price INTEGER NOT NULL,
                duration INTEGER DEFAULT 30,
                status TEXT DEFAULT 'Confirmed',
                notes TEXT DEFAULT '',
                FOREIGN KEY (account_id) REFERENCES salons(id)
            );
            """
        )
        conn.commit()
        conn.close()

    def get_appointments(self, account_id, date_str=None):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        if date_str:
            rows = cur.execute(
                "SELECT * FROM appointments WHERE account_id = ? AND date = ? ORDER BY time ASC",
                (account_id, date_str),
            ).fetchall()
        else:
            rows = cur.execute(
                "SELECT * FROM appointments WHERE account_id = ? ORDER BY id DESC",
                (account_id,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def create_appointment(self, account_id, client, phone, email, service, time_slot, date_str, staff, price, duration=30, status="Confirmed", notes=""):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO appointments(account_id, client, phone, email, service, time, date, staff, price, duration, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (account_id, client, phone, email, service, time_slot, date_str, staff, int(price), int(duration), status, notes),
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return new_id

    def update_status(self, appointment_id, account_id, status):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE appointments SET status = ? WHERE id = ? AND account_id = ?",
            (status, appointment_id, account_id),
        )
        conn.commit()
        conn.close()

    def seed_defaults_if_empty(self, account_id):
        # Cleared placeholder bookings per user specification
        pass


class BillRepository:
    def __init__(self):
        conn = get_db()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS bills(
                id TEXT PRIMARY KEY,
                account_id INTEGER NOT NULL,
                client_name TEXT,
                client_phone TEXT,
                subtotal INTEGER NOT NULL,
                discount INTEGER DEFAULT 0,
                tax INTEGER DEFAULT 0,
                grand_total INTEGER NOT NULL,
                payment_mode TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                items_json TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES salons(id)
            );
            """
        )
        conn.commit()
        conn.close()

    def create_bill(self, bill_id, account_id, client_name, client_phone, subtotal, discount, tax, grand_total, payment_mode, items_json):
        conn = get_db()
        cur = conn.cursor()
        created_at = int(datetime.now().timestamp())
        cur.execute(
            """
            INSERT INTO bills(id, account_id, client_name, client_phone, subtotal, discount, tax, grand_total, payment_mode, created_at, items_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (bill_id, account_id, client_name, client_phone, int(subtotal), int(discount), int(tax), int(grand_total), payment_mode, created_at, items_json),
        )
        conn.commit()
        conn.close()
        return bill_id

    def find_recent_duplicate(self, account_id, client_phone, grand_total, window_seconds=4):
        conn = get_db()
        cur = conn.cursor()
        threshold = int(datetime.now().timestamp()) - window_seconds
        row = cur.execute(
            "SELECT id FROM bills WHERE account_id = ? AND client_phone = ? AND grand_total = ? AND created_at >= ? LIMIT 1",
            (account_id, str(client_phone or "").strip(), int(grand_total), threshold),
        ).fetchone()
        conn.close()
        return row["id"] if row else None

    def get_recent_bills(self, account_id, limit=10, offset=0):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM bills WHERE account_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (account_id, int(limit), int(offset)),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_metrics(self, account_id, start_ts=None, end_ts=None):
        """Aggregate bill KPIs for a time window (defaults to all-time).

        Returns real values (never fabricated fallbacks).
        """
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        if start_ts is not None and end_ts is not None:
            sales_row = cur.execute(
                """
                SELECT SUM(grand_total) as total_sales, COUNT(*) as total_bills,
                       AVG(grand_total) as avg_ticket, SUM(discount) as total_discount,
                       SUM(tax) as total_tax
                FROM bills
                WHERE account_id = ? AND created_at >= ? AND created_at <= ?
                """,
                (account_id, start_ts, end_ts),
            ).fetchone()
            phone_row = cur.execute(
                """
                SELECT COUNT(DISTINCT client_phone) AS c FROM bills
                WHERE account_id = ? AND created_at >= ? AND created_at <= ?
                  AND trim(client_phone) != ''
                """,
                (account_id, start_ts, end_ts),
            ).fetchone()
        else:
            sales_row = cur.execute(
                """
                SELECT SUM(grand_total) as total_sales, COUNT(*) as total_bills,
                       AVG(grand_total) as avg_ticket, SUM(discount) as total_discount,
                       SUM(tax) as total_tax
                FROM bills WHERE account_id = ?
                """,
                (account_id,),
            ).fetchone()
            phone_row = cur.execute(
                "SELECT COUNT(DISTINCT client_phone) AS c FROM bills WHERE account_id = ? AND trim(client_phone) != ''",
                (account_id,),
            ).fetchone()
        conn.close()
        total_sales = int(sales_row["total_sales"] or 0)
        total_bills = int(sales_row["total_bills"] or 0)
        return {
            "total_sales": total_sales,
            "total_bills": total_bills,
            "avg_ticket": round(total_sales / total_bills) if total_bills else 0,
            "total_discount": int(sales_row["total_discount"] or 0),
            "total_tax": int(sales_row["total_tax"] or 0),
            "unique_customers": int(phone_row["c"] or 0),
        }

    def get_bills_in_range(self, account_id, start_ts, end_ts):
        """Return full bills (items parsed) between two timestamps, oldest first."""
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM bills WHERE account_id = ? AND created_at >= ? AND created_at <= ? ORDER BY created_at ASC",
            (account_id, start_ts, end_ts),
        ).fetchall()
        conn.close()
        bills = []
        for r in rows:
            d = dict(r)
            try:
                items = json.loads(d.pop("items_json") or "[]")
            except Exception:
                items = []
            d["items"] = items if isinstance(items, list) else []
            bills.append(d)
        return bills

    def seed_defaults_if_empty(self, account_id):
        # Cleared placeholder bills per user specification
        pass


class CustomerRepository:
    def __init__(self):
        conn = get_db()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at INTEGER NOT NULL,
                FOREIGN KEY (account_id) REFERENCES salons(id)
            );
            """
        )
        conn.commit()
        conn.close()

    def get_customers(self, account_id):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM customers WHERE account_id = ? ORDER BY id DESC",
            (account_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def count_customers(self, account_id):
        conn = get_db()
        cur = conn.cursor()
        count = cur.execute(
            "SELECT COUNT(*) AS c FROM customers WHERE account_id = ?", (account_id,)
        ).fetchone()["c"]
        conn.close()
        return count

    def search_customers(self, account_id, query, limit=8):
        """Find customers whose name or phone contains the query (case-insensitive)."""
        q = str(query or "").strip()
        if not q:
            return []
        like = f"%{q}%"
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT * FROM customers
            WHERE account_id = ? AND (name LIKE ? OR phone LIKE ?)
            ORDER BY name COLLATE NOCASE
            LIMIT ?
            """,
            (account_id, like, like, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_by_phone(self, account_id, phone):
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT * FROM customers WHERE account_id = ? AND phone = ?",
            (account_id, str(phone or "").strip()),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def add_customer(self, account_id, name, phone="", email="", notes="", created_at=None):
        if created_at is None:
            created_at = int(datetime.now().timestamp())
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO customers(account_id, name, phone, email, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (account_id, name, phone, email, notes, created_at),
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return new_id

    def bulk_add_customers(self, account_id, rows):
        """Mass-insert customers from uploaded rows. Duplicates (same phone) are skipped."""
        added, skipped, errors = 0, 0, []
        conn = get_db()
        cur = conn.cursor()
        existing = {
            str(r["phone"]).strip()
            for r in cur.execute(
                "SELECT phone FROM customers WHERE account_id = ?", (account_id,)
            ).fetchall()
            if str(r["phone"]).strip()
        }
        for idx, row in enumerate(rows, start=2):  # row 1 is the CSV header
            name = str(row.get("name", "") or "").strip()
            phone = str(row.get("phone", "") or "").strip()
            email = str(row.get("email", "") or "").strip()
            notes = str(row.get("notes", "") or "").strip()
            if not name:
                skipped += 1
                continue
            if phone and phone in existing:
                skipped += 1
                continue
            try:
                cur.execute(
                    """
                    INSERT INTO customers(account_id, name, phone, email, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (account_id, name, phone, email, notes, int(datetime.now().timestamp())),
                )
                if phone:
                    existing.add(phone)
                added += 1
            except sql.Error as e:
                errors.append(f"Row {idx}: {e}")
                skipped += 1
        conn.commit()
        conn.close()
        return {"added": added, "skipped": skipped, "errors": errors}

    def seed_defaults_if_empty(self, account_id):
        conn = get_db()
        cur = conn.cursor()
        count = cur.execute(
            "SELECT COUNT(*) as c FROM customers WHERE account_id = ?", (account_id,)
        ).fetchone()["c"]
        if count == 0:
            now = int(datetime.now().timestamp())
            defaults = [
                ("Ananya Sharma", "9876543210", "ananya@gmail.com", "Prefers weekend slots"),
                ("Vikram Malhotra", "9812345678", "vikram@gmail.com", "Regular client"),
            ]
            cur.executemany(
                """
                INSERT INTO customers(account_id, name, phone, email, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [(account_id, *d, now) for d in defaults],
            )
            conn.commit()
        conn.close()


class ReportRepository:
    """Read-only analytics across bills, items and appointments for the reports page."""

    # Business hours shown on the hourly chart (inclusive).
    HOUR_START = 9
    HOUR_END = 21

    @staticmethod
    def _base(staff_name):
        return StaffRepository.base_name(staff_name)

    @staticmethod
    def _bucket_bounds(start_ts, end_ts):
        """Pick the right bucketing for a date range: daily / weekly / monthly."""
        span_days = (end_ts - start_ts) / (24 * 60 * 60)
        if span_days <= 32:
            kind = "day"
        elif span_days <= 190:
            kind = "week"
        else:
            kind = "month"
        return kind

    def bills_in_range(self, account_id, start_ts, end_ts):
        return BillRepository().get_bills_in_range(account_id, start_ts, end_ts)

    def summary(self, account_id, start_ts, end_ts):
        return BillRepository().get_metrics(account_id, start_ts, end_ts)
    def revenue_by_day(self, account_id, start_ts, end_ts):
        """Total revenue & bill count bucketed by day / week / month depending on span."""
        bills = self.bills_in_range(account_id, start_ts, end_ts)
        kind = self._bucket_bounds(start_ts, end_ts)
        buckets = {}

        def key_for(ts):
            dt = datetime.fromtimestamp(ts)
            if kind == "day":
                return dt.strftime("%Y-%m-%d"), dt.strftime("%d %b")
            if kind == "week":
                iso = dt.isocalendar()
                start = dt - timedelta(days=dt.weekday())
                return f"{iso[0]}-W{iso[1]:02d}", start.strftime("%d %b")
            return dt.strftime("%Y-%m"), dt.strftime("%b %Y")

        for b in bills:
            key, label = key_for(b["created_at"])
            if key not in buckets:
                buckets[key] = {"label": label, "revenue": 0, "bills": 0, "sort": b["created_at"]}
            buckets[key]["revenue"] += b["grand_total"]
            buckets[key]["bills"] += 1
        series = list(buckets.values())
        series.sort(key=lambda x: x["sort"])
        for s in series:
            s.pop("sort", None)
        return {"kind": kind, "points": series}

    def revenue_by_hour(self, account_id, start_ts, end_ts):
        """Revenue across the salon business day (9:00 – 21:00)."""
        bills = self.bills_in_range(account_id, start_ts, end_ts)
        buckets = {h: {"hour": h, "label": f"{h:02d}:00", "revenue": 0, "bills": 0}
                   for h in range(self.HOUR_START, self.HOUR_END + 1)}
        for b in bills:
            h = datetime.fromtimestamp(b["created_at"]).hour
            if h in buckets:
                buckets[h]["revenue"] += b["grand_total"]
                buckets[h]["bills"] += 1
        return list(buckets.values())

    def _item_rows(self, account_id, start_ts, end_ts):
        """Flatten bills + items with service metadata into per-line rows."""
        bills = self.bills_in_range(account_id, start_ts, end_ts)
        svc_rows = ServiceRepository().get_services(account_id)
        svc_by_name = {str(s["name"]).strip().lower(): str(s["category"] or "Other") for s in svc_rows}
        rows = []
        for b in bills:
            for it in b.get("items", []):
                if not isinstance(it, dict):
                    continue
                name = str(it.get("name", "") or "").strip() or "Unnamed item"
                price = int(float(it.get("price", 0) or 0))
                qty = int(float(it.get("qty", 1) or 1))
                staff = str(it.get("staff", "") or "").strip()
                category = svc_by_name.get(name.lower(), "Other")
                rows.append({
                    "bill_id": b["id"], "created_at": b["created_at"],
                    "name": name, "price": price, "qty": qty,
                    "revenue": price * qty, "staff": staff, "category": category,
                    "mode": b["payment_mode"],
                })
        return rows

    def top_services(self, account_id, start_ts, end_ts, limit=6):
        rows = self._item_rows(account_id, start_ts, end_ts)
        agg = {}
        for r in rows:
            key = r["name"]
            if key not in agg:
                agg[key] = {"name": key, "qty": 0, "revenue": 0}
            agg[key]["qty"] += r["qty"]
            agg[key]["revenue"] += r["revenue"]
        services = sorted(agg.values(), key=lambda x: x["revenue"], reverse=True)
        return services[:limit]

    def staff_leaderboard(self, account_id, start_ts, end_ts):
        rows = self._item_rows(account_id, start_ts, end_ts)
        agg = {}
        for r in rows:
            base = self._base(r["staff"])
            if not base:
                continue
            if base not in agg:
                agg[base] = {"name": base, "revenue": 0, "services": 0}
            agg[base]["revenue"] += r["revenue"]
            agg[base]["services"] += r["qty"]
        staff_list = StaffRepository().get_staff(account_id)
        known = {StaffRepository.base_name(s["name"]): s["role"] for s in staff_list}
        # Include roster members who made no sales in the window (they rank last).
        for s in staff_list:
            base = StaffRepository.base_name(s["name"])
            if base not in agg:
                agg[base] = {"name": base, "revenue": 0, "services": 0}
        board = list(agg.values())
        for row in board:
            row["role"] = known.get(row["name"], "Stylist")
            row["commission"] = int(round(row["revenue"] * 0.15))
        board.sort(key=lambda x: x["revenue"], reverse=True)
        return board

    def payment_split(self, account_id, start_ts, end_ts):
        bills = self.bills_in_range(account_id, start_ts, end_ts)
        agg = {}
        for b in bills:
            mode = (b["payment_mode"] or "Other").strip() or "Other"
            if mode not in agg:
                agg[mode] = {"mode": mode, "revenue": 0, "count": 0}
            agg[mode]["revenue"] += b["grand_total"]
            agg[mode]["count"] += 1
        total = sum(v["revenue"] for v in agg.values()) or 1
        for v in agg.values():
            v["pct"] = round(v["revenue"] * 100 / total, 1)
        return list(agg.values())

    def category_split(self, account_id, start_ts, end_ts):
        rows = self._item_rows(account_id, start_ts, end_ts)
        agg = {}
        for r in rows:
            key = r["category"]
            if key not in agg:
                agg[key] = {"category": key, "revenue": 0, "qty": 0}
            agg[key]["revenue"] += r["revenue"]
            agg[key]["qty"] += r["qty"]
        total = sum(v["revenue"] for v in agg.values()) or 1
        values = sorted(agg.values(), key=lambda x: x["revenue"], reverse=True)
        for v in values:
            v["pct"] = round(v["revenue"] * 100 / total, 1)
        return values

    def appointments_in_range(self, account_id, start_ts, end_ts):
        conn = get_db()
        cur = conn.cursor()
        start_d = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d")
        end_d = datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d")
        rows = cur.execute(
            "SELECT * FROM appointments WHERE account_id = ? AND date >= ? AND date <= ?",
            (account_id, start_d, end_d),
        ).fetchall()
        conn.close()
        total = len(rows)
        by_status = {}
        for r in rows:
            st = r["status"] or "Confirmed"
            by_status[st] = by_status.get(st, 0) + 1
        return {"total": total, "by_status": by_status}


class AdminRepository:
    SETTING_ACCEPTING_PUBLIC = "accepting_public"

    def __init__(self):
        conn = get_db()
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_settings(
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at INTEGER NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()

    def get_setting(self, key, default=None):
        try:
            conn = get_db()
            cur = conn.cursor()
            row = cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
            conn.close()
            return row["value"] if row else default
        except Exception:
            return default

    def set_setting(self, key, value):
        try:
            conn = get_db()
            cur = conn.cursor()
            now = int(datetime.now().timestamp())
            cur.execute(
                """
                INSERT INTO app_settings(key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
                """,
                (key, str(value), now),
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("REPLACE INTO app_settings(key, value, updated_at) VALUES (?, ?, ?)", (key, str(value), int(datetime.now().timestamp())))
                conn.commit()
                conn.close()
                return True
            except Exception:
                return False

    def list_salons(self):
        conn = get_db()
        cur = conn.cursor()
        salons = [dict(r) for r in cur.execute("SELECT * FROM salons ORDER BY created_on DESC").fetchall()]
        out = []
        for s in salons:
            sid = s.get("id")
            s.setdefault("plan", "free")
            accs = [dict(r) for r in cur.execute("SELECT username FROM accounts WHERE auth_id = ?", (sid,)).fetchall()]
            s["accounts_count"] = len(accs)
            s["account_names"] = [a["username"] for a in accs]
            s["staff_count"] = cur.execute("SELECT COUNT(*) as c FROM staff WHERE account_id = ?", (sid,)).fetchone()["c"]
            s["services_count"] = cur.execute("SELECT COUNT(*) as c FROM services WHERE account_id = ?", (sid,)).fetchone()["c"]
            s["customers_count"] = cur.execute("SELECT COUNT(*) as c FROM customers WHERE account_id = ?", (sid,)).fetchone()["c"]
            s["appointments_count"] = cur.execute("SELECT COUNT(*) as c FROM appointments WHERE account_id = ?", (sid,)).fetchone()["c"]
            bill_row = cur.execute("SELECT COUNT(*) as c, COALESCE(SUM(grand_total), 0) as rev FROM bills WHERE account_id = ?", (sid,)).fetchone()
            s["bills_count"] = bill_row["c"]
            s["revenue_total"] = int(bill_row["rev"] or 0)
            out.append(s)
        conn.close()
        return out

    def salon_details(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        salon = cur.execute("SELECT * FROM salons WHERE id = ?", (salon_id,)).fetchone()
        if not salon:
            conn.close()
            return None
        salon = dict(salon)
        accounts = [dict(r) for r in cur.execute("SELECT id, username, auth_level FROM accounts WHERE auth_id = ? ORDER BY id", (salon_id,)).fetchall()]
        staff = [dict(r) for r in cur.execute("SELECT id, name, role, phone, email, total_revenue, services_done FROM staff WHERE account_id = ? ORDER BY id", (salon_id,)).fetchall()]
        bills = [dict(r) for r in cur.execute("SELECT id, client_name, grand_total, payment_mode, created_at FROM bills WHERE account_id = ? ORDER BY created_at DESC LIMIT 10", (salon_id,)).fetchall()]
        bill_stats = cur.execute("SELECT COUNT(*) as c, COALESCE(SUM(grand_total), 0) as rev FROM bills WHERE account_id = ?", (salon_id,)).fetchone()
        subscriptions = [dict(r) for r in cur.execute("SELECT * FROM subscriptions WHERE salon_id = ? ORDER BY created_at DESC", (salon_id,)).fetchall()]
        pendingorders = [dict(r) for r in cur.execute("SELECT * FROM pendingorders WHERE salon_id = ? ORDER BY created_at DESC LIMIT 5", (salon_id,)).fetchall()]
        deletion_requests = [dict(r) for r in cur.execute("SELECT * FROM deletion_requests WHERE salon_id = ? ORDER BY requested_at DESC", (salon_id,)).fetchall()]
        services_count = cur.execute("SELECT COUNT(*) as c FROM services WHERE account_id = ?", (salon_id,)).fetchone()["c"]
        customers_count = cur.execute("SELECT COUNT(*) as c FROM customers WHERE account_id = ?", (salon_id,)).fetchone()["c"]
        appointments_count = cur.execute("SELECT COUNT(*) as c FROM appointments WHERE account_id = ?", (salon_id,)).fetchone()["c"]
        conn.close()

        return {
            "salon": salon,
            "accounts": accounts,
            "staff": staff,
            "bills": bills,
            "bills_count": bill_stats["c"],
            "revenue_total": int(bill_stats["rev"] or 0),
            "services_count": services_count,
            "customers_count": customers_count,
            "appointments_count": appointments_count,
            "subscriptions": subscriptions,
            "pendingorders": pendingorders,
            "deletion_requests": deletion_requests,
        }


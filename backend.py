from dataclasses import dataclass, asdict
import sqlite3 as sql
from datetime import datetime, date, timedelta
import json
import os
import re
import time

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

# Concurrent active POS billing terminal limit per tier (None = unlimited)
TIER_TERMINAL_LIMITS = {"free": 1, "pro": 3, "studio": None}


def get_terminal_limit(tier):
    """Return max concurrent active POS billing terminals allowed for a tier (None = unlimited)."""
    t = (tier or "free").strip().lower()
    if "studio" in t:
        return None
    if "pro" in t:
        return 3
    return 1


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

# Supported access levels for salon team accounts (kept for backwards compatibility)
AUTH_LEVELS = ("admin", "manager", "cashier")

# Atomic permission definitions for AuraPOS RBAC
SYSTEM_PERMISSIONS = [
    # Point of Sale & Billing
    {"key": "billing:read", "module": "Point of Sale", "name": "View Billing Terminal", "description": "Access the POS billing page and past terminal drafts"},
    {"key": "billing:write", "module": "Point of Sale", "name": "Collect & Create Bills", "description": "Process payments, issue receipts and generate invoices"},
    {"key": "billing:discount", "module": "Point of Sale", "name": "Apply Custom Discounts", "description": "Apply invoice-level discounts during checkout"},
    
    # Appointments & Scheduling
    {"key": "appointments:read", "module": "Appointments", "name": "View Appointments", "description": "View booking calendar and appointment status"},
    {"key": "appointments:write", "module": "Appointments", "name": "Manage Appointments", "description": "Book, reschedule, or cancel client appointments"},

    # Customers & Patrons
    {"key": "customers:read", "module": "Customers", "name": "View Customer Directory", "description": "Access customer directory and search patrons"},
    {"key": "customers:write", "module": "Customers", "name": "Create & Edit Customers", "description": "Add new clients and update client profiles"},
    {"key": "customers:delete", "module": "Customers", "name": "Delete Customers", "description": "Remove customers from salon directory"},
    {"key": "customers:analytics", "module": "Customers", "name": "View Customer Analytics", "description": "View patron visit frequency, lifetime spend and churn"},

    # Service Catalog & Categories
    {"key": "services:read", "module": "Services", "name": "View Service Catalog", "description": "Browse salon service offerings and categories"},
    {"key": "services:write", "module": "Services", "name": "Modify Services & Catalog", "description": "Add, edit, or adjust pricing of services & categories"},
    {"key": "services:delete", "module": "Services", "name": "Delete Services", "description": "Remove services or service categories"},

    # Staff Management
    {"key": "staff:read", "module": "Staff", "name": "View Staff Members", "description": "View staff profiles, roles, and assigned services"},
    {"key": "staff:write", "module": "Staff", "name": "Manage Staff", "description": "Add or modify staff members and assignments"},
    {"key": "staff:delete", "module": "Staff", "name": "Delete Staff", "description": "Remove staff members from salon roster"},

    # Reports & Business Analytics
    {"key": "reports:read", "module": "Analytics", "name": "View Financial Reports", "description": "View gross revenue, sales trends, and staff commission"},
    {"key": "reports:export", "module": "Analytics", "name": "Export Financial CSVs", "description": "Download sales reports and business data dumps"},

    # Team Accounts & RBAC
    {"key": "accounts:read", "module": "Team & Roles", "name": "View Team Accounts", "description": "View team members and active role assignments"},
    {"key": "accounts:write", "module": "Team & Roles", "name": "Manage Team Members", "description": "Invite, edit, or remove team member logins"},
    {"key": "roles:manage", "module": "Team & Roles", "name": "Manage Roles & Permissions", "description": "Create, edit, duplicate, and delete custom roles"},

    # Settings & Salon Administration
    {"key": "settings:read", "module": "Settings", "name": "View Salon Settings", "description": "View salon profile, hours, and preferences"},
    {"key": "settings:write", "module": "Settings", "name": "Edit Salon Settings", "description": "Update salon profile, schedule, and payment options"},
    {"key": "data:import_export", "module": "Settings", "name": "Import & Backup Data", "description": "Mass import CSV records and download backups"},
]

ALL_PERMISSION_KEYS = [p["key"] for p in SYSTEM_PERMISSIONS]


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
        wants_returning = is_insert and "RETURNING" not in cleaned.upper()
        if wants_returning:
            if "app_settings" in cleaned.lower():
                ret_sql = cleaned.rstrip("; ") + " RETURNING key"
            else:
                ret_sql = cleaned.rstrip("; ") + " RETURNING id"
        else:
            ret_sql = cleaned

        try:
            self._cur.execute(ret_sql, params)
            self.rowcount = self._cur.rowcount
            if is_insert:
                try:
                    row = self._cur.fetchone()
                    if row:
                        if "id" in row:
                            self.lastrowid = row["id"]
                        elif "key" in row:
                            self.lastrowid = row["key"]
                except Exception:
                    pass
        except Exception as e:
            if wants_returning and "does not exist" in str(e).lower():
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                self._cur.execute(cleaned, params)
                self.rowcount = self._cur.rowcount
                return self
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
        dsn = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
        try:
            return PostgresConnWrapper(dsn)
        except Exception:
            pass
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
    if salons_columns and "booking_slug" not in salons_columns:
        cur.execute("ALTER TABLE salons ADD COLUMN booking_slug TEXT")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS salon_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            salon_id INTEGER UNIQUE,
            payment_methods TEXT DEFAULT '{}',
            session_timeout TEXT DEFAULT '7d',
            created_at INTEGER,
            updated_at INTEGER,
            FOREIGN KEY (salon_id) REFERENCES salons(id) ON DELETE CASCADE
        )
    """)
    settings_columns = {r["name"] for r in cur.execute("PRAGMA table_info(salon_settings)").fetchall()}
    if settings_columns and "session_timeout" not in settings_columns:
        cur.execute("ALTER TABLE salon_settings ADD COLUMN session_timeout TEXT DEFAULT '7d'")
    subs_columns = {r["name"] for r in cur.execute("PRAGMA table_info(subscriptions)").fetchall()}
    if subs_columns and "billing_cycle" not in subs_columns:
        cur.execute("ALTER TABLE subscriptions ADD COLUMN billing_cycle TEXT NOT NULL DEFAULT 'monthly'")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS terminal_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            salon_id INTEGER NOT NULL,
            terminal_id INTEGER NOT NULL,
            tab_id TEXT NOT NULL,
            account_id INTEGER DEFAULT 0,
            account_name TEXT DEFAULT '',
            last_heartbeat INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS terminal_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            salon_id INTEGER NOT NULL,
            terminal_id INTEGER NOT NULL,
            terminal_name TEXT DEFAULT '',
            cart_data TEXT NOT NULL DEFAULT '{}',
            updated_by_account_id INTEGER DEFAULT 0,
            updated_by_name TEXT DEFAULT '',
            updated_at INTEGER NOT NULL
        )
    """)

    # ================= RBAC TABLES & MIGRATION =================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            key TEXT PRIMARY KEY,
            module TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL
        )
    """)
    # Seed atomic system permissions
    for p in SYSTEM_PERMISSIONS:
        cur.execute("""
            INSERT OR IGNORE INTO permissions (key, module, name, description)
            VALUES (?, ?, ?, ?)
        """, (p["key"], p["module"], p["name"], p["description"]))

    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            role_name TEXT NOT NULL,
            description TEXT DEFAULT '',
            is_system_locked INTEGER DEFAULT 0,
            created_at INTEGER,
            updated_at INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            permission_key TEXT NOT NULL,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (permission_key) REFERENCES permissions(key) ON DELETE CASCADE
        )
    """)

    # Add role_id column to accounts if it doesn't exist
    accounts_columns = {r["name"] for r in cur.execute("PRAGMA table_info(accounts)").fetchall()}
    if accounts_columns and "role_id" not in accounts_columns:
        cur.execute("ALTER TABLE accounts ADD COLUMN role_id INTEGER")

    # Add default_role_id, tax_settings, printer_settings, whatsapp_settings to salon_settings if they don't exist
    settings_cols = {r["name"] for r in cur.execute("PRAGMA table_info(salon_settings)").fetchall()}
    if settings_cols and "default_role_id" not in settings_cols:
        cur.execute("ALTER TABLE salon_settings ADD COLUMN default_role_id INTEGER")
    if settings_cols and "tax_settings" not in settings_cols:
        cur.execute("ALTER TABLE salon_settings ADD COLUMN tax_settings TEXT DEFAULT '{}'")
    if settings_cols and "printer_settings" not in settings_cols:
        cur.execute("ALTER TABLE salon_settings ADD COLUMN printer_settings TEXT DEFAULT '{}'")
    if settings_cols and "whatsapp_settings" not in settings_cols:
        cur.execute("ALTER TABLE salon_settings ADD COLUMN whatsapp_settings TEXT DEFAULT '{}'")

    # Add payment tracking and per-bill tax configuration to bills if they don't exist
    bills_cols = {r["name"] for r in cur.execute("PRAGMA table_info(bills)").fetchall()}
    if bills_cols:
        if "amount_paid" not in bills_cols:
            cur.execute("ALTER TABLE bills ADD COLUMN amount_paid INTEGER DEFAULT 0")
        if "due_amount" not in bills_cols:
            cur.execute("ALTER TABLE bills ADD COLUMN due_amount INTEGER DEFAULT 0")
        if "payment_status" not in bills_cols:
            cur.execute("ALTER TABLE bills ADD COLUMN payment_status TEXT DEFAULT 'PAID'")
        if "tax_enabled" not in bills_cols:
            cur.execute("ALTER TABLE bills ADD COLUMN tax_enabled INTEGER DEFAULT 1")
        if "tax_inclusive" not in bills_cols:
            cur.execute("ALTER TABLE bills ADD COLUMN tax_inclusive INTEGER DEFAULT 0")
        if "tax_rate" not in bills_cols:
            cur.execute("ALTER TABLE bills ADD COLUMN tax_rate REAL DEFAULT 18.0")
        if "tax_amount" not in bills_cols:
            cur.execute("ALTER TABLE bills ADD COLUMN tax_amount INTEGER DEFAULT 0")

    # Create bill_payments table for payment history and recoverable settlements
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bill_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id TEXT NOT NULL,
            account_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            payment_mode TEXT DEFAULT 'Cash',
            received_by TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at INTEGER NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bill_payments_bill ON bill_payments(bill_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bill_payments_account ON bill_payments(account_id)")

    # Automatically sync PostgreSQL auto-increment sequences to max(id) to avoid
    # unique constraint violations if rows were seeded or imported with explicit IDs.
    if os.environ.get("USE_POSTGRES") or os.environ.get("DATABASE_URL"):
        sync_tables = ["salons", "accounts", "appointments", "services", "staff", "customers", "categories", "terminal_sessions", "terminal_drafts", "salon_settings", "roles", "role_permissions", "bill_payments"]
        for tbl in sync_tables:
            try:
                cur.execute(f"SELECT pg_get_serial_sequence('{tbl}', 'id') AS seq")
                s_row = cur.fetchone()
                seq_name = s_row["seq"] if s_row else None
                if seq_name:
                    cur.execute(f"""
                        SELECT setval(
                            '{seq_name}',
                            COALESCE((SELECT MAX(id) FROM {tbl}), 1),
                            (SELECT COUNT(*) FROM {tbl}) > 0
                        )
                    """)
            except Exception:
                pass
    conn.commit()
    conn.close()



import secrets

def generate_booking_slug(length=5):
    """Generate a clean 5-character lowercase alphanumeric slug for vanity booking links."""
    chars = "23456789abcdefghjkmnpqrstuvwxyz"
    return "".join(secrets.choice(chars) for _ in range(length))


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
    booking_slug: str | None = None

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
            booking_slug=(row["booking_slug"] if "booking_slug" in row.keys() else None),
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
    id: int | None = None
    role_id: int | None = None
    salon: Salon | None = None

    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        row_id = row.get("id") if isinstance(row, dict) else (row["id"] if "id" in row.keys() else (row["rowid"] if "rowid" in row.keys() else None))
        return cls(
            auth_id=row["auth_id"],
            username=row["username"],
            password=row["password"],
            auth_level=row["auth_level"],
            id=row_id,
            role_id=row.get("role_id") if isinstance(row, dict) else (row["role_id"] if "role_id" in row.keys() else None),
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

    def create_account(self, auth_id, username, password, auth_level="admin", role_id=None):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO accounts(auth_id, username, password, auth_level, role_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (auth_id, username, password, auth_level, role_id),
        )
        conn.commit()
        conn.close()

    def create_auth(self, name, salon_name, phone, email, password, plan="pro", created_on=None, auth_level="admin"):
        if created_on is None:
            created_on = int(datetime.now().timestamp())
        tier, cycle, _ = resolve_plan(plan)
        expires_on = expires_for(cycle, created_on)
        booking_slug = generate_booking_slug()
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO salons(name, salon_name, phone, email, plan, billing_cycle, created_on, expires_on, booking_slug)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, salon_name, str(phone), email, tier, cycle, created_on, expires_on, booking_slug),
        )
        auth_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Provision base roles and link the owner role
        roles_map = self.ensure_default_roles(auth_id)
        owner_role_id = roles_map.get("owner")
        self.create_account(auth_id, email, password, auth_level, role_id=owner_role_id)
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
        if not row:
            conn.close()
            return None
        salon = Salon.from_row(row)
        if not salon.booking_slug:
            slug = generate_booking_slug()
            try:
                cur.execute("UPDATE salons SET booking_slug = ? WHERE id = ?", (slug, salon_id))
                conn.commit()
                salon.booking_slug = slug
            except Exception:
                pass
        conn.close()
        return salon

    def get_salon_by_slug(self, slug):
        if not slug:
            return None
        slug_clean = str(slug).strip().lower()
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM salons WHERE LOWER(booking_slug) = ? LIMIT 1", (slug_clean,)).fetchone()
        if not row:
            try:
                row = cur.execute("SELECT * FROM salons WHERE id = ?", (int(slug),)).fetchone()
            except (ValueError, TypeError):
                row = None
        conn.close()
        return Salon.from_row(row) if row else None

    def get_payment_methods(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute("SELECT payment_methods FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        conn.close()
        if row and row["payment_methods"]:
            try:
                val = row["payment_methods"]
                res = json.loads(val) if isinstance(val, str) else val
                if isinstance(res, dict):
                    if "custom_methods" not in res or not isinstance(res.get("custom_methods"), list):
                        res["custom_methods"] = []
                    return res
            except Exception:
                pass
        return {"upi": "", "card_terminal": "", "custom_methods": []}

    def update_payment_methods(self, salon_id, methods):
        conn = get_db()
        cur = conn.cursor()
        methods_json = json.dumps(methods) if isinstance(methods, dict) else str(methods)
        now = int(datetime.now().timestamp())
        existing = cur.execute("SELECT id FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        if existing:
            cur.execute("UPDATE salon_settings SET payment_methods = ?, updated_at = ? WHERE salon_id = ?", (methods_json, now, salon_id))
        else:
            cur.execute("INSERT INTO salon_settings (salon_id, payment_methods, created_at, updated_at) VALUES (?, ?, ?, ?)", (salon_id, methods_json, now, now))
        conn.commit()
        conn.close()
        return True

    def get_session_timeout(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute("SELECT session_timeout FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        conn.close()
        if row and row["session_timeout"]:
            return str(row["session_timeout"]).strip().lower()
        return "7d"

    def update_session_timeout(self, salon_id, timeout):
        conn = get_db()
        cur = conn.cursor()
        timeout_clean = str(timeout).strip().lower()
        if timeout_clean not in ("30m", "1h", "12h", "24h", "7d", "never"):
            timeout_clean = "7d"
        now = int(datetime.now().timestamp())
        existing = cur.execute("SELECT id FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        if existing:
            cur.execute("UPDATE salon_settings SET session_timeout = ?, updated_at = ? WHERE salon_id = ?", (timeout_clean, now, salon_id))
        else:
            cur.execute("INSERT INTO salon_settings (salon_id, session_timeout, created_at, updated_at) VALUES (?, ?, ?, ?)", (salon_id, timeout_clean, now, now))
        conn.commit()
        conn.close()
        return True

    def get_tax_settings(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        defaults = {
            "enabled": True,
            "tax_name": "GST",
            "tax_rate": 18.0,
            "tax_type": "exclusive",
            "tax_number": "",
            "split_tax": True,
        }
        try:
            row = cur.execute("SELECT tax_settings FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
            if row and row["tax_settings"]:
                val = row["tax_settings"]
                res = json.loads(val) if isinstance(val, str) else val
                if isinstance(res, dict):
                    defaults.update(res)
        except Exception:
            pass
        finally:
            conn.close()
        return defaults

    def update_tax_settings(self, salon_id, settings):
        conn = get_db()
        cur = conn.cursor()
        settings_json = json.dumps(settings) if isinstance(settings, dict) else str(settings)
        now = int(datetime.now().timestamp())
        existing = cur.execute("SELECT id FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        if existing:
            cur.execute("UPDATE salon_settings SET tax_settings = ?, updated_at = ? WHERE salon_id = ?", (settings_json, now, salon_id))
        else:
            cur.execute("INSERT INTO salon_settings (salon_id, tax_settings, created_at, updated_at) VALUES (?, ?, ?, ?)", (salon_id, settings_json, now, now))
        conn.commit()
        conn.close()
        return True

    def get_printer_settings(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        defaults = {
            "paper_width": "3inch",  # '2inch' (58mm), '3inch' (80mm), '4inch' (104mm)
            "auto_cut": True,
            "header_text": "",
            "footer_text": "Thank you for visiting! Have a glowing day.",
        }
        try:
            row = cur.execute("SELECT printer_settings FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
            if row and row["printer_settings"]:
                val = row["printer_settings"]
                res = json.loads(val) if isinstance(val, str) else val
                if isinstance(res, dict):
                    defaults.update(res)
        except Exception:
            pass
        finally:
            conn.close()
        return defaults

    def update_printer_settings(self, salon_id, settings):
        conn = get_db()
        cur = conn.cursor()
        settings_json = json.dumps(settings) if isinstance(settings, dict) else str(settings)
        now = int(datetime.now().timestamp())
        existing = cur.execute("SELECT id FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        if existing:
            cur.execute("UPDATE salon_settings SET printer_settings = ?, updated_at = ? WHERE salon_id = ?", (settings_json, now, salon_id))
        else:
            cur.execute("INSERT INTO salon_settings (salon_id, printer_settings, created_at, updated_at) VALUES (?, ?, ?, ?)", (salon_id, settings_json, now, now))
        conn.commit()
        conn.close()
        return True

    def get_whatsapp_settings(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        defaults = {
            "enabled": True,
            "provider": "mock",
            "sender_phone": "",
            "template_id": "booking_confirmation",
        }
        try:
            row = cur.execute("SELECT whatsapp_settings FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
            if row and row["whatsapp_settings"]:
                val = row["whatsapp_settings"]
                res = json.loads(val) if isinstance(val, str) else val
                if isinstance(res, dict):
                    defaults.update(res)
        except Exception:
            pass
        finally:
            conn.close()
        return defaults

    def update_whatsapp_settings(self, salon_id, settings):
        conn = get_db()
        cur = conn.cursor()
        settings_json = json.dumps(settings) if isinstance(settings, dict) else str(settings)
        now = int(datetime.now().timestamp())
        existing = cur.execute("SELECT id FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        if existing:
            cur.execute("UPDATE salon_settings SET whatsapp_settings = ?, updated_at = ? WHERE salon_id = ?", (settings_json, now, salon_id))
        else:
            cur.execute("INSERT INTO salon_settings (salon_id, whatsapp_settings, created_at, updated_at) VALUES (?, ?, ?, ?)", (salon_id, settings_json, now, now))
        conn.commit()
        conn.close()
        return True

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

    # ---------- Settings: dynamic RBAC role & account management ----------
    def ensure_default_roles(self, salon_id):
        """Ensure standard base roles (Owner, Manager, Billing Desk) exist for a salon."""
        conn = get_db()
        cur = conn.cursor()
        now = int(datetime.now().timestamp())
        
        # Check existing roles for this tenant
        rows = cur.execute("SELECT id, role_name, is_system_locked FROM roles WHERE tenant_id = ?", (salon_id,)).fetchall()
        existing = {r["role_name"].lower(): dict(r) for r in rows}

        default_defs = [
            {
                "name": "Owner",
                "desc": "Primary salon administrator with unrestricted access to all modules and configurations.",
                "locked": 1,
                "perms": ALL_PERMISSION_KEYS
            },
            {
                "name": "Manager",
                "desc": "Day-to-day salon operations, staff, customer directory, and catalogs.",
                "locked": 0,
                "perms": [
                    "billing:read", "billing:write", "billing:discount",
                    "appointments:read", "appointments:write",
                    "customers:read", "customers:write",
                    "services:read", "services:write",
                    "staff:read", "staff:write",
                    "reports:read",
                    "accounts:read",
                    "settings:read"
                ]
            },
            {
                "name": "Billing Desk",
                "desc": "Front desk checkout, payment collection, and client appointments.",
                "locked": 0,
                "perms": [
                    "billing:read", "billing:write", "billing:discount",
                    "appointments:read", "appointments:write",
                    "customers:read", "customers:write",
                    "services:read"
                ]
            }
        ]

        created_or_found = {}
        for d in default_defs:
            name_key = d["name"].lower()
            if name_key in existing:
                role_id = existing[name_key]["id"]
            else:
                cur.execute(
                    "INSERT INTO roles (tenant_id, role_name, description, is_system_locked, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (salon_id, d["name"], d["desc"], d["locked"], now, now)
                )
                role_id = cur.lastrowid
                for pkey in d["perms"]:
                    cur.execute(
                        "INSERT INTO role_permissions (role_id, permission_key) VALUES (?, ?)",
                        (role_id, pkey)
                    )
            created_or_found[name_key] = role_id

        # Update salon_settings default_role_id if unset
        s_row = cur.execute("SELECT default_role_id FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        if not s_row or not s_row["default_role_id"]:
            cashier_role_id = created_or_found.get("billing desk") or created_or_found.get("cashier")
            if cashier_role_id:
                cur.execute("UPDATE salon_settings SET default_role_id = ? WHERE salon_id = ?", (cashier_role_id, salon_id))

        # Backfill any existing accounts without role_id
        owner_id = self.get_primary_account_id(salon_id)
        owner_role_id = created_or_found.get("owner")
        manager_role_id = created_or_found.get("manager")
        cashier_role_id = created_or_found.get("billing desk")

        acc_rows = cur.execute("SELECT rowid AS id, auth_level, role_id FROM accounts WHERE auth_id = ?", (salon_id,)).fetchall()
        for a in acc_rows:
            if not a["role_id"]:
                lvl = (a["auth_level"] or "").lower()
                assigned_role = owner_role_id
                if a["id"] == owner_id or lvl == "admin":
                    assigned_role = owner_role_id
                elif lvl == "manager":
                    assigned_role = manager_role_id
                elif lvl == "cashier":
                    assigned_role = cashier_role_id
                if assigned_role:
                    cur.execute("UPDATE accounts SET role_id = ? WHERE rowid = ?", (assigned_role, a["id"]))

        conn.commit()
        conn.close()
        return created_or_found

    def get_permissions(self):
        """Return all atomic system permissions."""
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute("SELECT key, module, name, description FROM permissions ORDER BY module ASC, key ASC").fetchall()
        conn.close()
        return [dict(r) for r in rows] if rows else SYSTEM_PERMISSIONS

    def get_roles(self, salon_id):
        """Get all custom and system roles for a salon with permissions and active user counts."""
        self.ensure_default_roles(salon_id)
        conn = get_db()
        cur = conn.cursor()
        roles_rows = cur.execute(
            """
            SELECT r.id, r.tenant_id, r.role_name, r.description, r.is_system_locked, r.created_at, r.updated_at,
                   COUNT(a.id) AS member_count
            FROM roles r
            LEFT JOIN accounts a ON a.role_id = r.id AND a.auth_id = r.tenant_id
            WHERE r.tenant_id = ?
            GROUP BY r.id
            ORDER BY r.is_system_locked DESC, r.id ASC
            """,
            (salon_id,)
        ).fetchall()

        roles = []
        for r in roles_rows:
            r_dict = dict(r)
            perm_rows = cur.execute(
                "SELECT permission_key FROM role_permissions WHERE role_id = ?",
                (r_dict["id"],)
            ).fetchall()
            r_dict["permissions"] = [p["permission_key"] for p in perm_rows]
            roles.append(r_dict)
        conn.close()
        return roles

    def get_role(self, salon_id, role_id):
        """Get a single role with its permissions."""
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, tenant_id, role_name, description, is_system_locked FROM roles WHERE tenant_id = ? AND id = ?",
            (salon_id, role_id)
        ).fetchone()
        if not row:
            conn.close()
            return None
        r_dict = dict(row)
        perm_rows = cur.execute("SELECT permission_key FROM role_permissions WHERE role_id = ?", (role_id,)).fetchall()
        r_dict["permissions"] = [p["permission_key"] for p in perm_rows]
        conn.close()
        return r_dict

    def get_role_permissions(self, role_id):
        """Fetch assigned permission keys for a given role ID."""
        if not role_id:
            return []
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute("SELECT permission_key FROM role_permissions WHERE role_id = ?", (role_id,)).fetchall()
        conn.close()
        return [r["permission_key"] for r in rows]

    def get_account_permissions(self, salon_id, account_id):
        """Fetch all permissions assigned to an account."""
        conn = get_db()
        cur = conn.cursor()
        acc = cur.execute("SELECT rowid AS id, auth_level, role_id FROM accounts WHERE auth_id = ? AND rowid = ?", (salon_id, account_id)).fetchone()
        conn.close()
        if not acc:
            return []
        primary_id = self.get_primary_account_id(salon_id)
        if acc["id"] == primary_id or acc["auth_level"] == "admin":
            return ALL_PERMISSION_KEYS
        if acc["role_id"]:
            perms = self.get_role_permissions(acc["role_id"])
            if perms:
                return perms
        # Fallback to legacy auth_level mapping if role_id not linked
        lvl = (acc["auth_level"] or "cashier").lower()
        if lvl == "admin":
            return ALL_PERMISSION_KEYS
        elif lvl == "manager":
            return [
                "billing:read", "billing:write", "billing:discount",
                "appointments:read", "appointments:write",
                "customers:read", "customers:write",
                "services:read", "services:write",
                "staff:read", "staff:write",
                "reports:read", "accounts:read", "settings:read"
            ]
        return ["billing:read", "billing:write", "billing:discount", "appointments:read", "appointments:write", "customers:read", "customers:write", "services:read"]

    def create_role(self, salon_id, role_name, description, permissions):
        """Create a new custom role with assigned permissions."""
        name = (role_name or "").strip()
        if not name:
            return {"success": False, "message": "Role name is required."}
        conn = get_db()
        cur = conn.cursor()
        existing = cur.execute("SELECT id FROM roles WHERE tenant_id = ? AND LOWER(role_name) = LOWER(?)", (salon_id, name)).fetchone()
        if existing:
            conn.close()
            return {"success": False, "message": f"A role named '{name}' already exists."}

        now = int(datetime.now().timestamp())
        cur.execute(
            "INSERT INTO roles (tenant_id, role_name, description, is_system_locked, created_at, updated_at) VALUES (?, ?, ?, 0, ?, ?)",
            (salon_id, name, (description or "").strip(), now, now)
        )
        role_id = cur.lastrowid
        valid_perms = set(ALL_PERMISSION_KEYS)
        for pkey in set(permissions or []):
            if pkey in valid_perms:
                cur.execute("INSERT INTO role_permissions (role_id, permission_key) VALUES (?, ?)", (role_id, pkey))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Role '{name}' created successfully.", "role_id": role_id}

    def update_role(self, salon_id, role_id, role_name, description, permissions):
        """Update an existing role and its permissions with security safeguards."""
        name = (role_name or "").strip()
        if not name:
            return {"success": False, "message": "Role name is required."}
        conn = get_db()
        cur = conn.cursor()
        role = cur.execute("SELECT * FROM roles WHERE tenant_id = ? AND id = ?", (salon_id, role_id)).fetchone()
        if not role:
            conn.close()
            return {"success": False, "message": "Role not found."}

        # Owner Lockout Protection: The system locked role must retain accounts:write & billing:write
        is_locked = bool(role["is_system_locked"])
        clean_perms = set(permissions or [])
        if is_locked:
            if "accounts:write" not in clean_perms or "billing:write" not in clean_perms:
                conn.close()
                return {"success": False, "message": "Owner Lockout Protection: The primary system role must retain account management and billing permissions."}

        # Check name collision
        collision = cur.execute("SELECT id FROM roles WHERE tenant_id = ? AND LOWER(role_name) = LOWER(?) AND id != ?", (salon_id, name, role_id)).fetchone()
        if collision:
            conn.close()
            return {"success": False, "message": f"Another role named '{name}' already exists."}

        now = int(datetime.now().timestamp())
        cur.execute(
            "UPDATE roles SET role_name = ?, description = ?, updated_at = ? WHERE id = ? AND tenant_id = ?",
            (name, (description or "").strip(), now, role_id, salon_id)
        )
        cur.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        valid_perms = set(ALL_PERMISSION_KEYS)
        for pkey in clean_perms:
            if pkey in valid_perms:
                cur.execute("INSERT INTO role_permissions (role_id, permission_key) VALUES (?, ?)", (role_id, pkey))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Role '{name}' updated successfully."}

    def delete_role(self, salon_id, role_id, reassign_to_role_id=None):
        """Delete a custom role, requiring reassignment if users are actively assigned."""
        conn = get_db()
        cur = conn.cursor()
        role = cur.execute("SELECT * FROM roles WHERE tenant_id = ? AND id = ?", (salon_id, role_id)).fetchone()
        if not role:
            conn.close()
            return {"success": False, "message": "Role not found."}
        if role["is_system_locked"]:
            conn.close()
            return {"success": False, "message": "System-critical roles cannot be deleted."}

        # Check assigned accounts
        assigned_count = cur.execute("SELECT COUNT(*) AS c FROM accounts WHERE auth_id = ? AND role_id = ?", (salon_id, role_id)).fetchone()["c"]
        if assigned_count > 0:
            if not reassign_to_role_id or int(reassign_to_role_id) == int(role_id):
                conn.close()
                return {
                    "success": False,
                    "requires_reassignment": True,
                    "assigned_count": assigned_count,
                    "message": f"{assigned_count} team member(s) are assigned to this role. Please choose a role to reassign them to before deletion."
                }
            # Verify target role exists
            target = cur.execute("SELECT id FROM roles WHERE tenant_id = ? AND id = ?", (salon_id, reassign_to_role_id)).fetchone()
            if not target:
                conn.close()
                return {"success": False, "message": "Target role for reassignment not found."}
            cur.execute("UPDATE accounts SET role_id = ? WHERE auth_id = ? AND role_id = ?", (reassign_to_role_id, salon_id, role_id))

        # Check default role setting
        s_row = cur.execute("SELECT default_role_id FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        if s_row and s_row["default_role_id"] == role_id:
            fallback_role = reassign_to_role_id or self.get_default_role_id(salon_id)
            cur.execute("UPDATE salon_settings SET default_role_id = ? WHERE salon_id = ?", (fallback_role, salon_id))

        cur.execute("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        cur.execute("DELETE FROM roles WHERE id = ? AND tenant_id = ?", (role_id, salon_id))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Role '{role['role_name']}' deleted successfully."}

    def get_default_role_id(self, salon_id):
        """Get the configured default role ID for new invites."""
        self.ensure_default_roles(salon_id)
        conn = get_db()
        cur = conn.cursor()
        s_row = cur.execute("SELECT default_role_id FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        if s_row and s_row["default_role_id"]:
            role = cur.execute("SELECT id FROM roles WHERE tenant_id = ? AND id = ?", (salon_id, s_row["default_role_id"])).fetchone()
            if role:
                conn.close()
                return role["id"]
        # Fallback to Billing Desk or lowest non-locked role
        fallback = cur.execute("SELECT id FROM roles WHERE tenant_id = ? AND is_system_locked = 0 ORDER BY id ASC LIMIT 1", (salon_id,)).fetchone()
        conn.close()
        return fallback["id"] if fallback else None

    def set_default_role_id(self, salon_id, role_id):
        """Set the default role ID for new team invites."""
        conn = get_db()
        cur = conn.cursor()
        role = cur.execute("SELECT id FROM roles WHERE tenant_id = ? AND id = ?", (salon_id, role_id)).fetchone()
        if not role:
            conn.close()
            return {"success": False, "message": "Selected role does not exist."}
        now = int(datetime.now().timestamp())
        existing = cur.execute("SELECT id FROM salon_settings WHERE salon_id = ?", (salon_id,)).fetchone()
        if existing:
            cur.execute("UPDATE salon_settings SET default_role_id = ?, updated_at = ? WHERE salon_id = ?", (role_id, now, salon_id))
        else:
            cur.execute("INSERT INTO salon_settings (salon_id, default_role_id, created_at, updated_at) VALUES (?, ?, ?, ?)", (salon_id, role_id, now, now))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Default invite role updated."}

    def get_accounts(self, salon_id):
        self.ensure_default_roles(salon_id)
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT a.rowid AS id, a.username, a.password, a.auth_level, a.role_id,
                   r.role_name, r.description AS role_description, r.is_system_locked
            FROM accounts a
            LEFT JOIN roles r ON a.role_id = r.id
            WHERE a.auth_id = ?
            ORDER BY a.rowid ASC
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

    def add_account(self, salon_id, username, password, auth_level=None, role_id=None, seat_limit=None):
        username = (username or "").strip().lower()
        if not username or not password:
            return {"success": False, "message": "Email and password are both required."}
        if seat_limit is not None and self.count_accounts(salon_id) >= seat_limit:
            return {
                "success": False,
                "message": f"Team seat limit reached — a salon can have up to {seat_limit} accounts.",
            }

        self.ensure_default_roles(salon_id)
        conn = get_db()
        cur = conn.cursor()

        # Resolve role_id and corresponding auth_level
        resolved_role_id = role_id
        if not resolved_role_id:
            resolved_role_id = self.get_default_role_id(salon_id)

        role = cur.execute("SELECT id, role_name, is_system_locked FROM roles WHERE tenant_id = ? AND id = ?", (salon_id, resolved_role_id)).fetchone()
        if not role:
            # Fallback to default
            resolved_role_id = self.get_default_role_id(salon_id)
            role = cur.execute("SELECT id, role_name, is_system_locked FROM roles WHERE tenant_id = ? AND id = ?", (salon_id, resolved_role_id)).fetchone()

        resolved_auth_level = auth_level or ("admin" if (role and role["is_system_locked"]) else "cashier")
        if role and role["role_name"].lower() == "manager":
            resolved_auth_level = "manager"
        elif role and role["is_system_locked"]:
            resolved_auth_level = "admin"

        try:
            cur.execute(
                "INSERT INTO accounts(auth_id, username, password, auth_level, role_id) VALUES (?, ?, ?, ?, ?)",
                (salon_id, username, password, resolved_auth_level, resolved_role_id),
            )
            conn.commit()
            conn.close()
        except sql.IntegrityError:
            conn.close()
            return {"success": False, "message": "An account with this email already exists."}
        return {"success": True, "message": f"Team account created for {username}."}

    def update_account(self, salon_id, row_id, username, auth_level=None, role_id=None, password=None):
        username = (username or "").strip().lower()
        primary_id = self.get_primary_account_id(salon_id)
        conn = get_db()
        cur = conn.cursor()
        row = cur.execute(
            "SELECT rowid AS id, role_id, auth_level FROM accounts WHERE rowid = ? AND auth_id = ?",
            (row_id, salon_id),
        ).fetchone()
        if not row:
            conn.close()
            return {"success": False, "message": "Account not found."}

        # Resolve role
        resolved_role_id = role_id if role_id is not None else row["role_id"]
        if row["id"] == primary_id:
            # Primary owner account must always retain Owner system role
            owner_role = cur.execute("SELECT id FROM roles WHERE tenant_id = ? AND is_system_locked = 1 LIMIT 1", (salon_id,)).fetchone()
            if owner_role:
                resolved_role_id = owner_role["id"]
            resolved_auth_level = "admin"
        else:
            role = cur.execute("SELECT id, role_name, is_system_locked FROM roles WHERE tenant_id = ? AND id = ?", (salon_id, resolved_role_id)).fetchone() if resolved_role_id else None
            if role and role["is_system_locked"]:
                resolved_auth_level = "admin"
            elif role and role["role_name"].lower() == "manager":
                resolved_auth_level = "manager"
            else:
                resolved_auth_level = auth_level or "cashier"

        try:
            if password:
                cur.execute(
                    "UPDATE accounts SET username = ?, auth_level = ?, role_id = ?, password = ? WHERE rowid = ? AND auth_id = ?",
                    (username, resolved_auth_level, resolved_role_id, password, row_id, salon_id),
                )
            else:
                cur.execute(
                    "UPDATE accounts SET username = ?, auth_level = ?, role_id = ? WHERE rowid = ? AND auth_id = ?",
                    (username, resolved_auth_level, resolved_role_id, row_id, salon_id),
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

    def bulk_add_staff(self, account_id, rows):
        """Mass-insert staff from uploaded CSV rows. Name is required."""
        added, skipped, errors = 0, 0, []
        conn = get_db()
        cur = conn.cursor()
        now = int(datetime.now().timestamp())

        existing_names = {
            str(r["name"]).strip().lower()
            for r in cur.execute("SELECT name FROM staff WHERE account_id = ?", (account_id,)).fetchall()
            if str(r["name"]).strip()
        }

        for idx, row in enumerate(rows, start=2):
            name = str(row.get("name", "") or "").strip()
            if not name:
                skipped += 1
                errors.append(f"Row {idx}: Missing mandatory staff name.")
                continue

            if name.lower() in existing_names:
                skipped += 1
                errors.append(f"Row {idx}: Staff member '{name}' already exists.")
                continue

            role = str(row.get("role", "") or "Stylist").strip() or "Stylist"
            phone = str(row.get("phone", "") or "").strip()
            gender = str(row.get("gender", "") or "").strip()
            email = str(row.get("email", "") or "").strip()

            try:
                services_done = max(0, int(float(str(row.get("services_done", "0") or 0))))
            except (ValueError, TypeError):
                services_done = 0

            try:
                total_revenue = max(0, int(float(str(row.get("total_revenue", "0") or 0))))
            except (ValueError, TypeError):
                total_revenue = 0

            try:
                cur.execute(
                    """
                    INSERT INTO staff(account_id, name, role, phone, gender, email, total_revenue, services_done, created_on)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (account_id, name, role, phone, gender, email, total_revenue, services_done, now),
                )
                existing_names.add(name.lower())
                added += 1
            except sql.Error as e:
                errors.append(f"Row {idx}: {e}")
                skipped += 1

        conn.commit()
        conn.close()
        return {"added": added, "skipped": skipped, "errors": errors}

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
                amount_paid INTEGER DEFAULT 0,
                due_amount INTEGER DEFAULT 0,
                payment_status TEXT DEFAULT 'PAID',
                tax_enabled INTEGER DEFAULT 1,
                tax_inclusive INTEGER DEFAULT 0,
                tax_rate REAL DEFAULT 18.0,
                tax_amount INTEGER DEFAULT 0,
                FOREIGN KEY (account_id) REFERENCES salons(id)
            );
            CREATE TABLE IF NOT EXISTS bill_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                payment_mode TEXT DEFAULT 'Cash',
                received_by TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_bill_payments_bill ON bill_payments(bill_id);
            CREATE INDEX IF NOT EXISTS idx_bill_payments_account ON bill_payments(account_id);
            """
        )
        conn.commit()
        conn.close()

    def create_bill(self, bill_id, account_id, client_name, client_phone, subtotal, discount, tax, grand_total, payment_mode, items_json, amount_paid=None, due_amount=None, payment_status=None, tax_enabled=1, tax_inclusive=0, tax_rate=18.0, tax_amount=None, created_at=None):
        conn = get_db()
        cur = conn.cursor()
        if created_at is None:
            created_at = int(datetime.now().timestamp())
        subtotal = int(subtotal)
        discount = int(discount)
        tax = int(tax)
        grand_total = int(grand_total)

        if amount_paid is None:
            amount_paid = grand_total
        else:
            amount_paid = max(0, min(grand_total, int(amount_paid)))

        if due_amount is None:
            due_amount = max(0, grand_total - amount_paid)
        else:
            due_amount = max(0, int(due_amount))

        if not payment_status:
            if amount_paid >= grand_total:
                payment_status = "PAID"
            elif amount_paid == 0:
                payment_status = "UNPAID"
            else:
                payment_status = "PARTIALLY_PAID"

        if tax_amount is None:
            tax_amount = tax

        cur.execute(
            """
            INSERT INTO bills(id, account_id, client_name, client_phone, subtotal, discount, tax, grand_total, payment_mode, created_at, items_json, amount_paid, due_amount, payment_status, tax_enabled, tax_inclusive, tax_rate, tax_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (bill_id, account_id, client_name, client_phone, subtotal, discount, tax, grand_total, payment_mode, created_at, items_json, amount_paid, due_amount, payment_status, int(tax_enabled), int(tax_inclusive), float(tax_rate), int(tax_amount)),
        )

        # Record initial ledger payment entry if funds were received
        if amount_paid > 0:
            cur.execute(
                """
                INSERT INTO bill_payments(bill_id, account_id, amount, payment_mode, received_by, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (bill_id, account_id, amount_paid, payment_mode, "Cashier", "Initial invoice payment", created_at),
            )

        conn.commit()
        conn.close()
        return bill_id

    def record_payment(self, bill_id, account_id, amount, payment_mode="Cash", received_by="Cashier", notes=""):
        """Record an incremental payment against an invoice and update recoverable due."""
        amount = int(amount)
        if amount <= 0:
            return {"success": False, "message": "Payment amount must be greater than zero."}

        conn = get_db()
        cur = conn.cursor()
        bill = cur.execute("SELECT * FROM bills WHERE id = ? AND account_id = ?", (bill_id, account_id)).fetchone()
        if not bill:
            conn.close()
            return {"success": False, "message": "Invoice not found."}

        current_due = int(bill["due_amount"] if bill["due_amount"] is not None else max(0, bill["grand_total"] - (bill["amount_paid"] or 0)))
        if current_due <= 0:
            conn.close()
            return {"success": False, "message": "Invoice is already fully paid."}

        pay_amount = min(amount, current_due)
        now = int(datetime.now().timestamp())
        new_paid = (bill["amount_paid"] or 0) + pay_amount
        new_due = max(0, bill["grand_total"] - new_paid)
        new_status = "PAID" if new_due == 0 else "PARTIALLY_PAID"

        cur.execute(
            """
            UPDATE bills
            SET amount_paid = ?, due_amount = ?, payment_status = ?
            WHERE id = ? AND account_id = ?
            """,
            (new_paid, new_due, new_status, bill_id, account_id),
        )

        cur.execute(
            """
            INSERT INTO bill_payments(bill_id, account_id, amount, payment_mode, received_by, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (bill_id, account_id, pay_amount, payment_mode, received_by or "Cashier", notes or "Due settlement", now),
        )
        payment_id = cur.lastrowid
        conn.commit()
        conn.close()

        return {
            "success": True,
            "bill_id": bill_id,
            "amount_paid": new_paid,
            "due_amount": new_due,
            "payment_status": new_status,
            "payment_id": payment_id,
            "settled_amount": pay_amount,
            "bill": {
                "id": bill_id,
                "amount_paid": new_paid,
                "due_amount": new_due,
                "payment_status": new_status,
            },
            "message": f"Successfully received ₹{pay_amount:,} towards invoice {bill_id}."
        }

    def get_bill_payments(self, bill_id, account_id):
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM bill_payments WHERE bill_id = ? AND account_id = ? ORDER BY created_at ASC",
            (bill_id, account_id),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_customer_dues(self, account_id, phone):
        phone_clean = str(phone or "").strip()
        if not phone_clean:
            return []
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, client_name, client_phone, grand_total, amount_paid, due_amount, payment_status, created_at
            FROM bills
            WHERE account_id = ? AND client_phone = ? AND due_amount > 0
            ORDER BY created_at DESC
            """,
            (account_id, phone_clean),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_bills_filtered(self, account_id, status=None, q=None, limit=50, offset=0):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        conditions = ["account_id = ?"]
        params = [account_id]

        if status:
            status_lower = status.strip().lower()
            if status_lower in ("due", "partially_paid", "partial"):
                conditions.append("due_amount > 0")
            elif status_lower == "paid":
                conditions.append("(due_amount = 0 OR payment_status = 'PAID')")
            elif status_lower == "unpaid":
                conditions.append("(amount_paid = 0 OR payment_status = 'UNPAID')")

        if q:
            term = f"%{q.strip()}%"
            conditions.append("(id LIKE ? OR client_name LIKE ? OR client_phone LIKE ?)")
            params.extend([term, term, term])

        where_clause = " WHERE " + " AND ".join(conditions)

        count_row = cur.execute(f"SELECT COUNT(*) as c FROM bills {where_clause}", params).fetchone()
        total_count = count_row["c"] if count_row else 0

        kpi_row = cur.execute(
            f"""
            SELECT SUM(grand_total) as total_invoiced,
                   SUM(amount_paid) as total_paid,
                   SUM(due_amount) as total_due
            FROM bills {where_clause}
            """,
            params,
        ).fetchone()

        query = f"SELECT * FROM bills {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        rows = cur.execute(query, params + [int(limit), int(offset)]).fetchall()
        conn.close()

        bills = []
        for r in rows:
            d = dict(r)
            try:
                items = json.loads(d.pop("items_json") or "[]")
            except Exception:
                items = []
            d["items"] = items if isinstance(items, list) else []
            d.setdefault("amount_paid", d.get("grand_total", 0))
            d.setdefault("due_amount", 0)
            d.setdefault("payment_status", "PAID" if d.get("due_amount", 0) == 0 else "PARTIALLY_PAID")
            bills.append(d)

        return {
            "bills": bills,
            "total": total_count,
            "summary": {
                "total_invoiced": int(kpi_row["total_invoiced"] or 0) if kpi_row else 0,
                "total_paid": int(kpi_row["total_paid"] or 0) if kpi_row else 0,
                "total_due": int(kpi_row["total_due"] or 0) if kpi_row else 0,
            }
        }

    def bulk_add_bills(self, account_id, rows):
        """Mass-insert bills/invoices from uploaded CSV rows."""
        added, skipped, errors = 0, 0, []
        conn = get_db()
        cur = conn.cursor()
        now = int(datetime.now().timestamp())

        existing_ids = {
            str(r["id"]).strip().upper()
            for r in cur.execute("SELECT id FROM bills WHERE account_id = ?", (account_id,)).fetchall()
            if str(r["id"]).strip()
        }

        for idx, row in enumerate(rows, start=2):
            raw_id = str(row.get("id", "") or "").strip().upper()
            if raw_id and raw_id in existing_ids:
                skipped += 1
                errors.append(f"Row {idx}: Invoice ID '{raw_id}' already exists.")
                continue

            bill_id = raw_id if raw_id else f"AP-{str(uuid4())[:6].upper()}"

            client_name = str(row.get("client_name", "") or row.get("client", "") or "Walk-in").strip() or "Walk-in"
            client_phone = str(row.get("client_phone", "") or row.get("phone", "") or "").strip()
            payment_mode = str(row.get("payment_mode", "") or row.get("payment", "") or "UPI").strip() or "UPI"

            try:
                subtotal = max(0, int(float(str(row.get("subtotal", "0") or 0))))
                discount = max(0, int(float(str(row.get("discount", "0") or 0))))
                tax = max(0, int(float(str(row.get("tax", "0") or 0))))
                raw_grand_total = row.get("grand_total") or row.get("total")
                if raw_grand_total is not None and str(raw_grand_total).strip() != "":
                    grand_total = max(0, int(float(str(raw_grand_total))))
                else:
                    grand_total = max(0, subtotal - discount + tax)

                raw_paid = row.get("amount_paid") or row.get("paid")
                if raw_paid is not None and str(raw_paid).strip() != "":
                    amount_paid = max(0, min(grand_total, int(float(str(raw_paid)))))
                else:
                    amount_paid = grand_total

                due_amount = max(0, grand_total - amount_paid)
                payment_status = "PAID" if due_amount == 0 else ("UNPAID" if amount_paid == 0 else "PARTIALLY_PAID")
            except (ValueError, TypeError):
                errors.append(f"Row {idx}: Invalid numeric figures.")
                skipped += 1
                continue

            if grand_total > 500000:
                errors.append(f"Row {idx}: Bill grand total ₹{grand_total:,} exceeds ₹5,00,000 cap.")
                skipped += 1
                continue

            # Parse items
            raw_items = row.get("items") or row.get("items_json") or row.get("services") or ""
            items_list = []
            if raw_items:
                raw_items_str = str(raw_items).strip()
                if raw_items_str.startswith("[") and raw_items_str.endswith("]"):
                    try:
                        parsed = json.loads(raw_items_str)
                        if isinstance(parsed, list):
                            items_list = parsed
                    except Exception:
                        pass
                if not items_list:
                    parts = [p.strip() for p in raw_items_str.split(",") if p.strip()]
                    for p in parts:
                        items_list.append({"name": p, "price": 0, "qty": 1, "staff": "Unassigned"})

            if not items_list:
                items_list = [{"name": "Service", "price": subtotal, "qty": 1, "staff": "Unassigned"}]

            created_at = now
            raw_date = str(row.get("created_at", "") or row.get("date", "") or "").strip()
            if raw_date:
                try:
                    if raw_date.isdigit():
                        created_at = int(raw_date)
                    else:
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
                            try:
                                dt = datetime.strptime(raw_date, fmt)
                                created_at = int(dt.timestamp())
                                break
                            except ValueError:
                                pass
                except Exception:
                    created_at = now

            try:
                cur.execute(
                    """
                    INSERT INTO bills(id, account_id, client_name, client_phone, subtotal, discount, tax, grand_total, payment_mode, created_at, items_json, amount_paid, due_amount, payment_status, tax_enabled, tax_inclusive, tax_rate, tax_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 18.0, ?)
                    """,
                    (bill_id, account_id, client_name, client_phone, subtotal, discount, tax, grand_total, payment_mode, created_at, json.dumps(items_list), amount_paid, due_amount, payment_status, tax),
                )
                if amount_paid > 0:
                    cur.execute(
                        """
                        INSERT INTO bill_payments(bill_id, account_id, amount, payment_mode, received_by, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (bill_id, account_id, amount_paid, payment_mode, "Import", "CSV Bulk Import", created_at),
                    )
                existing_ids.add(bill_id)
                added += 1
            except sql.Error as e:
                errors.append(f"Row {idx}: {e}")
                skipped += 1

        conn.commit()
        conn.close()
        return {"added": added, "skipped": skipped, "errors": errors}

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
        bills = []
        for r in rows:
            d = dict(r)
            try:
                items = json.loads(d.pop("items_json") or "[]")
            except Exception:
                items = []
            d["items"] = items if isinstance(items, list) else []
            d.setdefault("amount_paid", d.get("grand_total", 0))
            d.setdefault("due_amount", 0)
            d.setdefault("payment_status", "PAID" if d.get("due_amount", 0) == 0 else "PARTIALLY_PAID")
            bills.append(d)
        return bills

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

    def get_bills_by_phone(self, account_id, phone, limit=50):
        """Fetch bill history for a client phone number, newest first."""
        phone = str(phone or "").strip()
        if not phone:
            return []
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM bills WHERE account_id = ? AND client_phone = ? ORDER BY created_at DESC LIMIT ?",
            (account_id, phone, int(limit)),
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


class TerminalRepository:
    def __init__(self):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS terminal_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                salon_id INTEGER NOT NULL,
                terminal_id INTEGER NOT NULL,
                tab_id TEXT NOT NULL,
                account_id INTEGER DEFAULT 0,
                account_name TEXT DEFAULT '',
                last_heartbeat INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS terminal_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                salon_id INTEGER NOT NULL,
                terminal_id INTEGER NOT NULL,
                terminal_name TEXT DEFAULT '',
                cart_data TEXT NOT NULL DEFAULT '{}',
                updated_by_account_id INTEGER DEFAULT 0,
                updated_by_name TEXT DEFAULT '',
                updated_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def clean_stale_sessions(self, timeout_seconds=18):
        """Purge terminal sessions that haven't sent a heartbeat within timeout."""
        threshold = int(datetime.now().timestamp()) - timeout_seconds
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM terminal_sessions WHERE last_heartbeat < ?", (threshold,))
        conn.commit()
        conn.close()

    def get_active_sessions(self, salon_id):
        self.clean_stale_sessions()
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT terminal_id, tab_id, account_id, account_name, last_heartbeat, created_at "
            "FROM terminal_sessions WHERE salon_id = ? ORDER BY terminal_id ASC",
            (salon_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def heartbeat(self, salon_id, terminal_id, tab_id, account_id=0, account_name="", plan="free", open_terminal_ids=None):
        self.clean_stale_sessions()
        now = int(datetime.now().timestamp())
        try:
            terminal_id = int(terminal_id)
        except (ValueError, TypeError):
            terminal_id = 1
        limit = get_terminal_limit(plan)

        # Normalize open_terminal_ids
        clean_open_ids = set()
        if open_terminal_ids and isinstance(open_terminal_ids, (list, set, tuple)):
            for oid in open_terminal_ids:
                try:
                    clean_open_ids.add(int(oid))
                except (ValueError, TypeError):
                    pass
        clean_open_ids.add(terminal_id)

        conn = get_db()
        cur = conn.cursor()

        # 1. Check if another active tab already holds this specific active terminal_id
        other_holder = cur.execute(
            "SELECT tab_id, account_name FROM terminal_sessions WHERE salon_id = ? AND terminal_id = ? AND tab_id != ?",
            (salon_id, terminal_id, tab_id)
        ).fetchone()

        if other_holder:
            conn.close()
            active = self.get_active_sessions(salon_id)
            return {
                "allowed": False,
                "reason": "in_use",
                "limit": limit,
                "tier": plan,
                "terminal_id": terminal_id,
                "holder_tab": other_holder["tab_id"],
                "holder_name": other_holder["account_name"] or "Another window",
                "active_terminals": active,
                "message": f"Terminal #{terminal_id} is currently active in another browser tab."
            }

        # 2. Check total distinct terminals held by OTHER tabs
        other_terms = cur.execute(
            "SELECT DISTINCT terminal_id FROM terminal_sessions WHERE salon_id = ? AND tab_id != ?",
            (salon_id, tab_id)
        ).fetchall()
        other_terminal_ids = {r["terminal_id"] for r in other_terms}

        # If another tab holds any of this tab's secondary open_terminal_ids, remove them from this tab
        clean_open_ids = {oid for oid in clean_open_ids if oid not in other_terminal_ids}
        clean_open_ids.add(terminal_id)

        # 3. Check if total distinct terminals would exceed limit
        if limit is not None:
            tier_label = "Free Tier" if limit == 1 else f"Pro Tier (Max {limit})"
            # If other tabs already consume all available slots:
            if len(other_terminal_ids) >= limit:
                conn.close()
                active = self.get_active_sessions(salon_id)
                return {
                    "allowed": False,
                    "reason": "limit_reached",
                    "limit": limit,
                    "tier": plan,
                    "terminal_id": terminal_id,
                    "active_terminals": active,
                    "message": f"{tier_label} limit reached ({len(other_terminal_ids)}/{limit} active terminals across tabs). Upgrade your plan to open more terminals in parallel."
                }

            # If this tab requested more terminals than remaining capacity, trim to fit
            allowed_slots = limit - len(other_terminal_ids)
            if len(clean_open_ids) > allowed_slots:
                trimmed = {terminal_id}
                for oid in sorted(clean_open_ids):
                    if len(trimmed) >= allowed_slots:
                        break
                    trimmed.add(oid)
                clean_open_ids = trimmed

        # 4. Synchronize terminal_sessions for this tab_id
        # Delete any terminal sessions for this tab that are no longer in clean_open_ids
        cur.execute(
            f"DELETE FROM terminal_sessions WHERE salon_id = ? AND tab_id = ? AND terminal_id NOT IN ({','.join(['?']*len(clean_open_ids))})",
            [salon_id, tab_id] + list(clean_open_ids)
        )

        # Insert or update each terminal in clean_open_ids
        for oid in clean_open_ids:
            existing = cur.execute(
                "SELECT id FROM terminal_sessions WHERE salon_id = ? AND tab_id = ? AND terminal_id = ?",
                (salon_id, tab_id, oid)
            ).fetchone()
            if existing:
                cur.execute(
                    "UPDATE terminal_sessions SET last_heartbeat = ?, account_id = ?, account_name = ? WHERE id = ?",
                    (now, account_id, account_name, existing["id"])
                )
            else:
                cur.execute(
                    "INSERT INTO terminal_sessions (salon_id, terminal_id, tab_id, account_id, account_name, last_heartbeat, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (salon_id, oid, tab_id, account_id, account_name, now, now)
                )

        conn.commit()
        conn.close()
        active = self.get_active_sessions(salon_id)
        return {
            "allowed": True,
            "limit": limit,
            "terminal_id": terminal_id,
            "open_terminals": sorted(list(clean_open_ids)),
            "active_terminals": active
        }

    def takeover_terminal(self, salon_id, terminal_id, tab_id, account_id=0, account_name="", plan="free"):
        """Forcibly reassign terminal_id to this tab_id, releasing any prior holder."""
        now = int(datetime.now().timestamp())
        try:
            terminal_id = int(terminal_id)
        except (ValueError, TypeError):
            terminal_id = 1
        limit = get_terminal_limit(plan)

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM terminal_sessions WHERE salon_id = ? AND terminal_id = ?",
            (salon_id, terminal_id)
        )
        cur.execute(
            "DELETE FROM terminal_sessions WHERE salon_id = ? AND tab_id = ?",
            (salon_id, tab_id)
        )
        cur.execute(
            "INSERT INTO terminal_sessions (salon_id, terminal_id, tab_id, account_id, account_name, last_heartbeat, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (salon_id, terminal_id, tab_id, account_id, account_name, now, now)
        )
        conn.commit()
        conn.close()
        active = self.get_active_sessions(salon_id)
        return {"allowed": True, "limit": limit, "terminal_id": terminal_id, "active_terminals": active}

    def release_session(self, salon_id, tab_id, terminal_id=None):
        conn = get_db()
        cur = conn.cursor()
        if terminal_id:
            try:
                t_id = int(terminal_id)
            except (ValueError, TypeError):
                t_id = 1
            cur.execute(
                "DELETE FROM terminal_sessions WHERE salon_id = ? AND tab_id = ? AND terminal_id = ?",
                (salon_id, tab_id, t_id)
            )
        else:
            cur.execute(
                "DELETE FROM terminal_sessions WHERE salon_id = ? AND tab_id = ?",
                (salon_id, tab_id)
            )
        conn.commit()
        conn.close()
        return True

    # --- Studio Draft Cloud Sync Methods ---
    def save_draft(self, salon_id, terminal_id, terminal_name, cart_data, account_id=0, account_name=""):
        now = int(datetime.now().timestamp())
        try:
            terminal_id = int(terminal_id)
        except (ValueError, TypeError):
            terminal_id = 1
        if isinstance(cart_data, (dict, list)):
            cart_json = json.dumps(cart_data)
        else:
            cart_json = str(cart_data)

        conn = get_db()
        cur = conn.cursor()
        existing = cur.execute(
            "SELECT id FROM terminal_drafts WHERE salon_id = ? AND terminal_id = ?",
            (salon_id, terminal_id)
        ).fetchone()

        if existing:
            cur.execute(
                "UPDATE terminal_drafts SET terminal_name = ?, cart_data = ?, updated_by_account_id = ?, updated_by_name = ?, updated_at = ? "
                "WHERE salon_id = ? AND terminal_id = ?",
                (terminal_name, cart_json, account_id, account_name, now, salon_id, terminal_id)
            )
        else:
            cur.execute(
                "INSERT INTO terminal_drafts (salon_id, terminal_id, terminal_name, cart_data, updated_by_account_id, updated_by_name, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (salon_id, terminal_id, terminal_name, cart_json, account_id, account_name, now)
            )
        conn.commit()
        conn.close()
        return True

    def get_drafts(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT terminal_id, terminal_name, cart_data, updated_by_account_id, updated_by_name, updated_at "
            "FROM terminal_drafts WHERE salon_id = ? ORDER BY terminal_id ASC",
            (salon_id,)
        ).fetchall()
        conn.close()
        drafts = []
        for r in rows:
            d = dict(r)
            try:
                d["cart_data"] = json.loads(d["cart_data"])
            except Exception:
                d["cart_data"] = {}
            drafts.append(d)
        return drafts

    def get_draft(self, salon_id, terminal_id):
        conn = get_db()
        cur = conn.cursor()
        try:
            t_id = int(terminal_id)
        except (ValueError, TypeError):
            t_id = 1
        row = cur.execute(
            "SELECT terminal_id, terminal_name, cart_data, updated_by_account_id, updated_by_name, updated_at "
            "FROM terminal_drafts WHERE salon_id = ? AND terminal_id = ?",
            (salon_id, t_id)
        ).fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        try:
            d["cart_data"] = json.loads(d["cart_data"])
        except Exception:
            d["cart_data"] = {}
        return d

    def delete_draft(self, salon_id, terminal_id):
        conn = get_db()
        cur = conn.cursor()
        try:
            t_id = int(terminal_id)
        except (ValueError, TypeError):
            t_id = 1
        cur.execute(
            "DELETE FROM terminal_drafts WHERE salon_id = ? AND terminal_id = ?",
            (salon_id, t_id)
        )
        conn.commit()
        conn.close()
        return True


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
                gender TEXT DEFAULT '',
                created_at INTEGER NOT NULL,
                FOREIGN KEY (account_id) REFERENCES salons(id)
            );
            """
        )
        try:
            cur.execute("ALTER TABLE customers ADD COLUMN gender TEXT DEFAULT ''")
        except Exception:
            pass
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

    def add_customer(self, account_id, name, phone="", email="", notes="", created_at=None, gender=""):
        if created_at is None:
            created_at = int(datetime.now().timestamp())
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO customers(account_id, name, phone, email, notes, gender, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (account_id, name, phone, email, notes, gender or "", created_at),
        )
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return new_id

    def bulk_add_customers(self, account_id, rows, mode="conservative"):
        """Mass-insert customers from uploaded rows. Phone is required.
        mode='destructive': deletes all existing customers for this salon and replaces them.
        mode='conservative': preserves existing customers and skips duplicate phone numbers.
        """
        added, skipped, errors = 0, 0, []
        conn = get_db()
        cur = conn.cursor()

        if mode == "destructive":
            cur.execute("DELETE FROM customers WHERE account_id = ?", (account_id,))
            existing = set()
        else:
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
            gender = str(row.get("gender", "") or "").strip()
            if not name or not phone:
                skipped += 1
                if not phone:
                    errors.append(f"Row {idx}: Missing mandatory phone number for '{name or 'Unknown'}'.")
                continue
            if phone in existing:
                skipped += 1
                continue
            try:
                cur.execute(
                    """
                    INSERT INTO customers(account_id, name, phone, email, notes, gender, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (account_id, name, phone, email, notes, gender, int(datetime.now().timestamp())),
                )
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
                ("Ananya Sharma", "9876543210", "ananya@gmail.com", "Prefers weekend slots", "Female"),
                ("Vikram Malhotra", "9812345678", "vikram@gmail.com", "Regular client", "Male"),
            ]
            cur.executemany(
                """
                INSERT INTO customers(account_id, name, phone, email, notes, gender, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [(account_id, *d, now) for d in defaults],
            )
            conn.commit()
        conn.close()

    def update_customer(self, account_id, customer_id, name, phone="", email="", notes="", gender=""):
        """Update existing customer details."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE customers
            SET name = ?, phone = ?, email = ?, notes = ?, gender = ?
            WHERE id = ? AND account_id = ?
            """,
            (name, phone, email, notes, gender or "", customer_id, account_id),
        )
        affected = cur.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def delete_customer(self, account_id, customer_id):
        """Delete customer record."""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM customers WHERE id = ? AND account_id = ?", (customer_id, account_id))
        affected = cur.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def get_customer_analytics(self, account_id):
        """Compute advanced churn metrics, retention rate, and spend distribution for Studio tier."""
        self.seed_defaults_if_empty(account_id)
        customers = self.get_customers(account_id)

        conn = get_db()
        cur = conn.cursor()
        bills = cur.execute(
            "SELECT client_phone, grand_total, created_at FROM bills WHERE account_id = ?",
            (account_id,),
        ).fetchall()
        conn.close()

        phone_bills = {}
        for b in bills:
            phone = str(b["client_phone"] or "").strip()
            if phone:
                phone_bills.setdefault(phone, []).append(dict(b))

        now_ts = int(datetime.now().timestamp())
        day_sec = 86400
        active_threshold = now_ts - (30 * day_sec)     # <= 30 days
        churning_threshold = now_ts - (75 * day_sec)   # 31 to 75 days

        active_count = 0
        churning_count = 0
        churned_count = 0
        repeat_count = 0
        total_tracked_spend = 0

        annotated_customers = []
        for c in customers:
            phone = str(c.get("phone") or "").strip()
            c_bills = phone_bills.get(phone, [])
            total_spend = sum(int(b.get("grand_total") or 0) for b in c_bills)
            visit_count = len(c_bills)
            last_visit_ts = max((int(b.get("created_at") or 0) for b in c_bills), default=0)

            if visit_count > 1:
                repeat_count += 1
            total_tracked_spend += total_spend

            # Determine churn status
            if last_visit_ts == 0:
                created_at = int(c.get("created_at") or 0)
                if created_at >= active_threshold:
                    status = "active"
                    active_count += 1
                elif created_at >= churning_threshold:
                    status = "churning"
                    churning_count += 1
                else:
                    status = "churned"
                    churned_count += 1
            else:
                if last_visit_ts >= active_threshold:
                    status = "active"
                    active_count += 1
                elif last_visit_ts >= churning_threshold:
                    status = "churning"
                    churning_count += 1
                else:
                    status = "churned"
                    churned_count += 1

            c_copy = dict(c)
            c_copy["total_spend"] = total_spend
            c_copy["visit_count"] = visit_count
            c_copy["last_visit_ts"] = last_visit_ts
            c_copy["status"] = status
            annotated_customers.append(c_copy)

        total_customers = len(customers)
        retention_rate = round((active_count / total_customers * 100), 1) if total_customers else 0
        avg_spend = round(total_tracked_spend / total_customers) if total_customers else 0
        repeat_rate = round((repeat_count / total_customers * 100), 1) if total_customers else 0

        top_clients = sorted(annotated_customers, key=lambda x: x["total_spend"], reverse=True)[:5]

        return {
            "total_customers": total_customers,
            "active_count": active_count,
            "churning_count": churning_count,
            "churned_count": churned_count,
            "retention_rate": retention_rate,
            "repeat_rate": repeat_rate,
            "avg_spend": avg_spend,
            "total_tracked_spend": total_tracked_spend,
            "top_clients": top_clients,
            "customers_with_metrics": annotated_customers,
        }



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
        bills = self.bills_in_range(account_id, start_ts, end_ts)
        agg = {}
        for b in bills:
            for it in b.get("items", []):
                if not isinstance(it, dict):
                    continue
                price = int(float(it.get("price", 0) or 0))
                qty = int(float(it.get("qty", 1) or 1))
                line_total = price * qty
                splits = it.get("staff_split")
                if isinstance(splits, list) and len(splits) > 0:
                    for sp in splits:
                        if isinstance(sp, dict):
                            s_name = sp.get("name") or sp.get("staff")
                            s_base = self._base(s_name)
                            if not s_base:
                                continue
                            s_amt = int(float(sp.get("amount", 0) or 0))
                            if s_base not in agg:
                                agg[s_base] = {"name": s_base, "revenue": 0, "services": 0}
                            agg[s_base]["revenue"] += s_amt
                            agg[s_base]["services"] += 1
                elif isinstance(splits, dict) and splits.get("enabled"):
                    st1 = self._base(splits.get("stylist1"))
                    st2 = self._base(splits.get("stylist2"))
                    r1 = float(splits.get("ratio1", 50) or 50)
                    amt1 = int(round(line_total * r1 / 100.0))
                    amt2 = max(0, line_total - amt1)
                    if st1:
                        if st1 not in agg:
                            agg[st1] = {"name": st1, "revenue": 0, "services": 0}
                        agg[st1]["revenue"] += amt1
                        agg[st1]["services"] += 1
                    if st2:
                        if st2 not in agg:
                            agg[st2] = {"name": st2, "revenue": 0, "services": 0}
                        agg[st2]["revenue"] += amt2
                        agg[st2]["services"] += 1
                else:
                    staff = str(it.get("staff", "") or "").strip()
                    base = self._base(staff)
                    if base:
                        if base not in agg:
                            agg[base] = {"name": base, "revenue": 0, "services": 0}
                        agg[base]["revenue"] += line_total
                        agg[base]["services"] += qty

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
    _in_memory_settings = {}
    _settings_cache_ts = {}

    def __init__(self):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings(
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_setting(self, key, default=None):
        now = time.time()
        if key in self._in_memory_settings and (now - self._settings_cache_ts.get(key, 0) < 3.0):
            return self._in_memory_settings[key]
        try:
            conn = get_db()
            cur = conn.cursor()
            row = cur.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
            conn.close()
            if row and "value" in row:
                self._in_memory_settings[key] = row["value"]
                self._settings_cache_ts[key] = now
                return row["value"]
            return default
        except Exception:
            return self._in_memory_settings.get(key, default)

    def set_setting(self, key, value):
        str_val = str(value)
        self._in_memory_settings[key] = str_val
        self._settings_cache_ts[key] = time.time()
        if key == self.SETTING_ACCEPTING_PUBLIC:
            os.environ["ACCEPTING_PUBLIC"] = str_val

        try:
            conn = get_db()
            cur = conn.cursor()
            now = int(datetime.now().timestamp())
            cur.execute(
                """
                INSERT INTO app_settings(key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
                """,
                (key, str_val, now),
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute("REPLACE INTO app_settings(key, value, updated_at) VALUES (?, ?, ?)", (key, str_val, int(datetime.now().timestamp())))
                conn.commit()
                conn.close()
                return True
            except Exception:
                # Setting is already in-memory and applied to runtime environment
                return True

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

    def get_platform_metrics(self):
        conn = get_db()
        cur = conn.cursor()
        now = int(datetime.now().timestamp())
        
        salons = [dict(r) for r in cur.execute("SELECT id, salon_name, plan, created_on, expires_on FROM salons").fetchall()]
        total_salons = len(salons)
        pro_count = sum(1 for s in salons if s.get("plan") == "pro")
        studio_count = sum(1 for s in salons if s.get("plan") == "studio")
        free_count = sum(1 for s in salons if (s.get("plan") or "free") not in ("pro", "studio"))
        expired_count = sum(1 for s in salons if s.get("expires_on") and int(s.get("expires_on")) < now)
        
        bill_stats = cur.execute("SELECT COUNT(*) as c, COALESCE(SUM(grand_total), 0) as rev FROM bills").fetchone()
        total_bills = bill_stats["c"] if bill_stats else 0
        total_revenue = int(bill_stats["rev"] or 0) if bill_stats else 0
        
        pm_rows = [dict(r) for r in cur.execute("SELECT payment_mode, COUNT(*) as c, COALESCE(SUM(grand_total), 0) as rev FROM bills GROUP BY payment_mode").fetchall()]
        payment_split = {r["payment_mode"] or "Other": {"count": r["c"], "revenue": int(r["rev"] or 0)} for r in pm_rows}
        
        apt_stats = cur.execute("SELECT COUNT(*) as c FROM appointments").fetchone()
        total_appointments = apt_stats["c"] if apt_stats else 0
        apt_status_rows = [dict(r) for r in cur.execute("SELECT status, COUNT(*) as c FROM appointments GROUP BY status").fetchall()]
        appointments_by_status = {r["status"] or "Other": r["c"] for r in apt_status_rows}
        
        total_customers = cur.execute("SELECT COUNT(*) as c FROM customers").fetchone()["c"]
        total_staff = cur.execute("SELECT COUNT(*) as c FROM staff").fetchone()["c"]
        total_services = cur.execute("SELECT COUNT(*) as c FROM services").fetchone()["c"]
        
        recent_bills = [dict(r) for r in cur.execute("""
            SELECT b.id, b.client_name, b.grand_total, b.payment_mode, b.created_at, b.account_id, s.salon_name
            FROM bills b
            LEFT JOIN salons s ON b.account_id = s.id
            ORDER BY b.created_at DESC LIMIT 10
        """).fetchall()]
        
        top_salon_rows = [dict(r) for r in cur.execute("""
            SELECT b.account_id as id, s.salon_name, s.plan, COUNT(b.id) as bills_count, COALESCE(SUM(b.grand_total), 0) as revenue
            FROM bills b
            JOIN salons s ON b.account_id = s.id
            GROUP BY b.account_id, s.salon_name, s.plan
            ORDER BY revenue DESC LIMIT 5
        """).fetchall()]
        
        conn.close()
        
        return {
            "total_salons": total_salons,
            "pro_count": pro_count,
            "studio_count": studio_count,
            "free_count": free_count,
            "expired_count": expired_count,
            "total_bills": total_bills,
            "total_revenue": total_revenue,
            "payment_split": payment_split,
            "total_appointments": total_appointments,
            "appointments_by_status": appointments_by_status,
            "total_customers": total_customers,
            "total_staff": total_staff,
            "total_services": total_services,
            "recent_bills": recent_bills,
            "top_salons": top_salon_rows,
        }

    def update_salon(self, salon_id, updates):
        conn = get_db()
        cur = conn.cursor()
        fields = []
        vals = []
        allowed = ["salon_name", "name", "email", "phone", "address", "booking_slug", "plan", "billing_cycle"]
        for k in allowed:
            if k in updates:
                fields.append(f"{k} = ?")
                vals.append(updates[k])
        if not fields:
            conn.close()
            return False
        vals.append(salon_id)
        cur.execute(f"UPDATE salons SET {', '.join(fields)} WHERE id = ?", vals)
        conn.commit()
        conn.close()
        return True

    def reset_owner_password(self, salon_id, new_password):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE accounts SET password = ? WHERE auth_id = ? AND auth_level = 'admin'", (new_password, salon_id))
        conn.commit()
        conn.close()
        return True

    def delete_salon(self, salon_id):
        conn = get_db()
        cur = conn.cursor()
        for tbl in ["accounts", "categories", "services", "staff", "appointments", "bills", "customers"]:
            try:
                col = "auth_id" if tbl == "accounts" else "account_id"
                cur.execute(f"DELETE FROM {tbl} WHERE {col} = ?", (salon_id,))
            except Exception:
                pass
        for tbl in ["subscriptions", "pendingorders", "deletion_requests", "salon_settings"]:
            try:
                cur.execute(f"DELETE FROM {tbl} WHERE salon_id = ?", (salon_id,))
            except Exception:
                pass
        cur.execute("DELETE FROM salons WHERE id = ?", (salon_id,))
        conn.commit()
        conn.close()
        return True

    def export_salon(self, salon_id):
        details = self.salon_details(salon_id)
        if not details:
            return None
        conn = get_db()
        cur = conn.cursor()
        services = [dict(r) for r in cur.execute("SELECT * FROM services WHERE account_id = ?", (salon_id,)).fetchall()]
        customers = [dict(r) for r in cur.execute("SELECT * FROM customers WHERE account_id = ?", (salon_id,)).fetchall()]
        categories = [dict(r) for r in cur.execute("SELECT * FROM categories WHERE account_id = ?", (salon_id,)).fetchall()]
        all_bills = [dict(r) for r in cur.execute("SELECT * FROM bills WHERE account_id = ? ORDER BY created_at DESC", (salon_id,)).fetchall()]
        all_appts = [dict(r) for r in cur.execute("SELECT * FROM appointments WHERE account_id = ? ORDER BY date DESC", (salon_id,)).fetchall()]
        conn.close()
        return {
            "salon": details["salon"],
            "team_accounts": details["accounts"],
            "staff": details["staff"],
            "categories": categories,
            "services": services,
            "customers": customers,
            "appointments": all_appts,
            "bills": all_bills,
            "subscriptions": details["subscriptions"],
            "exported_at": int(datetime.now().timestamp()),
            "schema_version": "1.0",
        }

    def get_database_table_counts(self):
        conn = get_db()
        cur = conn.cursor()
        tables = [
            "salons", "accounts", "bills", "appointments", "customers",
            "services", "staff", "categories", "subscriptions",
            "pendingorders", "deletion_requests", "app_settings", "salon_settings"
        ]
        counts = {}
        for tbl in tables:
            try:
                row = cur.execute(f"SELECT COUNT(*) as c FROM {tbl}").fetchone()
                counts[tbl] = row["c"] if row else 0
            except Exception:
                counts[tbl] = 0
        conn.close()
        return counts

    def add_audit_log(self, admin_user, action, target, details=""):
        try:
            raw = self.get_setting("admin_audit_log", "[]")
            logs = json.loads(raw) if raw else []
            if not isinstance(logs, list):
                logs = []
            entry = {
                "timestamp": int(datetime.now().timestamp()),
                "admin": admin_user,
                "action": action,
                "target": str(target),
                "details": str(details),
            }
            logs.insert(0, entry)
            logs = logs[:100]
            self.set_setting("admin_audit_log", json.dumps(logs))
            return True
        except Exception:
            return False

    def get_audit_logs(self, limit=50):
        try:
            raw = self.get_setting("admin_audit_log", "[]")
            logs = json.loads(raw) if raw else []
            if not isinstance(logs, list):
                return []
            return logs[:limit]
        except Exception:
            return []


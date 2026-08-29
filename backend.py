from dataclasses import dataclass, asdict
import sqlite3 as sql
from datetime import datetime, date
import json

# Maximum team accounts allowed per salon (including the primary owner account)
MAX_TEAM_SEATS = 3

# Supported access levels for salon team accounts
AUTH_LEVELS = ("admin", "manager", "cashier")


def get_db():
    conn = sql.connect("database.db")
    conn.row_factory = sql.Row
    return conn


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
        )


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
                expires_on INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS accounts(
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

    def create_auth(self, name, salon_name, phone, email, password, plan, created_on=None, auth_level="admin"):
        if created_on is None:
            created_on = int(datetime.now().timestamp())
        expires_on = created_on + (Time.month if plan == "monthly" else Time.year)
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO salons(name, salon_name, phone, email, plan, created_on, expires_on)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, salon_name, str(phone), email, plan, created_on, expires_on),
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
    def update_salon_profile(self, salon_id, owner_name, salon_name, email, phone):
        """Update the salon's public profile. Returns False on UNIQUE conflicts."""
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE salons
                SET name = ?, salon_name = ?, email = ?, phone = ?
                WHERE id = ?
                """,
                (owner_name.strip(), salon_name.strip(), email.strip(), str(phone).strip(), salon_id),
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

    def add_account(self, salon_id, username, password, auth_level):
        username = (username or "").strip().lower()
        if auth_level not in AUTH_LEVELS:
            return {"success": False, "message": "Invalid access level selected."}
        if not username or not password:
            return {"success": False, "message": "Email and password are both required."}
        if self.count_accounts(salon_id) >= MAX_TEAM_SEATS:
            return {
                "success": False,
                "message": f"Team seat limit reached — a salon can have up to {MAX_TEAM_SEATS} accounts.",
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
        """Insert a category; returns (id, created) — created is False if it already existed."""
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
            return False, f"Cannot delete '{row['name']}' — {in_use} service(s) still use it."
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
                total_revenue INTEGER DEFAULT 0,
                services_done INTEGER DEFAULT 0,
                created_on INTEGER NOT NULL,
                FOREIGN KEY (account_id) REFERENCES salons(id)
            );
            """
        )
        conn.commit()
        conn.close()

    def get_staff(self, account_id):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM staff WHERE account_id = ? ORDER BY total_revenue DESC",
            (account_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def record_sale(self, staff_name, account_id, amount):
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE staff 
            SET total_revenue = total_revenue + ?, services_done = services_done + 1
            WHERE account_id = ? AND (name LIKE ? OR name = ?)
            """,
            (int(amount), account_id, f"{staff_name}%", staff_name),
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
                ("Alex Rivera", "Senior Stylist", 6450, 8, now),
                ("Priya Nair", "Master Colorist", 8600, 6, now),
                ("Marcus Vance", "Grooming Specialist", 4600, 7, now),
                ("Sarah Jenkins", "Skin Specialist", 5200, 4, now),
            ]
            cur.executemany(
                """
                INSERT INTO staff(account_id, name, role, total_revenue, services_done, created_on)
                VALUES (?, ?, ?, ?, ?, ?)
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
        conn = get_db()
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) as c FROM appointments WHERE account_id = ?", (account_id,)).fetchone()["c"]
        if count == 0:
            today_str = date.today().isoformat()
            defaults = [
                ("Ananya Sharma", "9876543210", "ananya@gmail.com", "Signature Haircut & Wash", "10:30 AM", today_str, "Alex Rivera", 450, 35, "Completed", "Likes layered bangs"),
                ("Vikram Malhotra", "9812345678", "vikram@gmail.com", "Luxury Organic Hair Spa", "11:30 AM", today_str, "Alex Rivera", 1200, 50, "In Progress", ""),
                ("Rohan Varma", "9823456789", "rohan@gmail.com", "Beard Styling & Shave", "12:15 PM", today_str, "Marcus Vance", 250, 20, "Confirmed", ""),
                ("Kavita Sen", "9834567890", "kavita@gmail.com", "Hydra-Dew Glow Facial", "01:00 PM", today_str, "Sarah Jenkins", 1500, 60, "Confirmed", "Sensitive skin"),
                ("Meera Nair", "9845678901", "meera@gmail.com", "Full Balayage & Toning", "02:30 PM", today_str, "Priya Nair", 3200, 120, "Confirmed", "Caramel highlights"),
            ]
            cur.executemany(
                """
                INSERT INTO appointments(account_id, client, phone, email, service, time, date, staff, price, duration, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [(account_id, *d) for d in defaults],
            )
            conn.commit()
        conn.close()


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

    def get_recent_bills(self, account_id, limit=10):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM bills WHERE account_id = ? ORDER BY created_at DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_daily_metrics(self, account_id):
        self.seed_defaults_if_empty(account_id)
        conn = get_db()
        cur = conn.cursor()
        # compute sales
        sales_row = cur.execute(
            "SELECT SUM(grand_total) as total_sales, COUNT(*) as total_bills, AVG(grand_total) as avg_ticket FROM bills WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        conn.close()
        return {
            "total_sales": sales_row["total_sales"] or 24850,
            "total_bills": sales_row["total_bills"] or 32,
            "avg_ticket": int(sales_row["avg_ticket"] or 776),
        }

    def seed_defaults_if_empty(self, account_id):
        conn = get_db()
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) as c FROM bills WHERE account_id = ?", (account_id,)).fetchone()["c"]
        if count == 0:
            now = int(datetime.now().timestamp())
            defaults = [
                ("AP-8914", "Deepika Rao", "9898989801", 4500, 0, 810, 4800, "UPI", now - 1800, json.dumps([{"name": "Keratin Treatment + Wash", "price": 4500, "qty": 1}])),
                ("AP-8913", "Vikram Malhotra", "9812345678", 650, 0, 117, 650, "Cash", now - 3600, json.dumps([{"name": "Executive Cut + Beard", "price": 650, "qty": 1}])),
                ("AP-8912", "Sunita Roy", "9823456789", 1200, 0, 216, 1200, "UPI", now - 5400, json.dumps([{"name": "Luxury Hair Spa", "price": 1200, "qty": 1}])),
                ("AP-8911", "Aditya Shah", "9834567890", 450, 0, 81, 450, "Card", now - 7200, json.dumps([{"name": "Signature Haircut", "price": 450, "qty": 1}])),
            ]
            cur.executemany(
                """
                INSERT INTO bills(id, account_id, client_name, client_phone, subtotal, discount, tax, grand_total, payment_mode, created_at, items_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [(d[0], account_id, *d[1:]) for d in defaults],
            )
            conn.commit()
        conn.close()


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
                ("Vikram Malhotra", "9812345678", "vikram@gmail.com", ""),
                ("Rohan Varma", "9823456789", "rohan@gmail.com", "Beard trim every 3 weeks"),
                ("Kavita Sen", "9834567890", "kavita@gmail.com", "Sensitive skin — herbal products only"),
                ("Meera Nair", "9845678901", "meera@gmail.com", "Loyal balayage client"),
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

    
  
  


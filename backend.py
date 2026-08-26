from dataclasses import dataclass, asdict
import sqlite3 as sql
from datetime import datetime, date
import json

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

    
  
  


"""
Database seeder for AuraPOS PostgreSQL database.

Usage:
    python seed.py
"""

import os
import sys
import time
import random
from datetime import datetime, timedelta
import json
import psycopg2

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")

def seed_database(include_demo_transactions=True):
    print(f"[SEED] Connecting to {DATABASE_URL}...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
    except Exception as e:
        print(f"[ERROR] Could not connect to PostgreSQL: {e}")
        sys.exit(1)

    now = int(time.time())
    one_year_later = now + 365 * 24 * 3600

    print("[SEED] Resetting database tables...")
    cur.execute("""
        TRUNCATE public.salon_settings, public.app_settings, public.customers,
                 public.bills, public.appointments, public.staff, public.services,
                 public.categories, public.deletion_requests, public.subscriptions,
                 public.pendingorders, public.accounts, public.salons
        RESTART IDENTITY CASCADE;
    """)

    # 1. Primary Salon
    print("[SEED] Seeding primary salon (Aura Studio Elite)...")
    opening_hours = json.dumps({
        "monday": {"open": "09:00", "close": "21:00", "isOpen": True},
        "tuesday": {"open": "09:00", "close": "21:00", "isOpen": True},
        "wednesday": {"open": "09:00", "close": "21:00", "isOpen": True},
        "thursday": {"open": "09:00", "close": "21:00", "isOpen": True},
        "friday": {"open": "09:00", "close": "21:00", "isOpen": True},
        "saturday": {"open": "09:00", "close": "21:00", "isOpen": True},
        "sunday": {"open": "10:00", "close": "18:00", "isOpen": False},
    })

    cur.execute("""
        INSERT INTO public.salons (id, name, phone, salon_name, email, created_on, plan, expires_on, billing_cycle, address, opening_hours, latitude, longitude)
        OVERRIDING SYSTEM VALUE
        VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Salon Owner", "9876543210", "Aura Studio Elite", "admin@aurasalon.com", now, "studio", one_year_later, "yearly", "402 High Street Mall, Indiranagar, Bengaluru", opening_hours, 12.9716, 77.5946))

    salon_id = cur.fetchone()[0]

    # 2. Admin Account
    print("[SEED] Seeding admin account (admin@aurasalon.com / password)...")
    cur.execute("""
        INSERT INTO public.accounts (id, auth_id, username, password, auth_level)
        OVERRIDING SYSTEM VALUE
        VALUES (1, %s, %s, %s, %s);
    """, (salon_id, "admin@aurasalon.com", "password", "admin"))

    # 3. Categories
    print("[SEED] Seeding 6 service categories...")
    categories = ["Haircuts", "Spa & Facial", "Hair Color", "Styling", "Treatments", "Bridal & Grooming"]
    for cat in categories:
        cur.execute("INSERT INTO public.categories (account_id, name, created_at) VALUES (%s, %s, %s);", (salon_id, cat, now))

    # 4. Services
    print("[SEED] Seeding 8 services...")
    services_data = [
        ("Signature Haircut & Wash", "Haircuts", 450, 35, "Alex Rivera", "Includes shampoo, customized hair wash, and blow dry finish.", "Any", 1),
        ("Women's Layer Cut & Blowdry", "Haircuts", 750, 45, "Alex Rivera", "Consultation, texture layering, and heat styling.", "Female", 1),
        ("Hydra-Dew Glow Facial", "Spa & Facial", 1500, 60, "Priya Nair", "Deep pore ultrasonic cleanse & hydration infusion.", "Any", 1),
        ("Luxury Organic Hair Spa", "Treatments", 1200, 50, "Priya Nair", "Scalp therapy, argan oil steam wrap & relaxing massage.", "Any", 1),
        ("Full Balayage & Toning", "Hair Color", 3200, 120, "Priya Nair", "Artisan hair painting with gloss and bond repair.", "Female", 1),
        ("Royal Beard Sculpt & Hot Towel", "Bridal & Grooming", 350, 25, "Marcus Vance", "Precision beard shaping with essential oils & hot towel steam.", "Male", 1),
        ("Keratin Smooth Treatment", "Treatments", 4500, 90, "Alex Rivera", "Formaldehyde-free protein smoothing with intense shine.", "Any", 1),
        ("Express Blowdry & Styling", "Styling", 500, 30, "Priya Nair", "Volume blowdry with heat protectant and styling spray.", "Any", 1),
    ]
    for name, cat, price, dur, staff_name, desc, gender, active in services_data:
        cur.execute("""
            INSERT INTO public.services (account_id, name, category, price, duration, staff, description, gender, active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (salon_id, name, cat, price, dur, staff_name, desc, gender, active, now))

    # 5. Staff
    print("[SEED] Seeding 3 staff members...")
    staff_members = [
        ("Alex Rivera", "Senior Stylist", "9811023456", "Male", "alex@aurasalon.in"),
        ("Priya Nair", "Master Colorist", "9822034567", "Female", "priya@aurasalon.in"),
        ("Marcus Vance", "Grooming Specialist", "9833045678", "Male", "marcus@aurasalon.in"),
    ]
    for name, role, phone, gender, email in staff_members:
        cur.execute("""
            INSERT INTO public.staff (account_id, name, role, phone, gender, email, total_revenue, services_done, created_on)
            VALUES (%s, %s, %s, %s, %s, %s, 0, 0, %s);
        """, (salon_id, name, role, phone, gender, email, now))

    # 6. Customers
    print("[SEED] Seeding 2 customers...")
    customer_data = [
        ("Ananya Sharma", "9876543210", "ananya@gmail.com", "Prefers weekend slots", now),
        ("Vikram Malhotra", "9812345678", "vikram@gmail.com", "Regular client", now),
    ]
    for name, phone, email, notes, c_at in customer_data:
        cur.execute("""
            INSERT INTO public.customers (account_id, name, phone, email, notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (salon_id, name, phone, email, notes, c_at))

    # 7. Settings
    print("[SEED] Seeding app & salon settings...")
    cur.execute("""
        INSERT INTO public.app_settings (key, value, updated_at)
        VALUES ('accepting_public', 'true', %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at;
    """, (now,))

    cur.execute("""
        INSERT INTO public.salon_settings (salon_id, payment_methods, created_at, updated_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (salon_id) DO UPDATE SET payment_methods = EXCLUDED.payment_methods, updated_at = EXCLUDED.updated_at;
    """, (salon_id, json.dumps({"upi": "aura.salon@okaxis", "card_terminal": "Razorpay Smart POS"}), now, now))

    # 8. Demo Transactions (~200 appointments & bills)
    if include_demo_transactions:
        print("[SEED] Generating ~200 realistic bills & appointments across past 35 days...")
        first_names = ['Rohan', 'Neha', 'Siddharth', 'Kavita', 'Aditya', 'Pooja', 'Rahul', 'Sneha', 'Manish', 'Meera', 'Arjun', 'Divya', 'Varun', 'Rhea', 'Karan', 'Shreya', 'Akash', 'Tanvi', 'Sameer', 'Ananya', 'Vikram', 'Ishita', 'Gaurav', 'Nandini', 'Amit', 'Deepika', 'Kunal', 'Simran', 'Nikhil', 'Tara', 'Rajesh', 'Sanjana']
        last_names = ['Kapoor', 'Mehta', 'Roy', 'Rao', 'Verma', 'Iyer', 'Joshi', 'Gupta', 'Nair', 'Reddy', 'Chopra', 'Saxena', 'Deshmukh', 'Singhania', 'Bhatia', 'Malhotra', 'Kulkarni', 'Menon', 'Aggarwal', 'Patel', 'Sen', 'Sharma', 'Mukherjee', 'Bose']
        time_slots = ['10:00 AM', '11:15 AM', '12:30 PM', '02:00 PM', '03:30 PM', '04:45 PM', '06:00 PM', '07:15 PM']
        payment_modes = ['UPI', 'Card', 'Cash']
        statuses = ['Completed', 'Completed', 'Completed', 'Confirmed', 'Confirmed']

        random.seed(42)
        staff_revenue = {s[0]: 0 for s in staff_members}
        staff_services = {s[0]: 0 for s in staff_members}

        bills_to_insert = []
        appts_to_insert = []

        for i in range(1, 201):
            days_ago = random.randint(0, 35)
            minute = random.choice([0, 15, 30, 45])
            event_dt = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 5), minutes=minute)
            ts = int(event_dt.timestamp())
            date_str = event_dt.strftime('%Y-%m-%d')
            time_str = random.choice(time_slots)

            client_fname = random.choice(first_names)
            client_lname = random.choice(last_names)
            client_name = f"{client_fname} {client_lname}"
            client_phone = f"98{random.randint(10000000, 99999999)}"
            client_email = f"{client_fname.lower()}.{client_lname.lower()}{random.randint(10,99)}@gmail.com"

            num_items = 1 if random.random() < 0.75 else 2
            selected_servs = random.sample(services_data, num_items)
            selected_staff = random.choice(staff_members)[0]

            subtotal = sum(s[2] for s in selected_servs)
            discount = random.choice([0, 0, 50, 100]) if subtotal > 1000 else 0
            tax = int(round((subtotal - discount) * 0.18)) if random.random() < 0.3 else 0
            grand_total = subtotal - discount + tax
            payment_mode = random.choice(payment_modes)

            items_json = json.dumps([{
                'name': s[0], 'category': s[1], 'price': s[2], 'qty': 1, 'staff': selected_staff
            } for s in selected_servs])

            bill_id = f"INV-2026-{1000 + i}"
            bills_to_insert.append((bill_id, salon_id, client_name, client_phone, subtotal, discount, tax, grand_total, payment_mode, ts, items_json))

            staff_revenue[selected_staff] += grand_total
            staff_services[selected_staff] += len(selected_servs)

            appt_status = 'Completed' if days_ago > 1 else random.choice(statuses)
            primary_serv = selected_servs[0]
            appts_to_insert.append((
                salon_id, client_name, client_phone, client_email,
                ' + '.join(s[0] for s in selected_servs),
                time_str, date_str, selected_staff, grand_total, primary_serv[3],
                appt_status, 'Booked via POS & Online Portal'
            ))

        cur.executemany("""
            INSERT INTO public.bills (id, account_id, client_name, client_phone, subtotal, discount, tax, grand_total, payment_mode, created_at, items_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, bills_to_insert)

        cur.executemany("""
            INSERT INTO public.appointments (account_id, client, phone, email, service, time, date, staff, price, duration, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, appts_to_insert)

        for staff_name, total_rev in staff_revenue.items():
            cur.execute("""
                UPDATE public.staff
                SET total_revenue = %s, services_done = %s
                WHERE account_id = %s AND name = %s;
            """, (total_rev, staff_services[staff_name], salon_id, staff_name))

    conn.commit()
    conn.close()
    print("[OK] PostgreSQL database seeded successfully with complete dataset & 200 demo transactions!")

if __name__ == "__main__":
    seed_database()

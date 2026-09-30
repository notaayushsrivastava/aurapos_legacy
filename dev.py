"""
Development runner for AuraPOS linked to local Supabase development setup.

Usage:
    python dev.py
"""

import os
import sys

# 0. Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 1. Configure Development Environment Variables
os.environ.setdefault("USE_POSTGRES", "1")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:54321")
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_N7UND0UgjKTVK-Uodkm0Hg_xSvEMPvz")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("FLASK_DEBUG", "1")

use_postgres = os.environ.get("USE_POSTGRES", "").strip().lower() in ("1", "true", "yes", "on")

print("=" * 65)
print("[DEV] AuraPOS Local Development Server (Local Supabase)")
print("=" * 65)
print(f"[DB] Database URL : {os.environ.get('DATABASE_URL')}")
print(f"[API] Supabase URL : {os.environ.get('SUPABASE_URL')}")
print(f"[MODE] Backend    : {'Direct PostgreSQL (backend.py)' if use_postgres else 'Supabase REST (supabase_backend.py)'}")

# 2. Test Connection & Auto-Verify Database
try:
    if use_postgres:
        import psycopg2
        from backend import (
            AuthorizationRepository, CategoryRepository, ServiceRepository,
            StaffRepository, AppointmentRepository, BillRepository, CustomerRepository
        )

        print("[DB] Connecting to local Supabase PostgreSQL database...")
        auth_repo = AuthorizationRepository()
        cat_repo = CategoryRepository()
        service_repo = ServiceRepository()
        staff_repo = StaffRepository()
        apt_repo = AppointmentRepository()
        bill_repo = BillRepository()
        cust_repo = CustomerRepository()

        # Seed default admin account if database is empty
        if not auth_repo.check_exists("admin@aurasalon.com", "9876543210"):
            print("[SEED] Seeding default salon & admin account...")
            auth_repo.create_auth(
                name="Salon Owner",
                salon_name="Aura Studio Elite",
                phone="9876543210",
                email="admin@aurasalon.com",
                password="password",
                plan="studio",
            )
            service_repo.seed_defaults_if_empty(1)
            staff_repo.seed_defaults_if_empty(1)
            cust_repo.seed_defaults_if_empty(1)
            print("[SEED] Default credentials: Username: admin@aurasalon.com | Password: password")

        print("[OK] Supabase PostgreSQL database is connected and ready!")
    else:
        from supabase_backend import AuthorizationRepository
        print("[DB] Verifying Supabase REST API connection...")
        auth_repo = AuthorizationRepository()
        salon = auth_repo.get_salon(1)
        if salon:
            print(f"[OK] Supabase REST connected! Loaded: {salon.salon_name}")
        else:
            print("[OK] Supabase REST connected! Database is ready.")

except Exception as err:
    print(f"[ERROR] Could not connect to database: {err}")
    print("[HINT] Ensure local Supabase is running with: npx supabase start")
    sys.exit(1)

# 3. Launch Flask App with Socket.IO Realtime Engine
from app import app, socketio

if __name__ == "__main__":
    print("-" * 65)
    print("[SERVER] Terminal starting with Socket.IO Realtime on http://localhost:5000")
    print("         Press CTRL+C to stop the development server.")
    print("-" * 65)
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)

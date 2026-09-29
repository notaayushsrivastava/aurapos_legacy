"""
Development runner for AuraPOS linked to local Docker PostgreSQL (Supabase simulation).

Usage:
    python dev.py
"""

import os
import sys

# 1. Configure PostgreSQL Environment Variables
os.environ["USE_POSTGRES"] = "1"
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/postgres")
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("FLASK_DEBUG", "1")

print("=" * 65)
print("[DEV] AuraPOS Local Development Server (Docker PostgreSQL)")
print("=" * 65)
print(f"[DB] Database URL : {os.environ['DATABASE_URL']}")

# 2. Test Connection & Auto-Migrate PostgreSQL Tables
try:
    import psycopg2
    from backend import (
        AuthorizationRepository, CategoryRepository, ServiceRepository,
        StaffRepository, AppointmentRepository, BillRepository, CustomerRepository
    )

    print("[DB] Connecting to Docker PostgreSQL server...")
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

    print("[OK] PostgreSQL database is connected, migrated, and ready!")

except Exception as err:
    print(f"[ERROR] Could not connect to PostgreSQL: {err}")
    print("[HINT] Please make sure Docker Desktop is unpaused and container 'supabase-postgres' is running on port 5433.")
    print("       To start container: docker start supabase-postgres")
    sys.exit(1)

# 3. Launch Flask App
from app import app

if __name__ == "__main__":
    print("-" * 65)
    print("[SERVER] Terminal starting on http://localhost:5000")
    print("         Press CTRL+C to stop the development server.")
    print("-" * 65)
    app.run(host="0.0.0.0", port=5000, debug=True)

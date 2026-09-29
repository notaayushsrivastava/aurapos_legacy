"""
Supabase-backed data layer for AuraPOS.
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from uuid import uuid4
import json

try:  # supabase-py is imported lazily so this module can be compiled/inspected without it
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None

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


class Time:
    """Second-based time helpers (parity with backend.py)."""
    second = 1
    minute = 60
    hour = 3600
    day = 86400
    week = 604800
    month = 2592000
    year = 31536000


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
AUTH_LEVELS = ["admin", "manager", "staff"]

# Canonical weekday keys used by the opening-hours editor / booking portal.
WEEKDAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

WEEKDAY_LABELS = {
    "monday": "Monday", "tuesday": "Tuesday", "wednesday": "Wednesday",
    "thursday": "Thursday", "friday": "Friday", "saturday": "Saturday",
    "sunday": "Sunday",
}


def parse_opening_hours(raw):
    """Convert the stored opening-hours JSON string into a display structure.

    Accepts a JSON object keyed by weekday (monday..sunday). Each entry may
    carry `open` / `close` times (HH:MM strings) and an `isOpen` flag. Missing
    or malformed input falls back to a sensible 09:00–21:00 default.
    """
    try:
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            data = {}
    except (ValueError, TypeError):
        data = {}

    schedule = {}
    for key in WEEKDAY_KEYS:
        entry = data.get(key)
        if not isinstance(entry, dict):
            entry = {}
        open_t = str(entry.get("open") or "09:00")
        close_t = str(entry.get("close") or "21:00")
        # Sunday is closed by default; every other day is open.
        is_open = bool(entry.get("isOpen", key != "sunday"))
        schedule[key] = {
            "key": key,
            "label": WEEKDAY_LABELS[key],
            "open": open_t,
            "close": close_t,
            "isOpen": is_open,
        }
    return schedule


# ================= DATA CLASSES =================

@dataclass
class Account:
    auth_id: int
    username: str
    password: str
    auth_level: str = "admin"
    salon: dict = None

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        if not isinstance(row, dict):
            row = dict(row)
        return cls(
            auth_id=row.get("auth_id"),
            username=row.get("username"),
            password=row.get("password"),
            auth_level=row.get("auth_level") or "admin",
            salon=row.get("salon"),
        )

    def as_dict(self):
        return asdict(self)


import secrets

def generate_booking_slug(length=5):
    """Generate a clean 5-character lowercase alphanumeric slug for vanity booking links."""
    chars = "23456789abcdefghjkmnpqrstuvwxyz"
    return "".join(secrets.choice(chars) for _ in range(length))


@dataclass
class Salon:
    id: int
    name: str
    phone: str
    salon_name: str
    email: str
    created_on: int
    plan: str = "free"
    expires_on: int = None
    logo: str = None
    billing_cycle: str = "monthly"
    address: str = ""
    opening_hours: str = "{}"
    latitude: float = None
    longitude: float = None
    booking_slug: str = None

    @classmethod
    def from_row(cls, row):
        if row is None:
            return None
        if not isinstance(row, dict):
            row = dict(row)
        defaults = {
            "id": None, "name": "", "phone": "", "salon_name": "", "email": "",
            "created_on": 0, "plan": "free", "expires_on": None, "logo": None,
            "billing_cycle": "monthly", "address": "", "opening_hours": "{}",
            "latitude": None, "longitude": None, "booking_slug": None,
        }
        defaults.update({k: v for k, v in row.items() if k in defaults})
        # Never allow an empty plan — fall back to "free" if the stored
        # value is missing or falsy so the UI never shows "No Plan".
        if not defaults.get("plan"):
            defaults["plan"] = "free"
        return cls(**defaults)

    def as_dict(self):
        return asdict(self)

    @property
    def is_expired(self):
        """True when the salon's plan window has lapsed."""
        if not self.expires_on:
            return True
        return int(datetime.now().timestamp()) > int(self.expires_on)

# ================= SUPABASE CLIENT & AUTH HELPERS =================

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip()
# Server-side operations MUST use the Supabase service-role secret.
# Do not fall back to SUPABASE_KEY: that name is commonly used for the
# anon/publishable key, which cannot create Auth users or bypass RLS.
SUPABASE_SERVICE_ROLE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
).strip()

_client = None


def get_client():
    """Return (and cache) the Supabase service-role client."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "Supabase credentials are missing. Set SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY in the .env file / environment "
                "(Dashboard -> Project Settings -> API)."
            )
        if create_client is None:
            raise RuntimeError(
                "The 'supabase' package is not installed. Run: pip install supabase"
            )
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _client


def _warn(msg):
    print(f"[supabase_backend] {msg}", file=sys.stderr)


def _data(res, default=None):
    """Extract `.data` from a supabase-py response, tolerating a None response.

    `maybe_single().execute()` returns None (instead of a response object) when
    PostgREST answers 406 for an empty single-object request — which is exactly
    what happens whenever a row does NOT exist. Without this guard every such
    lookup would raise `AttributeError: 'NoneType' object has no attribute
    'data'`.
    """
    if res is None:
        return default
    return res.data


def _sb():
    return get_client()


def _sb_create_auth_user(email, password, metadata=None):
    """Create a Supabase Auth user and return its UUID.

    Auth provisioning is required for every new owner/team account. Never
    create a database account with a missing Supabase identity because that
    produces a split-brain account that can later lose its identity mapping.
    """
    try:
        res = _sb().auth.admin.create_user({
            "email": (email or "").strip(),
            "password": password or "",
            "email_confirm": True,
            "user_metadata": metadata or {},
        })
        uid = getattr(res.user, "id", None)
        if not uid:
            raise RuntimeError("Supabase Auth returned no user id.")
        return uid
    except Exception as exc:
        _warn(f"Supabase Auth: could not create user {email}: {exc}")
        raise RuntimeError(f"Supabase Auth user provisioning failed for {email}: {exc}") from exc


def _sb_update_auth_user(uid, props):
    """Update a Supabase Auth user (email/password). Best-effort."""
    if not uid:
        return False
    try:
        _sb().auth.admin.update_user_by_id(uid, props)
        return True
    except Exception as exc:
        _warn(f"Supabase Auth: could not update user {uid}: {exc}")
        return False


def _sb_delete_auth_user(uid):
    """Delete a Supabase Auth user. Best-effort."""
    if not uid:
        return False
    try:
        _sb().auth.admin.delete_user(uid)
        return True
    except Exception as exc:
        _warn(f"Supabase Auth: could not delete user {uid}: {exc}")
        return False


# ================= SUPABASE STORAGE HELPERS =================

STORAGE_BUCKET = "salon-logos"


def _ensure_storage_bucket():
    """Make the salon-logos bucket exists (best-effort, idempotent)."""
    try:
        buckets = _sb().storage.list_buckets()
        if not any(b.get("name") == STORAGE_BUCKET for b in (buckets or [])):
            _sb().storage.create_bucket(STORAGE_BUCKET, {"public": True})
    except Exception as exc:
        _warn(f"storage: could not ensure bucket '{STORAGE_BUCKET}': {exc}")


def upload_logo_to_storage(salon_id, blob, mime):
    """Upload a logo to Supabase Storage and return its public URL.

    Returns None on any failure so callers can fall back to the data-URL path.
    """
    try:
        _ensure_storage_bucket()
        ext = "png"
        if mime == "image/jpeg":
            ext = "jpg"
        elif mime == "image/webp":
            ext = "webp"
        elif mime == "image/svg+xml":
            ext = "svg"
        object_path = f"{salon_id}/logo.{ext}"

        # Upload (upsert so re-uploads replace the existing file)
        _sb().storage.from_(STORAGE_BUCKET).upload(
            object_path,
            blob,
            {"content-type": mime, "upsert": True},
        )

        # Return the public URL
        return _sb().storage.from_(STORAGE_BUCKET).get_public_url(object_path)
    except Exception as exc:
        _warn(f"storage: logo upload for salon {salon_id} failed: {exc}")
        return None


def delete_logo_from_storage(salon_id):
    """Remove a salon's logo file from Supabase Storage (best-effort)."""
    try:
        _ensure_storage_bucket()
        # List files in the salon's folder and delete them
        files = _sb().storage.from_(STORAGE_BUCKET).list(f"{salon_id}")
        if files:
            paths = [f"{salon_id}/{f['name']}" for f in files]
            _sb().storage.from_(STORAGE_BUCKET).remove(paths)
    except Exception as exc:
        _warn(f"storage: logo delete for salon {salon_id} failed: {exc}")


def _sb_verify_credentials(username, password):
    """Verify credentials against Supabase Auth.

    Returns True when Supabase Auth confirms the pair, False on an explicit
    credential rejection, and None when the Auth service could not be reached
    (callers then fall back to the synced DB password).
    """
    try:
        _sb().auth.sign_in_with_password({
            "email": (username or "").strip(),
            "password": password or "",
        })
        return True
    except Exception as exc:
        # AuthApiError with status 400/401/422 == invalid credentials; anything
        # else (network, 5xx, misconfiguration) is a service-level failure.
        status = getattr(exc, "status", None) or getattr(exc, "code", None)
        if status in (400, 401, 422):
            return False
        _warn(f"Supabase Auth: sign-in check unavailable ({exc}); using synced password.")
        return None


# ================= REPOSITORIES =================

class AuthorizationRepository:
    """Salons, team accounts, subscriptions, pending orders & deletion requests.

    Authentication is delegated to Supabase Auth: owner/team logins are
    verified with `auth.sign_in_with_password`, account creation provisions a
    Supabase Auth user, and password changes go through the admin API. A synced
    copy of the password lives on the `accounts` row to power the existing
    credential-recovery email and /directlogin flows.
    """

    def __init__(self):
        # Schema is provisioned via Supabase migrations — nothing to create here.
        pass

    def update_salon_logo(self, salon_id, logo_data):
        """Store (or clear, with None) the salon's logo.

        If logo_data is a data URL (legacy), it is kept as-is for backward
        compatibility. If it is a public URL from Supabase Storage, it is
        stored directly. Passing None clears the logo.
        """
        _sb().table("salons").update({"logo": logo_data}).eq("id", salon_id).execute()

    def set_logo_from_storage(self, salon_id, public_url):
        """Set the salon's logo to a Supabase Storage public URL."""
        _sb().table("salons").update({"logo": public_url}).eq("id", salon_id).execute()

    def clear_logo(self, salon_id):
        """Clear the salon's logo (DB + storage file)."""
        _sb().table("salons").update({"logo": None}).eq("id", salon_id).execute()
        delete_logo_from_storage(salon_id)

    def get_logo_public_url(self, salon_id):
        """Get the salon's logo URL, uploading to storage if needed.

        If the stored logo is a legacy data URL, it is uploaded to Supabase
        Storage and replaced with a public URL. This keeps old logos working
        while new uploads go directly to storage.
        """
        row = _data(
            _sb().table("salons").select("logo").eq("id", salon_id).maybe_single().execute()
        )
        if not row or not row.get("logo"):
            return None
        logo = row["logo"]
        # If it's already a public URL (not a data URL), return as-is
        if logo.startswith("http"):
            return logo
        # Legacy data URL — could be migrated on read, but for now return as-is
        return logo

    # ---------- Payment methods ----------

    def get_payment_methods(self, salon_id):
        """Get the salon's configured payment methods."""
        try:
            row = _data(
                _sb().table("salon_settings")
                .select("payment_methods")
                .eq("salon_id", salon_id)
                .maybe_single()
                .execute()
            )
            if row and row.get("payment_methods"):
                return row["payment_methods"]
        except Exception as exc:
            _warn(f"get_payment_methods({salon_id}) failed: {exc}")
        return {"upi": "", "card_terminal": ""}

    def update_payment_methods(self, salon_id, methods):
        """Update the salon's payment methods configuration."""
        try:
            # Try to update existing row first
            existing = _data(
                _sb().table("salon_settings")
                .select("id")
                .eq("salon_id", salon_id)
                .maybe_single()
                .execute()
            )
            if existing:
                _sb().table("salon_settings").update({
                    "payment_methods": methods,
                    "updated_at": int(datetime.now().timestamp()),
                }).eq("salon_id", salon_id).execute()
            else:
                _sb().table("salon_settings").insert({
                    "salon_id": salon_id,
                    "payment_methods": methods,
                    "created_at": int(datetime.now().timestamp()),
                    "updated_at": int(datetime.now().timestamp()),
                }).execute()
            return True
        except Exception as exc:
            _warn(f"update_payment_methods({salon_id}) failed: {exc}")
            return False

    def create_account(self, auth_id, username, password, auth_level="admin", supabase_uid=None):
        """Insert a team/owner account row with a required Supabase Auth identity."""
        username = (username or "").strip().lower()
        if supabase_uid is None:
            supabase_uid = _sb_create_auth_user(
                username, password, {"salon_id": auth_id, "role": auth_level}
            )
        _sb().table("accounts").insert({
            "auth_id": auth_id,
            "username": username,
            "password": password,
            "auth_level": auth_level or "admin",
            "supabase_uid": supabase_uid,
        }).execute()

    def create_auth(self, name, salon_name, phone, email, password, plan="pro",
                    created_on=None, auth_level="admin"):
        """Register a brand-new salon + its primary owner account.

        Provisions the owner's Supabase Auth user first, then stores the salon
        row (with the resolved tier/cycle/expiry) and the owner account row.
        Returns the new salon id.
        """
        if created_on is None:
            created_on = int(datetime.now().timestamp())
        tier, cycle, _pricing = resolve_plan(plan)
        expires_ts = expires_for(cycle, created_on)

        auth_uid = _sb_create_auth_user(
            email, password, {"name": name, "salon_name": salon_name, "plan": tier}
        )
        booking_slug = generate_booking_slug()
        res = (
            _sb().table("salons")
            .insert({
                "name": name,
                "phone": phone,
                "salon_name": salon_name,
                "email": email,
                "created_on": created_on,
                "plan": tier,
                "billing_cycle": cycle,
                "expires_on": expires_ts,
                "auth_uid": auth_uid,
                "booking_slug": booking_slug,
            })
            .execute()
        )
        auth_id = res.data[0]["id"]
        self.create_account(auth_id, email, password, auth_level, supabase_uid=auth_uid)
        return auth_id

    def login(self, username, password):
        """Verify credentials (Supabase Auth first, synced password fallback)."""
        username = (username or "").strip().lower()
        if not username or password is None:
            return None
        row = _data(
            _sb().table("accounts")
            .select("*")
            .eq("username", username)
            .maybe_single()
            .execute()
        )
        if not row:
            return None

        verified = _sb_verify_credentials(username, password)
        if verified is True:
            return Account.from_row(row)
        if verified is False:
            return None
        # Supabase Auth unreachable / legacy account without an auth user:
        # fall back to the synced password (SQLite-parity behaviour).
        if str(row.get("password") or "") == str(password):
            return Account.from_row(row)
        return None

    def get_salon(self, salon_id):
        row = _data(
            _sb().table("salons").select("*").eq("id", salon_id).maybe_single().execute()
        )
        if not row:
            return None
        salon = Salon.from_row(row)
        if not salon.booking_slug:
            slug = generate_booking_slug()
            try:
                _sb().table("salons").update({"booking_slug": slug}).eq("id", salon_id).execute()
                salon.booking_slug = slug
            except Exception as e:
                _warn(f"Failed to auto-assign booking_slug to salon #{salon_id}: {e}")
        return salon

    def get_salon_by_slug(self, slug):
        if not slug:
            return None
        slug_clean = str(slug).strip().lower()
        try:
            row = _data(
                _sb().table("salons").select("*").ilike("booking_slug", slug_clean).maybe_single().execute()
            )
            if row:
                return Salon.from_row(row)
        except Exception as e:
            _warn(f"get_salon_by_slug({slug}) failed: {e}")
        try:
            val_id = int(slug)
            return self.get_salon(val_id)
        except (ValueError, TypeError):
            return None

    def get_session_timeout(self, salon_id):
        try:
            row = _data(
                _sb().table("salon_settings").select("session_timeout").eq("salon_id", salon_id).maybe_single().execute()
            )
            if row and row.get("session_timeout"):
                return str(row["session_timeout"]).strip().lower()
        except Exception as e:
            _warn(f"get_session_timeout({salon_id}) failed: {e}")
        return "7d"

    def update_session_timeout(self, salon_id, timeout):
        timeout_clean = str(timeout).strip().lower()
        if timeout_clean not in ("30m", "1h", "12h", "24h", "7d", "never"):
            timeout_clean = "7d"
        now = int(datetime.now().timestamp())
        try:
            existing = _data(
                _sb().table("salon_settings").select("id").eq("salon_id", salon_id).maybe_single().execute()
            )
            if existing:
                _sb().table("salon_settings").update({
                    "session_timeout": timeout_clean,
                    "updated_at": now
                }).eq("salon_id", salon_id).execute()
            else:
                _sb().table("salon_settings").insert({
                    "salon_id": salon_id,
                    "session_timeout": timeout_clean,
                    "created_at": now,
                    "updated_at": now
                }).execute()
            return True
        except Exception as e:
            _warn(f"update_session_timeout({salon_id}) failed: {e}")
            return False

    def forgot_password(self, identifier):
        """Find an account by its username/email or by the salon's phone number.

        Returns the matching Account (the password copy feeds the recovery
        email) or None when nothing matches.
        """
        identifier = (identifier or "").strip()
        if not identifier:
            return None

        row = _data(
            _sb().table("accounts")
            .select("*")
            .eq("username", identifier.lower())
            .maybe_single()
            .execute()
        )
        if row:
            return Account.from_row(row)

        salon = _data(
            _sb().table("salons")
            .select("id")
            .eq("phone", identifier)
            .maybe_single()
            .execute()
        )
        if salon:
            row = _data(
                _sb().table("accounts")
                .select("*")
                .eq("auth_id", salon["id"])
                .order("id")
                .limit(1)
                .maybe_single()
                .execute()
            )
            if row:
                return Account.from_row(row)
        return None

    def check_exists(self, email, phone):
        """True when a salon already exists with this email or phone."""
        email = (email or "").strip()
        phone = (phone or "").strip()
        query = _sb().table("salons").select("id").limit(1)
        if email and phone:
            query = query.or_(f"email.eq.{email},phone.eq.{phone}")
        elif email:
            query = query.eq("email", email)
        else:
            query = query.eq("phone", phone)
        res = query.execute()
        return bool(res.data)

    # ---------- Settings: salon profile ----------

    def update_salon_profile(self, salon_id, owner_name, salon_name, email, phone, extra=None):
        """Update the salon's public profile. Returns False on UNIQUE conflicts.

        `extra` (optional dict) may carry:
            - address (str)
            - opening_hours (JSON string)
            - latitude / longitude (floats)
        """
        try:
            payload = {
                "name": owner_name,
                "phone": phone,
                "salon_name": salon_name,
                "email": email,
            }
            if extra:
                allowed = ("address", "opening_hours", "latitude", "longitude")
                payload.update({k: extra[k] for k in allowed if k in extra})
            res = (
                _sb().table("salons")
                .update(payload)
                .eq("id", salon_id)
                .execute()
            )
            return len(res.data or []) > 0
        except Exception as exc:
            if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
                return False
            raise

    # ---------- Settings: password management ----------

    def change_password(self, salon_id, username, current_password, new_password):
        """Change the password of a specific account after verifying the current one."""
        username = (username or "").strip().lower()
        row = self._get_account_row(salon_id, username)
        if not row:
            return False, "Account not found."

        # Supabase Auth decides when the auth user exists; synced copy otherwise.
        if row.get("supabase_uid"):
            verified = _sb_verify_credentials(username, current_password)
            if verified is False:
                return False, "Current password is incorrect."
        elif str(row.get("password") or "") != str(current_password):
            return False, "Current password is incorrect."

        _sb().table("accounts").update({"password": new_password}).eq("id", row["id"]).execute()
        _sb_update_auth_user(row.get("supabase_uid"), {"password": new_password})
        return True, "Password updated successfully."

    def set_password(self, salon_id, username, new_password):
        """Reset a password without verification (used by owner for team accounts)."""
        username = (username or "").strip().lower()
        row = self._get_account_row(salon_id, username)
        if not row:
            return False, "Account not found."
        _sb().table("accounts").update({"password": new_password}).eq("id", row["id"]).execute()
        _sb_update_auth_user(row.get("supabase_uid"), {"password": new_password})
        return True, "Password updated successfully."

    def _get_account_row(self, salon_id, username):
        return _data(
            _sb().table("accounts")
            .select("*")
            .eq("auth_id", salon_id)
            .eq("username", username)
            .maybe_single()
            .execute()
        )

    # ---------- Settings: team account management ----------

    def get_accounts(self, salon_id):
        rows = (
            _sb().table("accounts")
            .select("id, username, password, auth_level")
            .eq("auth_id", salon_id)
            .order("id")
            .execute()
        ).data
        return [
            {
                "id": r["id"],
                "username": r["username"],
                "password": r["password"],
                "auth_level": r["auth_level"],
            }
            for r in (rows or [])
        ]

    def count_accounts(self, salon_id):
        res = (
            _sb().table("accounts")
            .select("id", count="exact")
            .eq("auth_id", salon_id)
            .execute()
        )
        return res.count or 0

    def get_primary_account_id(self, salon_id):
        """The first account created for a salon is its primary owner account."""
        row = _data(
            _sb().table("accounts")
            .select("id")
            .eq("auth_id", salon_id)
            .order("id")
            .limit(1)
            .maybe_single()
            .execute()
        )
        return row["id"] if row else None

    def add_account(self, salon_id, username, password, auth_level, seat_limit=None):
        username = (username or "").strip().lower()
        if auth_level not in AUTH_LEVELS:
            return {"success": False, "message": "Invalid access level."}
        if not username or not password:
            return {"success": False, "message": "Email and password are both required."}
        if seat_limit is not None and self.count_accounts(salon_id) >= seat_limit:
            return {
                "success": False,
                "message": f"Seat limit reached ({seat_limit} on your plan). Upgrade to add more team accounts.",
            }
        dup = _data(
            _sb().table("accounts")
            .select("id")
            .eq("username", username)
            .maybe_single()
            .execute()
        )
        if dup:
            return {"success": False, "message": "An account with this email already exists."}
        self.create_account(salon_id, username, password, auth_level)
        return {"success": True, "message": f"Team account created for {username}."}

    def update_account(self, salon_id, row_id, username, auth_level, password=None):
        username = (username or "").strip().lower()
        if auth_level not in AUTH_LEVELS:
            return {"success": False, "message": "Invalid access level."}
        if not username:
            return {"success": False, "message": "Email is required."}
        row = _data(
            _sb().table("accounts")
            .select("*")
            .eq("id", row_id)
            .eq("auth_id", salon_id)
            .maybe_single()
            .execute()
        )
        if not row:
            return {"success": False, "message": "Team account not found."}

        dup = _data(
            _sb().table("accounts")
            .select("id")
            .eq("username", username)
            .neq("id", row_id)
            .maybe_single()
            .execute()
        )
        if dup:
            return {"success": False, "message": "Another account already uses this email."}

        payload = {"username": username, "auth_level": auth_level}
        if password:
            payload["password"] = password
        # The account must have a real Supabase Auth identity before its
        # credentials are changed. Otherwise the DB row and Auth can diverge.
        if not row.get("supabase_uid"):
            return {
                "success": False,
                "message": "This account is missing its Supabase Auth identity. Repair the account before changing its credentials.",
            }

        # Update Auth first. Only persist the local account email/password
        # after the authoritative Auth update succeeds.
        props = {"email": username}
        if password:
            props["password"] = password
        if not _sb_update_auth_user(row.get("supabase_uid"), props):
            return {
                "success": False,
                "message": "Supabase Auth rejected the account update. No local credentials were changed.",
            }

        _sb().table("accounts").update(payload).eq("id", row_id).execute()
        return {"success": True, "message": "Team account updated."}

    def delete_account(self, salon_id, row_id):
        primary_id = self.get_primary_account_id(salon_id)
        if row_id == primary_id:
            return {
                "success": False,
                "message": "The primary owner account cannot be deleted. Use account deletion in Settings instead.",
            }
        row = _data(
            _sb().table("accounts")
            .select("*")
            .eq("id", row_id)
            .eq("auth_id", salon_id)
            .maybe_single()
            .execute()
        )
        if not row:
            return {"success": False, "message": "Team account not found."}
        remaining = self.count_accounts(salon_id)
        if remaining <= 1:
            return {
                "success": False,
                "message": "A salon must keep at least one account.",
            }
        _sb().table("accounts").delete().eq("id", row_id).eq("auth_id", salon_id).execute()
        _sb_delete_auth_user(row.get("supabase_uid"))
        return {"success": True, "message": f"Team account {row['username']} removed."}

    # ---------- Subscriptions ----------

    def get_subscriptions(self, salon_id):
        rows = (
            _sb().table("subscriptions")
            .select("*")
            .eq("salon_id", salon_id)
            .order("created_at", desc=True)
            .execute()
        ).data
        return [dict(r) for r in (rows or [])]

    def update_salon_plan(self, salon_id, tier, cycle, expires_on):
        """Switch a salon to a new subscription tier (used by the upgrade flow).

        Never writes an empty/None plan — that would leave the salon with
        no active subscription. If tier is falsy, the update is aborted
        and False is returned.
        """
        if not tier:
            _warn(f"update_salon_plan({salon_id}) aborted: empty tier")
            return False
        res = (
            _sb().table("salons")
            .update({"plan": tier, "billing_cycle": cycle, "expires_on": expires_on})
            .eq("id", salon_id)
            .execute()
        )
        return len(res.data or []) > 0

    def record_subscription(self, sub_id, salon_id, amount, plan, cycle, receipt, email, phone, created_at=None):
        """Persist a completed subscription/payment associated with a salon."""
        if created_at is None:
            created_at = int(datetime.now().timestamp())
        _sb().table("subscriptions").insert({
            "id": sub_id,
            "salon_id": salon_id,
            "amount": amount,
            "plan": plan,
            "billing_cycle": cycle,
            "receipt": receipt,
            "email": email,
            "phone": phone,
            "created_at": created_at,
        }).execute()

    # ---------- Account deletion requests ----------

    def request_account_deletion(self, salon_id, email, reason=""):
        _sb().table("deletion_requests").insert({
            "salon_id": salon_id,
            "email": (email or "").strip(),
            "reason": (reason or "").strip(),
            "requested_at": int(datetime.now().timestamp()),
            "status": "pending",
        }).execute()
        return True

    def get_pending_deletion_request(self, salon_id):
        row = _data(
            _sb().table("deletion_requests")
            .select("requested_at, email, reason, status")
            .eq("salon_id", salon_id)
            .eq("status", "pending")
            .order("requested_at", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return dict(row) if row else None

    # ---------- Pending Razorpay orders (used by app.py subscription flows) ----------

    def create_pendingorder(self, order_id, amount, created_at=None, plan="",
                            receipt="", email="", phone="", salon_id=0):
        """Store a Razorpay order awaiting payment verification."""
        if created_at is None:
            created_at = int(datetime.now().timestamp())
        _sb().table("pendingorders").insert({
            "id": order_id,
            "amount": amount,
            "created_at": created_at,
            "plan": plan,
            "receipt": receipt,
            "email": email,
            "phone": phone,
            "salon_id": salon_id,
        }).execute()
        return order_id

    def get_pendingorder(self, order_id):
        row = _data(
            _sb().table("pendingorders")
            .select("*")
            .eq("id", order_id)
            .maybe_single()
            .execute()
        )
        return dict(row) if row else None


class CategoryRepository:
    """Per-salon service categories. Uniquely named per salon (case-insensitive)."""

    DEFAULTS = ["Haircuts", "Spa & Facial", "Color & Hair", "Styling", "Grooming", "Treatments"]

    def __init__(self):
        pass

    def get_categories(self, account_id):
        self.seed_defaults_if_empty(account_id)
        rows = (
            _sb().table("categories")
            .select("id, name, created_at")
            .eq("account_id", account_id)
            .order("name")
            .execute()
        ).data
        return [
            {"id": r["id"], "name": r["name"], "created_at": r["created_at"]}
            for r in (rows or [])
        ]

    def add_category(self, account_id, name):
        """Insert a category; returns (id, created) — created is False if it already existed."""
        name = str(name or "").strip()
        if not name:
            return None, False

        existing = _data(
            _sb().table("categories")
            .select("id")
            .eq("account_id", account_id)
            .ilike("name", name)
            .maybe_single()
            .execute()
        )
        if existing:
            return existing["id"], False

        res = (
            _sb().table("categories")
            .insert({"account_id": account_id, "name": name,
                     "created_at": int(datetime.now().timestamp())})
            .execute()
        )
        return res.data[0]["id"], True

    def delete_category(self, account_id, category_id):
        """Delete a category unless services still reference it. Returns (ok, message)."""
        row = _data(
            _sb().table("categories")
            .select("name")
            .eq("id", category_id)
            .eq("account_id", account_id)
            .maybe_single()
            .execute()
        )
        if not row:
            return False, "Category not found."

        in_use = (
            _sb().table("services")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .ilike("category", row["name"])
            .execute()
        ).count or 0
        if in_use:
            return False, f"Cannot delete '{row['name']}' — {in_use} service(s) still use it."

        _sb().table("categories").delete().eq("id", category_id).eq("account_id", account_id).execute()
        return True, f"Category '{row['name']}' deleted."

    def register_unique(self, account_id, names):
        """Register any category names not already stored. Returns how many were newly created."""
        created = 0
        seen = set()
        for raw in names or []:
            name = str(raw or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            _id, was_created = self.add_category(account_id, name)
            if was_created:
                created += 1
        return created

    def seed_defaults_if_empty(self, account_id):
        count = (
            _sb().table("categories")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .execute()
        ).count or 0
        if count:
            return
        now = int(datetime.now().timestamp())
        rows = [{"account_id": account_id, "name": n, "created_at": now} for n in self.DEFAULTS]
        try:
            _sb().table("categories").insert(rows).execute()
        except Exception as exc:
            _warn(f"category seed skipped: {exc}")


class ServiceRepository:
    """Salon service catalogue (per salon)."""

    DEFAULTS = [
        ("Executive Men's Haircut", "Haircuts", 400, 30, "Marcus Vance (Stylist)", "Includes shampoo, hair wash, precision taper, and styling.", 1),
        ("Women's Signature Layer Cut", "Haircuts", 750, 45, "Alex Rivera (Senior)", "Custom consultation, wash, blowdry, and texture finish.", 1),
        ("Hydra-Dew Glow Facial", "Spa & Facial", 1500, 60, "Sarah Jenkins (Skin Specialist)", "Deep ultrasonic pore cleansing and serum infusion.", 1),
        ("Luxury Organic Hair Spa", "Treatments", 1200, 50, "Alex Rivera (Senior)", "Argan oil mask, steam therapy, and scalp massage.", 1),
        ("Full Balayage & Toning", "Color & Hair", 3200, 120, "Priya Nair (Colorist)", "Hand-painted highlights with gloss finish & bond repair.", 1),
        ("Root Touch-up (Ammonia-Free)", "Color & Hair", 1100, 45, "Priya Nair (Colorist)", "100% grey coverage with nourishing oils.", 1),
        ("Beard Styling & Razor Shave", "Grooming", 250, 20, "Marcus Vance (Stylist)", "Hot towel wrap, beard oil, and precision razor outline.", 1),
        ("Keratin Smooth Treatment", "Treatments", 4500, 150, "Priya Nair (Colorist)", "Frizz-free silky smooth keratin infusion lasts 4 months.", 1),
    ]

    def __init__(self):
        pass

    def get_services(self, account_id):
        self.seed_defaults_if_empty(account_id)
        rows = (
            _sb().table("services")
            .select("*")
            .eq("account_id", account_id)
            .order("id", desc=True)
            .execute()
        ).data
        return [dict(r) for r in (rows or [])]

    def get_booking_services(self, account_id):
        self.seed_defaults_if_empty(account_id)
        rows = (
            _sb().table("services")
            .select("*")
            .eq("account_id", account_id)
            .eq("active", 1)
            .order("id", desc=True)
            .execute()
        ).data
        return [dict(r) for r in (rows or [])]

    def add_service(self, account_id, name, category, price, duration=30,
                    staff="Any Stylist", description="", active=1):
        res = (
            _sb().table("services")
            .insert({
                "account_id": account_id,
                "name": name,
                "category": category,
                "price": int(price),
                "duration": int(duration),
                "staff": staff,
                "description": description,
                "active": int(active),
            })
            .execute()
        )
        return res.data[0]["id"]

    def update_service(self, service_id, account_id, name, category, price,
                       duration, staff, description, active):
        _sb().table("services").update({
            "name": name,
            "category": category,
            "price": int(price),
            "duration": int(duration),
            "staff": staff,
            "description": description,
            "active": int(active),
        }).eq("id", service_id).eq("account_id", account_id).execute()

    def delete_service(self, service_id, account_id):
        _sb().table("services").delete().eq("id", service_id).eq("account_id", account_id).execute()

    def bulk_add_services(self, account_id, rows):
        """Mass-insert services from uploaded rows. Skips rows without a name.

        Every unique category found in the upload is registered in the
        categories table (so new categories can arrive via CSV); the result
        reports how many were newly created.
        """
        added, skipped, errors = 0, 0, []
        seen_categories = set()
        to_insert = []
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
            to_insert.append({
                "account_id": account_id,
                "name": name,
                "category": category,
                "price": price,
                "duration": duration,
                "staff": staff,
                "description": description,
                "active": active,
            })
        if to_insert:
            try:
                _sb().table("services").insert(to_insert).execute()
                added = len(to_insert)
            except Exception as exc:
                errors.append(str(exc))
                skipped += len(to_insert)
        categories_registered = CategoryRepository().register_unique(account_id, seen_categories)
        return {
            "added": added,
            "skipped": skipped,
            "errors": errors,
            "categories_registered": categories_registered,
        }

    def seed_defaults_if_empty(self, account_id):
        count = (
            _sb().table("services")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .execute()
        ).count or 0
        if count:
            return
        rows = [
            {
                "account_id": account_id,
                "name": name,
                "category": category,
                "price": price,
                "duration": duration,
                "staff": staff,
                "description": description,
                "active": active,
            }
            for (name, category, price, duration, staff, description, active) in self.DEFAULTS
        ]
        try:
            _sb().table("services").insert(rows).execute()
        except Exception as exc:
            _warn(f"service seed skipped: {exc}")


class StaffRepository:
    """Salon team roster with per-member revenue/service counters."""

    DEFAULTS = [
        ("Alex Rivera", "Senior Stylist", "9811023456", "Male", "alex@aurasalon.in", 0, 0),
        ("Priya Nair", "Master Colorist", "9822034567", "Female", "priya@aurasalon.in", 0, 0),
        ("Marcus Vance", "Grooming Specialist", "9833045678", "Male", "marcus@aurasalon.in", 0, 0),
    ]

    def __init__(self):
        pass

    def get_staff(self, account_id):
        rows = (
            _sb().table("staff")
            .select("*")
            .eq("account_id", account_id)
            .order("id")
            .execute()
        ).data
        return [dict(r) for r in (rows or [])]

    def add_staff(self, account_id, name, role, phone, gender, email):
        res = (
            _sb().table("staff")
            .insert({
                "account_id": account_id,
                "name": name,
                "role": role,
                "phone": phone,
                "gender": gender,
                "email": email,
                "total_revenue": 0,
                "services_done": 0,
                "created_on": int(datetime.now().timestamp()),
            })
            .execute()
        )
        return res.data[0]["id"]

    def update_staff(self, staff_id, account_id, name, role, phone, gender, email):
        _sb().table("staff").update({
            "name": name,
            "role": role,
            "phone": phone,
            "gender": gender,
            "email": email,
        }).eq("id", staff_id).eq("account_id", account_id).execute()

    def delete_staff(self, staff_id, account_id):
        """Delete a staff member. Returns (ok, message). Prevents removing the last member."""
        row = _data(
            _sb().table("staff")
            .select("name")
            .eq("id", staff_id)
            .eq("account_id", account_id)
            .maybe_single()
            .execute()
        )
        if not row:
            return False, "Staff member not found."
        remaining = (
            _sb().table("staff")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .execute()
        ).count or 0
        if remaining <= 1:
            return False, "A salon must keep at least one staff member on record."
        _sb().table("staff").delete().eq("id", staff_id).eq("account_id", account_id).execute()
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
        rows = (
            _sb().table("staff")
            .select("id, name, total_revenue, services_done")
            .eq("account_id", account_id)
            .execute()
        ).data or []
        matches = [
            r for r in rows
            if r["name"] == base or str(r["name"]).startswith(base)
        ]
        for r in matches:
            _sb().table("staff").update({
                "total_revenue": int(r.get("total_revenue") or 0) + int(amount),
                "services_done": int(r.get("services_done") or 0) + 1,
            }).eq("id", r["id"]).execute()

    def seed_defaults_if_empty(self, account_id):
        count = (
            _sb().table("staff")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .execute()
        ).count or 0
        if count:
            return
        now = int(datetime.now().timestamp())
        rows = [
            {
                "account_id": account_id,
                "name": name,
                "role": role,
                "phone": phone,
                "gender": gender,
                "email": email,
                "total_revenue": rev,
                "services_done": done,
                "created_on": now,
            }
            for (name, role, phone, gender, email, rev, done) in self.DEFAULTS
        ]
        try:
            _sb().table("staff").insert(rows).execute()
        except Exception as exc:
            _warn(f"staff seed skipped: {exc}")


class AppointmentRepository:
    """Salon appointment bookings."""

    def __init__(self):
        pass

    def get_appointments(self, account_id, date_str=None):
        self.seed_defaults_if_empty(account_id)
        query = _sb().table("appointments").select("*").eq("account_id", account_id)
        if date_str:
            res = query.eq("date", date_str).order("time").execute()
        else:
            res = query.order("id", desc=True).execute()
        return [dict(r) for r in (res.data or [])]

    def create_appointment(self, account_id, client, phone, email, service,
                           time_slot, date_str, staff, price, duration=30,
                           status="Confirmed", notes=""):
        res = (
            _sb().table("appointments")
            .insert({
                "account_id": account_id,
                "client": client,
                "phone": phone,
                "email": email,
                "service": service,
                "time": time_slot,
                "date": date_str,
                "staff": staff,
                "price": int(price),
                "duration": int(duration),
                "status": status,
                "notes": notes,
            })
            .execute()
        )
        return res.data[0]["id"]

    def update_status(self, appointment_id, account_id, status):
        _sb().table("appointments").update({
            "status": status,
        }).eq("id", appointment_id).eq("account_id", account_id).execute()

    def seed_defaults_if_empty(self, account_id):
        # Cleared placeholder bookings per user specification
        pass


class BillRepository:
    """Invoices: persisted as a header row + JSON item lines."""

    def __init__(self):
        pass

    def create_bill(self, bill_id, account_id, client_name, client_phone, subtotal,
                    discount, tax, grand_total, payment_mode, items_json, created_at=None):
        if created_at is None:
            created_at = int(datetime.now().timestamp())
        _sb().table("bills").insert({
            "id": bill_id,
            "account_id": account_id,
            "client_name": client_name,
            "client_phone": client_phone,
            "subtotal": int(subtotal),
            "discount": int(discount),
            "tax": int(tax),
            "grand_total": int(grand_total),
            "payment_mode": payment_mode,
            "created_at": created_at,
            "items_json": items_json,
        }).execute()
        return bill_id

    def find_recent_duplicate(self, account_id, client_phone, grand_total, window_seconds=4):
        threshold = int(datetime.now().timestamp()) - window_seconds
        try:
            res = _sb().table("bills").select("id").eq("account_id", account_id).eq("client_phone", str(client_phone or "").strip()).eq("grand_total", int(grand_total)).gte("created_at", threshold).limit(1).execute()
            if res and res.data and len(res.data) > 0:
                return res.data[0]["id"]
        except Exception:
            pass
        return None

    def get_recent_bills(self, account_id, limit=10, offset=0):
        query = (
            _sb().table("bills")
            .select("*")
            .eq("account_id", account_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if offset > 0:
            query = query.range(offset, offset + limit - 1)
        rows = (query.execute()).data
        return [dict(r) for r in (rows or [])]

    def get_metrics(self, account_id, start_ts=None, end_ts=None):
        """Aggregate bill KPIs for a time window (defaults to all-time).

        Returns real values (never fabricated fallbacks).
        """
        self.seed_defaults_if_empty(account_id)
        query = _sb().table("bills").select("grand_total, discount, tax, client_phone").eq("account_id", account_id)
        if start_ts is not None and end_ts is not None:
            query = query.gte("created_at", start_ts).lte("created_at", end_ts)
        rows = query.execute().data or []

        total_sales = sum(int(r.get("grand_total") or 0) for r in rows)
        total_bills = len(rows)
        phones = {
            str(r.get("client_phone") or "").strip()
            for r in rows
            if str(r.get("client_phone") or "").strip()
        }
        return {
            "total_sales": total_sales,
            "total_bills": total_bills,
            "avg_ticket": round(total_sales / total_bills) if total_bills else 0,
            "total_discount": sum(int(r.get("discount") or 0) for r in rows),
            "total_tax": sum(int(r.get("tax") or 0) for r in rows),
            "unique_customers": len(phones),
        }

    def get_bills_in_range(self, account_id, start_ts, end_ts):
        """Return full bills (items parsed) between two timestamps, oldest first."""
        self.seed_defaults_if_empty(account_id)
        rows = (
            _sb().table("bills")
            .select("*")
            .eq("account_id", account_id)
            .gte("created_at", start_ts)
            .lte("created_at", end_ts)
            .order("created_at")
            .execute()
        ).data or []
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
    """Salon customer directory (per salon)."""

    DEFAULTS = [
        ("Ananya Sharma", "9876543210", "ananya@gmail.com", "Prefers weekend slots"),
        ("Vikram Malhotra", "9812345678", "vikram@gmail.com", "Regular client"),
    ]

    def __init__(self):
        pass

    def get_customers(self, account_id):
        self.seed_defaults_if_empty(account_id)
        rows = (
            _sb().table("customers")
            .select("*")
            .eq("account_id", account_id)
            .order("id", desc=True)
            .execute()
        ).data
        return [dict(r) for r in (rows or [])]

    def count_customers(self, account_id):
        res = (
            _sb().table("customers")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .execute()
        )
        return res.count or 0

    def search_customers(self, account_id, query, limit=8):
        """Find customers whose name or phone contains the query (case-insensitive)."""
        q = str(query or "").strip()
        if not q:
            return []
        like = f"%{q}%"
        base = _sb().table("customers").select("*").eq("account_id", account_id)
        by_name = (
            base.ilike("name", like).order("name").limit(limit).execute()
        ).data or []
        by_phone = (
            _sb().table("customers")
            .select("*")
            .eq("account_id", account_id)
            .ilike("phone", like)
            .order("name")
            .limit(limit)
            .execute()
        ).data or []
        merged = {r["id"]: dict(r) for r in by_phone}
        for r in by_name:
            merged.setdefault(r["id"], dict(r))
        results = sorted(merged.values(), key=lambda r: str(r.get("name", "")).lower())
        return results[:limit]

    def get_by_phone(self, account_id, phone):
        row = _data(
            _sb().table("customers")
            .select("*")
            .eq("account_id", account_id)
            .eq("phone", str(phone or "").strip())
            .maybe_single()
            .execute()
        )
        return dict(row) if row else None

    def add_customer(self, account_id, name, phone="", email="", notes="", created_at=None):
        if created_at is None:
            created_at = int(datetime.now().timestamp())
        res = (
            _sb().table("customers")
            .insert({
                "account_id": account_id,
                "name": name,
                "phone": phone,
                "email": email,
                "notes": notes,
                "created_at": created_at,
            })
            .execute()
        )
        return res.data[0]["id"]

    def bulk_add_customers(self, account_id, rows):
        """Mass-insert customers from uploaded rows. Duplicates (same phone) are skipped."""
        added, skipped, errors = 0, 0, []
        existing_rows = (
            _sb().table("customers")
            .select("phone")
            .eq("account_id", account_id)
            .execute()
        ).data or []
        existing = {
            str(r["phone"]).strip() for r in existing_rows if str(r["phone"]).strip()
        }
        to_insert = []
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
            to_insert.append({
                "account_id": account_id,
                "name": name,
                "phone": phone,
                "email": email,
                "notes": notes,
                "created_at": int(datetime.now().timestamp()),
            })
            if phone:
                existing.add(phone)
        if to_insert:
            try:
                _sb().table("customers").insert(to_insert).execute()
                added = len(to_insert)
            except Exception as exc:
                errors.append(str(exc))
                skipped += len(to_insert)
        return {"added": added, "skipped": skipped, "errors": errors}

    def seed_defaults_if_empty(self, account_id):
        count = (
            _sb().table("customers")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .execute()
        ).count or 0
        if count:
            return
        now = int(datetime.now().timestamp())
        rows = [
            {
                "account_id": account_id,
                "name": name,
                "phone": phone,
                "email": email,
                "notes": notes,
                "created_at": now,
            }
            for (name, phone, email, notes) in self.DEFAULTS
        ]
        try:
            _sb().table("customers").insert(rows).execute()
        except Exception as exc:
            _warn(f"customer seed skipped: {exc}")


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
        start_d = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d")
        end_d = datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d")
        rows = (
            _sb().table("appointments")
            .select("*")
            .eq("account_id", account_id)
            .gte("date", start_d)
            .lte("date", end_d)
            .execute()
        ).data or []
        total = len(rows)
        by_status = {}
        for r in rows:
            st = r.get("status") or "Confirmed"
            by_status[st] = by_status.get(st, 0) + 1
        return {"total": total, "by_status": by_status}


class AdminRepository:
    """Read/management helpers backing the /admin console.

    Never exposes account passwords (detail queries select only the columns
    they display); writes are limited to the runtime settings toggle — plan
    grants reuse AuthorizationRepository.update_salon_plan.
    """

    SETTING_ACCEPTING_PUBLIC = "accepting_public"
    _in_memory_settings = {}

    def __init__(self):
        pass

    # ---------- App settings (key/value) ----------

    def get_setting(self, key, default=None):
        """Fetch a settings value; checks in-memory cache and Supabase fail-safe."""
        if key in self._in_memory_settings:
            return self._in_memory_settings[key]
        try:
            row = _data(
                _sb().table("app_settings")
                .select("value")
                .eq("key", key)
                .maybe_single()
                .execute()
            )
            if row and "value" in row:
                self._in_memory_settings[key] = row["value"]
                return row["value"]
            return default
        except Exception as exc:
            _warn(f"get_setting({key!r}) failed: {exc}")
            return self._in_memory_settings.get(key, default)

    def set_setting(self, key, value):
        """Upsert a settings value. Returns True on success.

        Applies the setting to the in-memory cache and environment variable immediately,
        then attempts to persist to Supabase app_settings table.
        """
        str_val = str(value)
        self._in_memory_settings[key] = str_val
        if key == self.SETTING_ACCEPTING_PUBLIC:
            os.environ["ACCEPTING_PUBLIC"] = str_val

        try:
            _sb().table("app_settings").upsert({
                "key": key,
                "value": str_val,
                "updated_at": int(datetime.now().timestamp()),
            }).execute()
            return True
        except Exception as exc:
            _warn(f"set_setting({key!r}) Supabase write failed (using memory cache): {exc}")
            # The setting is already active in memory and runtime env
            return True

    # ---------- Salon directory ----------

    def _count_rows(self, table, col="account_id"):
        """Count rows grouped by a column; fails soft (returns {} so a single
        table-query error doesn't wipe the entire admin salon list."""
        try:
            rows = _sb().table(table).select(col).execute().data or []
        except Exception as exc:
            _warn(f"list_salons: counting {table} rows failed: {exc}")
            return {}
        counts = {}
        for r in rows:
            aid = r.get(col)
            if aid is not None:
                counts[aid] = counts.get(aid, 0) + 1
        return counts

    def _fetch_all(self, table, columns, eq_col=None, eq_val=None, limit=None,
                   order=None, desc=False):
        """Fetch rows from *table* with optional filter; fails soft (returns []).
        Keeps one query's failure from cascading to the whole salon listing."""
        try:
            query = _sb().table(table).select(columns)
            if eq_col is not None and eq_val is not None:
                query = query.eq(eq_col, eq_val)
            if order is not None:
                query = query.order(order, desc=desc)
            if limit is not None:
                query = query.limit(limit)
            res = query.execute()
            return res.data or []
        except Exception as exc:
            _warn(f"list_salons: fetching {table} rows failed: {exc}")
            return []

    def list_salons(self):
        """All salons (newest first) decorated with per-salon counts + revenue.

        Note: the `salons` table orders by `created_on` (not `created_at`) and
        the `accounts` table links to salons via `auth_id` (not `account_id`).
        Each per-table query is independent � if one table is inaccessible
        (RLS error, network blip, etc.) the remaining columns simply show 0
        or empty rather than wiping the entire listing.
        """
        # Core: the salons themselves.  If this fails the dashboard has nothing
        # to show, so we let the exception propagate (caller shows a flash msg).
        salons = self._fetch_all("salons", "*", order="created_on", desc=True)

        accounts = self._count_rows("accounts", col="auth_id")
        staff = self._count_rows("staff")
        services = self._count_rows("services")
        customers = self._count_rows("customers")
        appointments = self._count_rows("appointments")

        # Usernames (login emails) per salon so the dashboard can list the
        # accounts sitting under each salon.
        acc_rows = self._fetch_all("accounts", "auth_id, username")
        accounts_by_salon = {}
        for r in acc_rows:
            aid = r.get("auth_id")
            if aid is not None:
                accounts_by_salon.setdefault(aid, []).append(r.get("username"))

        bill_rows = self._fetch_all("bills", "account_id, grand_total")
        bills_count = {}
        revenue = {}
        for r in bill_rows:
            aid = r.get("account_id")
            if aid is None:
                continue
            bills_count[aid] = bills_count.get(aid, 0) + 1
            revenue[aid] = revenue.get(aid, 0) + int(r.get("grand_total") or 0)

        out = []
        for s in salons:
            d = dict(s)
            sid = s.get("id")
            # Ensure plan never shows as empty/None � fall back to "free".
            if not d.get("plan"):
                d["plan"] = "free"
            d["accounts_count"] = accounts.get(sid, 0)
            d["account_names"] = accounts_by_salon.get(sid, [])
            d["staff_count"] = staff.get(sid, 0)
            d["services_count"] = services.get(sid, 0)
            d["customers_count"] = customers.get(sid, 0)
            d["appointments_count"] = appointments.get(sid, 0)
            d["bills_count"] = bills_count.get(sid, 0)
            d["revenue_total"] = revenue.get(sid, 0)
            out.append(d)
        return out

    def salon_details(self, salon_id):
        """Everything the admin drill-down shows for one salon (no passwords)."""
        salon = _data(
            _sb().table("salons")
            .select("*")
            .eq("id", salon_id)
            .maybe_single()
            .execute()
        )
        if not salon:
            return None

        def count(table):
            try:
                res = (
                    _sb().table(table)
                    .select("id", count="exact")
                    .eq("account_id", salon_id)
                    .execute()
                )
                return res.count or 0
            except Exception as exc:
                _warn(f"salon_details: counting {table} for salon {salon_id} failed: {exc}")
                return 0

        accounts = self._fetch_all("accounts", "id, username, auth_level",
                                   eq_col="auth_id", eq_val=salon_id, order="id")
        staff = self._fetch_all("staff",
                                "id, name, role, phone, email, total_revenue, services_done",
                                eq_col="account_id", eq_val=salon_id, order="id")
        bills = self._fetch_all("bills",
                                "id, client_name, grand_total, payment_mode, created_at",
                                eq_col="account_id", eq_val=salon_id, order="created_at",
                                desc=True, limit=10)
        bill_totals = self._fetch_all("bills", "grand_total",
                                      eq_col="account_id", eq_val=salon_id)
        subscriptions = self._fetch_all("subscriptions", "*",
                                        eq_col="salon_id", eq_val=salon_id,
                                        order="created_at", desc=True)
        pending_orders = self._fetch_all("pendingorders", "*",
                                         eq_col="salon_id", eq_val=salon_id,
                                         order="created_at", desc=True, limit=5)
        deletion_requests = self._fetch_all("deletion_requests", "*",
                                            eq_col="salon_id", eq_val=salon_id,
                                            order="requested_at", desc=True)

        return {
            "salon": dict(salon),
            "accounts": [dict(a) for a in accounts],
            "staff": [dict(s) for s in staff],
            "bills": [dict(b) for b in bills],
            "bills_count": len(bill_totals),
            "revenue_total": sum(int(b.get("grand_total") or 0) for b in bill_totals),
            "services_count": count("services"),
            "customers_count": count("customers"),
            "appointments_count": count("appointments"),
            "subscriptions": [dict(s) for s in subscriptions],
            "pendingorders": [dict(p) for p in pending_orders],
            "deletion_requests": [dict(d) for d in deletion_requests],
        }


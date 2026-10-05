import os
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import (
    Flask, jsonify, request, render_template, flash, redirect, url_for, session, Response,
    Blueprint, send_from_directory,
)
import razorpay
import threading
try:
    import resend
except ImportError:
    resend = None
from types import SimpleNamespace
from uuid import uuid4

if not os.environ.get("VERCEL") and (
    os.environ.get("USE_POSTGRES")
    or os.environ.get("USE_POSTGRESQL")
    or (os.environ.get("DATABASE_URL") and not os.environ.get("SUPABASE_URL"))
):
    from backend import *
else:
    from supabase_backend import *

from flask_mail import Mail, Message
from flask_socketio import SocketIO, emit
from functools import wraps
from datetime import timedelta, datetime, date
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
import csv
import io
import json
import base64
import hmac
import re

ACCEPTING_PUBLIC = os.environ.get("ACCEPTING_PUBLIC", "").strip().lower() in ("1", "true", "yes", "on")
BETA_PUBLIC_MESSAGE = "We are currently in beta testing. This will be available to the general public very soon."

# ================= ADMIN CONSOLE (/admin) CREDENTIALS =================
# Used by the admin console at /admin. ADMIN_PASSWORD is required — without it
# the admin login stays disabled. Change the default below before deploying.
ADMIN_USER = (os.environ.get("ADMIN_USER") or "admin").strip()
ADMIN_PASSWORD = (os.environ.get("ADMIN_PASSWORD") or "").strip()
DEFAULT_ADMIN_PASSWORD = "aurapos-admin"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "id" not in session:
            flash("Please sign in to access your salon terminal.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def get_user_permissions(salon_id=None, account_id=None):
    """Retrieve granted permissions set for the current user or given account."""
    if salon_id is None:
        salon_id = session.get("id", 1)
    if account_id is None:
        account_id = session.get("account_id")

    # If the user is the tenant owner or admin, grant all permissions
    if session.get("auth_level") == "admin":
        return set(ALL_PERMISSION_KEYS)

    # Use cached session permissions if available
    cached = session.get("permissions")
    if cached is not None and isinstance(cached, (list, set)):
        return set(cached)

    if account_id:
        try:
            perms = authRepo.get_account_permissions(salon_id, account_id)
            session["permissions"] = list(perms)
            return set(perms)
        except Exception:
            pass

    # Fallback to level-based defaults
    lvl = (session.get("auth_level") or "cashier").lower()
    if lvl == "admin":
        return set(ALL_PERMISSION_KEYS)
    elif lvl == "manager":
        return {
            "billing:read", "billing:write", "billing:discount",
            "appointments:read", "appointments:write",
            "customers:read", "customers:write",
            "services:read", "services:write",
            "staff:read", "staff:write",
            "reports:read", "accounts:read", "settings:read"
        }
    return {
        "billing:read", "billing:write", "billing:discount",
        "appointments:read", "appointments:write",
        "customers:read", "customers:write",
        "services:read"
    }


def has_permission(resource, action):
    """Check if the currently logged-in user possesses a specific permission claim."""
    claim = f"{resource}:{action}"
    perms = get_user_permissions()
    return claim in perms


def permission_required(resource, action):
    """Gate a route to a granular permission claim (f'{resource}:{action}')."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "id" not in session:
                flash("Please sign in to access your salon terminal.", "warning")
                return redirect(url_for("login"))

            claim = f"{resource}:{action}"
            perms = get_user_permissions()
            if claim not in perms:
                if request.path.startswith("/api/"):
                    return jsonify({
                        "success": False,
                        "message": f"Insufficient permissions: requires '{claim}'.",
                    }), 403
                flash("Your role doesn't have permission to access that section.", "error")
                return redirect(url_for("billing"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_required(*levels):
    """Gate a route to specific auth levels or matching granular permissions."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "id" not in session:
                flash("Please sign in to access your salon terminal.", "warning")
                return redirect(url_for("login"))
            if session.get("auth_level", "admin") not in levels:
                if request.path.startswith("/api/"):
                    return jsonify({
                        "success": False,
                        "message": "Your access level is not authorised for this action.",
                    }), 403
                flash("Your access level doesn't allow that page.", "error")
                return redirect(url_for("billing"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def tier_required(*tiers):
    """Gate a route to salons subscribed to one of the given tiers (e.g. 'studio').

    The salon's plan is read fresh from the database on every request, so plan
    changes take effect immediately. JSON endpoints get a 403 payload while
    pages redirect to the dashboard with a flash message.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "id" not in session:
                flash("Please sign in to access your salon terminal.", "warning")
                return redirect(url_for("login"))
            salon = authRepo.get_salon(session.get("id", 1))
            plan = (salon.plan if salon else "") or ""
            if plan not in tiers:
                label = " / ".join(t.title() for t in tiers)
                if request.path.startswith("/api/"):
                    return jsonify({
                        "success": False,
                        "message": f"This feature is exclusive to the {label} plan — upgrade to unlock it.",
                        "upgrade_required": True,
                    }), 403
                flash(f"This feature is part of the {label} plan — upgrade to unlock it.", "error")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_seat_limit(plan):
    """Team seat limit for a subscription plan (None = unlimited, i.e. Studio)."""
    return TIER_SEAT_LIMITS.get(plan, TIER_SEAT_LIMITS["pro"])


# Tiers that unlock the salon location feature (map pin + directions).
# Pro is the entry paid tier, so Pro and Studio both unlock it.
LOCATION_FEATURE_TIERS = ("pro", "studio")

# Tiers that may set the salon address shown on bills and the booking portal.
# The free trial gets core POS only, so its address stays locked.
ADDRESS_FEATURE_TIERS = ("pro", "studio")


def sanitize_opening_hours(raw):
    """Validate a weekly schedule dict (or JSON-encoded string) and return a
    canonical JSON string.

    Expects {weekday: {"closed": bool, "open": "HH:MM", "close": "HH:MM"}} for
    all seven weekdays. The frontend sends scheduleJson() (a JSON string), so a
    string payload is decoded transparently. Returns None when the payload is
    malformed so callers can reject it.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return None
    if not isinstance(raw, dict):
        return None
    time_re = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
    clean = {}
    for day in WEEKDAY_KEYS:
        entry = raw.get(day)
        if not isinstance(entry, dict):
            return None
        closed = bool(entry.get("closed"))
        open_t = str(entry.get("open") or "").strip()
        close_t = str(entry.get("close") or "").strip()
        if not closed:
            # Same-format HH:MM validation; close < open is allowed (past-midnight
            # closing), only identical open/close times are ambiguous.
            if not time_re.match(open_t) or not time_re.match(close_t) or open_t == close_t:
                return None
        clean[day] = {
            "closed": closed,
            "open": open_t if time_re.match(open_t) else "09:00",
            "close": close_t if time_re.match(close_t) else "19:00",
        }
    return json.dumps(clean)


def get_salon_tier(salon_id):
    """Return (tier, salon) for a salon id; unknown/legacy plans fall back to 'pro'."""
    salon = authRepo.get_salon(salon_id)
    plan = (salon.plan if salon else "") or ""
    tier = plan if plan in TIER_PLANS else "pro"
    return tier, salon


MAX_LOGO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB cap for salon logo uploads



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'public')
else:
    template_folder = os.path.join(BASE_DIR, 'templates')
    static_folder = os.path.join(BASE_DIR, 'public')

# Configure structured logging
import logging
log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format='[%(asctime)s] [%(levelname)s] in %(module)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("aurapos")

# 'app' must be declared at the module root level
app = Flask(__name__, template_folder=template_folder, static_folder=static_folder,
            static_url_path='')

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    transports=["polling"],
    allow_upgrades=False,
    ping_timeout=25,
    ping_interval=10
)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "oqhwd9qyweijsdiuweqifbu")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB maximum upload limit

# Repositories
authRepo = AuthorizationRepository()
serviceRepo = ServiceRepository()
staffRepo = StaffRepository()
appointmentRepo = AppointmentRepository()
billRepo = BillRepository()
customerRepo = CustomerRepository()
categoryRepo = CategoryRepository()
reportRepo = ReportRepository()
adminRepo = AdminRepository()
terminalRepo = TerminalRepository()
productRepo = ProductRepository()
membershipRepo = MembershipRepository()

# Short-lived per-instance cache for settings/salon metadata. Vercel may reuse a
# function instance across requests, so this avoids repeated Supabase round-trips
# without making admin changes effectively stale.
_SETTING_CACHE = {}
_SALON_CACHE = {}
_METADATA_CACHE_TTL = 10.0


def _cached_setting(key, default=None):
    if app.config.get("TESTING"):
        try:
            return adminRepo.get_setting(key, default)
        except Exception:
            return default
    now = time.monotonic()
    hit = _SETTING_CACHE.get(key)
    if hit and now - hit[0] < _METADATA_CACHE_TTL:
        return hit[1]
    try:
        value = adminRepo.get_setting(key, default)
    except Exception:
        return default
    _SETTING_CACHE[key] = (now, value)
    return value


def _cached_salon(salon_id):
    now = time.monotonic()
    hit = _SALON_CACHE.get(salon_id)
    if hit and now - hit[0] < _METADATA_CACHE_TTL:
        return hit[1]
    try:
        salon = authRepo.get_salon(salon_id)
    except Exception:
        return None
    _SALON_CACHE[salon_id] = (now, salon)
    return salon


def is_maintenance_active():
    """Returns (active: bool, message: str) for the platform maintenance lock."""
    try:
        maint_raw = _cached_setting("platform_maintenance", "{}")
        if not maint_raw:
            return False, ""
        data = json.loads(maint_raw)
        return bool(data.get("active")), str(data.get("message") or "Scheduled platform maintenance in progress. We'll be back shortly.")
    except Exception:
        return False, ""


@app.before_request
def check_maintenance_mode():
    """Gating middleware for platform-wide maintenance mode."""
    active, msg = is_maintenance_active()
    if not active:
        return None

    path = request.path or "/"
    # Admin console paths are exempt so SuperAdmin can access control center to monitor and toggle settings
    if path.startswith("/admin") or path == "/admin":
        return None

    # Static assets, socket.io, health, and status APIs exempt
    if (
        path.startswith("/static")
        or path.startswith("/assets")
        or path.startswith("/js")
        or path.startswith("/socket.io")
        or path in ("/output.css", "/favicon.ico", "/robots.txt", "/sitemap.xml", "/api/platform-status")
    ):
        return None

    # API endpoints receive 503 JSON payload
    if path.startswith("/api/"):
        return jsonify({
            "success": False,
            "maintenance": True,
            "message": msg,
        }), 503

    # Browser requests receive dedicated 503 maintenance page
    return render_template(
        "maintenance.html",
        maintenance_message=msg,
        is_superadmin=bool(session.get("is_admin")),
    ), 503


def public_signup_state():
    """Effective public-signup flag for the beta gate.

    The /admin console override stored in Supabase (app_settings) wins over
    the ACCEPTING_PUBLIC environment default; if the setting cannot be read,
    the env default is used (fail-safe).
    """
    val = _cached_setting(AdminRepository.SETTING_ACCEPTING_PUBLIC)
    if val is None:
        return ACCEPTING_PUBLIC
    return str(val).strip().lower() == "true"

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["300 per minute", "3000 per hour"],
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 'yes')
app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('true', '1', 'yes')
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'salonbillingsoftware@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'ifqrgmhhvnaiqhto')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'salonbillingsoftware@gmail.com')
app.config["SESSION_REFRESH_EACH_REQUEST"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

mailer = Mail(app)

# Resend Email Configuration
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "aayush@aayushsrivastava.com")
if resend and RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


def send_resend_email(to_email, subject, html_content, sync=False):
    """
    Sends transactional email via Resend SDK with graceful fallback to Flask-Mail SMTP.
    Runs asynchronously in a daemon thread by default to keep HTTP request latencies instantaneous.
    """
    to_email = (to_email or "").strip()
    if not to_email:
        return False

    def _deliver():
        # 1. Try Resend if configured
        if resend and RESEND_API_KEY:
            try:
                params = {
                    "from": "AuraPOS <reciepts@aurapos.aayushsrivastava.com>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content,
                    "reply_to": SUPPORT_EMAIL,
                }
                res = resend.Emails.send(params)
                logger.info(f"Resend email sent to {to_email} (subject: '{subject}', id: {getattr(res, 'id', res)})")
                return True
            except Exception as e:
                logger.warning(f"Resend send failed for {to_email}: {e}. Attempting SMTP fallback...")

        # 2. Fallback to Flask-Mail SMTP if available
        try:
            with app.app_context():
                mailer.connect()
                mailer.send(
                    Message(
                        subject=subject,
                        recipients=[to_email],
                        html=html_content
                    )
                )
                logger.info(f"Fallback SMTP email sent to {to_email}")
                return True
        except Exception as e:
            logger.warning(f"Fallback SMTP send error for {to_email}: {e}")
            return False

    if sync:
        return _deliver()
    t = threading.Thread(target=_deliver, daemon=True)
    t.start()
    return True


def _safe_external_url(endpoint, default_path="/"):
    try:
        return url_for(endpoint, _external=True)
    except Exception:
        app_domain = os.environ.get("APP_URL", "https://aurapos.aayushsrivastava.com").rstrip("/")
        return f"{app_domain}{default_path}"


def send_purchase_invoice_email(recipient_email, salon_name, owner_name, plan_tier, cycle, amount, invoice_id, expires_ts=None):
    """Triggers the purchase invoice transactional email via Resend."""
    if not recipient_email:
        return False
    try:
        tier_label = TIER_PLANS.get(plan_tier, {}).get("label", plan_tier.title())
        now_dt = datetime.now()
        invoice_date_str = now_dt.strftime("%d %b %Y")
        next_billing_str = _fmt_date(expires_ts) if expires_ts else (now_dt + timedelta(days=365 if cycle == 'yearly' else 30)).strftime("%d %b %Y")
        
        # Razorpay stores billing amounts in paise, but the invoice email should
        # display them in rupees for customer-facing amounts.
        total_amt = (float(amount or 0) / 100.0)
        subtotal_val = round(total_amt / 1.18, 2) if total_amt > 0 else 0
        tax_val = round(total_amt - subtotal_val, 2) if total_amt > 0 else 0

        html_body = render_template(
            "email/purchase-invoice.html",
            invoice_id=invoice_id or f"INV-{now_dt.strftime('%Y%m%d')}-{str(uuid4())[:6].upper()}",
            invoice_date=invoice_date_str,
            salon_name=salon_name or "Your Salon",
            owner_name=owner_name or "Partner",
            customer_email=recipient_email,
            plan_name=f"{tier_label} Plan",
            billing_cycle=f"{cycle.title()} Recurring Subscription",
            currency_symbol="₹",
            amount_paid=f"{int(total_amt):,}" if total_amt.is_integer() else f"{total_amt:,.2f}",
            subtotal=f"{subtotal_val:,.2f}",
            tax_amount=f"{tax_val:,.2f}",
            next_billing_date=next_billing_str,
            payment_method="Razorpay Online",
            dashboard_url=_safe_external_url("dashboard", "/dashboard"),
            receipt_url=_safe_external_url("settings", "/settings"),
            support_email=SUPPORT_EMAIL,
        )
        return send_resend_email(
            to_email=recipient_email,
            subject=f"Payment Receipt: {tier_label} Plan Subscription — AuraPOS",
            html_content=html_body,
        )
    except Exception as e:
        logger.warning(f"Error preparing purchase invoice email: {e}")
        return False


def send_account_withheld_email(recipient_email, salon_name, owner_name, reason=None):
    """Triggers the account withheld notice transactional email via Resend."""
    if not recipient_email:
        return False
    try:
        now_dt = datetime.now()
        notice_date_str = now_dt.strftime("%d %b %Y")
        default_reason = reason or "Subscription expired or payment verification pending. Salon terminal access has been placed on hold."
        account_ref = f"HOLD-{now_dt.strftime('%y%m')}-{str(uuid4())[:6].upper()}"

        resolve_link = _safe_external_url("upgrade", "/upgrade")
        html_body = render_template(
            "email/account-withheld.html",
            salon_name=salon_name or "Your Salon",
            owner_name=owner_name or "Account Owner",
            notice_date=notice_date_str,
            reason=default_reason,
            resolve_url=resolve_link,
            action_url=resolve_link,
            account_ref=account_ref,
            support_email=SUPPORT_EMAIL,
        )
        return send_resend_email(
            to_email=recipient_email,
            subject="Action Required: Account Access Withheld — AuraPOS",
            html_content=html_body,
        )
    except Exception as e:
        logger.warning(f"Error preparing account withheld email: {e}")
        return False

rzp_key_id = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_SxU2RG4SoMaOcI")
rzp_key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "nYTCHgr6NQy1b5X0VDEXcELO")
rzp_client = razorpay.Client(
    auth=(rzp_key_id, rzp_key_secret)
)


@app.after_request
def apply_security_and_cache_headers(response):
    """Apply defense-in-depth security headers and optimal caching policies."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Static assets caching
    path = request.path
    if path == "/output.css" or path.startswith("/public/") or path.endswith((".css", ".js", ".svg", ".png", ".jpg", ".webp", ".ico", ".woff2")):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

    # The public landing page is not personalized. Let Vercel's CDN serve a
    # short-lived copy while keeping browser caching conservative.
    if request.method == "GET" and path == "/" and response.status_code == 200:
        response.headers["CDN-Cache-Control"] = (
            "public, max-age=30, stale-while-revalidate=120, stale-if-error=300"
        )

    return response


# ================= HEALTH & UPTIME MONITORING =================

@app.route('/healthz')
@app.route('/api/health')
@limiter.exempt
def health_check():
    """Uptime monitoring & health check probe for Vercel, UptimeRobot, and load balancers."""
    db_ok = True
    try:
        # Perform quick non-blocking DB probe
        adminRepo.get_setting("health_probe_ping", None)
    except Exception as e:
        logger.warning(f"Health check DB probe error: {e}")
        db_ok = False

    status_code = 200 if db_ok else 503
    return jsonify({
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "timestamp": int(datetime.now().timestamp()),
        "version": "2.5.0",
        "environment": "serverless" if os.environ.get("VERCEL") else "standard"
    }), status_code


def compress_image_blob(blob, mime, max_dim=800, quality=85):
    """Compress image buffer using Pillow if available, falling back to original blob."""
    if mime == "image/svg+xml":
        return blob, mime
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(blob))
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        if mime in ("image/jpeg", "image/jpg"):
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(out, format="JPEG", quality=quality, optimize=True)
            return out.getvalue(), "image/jpeg"
        elif mime == "image/webp":
            img.save(out, format="WEBP", quality=quality)
            return out.getvalue(), "image/webp"
        else:
            img.save(out, format="PNG", optimize=True)
            return out.getvalue(), "image/png"
    except Exception as e:
        logger.debug(f"Image compression fallback: {e}")
        return blob, mime


@app.context_processor
def inject_salon():
    """Expose current salon, tier helpers, impersonation state, global announcement and maintenance state."""
    announcement = {}
    try:
        ann_raw = _cached_setting("platform_announcement", "{}")
        announcement = json.loads(ann_raw) if ann_raw else {}
    except Exception:
        pass

    maintenance = {}
    try:
        maint_raw = _cached_setting("platform_maintenance", "{}")
        maintenance = json.loads(maint_raw) if maint_raw else {}
    except Exception:
        pass

    is_impersonating = False
    is_superadmin = False
    salon_id = None
    try:
        from flask import has_request_context
        if has_request_context():
            is_impersonating = bool(session.get("impersonating"))
            is_superadmin = bool(session.get("is_admin"))
            salon_id = session.get("id")
    except Exception:
        pass

    res = {
        "platform_announcement": announcement,
        "platform_maintenance": maintenance,
        "is_impersonating": is_impersonating,
        "is_superadmin": is_superadmin,
    }
    if salon_id:
        salon = _cached_salon(salon_id)
        plan = (salon.plan if salon else "") or ""
        tier = plan if plan in TIER_PLANS else "pro"
        res.update(dict(
            current_salon=salon,
            salon=salon,
            tier=tier,
            is_studio=(tier == "studio"),
            is_pro=(tier == "pro"),
            is_free=(tier == "free"),
            TIER_PLANS=TIER_PLANS,
            has_permission=has_permission,
            current_user_permissions=get_user_permissions(),
        ))
        return res
    res.update(dict(
        current_salon=None, salon=None, tier="pro", is_studio=False, is_pro=False, is_free=False,
        TIER_PLANS=TIER_PLANS, has_permission=has_permission, current_user_permissions=set(),
    ))
    return res


# ================= PUBLIC ROUTES =================

@limiter.exempt
@app.route('/', methods=['GET'])
@app.route('/api/index', methods=['GET'])
@app.route('/api/index.py', methods=['GET'])
def index():
    return render_template('intro/about.html')


# ================= HARDCODED DEMO SALON DATA (/b/demo) =================
DEMO_SALON = SimpleNamespace(
    id=1,
    name="Aura Demo Master",
    salon_name="Aura Luxury Salon & Studio",
    phone="+91 98765 43210",
    email="demo@aurasalon.com",
    address="402 High Street Mall, 100ft Road, Indiranagar, Bengaluru",
    latitude=12.9716,
    longitude=77.5946,
    logo=None,
    booking_slug="demo",
    plan="studio",
    billing_cycle="yearly",
    opening_hours="{}",
)

DEMO_OPENING_HOURS = {
    "monday": {"key": "monday", "label": "Monday", "open": "09:00", "close": "21:00", "isOpen": True},
    "tuesday": {"key": "tuesday", "label": "Tuesday", "open": "09:00", "close": "21:00", "isOpen": True},
    "wednesday": {"key": "wednesday", "label": "Wednesday", "open": "09:00", "close": "21:00", "isOpen": True},
    "thursday": {"key": "thursday", "label": "Thursday", "open": "09:00", "close": "21:00", "isOpen": True},
    "friday": {"key": "friday", "label": "Friday", "open": "09:00", "close": "21:00", "isOpen": True},
    "saturday": {"key": "saturday", "label": "Saturday", "open": "09:00", "close": "21:00", "isOpen": True},
    "sunday": {"key": "sunday", "label": "Sunday", "open": "10:00", "close": "19:00", "isOpen": True},
}

DEMO_SERVICES = [
    {
        "id": 101,
        "name": "Signature Haircut & Wash",
        "category": "Haircuts",
        "price": 450,
        "duration": 35,
        "staff": "Alex Rivera",
        "description": "Includes consultation, deep cleansing wash, precision haircut, and blow-dry finish.",
        "gender": "Any",
        "active": 1,
    },
    {
        "id": 102,
        "name": "Women's Layer Cut & Blowdry",
        "category": "Haircuts",
        "price": 750,
        "duration": 45,
        "staff": "Alex Rivera",
        "description": "Personalized face-framing texture layering with heat styling and argan shine spray.",
        "gender": "Female",
        "active": 1,
    },
    {
        "id": 103,
        "name": "Hydra-Dew Glow Facial",
        "category": "Spa & Facial",
        "price": 1500,
        "duration": 60,
        "staff": "Priya Nair",
        "description": "Deep pore ultrasonic cleanse, antioxidant serum infusion, and cooling collagen mask.",
        "gender": "Any",
        "active": 1,
    },
    {
        "id": 104,
        "name": "Luxury Organic Hair Spa",
        "category": "Treatments",
        "price": 1200,
        "duration": 50,
        "staff": "Priya Nair",
        "description": "Detox scalp therapy with hot oil massage, lavender steam wrap, and deep conditioning.",
        "gender": "Any",
        "active": 1,
    },
    {
        "id": 105,
        "name": "Full Balayage & Toning Gloss",
        "category": "Hair Color",
        "price": 3200,
        "duration": 120,
        "staff": "Priya Nair",
        "description": "Hand-painted sun-kissed dimension followed by a conditioning gloss treatment.",
        "gender": "Female",
        "active": 1,
    },
    {
        "id": 106,
        "name": "Royal Beard Sculpt & Hot Towel",
        "category": "Bridal & Grooming",
        "price": 350,
        "duration": 25,
        "staff": "Marcus Vance",
        "description": "Straight razor edge lining, organic beard oil hydration, and eucalyptus hot towel steam.",
        "gender": "Male",
        "active": 1,
    },
    {
        "id": 107,
        "name": "Keratin Protein Smoothing",
        "category": "Treatments",
        "price": 4500,
        "duration": 90,
        "staff": "Alex Rivera",
        "description": "Frizz-eliminating botanical keratin treatment for silky, high-shine hair lasting up to 3 months.",
        "gender": "Any",
        "active": 1,
    },
    {
        "id": 108,
        "name": "Express Blowdry & Volume Styling",
        "category": "Styling",
        "price": 500,
        "duration": 30,
        "staff": "Marcus Vance",
        "description": "Bouncy voluminous blowout with thermal protection and flexible hold finish.",
        "gender": "Any",
        "active": 1,
    },
]

DEMO_STAFF = [
    {
        "id": 201,
        "name": "Alex Rivera",
        "role": "Senior Stylist",
        "phone": "+91 98110 23456",
        "gender": "Male",
        "email": "alex@aurasalon.in",
    },
    {
        "id": 202,
        "name": "Priya Nair",
        "role": "Master Colorist",
        "phone": "+91 98220 34567",
        "gender": "Female",
        "email": "priya@aurasalon.in",
    },
    {
        "id": 203,
        "name": "Marcus Vance",
        "role": "Grooming Specialist",
        "phone": "+91 98330 45678",
        "gender": "Male",
        "email": "marcus@aurasalon.in",
    },
]


def render_booking_portal(salon, services=None, staff=None, opening_hours=None, is_demo=False):
    """Helper to render the live client self-booking portal for a specific salon."""
    target_id = getattr(salon, "id", None) or (salon.get("id") if isinstance(salon, dict) else 1) or 1
    if services is None:
        services = serviceRepo.get_booking_services(target_id)
    if staff is None:
        staff = staffRepo.get_staff(target_id)

    if opening_hours is None:
        opening_hours = parse_opening_hours(salon)

    now = datetime.now()
    weekday = WEEKDAY_KEYS[now.weekday()]
    today_entry = opening_hours.get(weekday) or {}
    open_now = False
    today_hours_label = "Hours not set"
    if today_entry and not today_entry.get("closed") and today_entry.get("isOpen", True):
        open_t = str(today_entry.get("open") or "")
        close_t = str(today_entry.get("close") or "")
        if open_t and close_t:
            fmt = lambda t: datetime.strptime(t, "%H:%M").strftime("%I:%M %p").lstrip("0")
            now_s = now.strftime("%H:%M")
            if close_t > open_t:
                open_now = open_t <= now_s <= close_t
            else:
                open_now = now_s >= open_t or now_s <= close_t
            today_hours_label = f"{fmt(open_t)} \u2013 {fmt(close_t)}"
    elif today_entry:
        today_hours_label = "Closed today"

    return render_template(
        'service/booking.html',
        salon=salon,
        services=services,
        staff=staff,
        opening_hours=opening_hours,
        today_hours_label=today_hours_label,
        open_now=open_now,
        is_demo=is_demo,
    )


@app.route('/b/demo')
def demo_booking():
    """Hardcoded showcase demo booking page for previewing client self-scheduling."""
    return render_booking_portal(
        salon=DEMO_SALON,
        services=DEMO_SERVICES,
        staff=DEMO_STAFF,
        opening_hours=DEMO_OPENING_HOURS,
        is_demo=True,
    )


@app.route('/b/<string:slug>')
def vanity_booking(slug):
    """Client booking portal opened via unique 5-char vanity ID (/b/<ID>)."""
    slug_clean = str(slug).strip()
    if slug_clean.lower() == "demo":
        return redirect(url_for('demo_booking'))

    salon = authRepo.get_salon_by_slug(slug_clean)
    if not salon:
        flash("The requested salon booking portal could not be found.", "warning")
        return redirect(url_for('booking_showcase'))
    return render_booking_portal(salon)


@app.route('/booking', methods=["GET"])
@app.route('/booking/', methods=["GET"])
def booking():
    """Showcase demo salon booking page with features, or redirect to vanity portal if salon_id is provided."""
    salon_id = request.args.get("salon_id")
    if salon_id:
        try:
            target_salon = authRepo.get_salon(int(salon_id))
            if target_salon and target_salon.booking_slug:
                return redirect(url_for('vanity_booking', slug=target_salon.booking_slug))
        except (ValueError, TypeError):
            pass
    user_salon = None
    if "id" in session:
        user_salon = authRepo.get_salon(session["id"])
    return render_template('service/booking_showcase.html', user_salon=user_salon)

booking_showcase = booking
legacy_booking = booking


@app.route('/pricing', methods=["GET"])
@app.route('/prices', methods=["GET"])
def pricing_redirect():
    """Redirect /pricing and /prices to the pricing chapter on the landing page."""
    return redirect('/#pricing')



@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/x-icon')


@app.route('/js/lucide.min.js')
@app.route('/lucide.min.js')
def lucide_min_js():
    return send_from_directory(os.path.join(app.static_folder, 'js'), 'lucide.min.js', mimetype='text/javascript')


@app.route('/js/lucide.min.js.map')
@app.route('/lucide.min.js.map')
def lucide_min_js_map():
    return send_from_directory(os.path.join(app.static_folder, 'js'), 'lucide.min.js.map', mimetype='application/json')


@app.route('/robots.txt')
def robots_txt():
    return send_from_directory(app.static_folder, 'robots.txt', mimetype='text/plain')


@app.route('/llms.txt')
def llms_txt():
    return send_from_directory(app.static_folder, 'llms.txt', mimetype='text/plain')


@app.route('/sitemap.xml')
@limiter.exempt
def sitemap_xml():
    """Dynamically generate sitemap.xml with domain-aware loc elements."""
    base_url = request.url_root.rstrip('/')
    today = date.today().isoformat()
    pages = [
        {"loc": f"{base_url}/", "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{base_url}/pricing", "changefreq": "weekly", "priority": "0.9"},
        {"loc": f"{base_url}/booking", "changefreq": "weekly", "priority": "0.9"},
        {"loc": f"{base_url}/register", "changefreq": "monthly", "priority": "0.8"},
        {"loc": f"{base_url}/login", "changefreq": "monthly", "priority": "0.7"},
        {"loc": f"{base_url}/contact", "changefreq": "monthly", "priority": "0.6"},
        {"loc": f"{base_url}/privacy", "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{base_url}/terms", "changefreq": "monthly", "priority": "0.5"},
    ]
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in pages:
        xml_parts.append(f'  <url><loc>{p["loc"]}</loc><lastmod>{today}</lastmod><changefreq>{p["changefreq"]}</changefreq><priority>{p["priority"]}</priority></url>')
    xml_parts.append('</urlset>')
    return Response('\n'.join(xml_parts), mimetype='application/xml')


@app.route('/sitemap')
def sitemap_redirect():
    return redirect(url_for('sitemap_xml'))


@app.route('/contact', methods=["GET", "POST"])
def contact():
    if request.method == "GET":
        return render_template('intro/contact.html')
    else:
        flash("Thank you! Your inquiry has been sent to our concierge team.", "success")
        return redirect(url_for('contact'))


@limiter.exempt
@app.route('/privacy')
def privacy_policy():
    return render_template('intro/privacy.html')


@limiter.exempt
@app.route('/terms')
def terms_of_service():
    return render_template('intro/tos.html')


@app.route('/register')
def register():
    return render_template(
        'service/register.html',
        razorpay_key_id='rzp_test_SxU2RG4SoMaOcI',
        accepting_public=public_signup_state(),
        beta_message=BETA_PUBLIC_MESSAGE,
    )


def get_upgrade_options(current_tier):
    """Purchaseable plan ids strictly above the salon's current tier.

    Free-trial salons may buy Pro or Studio; Pro salons may buy Studio;
    Studio salons have nothing strictly higher on the ladder.
    """
    try:
        index = TIER_ORDER.index(current_tier)
    except ValueError:
        index = 0
    return {
        plan_id: pricing
        for plan_id, pricing in PLAN_PRICING.items()
        if TIER_ORDER.index(pricing["tier"]) > index
    }


@app.route('/upgrade')
@login_required
def upgrade():
    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)
    current_tier = (salon.plan if salon and salon.plan in TIER_PLANS else "free") or "free"
    return render_template(
        'service/upgrade.html',
        salon=salon,
        current_tier=current_tier,
        razorpay_key_id='rzp_test_SxU2RG4SoMaOcI',
        upgrade_options=get_upgrade_options(current_tier),
        accepting_public=public_signup_state(),
        beta_message=BETA_PUBLIC_MESSAGE,
    )


# ================= AUTHENTICATION ROUTES =================

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("15 per minute")
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        logged_in_acc = authRepo.login(username, password)

        if logged_in_acc:
            session["id"] = logged_in_acc.auth_id
            session["auth_level"] = logged_in_acc.auth_level
            session["password"] = logged_in_acc.password
            session["username"] = logged_in_acc.username
            session["account_id"] = logged_in_acc.id
            session["role_id"] = logged_in_acc.role_id
            try:
                session["permissions"] = list(authRepo.get_account_permissions(logged_in_acc.auth_id, logged_in_acc.id))
            except Exception:
                session["permissions"] = list(ALL_PERMISSION_KEYS if logged_in_acc.auth_level == "admin" else [])
            flash(f"Welcome back, {logged_in_acc.username}!", "success")
            return redirect(url_for('dashboard'))

        flash("Invalid email or password. Please try again.", "error")

    return render_template("service/login.html")


@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out successfully.", "success")
    return redirect(url_for('login'))


@app.route('/directlogin')
@limiter.limit("10 per minute")
def directlogin():
    username = request.args.get("username")
    password = request.args.get("password")
    
    logged_in_acc = authRepo.login(username, password)
    
    if logged_in_acc:
        session["id"] = logged_in_acc.auth_id
        session["auth_level"] = logged_in_acc.auth_level
        session["password"] = logged_in_acc.password
        session["username"] = logged_in_acc.username
        session["account_id"] = logged_in_acc.id
        session["role_id"] = logged_in_acc.role_id
        try:
            session["permissions"] = list(authRepo.get_account_permissions(logged_in_acc.auth_id, logged_in_acc.id))
        except Exception:
            session["permissions"] = list(ALL_PERMISSION_KEYS if logged_in_acc.auth_level == "admin" else [])
        return redirect(url_for('dashboard'))

    return render_template('page_not_found.html')


@app.route("/forgotpassword", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgotpassword():
    if request.method == "GET":
        return render_template('service/forgotpwd.html')
    
    data = request.get_json() or {}
    identifier = data.get("identifier", "").strip()

    user = authRepo.forgot_password(identifier)

    if user and user.username:
        try:
            salon = authRepo.get_salon(user.auth_id) if getattr(user, 'auth_id', None) else None
            html_body = render_template(
                "email/forgot-password.html",
                password=user.password,
                username=user.username,
                salon_name=salon.salon_name if salon else "Your Salon",
                login_url=url_for('directlogin', username=user.username, password=user.password, _external=True),
                support_email=SUPPORT_EMAIL,
            )
            send_resend_email(
                to_email=user.username,
                subject="Your AuraPOS Account Credentials",
                html_content=html_body,
            )
        except Exception as e:
            logger.warning(f"Forgot password mail error (safe fallback): {e}")

    return jsonify({
        "success": True,
        "message": "If an account exists with this email/phone, recovery instructions have been sent."
    }), 200


# ================= RAZORPAY SUBSCRIPTION =================

@app.post("/create-subscription")
@limiter.limit("20 per minute")
def create_subscription():
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    phone = str(data.get("phone", "")).strip()

    if email and phone and authRepo.check_exists(email, phone):
        return jsonify({"error": "An account with this email address or phone number already exists. Please sign in instead."}), 400

    plan = data.get("plan", "pro")

    pricing = PLAN_PRICING.get(plan)
    if not pricing:
        return jsonify({"error": "Invalid plan selected"}), 400

    # Beta gating: paid plans are closed to the public until launch.
    if not public_signup_state() and pricing["tier"] in ("pro", "studio"):
        return jsonify({"error": BETA_PUBLIC_MESSAGE}), 403

    # pro ₹69/mo · pro_yearly ₹690/yr · studio ₹149/mo · studio_yearly ₹1,490/yr (2 months free)
    amount = pricing["amount"]

    receipt = str(uuid4())

    try:
        order = rzp_client.order.create({
            "amount": amount,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1
        })
    except Exception as e:
        logger.warning(f"Razorpay order creation fallback: {e}")
        order = {
            "id": f"order_{str(uuid4())[:14]}",
            "amount": amount,
            "currency": "INR",
            "receipt": receipt,
            "created_at": int(datetime.now().timestamp())
        }

    authRepo.create_pendingorder(
        order_id=order["id"],
        amount=order["amount"],
        created_at=order["created_at"],
        plan=plan,
        receipt=receipt,
        email=email,
        phone=phone,
    )

    return jsonify(order)


@app.post("/verify-subscription")
@limiter.limit("20 per minute")
def verify_subscription():
    payload = request.get_json() or {}
    data = payload.get("payment", {})
    account_data = payload.get("formData", {})
    
    email = account_data.get("email", "").strip()
    phone = str(account_data.get("phone", "")).strip()

    if authRepo.check_exists(email, phone):
        return jsonify({
            "success": False,
            "message": "An account with this email address or phone number already exists. Please sign in."
        }), 400

    try:
        # Verify Razorpay signature if live keys used
        if "razorpay_signature" in data and data["razorpay_signature"]:
            try:
                rzp_client.utility.verify_payment_signature({
                    "razorpay_order_id": data["razorpay_order_id"],
                    "razorpay_payment_id": data["razorpay_payment_id"],
                    "razorpay_signature": data["razorpay_signature"],
                })
            except Exception:
                pass # Allow test mode bypass in development
    except Exception as e:
        print("Signature check warning:", e)

    plan = account_data.get("plan", "pro")
    pricing = PLAN_PRICING.get(plan)
    if not pricing:
        return jsonify({"success": False, "message": "Invalid plan selected."}), 400

    # Beta gating: creating paid accounts is closed while in beta.
    if not public_signup_state() and pricing["tier"] in ("pro", "studio"):
        return jsonify({"success": False, "message": BETA_PUBLIC_MESSAGE}), 403

    # Creates the salon + owner account (and provisions the Supabase Auth user)
    # with the resolved tier, billing cycle and expiry window applied.
    accid = authRepo.create_auth(
        account_data.get("owner_name", "Salon Owner").capitalize(),
        account_data.get("salon_name", "Studio Elite"),
        phone,
        email,
        account_data.get("password", ""),
        plan=plan,
    )

    # Automatically initialize defaults and login the newly subscribed user
    session["id"] = accid
    session["username"] = email
    session["auth_level"] = "admin"

    serviceRepo.seed_defaults_if_empty(accid)
    staffRepo.seed_defaults_if_empty(accid)
    appointmentRepo.seed_defaults_if_empty(accid)
    billRepo.seed_defaults_if_empty(accid)

    flash("🎉 Subscription activated successfully! Welcome to AuraPOS.", "success")

    # Send Resend purchase invoice email
    try:
        new_salon = authRepo.get_salon(accid)
        send_purchase_invoice_email(
            recipient_email=email,
            salon_name=account_data.get("salon_name", "Studio Elite"),
            owner_name=account_data.get("owner_name", "Salon Owner"),
            plan_tier=pricing["tier"],
            cycle=pricing["cycle"],
            amount=pricing["amount"],
            invoice_id=data.get("razorpay_payment_id") or f"INV-{str(uuid4())[:8].upper()}",
            expires_ts=getattr(new_salon, 'expires_on', None),
        )
    except Exception as e:
        logger.warning(f"Error triggering purchase invoice on signup: {e}")

    return jsonify({
        "success": True,
        "redirect": url_for("dashboard")
    })


# ================= FREE 14-DAY TRIAL =================

@app.post("/register-trial")
@limiter.limit("10 per minute")
def register_trial():
    """Create a brand-new salon on the 14-day free trial (single seat)."""
    data = request.get_json() or {}
    owner_name = (data.get("owner_name") or "Salon Owner").strip().capitalize()
    salon_name = (data.get("salon_name") or "My Salon").strip()
    email = (data.get("email") or "").strip()
    phone = str(data.get("phone") or "").strip()
    password = data.get("password") or ""

    if authRepo.check_exists(email, phone):
        return jsonify({
            "success": False,
            "message": "An account with this email address or phone number already exists. Please sign in."
        }), 400

    # resolve_plan("free") → plan "free", billing_cycle "trial", 14-day expiry.
    accid = authRepo.create_auth(owner_name, salon_name, phone, email, password, plan="free")

    session["id"] = accid
    session["username"] = email
    session["auth_level"] = "admin"

    serviceRepo.seed_defaults_if_empty(accid)
    staffRepo.seed_defaults_if_empty(accid)
    appointmentRepo.seed_defaults_if_empty(accid)
    billRepo.seed_defaults_if_empty(accid)

    flash("🚀 Your 14-day free trial is active — welcome to AuraPOS!", "success")
    return jsonify({
        "success": True,
        "redirect": url_for("dashboard")
    })


# ================= PLAN UPGRADES (existing salons) =================

@app.post("/create-upgrade")
@login_required
@limiter.limit("20 per minute")
def create_upgrade():
    """Create a Razorpay order when an existing salon upgrades to a higher tier."""
    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)
    current_tier = (salon.plan if salon else "") or ""

    data = request.get_json() or {}
    plan = data.get("plan", "")

    pricing = PLAN_PRICING.get(plan)
    if not pricing:
        return jsonify({"error": "Invalid plan selected"}), 400

    # Beta gating: paid plan upgrades are closed to the public until launch.
    if not public_signup_state() and pricing["tier"] in ("pro", "studio"):
        return jsonify({"error": BETA_PUBLIC_MESSAGE}), 403

    current_index = TIER_ORDER.index(current_tier) if current_tier in TIER_ORDER else 0
    target_index = TIER_ORDER.index(pricing["tier"])
    if target_index < current_index:
        return jsonify({"error": "That plan is below your current tier."}), 400
    if current_tier == pricing["tier"]:
        return jsonify({"error": "You are already on the " + TIER_PLANS[pricing["tier"]]["label"] + " plan."}), 400

    receipt = str(uuid4())
    try:
        order = rzp_client.order.create({
            "amount": int(pricing["amount"]),
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1,
        })
    except Exception as e:
        logger.warning(f"Razorpay upgrade order creation fallback: {e}")
        order = {
            "id": f"order_{str(uuid4())[:14]}",
            "amount": int(pricing["amount"]),
            "currency": "INR",
            "receipt": receipt,
            "created_at": int(datetime.now().timestamp()),
        }

    authRepo.create_pendingorder(
        order_id=order["id"],
        amount=order["amount"],
        created_at=order["created_at"],
        plan=plan,
        receipt=receipt,
        email=(salon.email if salon else "") or "",
        phone=(salon.phone if salon else "") or "",
        salon_id=salon_id,
    )

    return jsonify(order)


@app.post("/verify-upgrade")
@login_required
@limiter.limit("20 per minute")
def verify_upgrade():
    """Finalise an upgrade: verify the payment, switch the salon's plan and log the receipt."""
    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)

    payload = request.get_json() or {}
    data = payload.get("payment", {})
    account_data = payload.get("formData", {})

    plan = account_data.get("plan", "")
    pricing = PLAN_PRICING.get(plan)
    if not pricing:
        return jsonify({"success": False, "message": "Invalid plan selected."}), 400

    # Beta gating: paid plan upgrades are closed while in beta.
    if not public_signup_state() and pricing["tier"] in ("pro", "studio"):
        return jsonify({"success": False, "message": BETA_PUBLIC_MESSAGE}), 403

    # Duplicate payment check
    pay_id = data.get("razorpay_payment_id")
    if pay_id:
        existing_sub = authRepo.get_subscription(pay_id)
        if existing_sub:
            return jsonify({
                "success": True,
                "redirect": url_for("dashboard"),
                "message": "Payment already processed."
            })

    # Best-effort signature check (mirrors the register flow's test-mode bypass).
    if data.get("razorpay_signature"):
        try:
            rzp_client.utility.verify_payment_signature({
                "razorpay_order_id": data.get("razorpay_order_id"),
                "razorpay_payment_id": data.get("razorpay_payment_id"),
                "razorpay_signature": data.get("razorpay_signature"),
            })
        except Exception:
            pass  # Allow test mode bypass in development

    # Soft ownership check — the pending order should belong to this salon.
    try:
        order = authRepo.get_pendingorder(data.get("razorpay_order_id", ""))
        if not order or order.get("salon_id") != salon_id:
            logger.warning(f"UPGRADE WARNING: pending order not found for salon {salon_id}")
    except Exception as e:
        logger.warning(f"Upgrade order lookup warning: {e}")

    tier, cycle = pricing["tier"], pricing["cycle"]
    now_ts = int(datetime.now().timestamp())
    expires_ts = now_ts + (Time.year if cycle == "yearly" else Time.month)

    authRepo.update_salon_plan(salon_id, tier, cycle, expires_ts)
    authRepo.record_subscription(
        sub_id=data.get("razorpay_payment_id") or f"sub_{str(uuid4())[:14]}",
        salon_id=salon_id,
        amount=pricing["amount"],
        plan=tier,
        cycle=cycle,
        receipt=data.get("razorpay_order_id") or str(uuid4()),
        email=(salon.email if salon else "") or "",
        phone=(salon.phone if salon else "") or "",
    )

    flash(f"🎉 You're on the {TIER_PLANS[tier]['label']} plan now!", "success")

    # Send Resend purchase invoice email
    try:
        updated_salon = authRepo.get_salon(salon_id)
        recipient = (updated_salon.email if updated_salon else "") or session.get("username", "")
        send_purchase_invoice_email(
            recipient_email=recipient,
            salon_name=updated_salon.salon_name if updated_salon else "Your Salon",
            owner_name=updated_salon.name if updated_salon else "Partner",
            plan_tier=tier,
            cycle=cycle,
            amount=pricing["amount"],
            invoice_id=data.get("razorpay_payment_id") or f"INV-{str(uuid4())[:8].upper()}",
            expires_ts=expires_ts,
        )
    except Exception as e:
        logger.warning(f"Error triggering purchase invoice on upgrade: {e}")

    return jsonify({
        "success": True,
        "redirect": url_for("dashboard")
    })


@app.post("/api/check-account")
def check_account():
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    phone = str(data.get("phone", "")).strip()
    if authRepo.check_exists(email, phone):
        return jsonify({"exists": True, "message": "An account with this email address or phone number already exists."})
    return jsonify({"exists": False})


# ================= AUTHENTICATED CORE APP PAGES =================

@app.route('/dashboard')
@login_required
def dashboard():
    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)
    staff = staffRepo.get_staff(salon_id)
    appointments = appointmentRepo.get_appointments(salon_id, date.today().isoformat())
    recent_bills = billRepo.get_recent_bills(salon_id)

    now = datetime.now()
    day_start = datetime.combine(now.date(), datetime.min.time())
    yesterday_start = day_start - timedelta(days=1)
    today_metrics = billRepo.get_metrics(
        salon_id, int(day_start.timestamp()), int(now.timestamp())
    )
    yesterday_metrics = billRepo.get_metrics(
        salon_id, int(yesterday_start.timestamp()), int(day_start.timestamp()) - 1
    )

    can_view_revenue = session.get("auth_level", "admin") != "cashier"

    def pct_delta(current, previous):
        if previous <= 0:
            return None if current <= 0 else None
        return round((current - previous) * 100 / previous, 1)

    sales_delta = pct_delta(today_metrics["total_sales"], yesterday_metrics["total_sales"])
    ticket_delta = pct_delta(today_metrics["avg_ticket"], yesterday_metrics["avg_ticket"])

    invoice_time = lambda ts: datetime.fromtimestamp(ts).strftime("%I:%M %p")

    staff_data = []
    for s in sorted(staff, key=lambda x: x["total_revenue"], reverse=True):
        display = f"{s['name']} ({s['role']})"
        staff_data.append({
            "name": display,
            "services": s["services_done"],
            "revenue": s["total_revenue"] if can_view_revenue else None,
        })

    invoice_data = []
    if can_view_revenue:
        for b in recent_bills:
            items = []
            try:
                items = json.loads(b["items_json"] or "[]")
            except Exception:
                items = []
            first_item = (items[0]["name"] if items and isinstance(items[0], dict) else "Service") or "Service"
            invoice_data.append({
                "id": b["id"],
                "client": b["client_name"] or "Walk-in",
                "services": first_item + (f" +{len(items) - 1} more" if len(items) > 1 else ""),
                "amount": b["grand_total"],
                "payment": b["payment_mode"],
                "time": invoice_time(b["created_at"]),
            })

    dash_data = {
        "today_sales": today_metrics["total_sales"],
        "today_bills": today_metrics["total_bills"],
        "avg_ticket": today_metrics["avg_ticket"],
        "sales_delta": sales_delta,
        "ticket_delta": ticket_delta,
        "active_staff": len(staff),
        "staff_leaderboard": staff_data,
        "recent_invoices": invoice_data,
        "today_appointments": [
            {
                "id": a["id"],
                "time": a["time"],
                "client": a["client"],
                "service": a["service"],
                "staff": a["staff"],
                "status": a["status"],
            }
            for a in appointments
        ],
    }

    # Subscription banner facts (owner only)
    tier_label = salon.plan.title() if salon and salon.plan in TIER_PLANS else "Pro"
    cycle_label = "Annual" if salon and getattr(salon, "billing_cycle", "monthly") == "yearly" else "Monthly"
    if salon and getattr(salon, "billing_cycle", "monthly") == "trial":
        plan_display = "Free 14-day Trial"
    else:
        plan_display = f"{tier_label} {cycle_label}"
    days_left = 0
    expires_readable = None
    if salon and salon.expires_on:
        seconds_left = salon.expires_on - int(now.timestamp())
        days_left = max(0, int(seconds_left / 86400))
        expires_readable = datetime.fromtimestamp(salon.expires_on).strftime("%B %d, %Y")

    today_label = now.strftime("%d %b %Y")

    return render_template(
        'service/dashboard.html',
        salon=salon,
        staff=staff,
        appointments=appointments,
        recent_bills=recent_bills,
        metrics=today_metrics,
        dashboard_data=dash_data,
        plan_display=plan_display,
        days_left=days_left,
        expires_readable=expires_readable,
        today_label=today_label,
        # Billing Desk sees the dashboard but never revenue figures
        can_view_revenue=can_view_revenue
    )


@app.route('/services')
@role_required("admin", "manager")
def services():
    salon_id = session.get("id", 1)
    service_list = serviceRepo.get_services(salon_id)
    return render_template('service/services.html', services=service_list)


@app.route('/billing')
@login_required
def billing():
    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)
    service_list = serviceRepo.get_services(salon_id)
    staff_list = staffRepo.get_staff(salon_id)
    billing_staff = [f"{s['name']} ({s['role']})" for s in staff_list] + ["Unassigned"]
    plan = (salon.plan if salon else "free") or "free"
    terminal_limit = get_terminal_limit(plan)
    return render_template(
        'service/billing.html',
        salon=salon,
        current_salon=salon,
        services=service_list,
        staff=staff_list,
        billing_staff=billing_staff,
        current_tier=plan,
        terminal_limit=terminal_limit,
        account_id=session.get("account_id", 0),
        account_username=session.get("username", "Staff"),
        tax_settings=authRepo.get_tax_settings(salon_id),
        printer_settings=authRepo.get_printer_settings(salon_id),
    )



@app.route('/appointments')
@login_required
def appointments():
    salon_id = session.get("id", 1)
    appointment_list = appointmentRepo.get_appointments(salon_id)
    staff_list = staffRepo.get_staff(salon_id)
    return render_template('service/appointments.html', appointments=appointment_list, staff=staff_list)


@app.route('/staff')
@role_required("admin", "manager")
def staff_page():
    salon_id = session.get("id", 1)
    staff_list = staffRepo.get_staff(salon_id)
    return render_template('service/staff.html', staff=staff_list)


@app.route('/customers')
@role_required("admin", "manager")
def customers_page():
    salon_id = session.get("id", 1)
    tier, salon = get_salon_tier(salon_id)
    is_studio = (tier == "studio")
    is_free = (tier == "free")
    
    customer_list = customerRepo.get_customers(salon_id)
    analytics = customerRepo.get_customer_analytics(salon_id) if is_studio else {
        "total_customers": len(customer_list),
        "active_count": len(customer_list),
        "churning_count": 0,
        "churned_count": 0,
        "retention_rate": 100.0,
        "repeat_rate": 0.0,
        "avg_spend": 0,
        "total_tracked_spend": 0,
        "top_clients": [],
        "customers_with_metrics": customer_list,
    }
    
    return render_template(
        'service/customers.html',
        customers=customer_list,
        analytics=analytics,
        tier=tier,
        is_studio=is_studio,
        is_free=is_free,
        salon=salon,
    )


@app.route('/reports')
@role_required("admin", "manager")
def reports_page():
    salon_id = session.get("id", 1)
    return render_template('service/reports.html', staff=staffRepo.get_staff(salon_id))


# ================= REST JSON API ENDPOINTS =================

@app.get('/api/services')
@login_required
def api_get_services():
    salon_id = session.get("id", 1)
    return jsonify(serviceRepo.get_services(salon_id))


@app.post('/api/services')
@role_required("admin", "manager")
def api_add_service():
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    new_id = serviceRepo.add_service(
        account_id=salon_id,
        name=data.get("name", "New Service"),
        category=data.get("category", "General"),
        price=data.get("price", 0),
        duration=data.get("duration", 30),
        staff=data.get("staff", "Any Stylist"),
        description=data.get("description", ""),
        active=data.get("active", 1)
    )
    return jsonify({"success": True, "id": new_id})


@app.put('/api/services/<int:service_id>')
@role_required("admin", "manager")
def api_update_service(service_id):
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    serviceRepo.update_service(
        service_id=service_id,
        account_id=salon_id,
        name=data.get("name"),
        category=data.get("category"),
        price=data.get("price"),
        duration=data.get("duration"),
        staff=data.get("staff"),
        description=data.get("description"),
        active=data.get("active")
    )
    return jsonify({"success": True})


@app.delete('/api/services/<int:service_id>')
@role_required("admin", "manager")
def api_delete_service(service_id):
    salon_id = session.get("id", 1)
    serviceRepo.delete_service(service_id, salon_id)
    return jsonify({"success": True})


# ================= SERVICE CATEGORIES =================

@app.get('/api/categories')
@login_required
def api_get_categories():
    salon_id = session.get("id", 1)
    return jsonify({"categories": categoryRepo.get_categories(salon_id)})


@app.post('/api/categories')
@role_required("admin", "manager")
def api_add_category():
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = str(data.get("name", "") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Category name is required."}), 400
    if len(name) > 40:
        return jsonify({"success": False, "message": "Category name must be 40 characters or fewer."}), 400
    cat_id, created = categoryRepo.add_category(salon_id, name)
    if created:
        return jsonify({"success": True, "id": cat_id, "created": True, "message": f"Category '{name}' added."})
    return jsonify({"success": True, "id": cat_id, "created": False, "message": f"Category '{name}' already exists."})


@app.delete('/api/categories/<int:category_id>')
@role_required("admin", "manager")
def api_delete_category(category_id):
    salon_id = session.get("id", 1)
    ok, message = categoryRepo.delete_category(salon_id, category_id)
    return jsonify({"success": ok, "message": message}), (200 if ok else 409)


# ================= PRODUCTS & INVENTORY APIS =================

@app.get('/api/products')
@login_required
def api_get_products():
    salon_id = session.get("id", 1)
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    products = productRepo.get_products(salon_id, active_only=active_only)
    categories = productRepo.get_categories(salon_id)
    return jsonify({"products": products, "categories": categories})


@app.post('/api/products')
@role_required("admin", "manager")
def api_create_product():
    if not (has_permission("inventory", "write") or session.get("auth_level") in ("admin", "manager")):
        return jsonify({"success": False, "message": "Permission denied: inventory:write required."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = str(data.get("name", "") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Product name is required."}), 400
    new_id = productRepo.add_product(
        account_id=salon_id,
        name=name,
        category=data.get("category", "Retail"),
        sku=data.get("sku", ""),
        barcode=data.get("barcode", ""),
        price=data.get("price", 0),
        cost_price=data.get("cost_price", 0),
        stock=data.get("stock", data.get("stock_quantity", 0)),
        tax_rate=data.get("tax_rate", 18.0),
        description=data.get("description", ""),
        active=data.get("active", 1)
    )
    product = productRepo.get_product(new_id, salon_id)
    return jsonify({"success": True, "id": new_id, "product": product, "message": f"Product '{name}' created."}), 201


@app.put('/api/products/<int:product_id>')
@role_required("admin", "manager")
def api_update_product(product_id):
    if not (has_permission("inventory", "write") or session.get("auth_level") in ("admin", "manager")):
        return jsonify({"success": False, "message": "Permission denied: inventory:write required."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = str(data.get("name", "") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Product name is required."}), 400
    ok = productRepo.update_product(
        product_id=product_id,
        account_id=salon_id,
        name=name,
        category=data.get("category", "Retail"),
        sku=data.get("sku", ""),
        barcode=data.get("barcode", ""),
        price=data.get("price", 0),
        cost_price=data.get("cost_price", 0),
        stock=data.get("stock", 0),
        tax_rate=data.get("tax_rate", 18.0),
        description=data.get("description", ""),
        active=data.get("active", 1)
    )
    return jsonify({"success": ok})


@app.delete('/api/products/<int:product_id>')
@role_required("admin", "manager")
def api_delete_product(product_id):
    if not (has_permission("inventory", "write") or session.get("auth_level") in ("admin", "manager")):
        return jsonify({"success": False, "message": "Permission denied: inventory:write required."}), 403
    salon_id = session.get("id", 1)
    ok = productRepo.delete_product(product_id, salon_id)
    return jsonify({"success": ok})


@app.post('/api/products/<int:product_id>/stock')
@role_required("admin", "manager")
def api_adjust_product_stock(product_id):
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    delta = int(data.get("adjustment", data.get("delta", 0)) or 0)
    ok = productRepo.adjust_stock(product_id, salon_id, delta)
    prod = productRepo.get_product(product_id, salon_id)
    return jsonify({"success": ok, "product": prod})


# ================= MEMBERSHIPS & TIERS APIS =================

@app.get('/api/memberships/tiers')
@login_required
def api_get_membership_tiers():
    salon_id = session.get("id", 1)
    active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
    tiers = membershipRepo.get_tiers(salon_id, active_only=active_only)
    return jsonify({"tiers": tiers})


@app.post('/api/memberships/tiers')
@role_required("admin", "manager")
def api_create_membership_tier():
    if not (has_permission("memberships", "manage") or session.get("auth_level") in ("admin", "manager")):
        return jsonify({"success": False, "message": "Permission denied: memberships:manage required."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = str(data.get("name", "") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Tier name is required."}), 400
    new_id = membershipRepo.add_tier(
        account_id=salon_id,
        name=name,
        description=data.get("description", ""),
        price=data.get("price", 0),
        duration_days=data.get("duration_days", data.get("validity_days", 365)),
        service_discount_pct=data.get("service_discount_pct", 10.0),
        product_discount_pct=data.get("product_discount_pct", 5.0),
        perks=data.get("perks", []),
        color=data.get("color", "#7928ca"),
        active=data.get("active", 1)
    )
    tier = membershipRepo.get_tier(new_id, salon_id)
    return jsonify({"success": True, "id": new_id, "tier": tier, "message": f"Membership tier '{name}' created."}), 201


@app.put('/api/memberships/tiers/<int:tier_id>')
@role_required("admin", "manager")
def api_update_membership_tier(tier_id):
    if not (has_permission("memberships", "manage") or session.get("auth_level") in ("admin", "manager")):
        return jsonify({"success": False, "message": "Permission denied: memberships:manage required."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = str(data.get("name", "") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Tier name is required."}), 400
    ok = membershipRepo.update_tier(
        tier_id=tier_id,
        account_id=salon_id,
        name=name,
        description=data.get("description", ""),
        price=data.get("price", 0),
        duration_days=data.get("duration_days", 365),
        service_discount_pct=data.get("service_discount_pct", 10.0),
        product_discount_pct=data.get("product_discount_pct", 5.0),
        perks=data.get("perks", []),
        color=data.get("color", "#7928ca"),
        active=data.get("active", 1)
    )
    return jsonify({"success": ok})


@app.delete('/api/memberships/tiers/<int:tier_id>')
@role_required("admin", "manager")
def api_delete_membership_tier(tier_id):
    if not (has_permission("memberships", "manage") or session.get("auth_level") in ("admin", "manager")):
        return jsonify({"success": False, "message": "Permission denied: memberships:manage required."}), 403
    salon_id = session.get("id", 1)
    ok = membershipRepo.delete_tier(tier_id, salon_id)
    return jsonify({"success": ok})


@app.post('/api/customers/<int:customer_id>/membership')
@role_required("admin", "manager")
def api_assign_customer_membership(customer_id):
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    tier_id = int(data.get("tier_id", 0) or 0)
    if not tier_id:
        return jsonify({"success": False, "message": "tier_id is required."}), 400
    res = membershipRepo.assign_membership(
        account_id=salon_id,
        customer_id=customer_id,
        tier_id=tier_id,
        price_paid=data.get("price_paid")
    )
    if not res:
        return jsonify({"success": False, "message": "Tier or customer not found."}), 404
    return jsonify({"success": True, "membership": res, "message": f"Assigned {res['tier_name']} to customer."})


@app.get('/api/customers/<int:customer_id>/membership')
@login_required
def api_get_customer_membership(customer_id):
    salon_id = session.get("id", 1)
    mem = membershipRepo.get_customer_membership(salon_id, customer_id)
    has_mem = bool(mem and mem.get("is_active"))
    return jsonify({
        "success": True,
        "has_membership": has_mem,
        "active_membership": mem if has_mem else None,
        "membership": mem
    })


# ================= CUSTOMER LOOKUP (POS BILLING) =================

@app.get('/api/customers/search')
@login_required
def api_search_customers():
    salon_id = session.get("id", 1)
    query = request.args.get("q", "")
    return jsonify({"query": query, "customers": customerRepo.search_customers(salon_id, query)})


@app.post('/api/customers')
@login_required
def api_create_customer():
    """Create a customer from the POS lookup dialog. Phone must be exactly 10 digits."""
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = str(data.get("name", "") or "").strip()
    phone_digits = "".join(ch for ch in str(data.get("phone", "") or "") if ch.isdigit())
    if not name:
        return jsonify({"success": False, "message": "Customer name is required."}), 400
    if len(phone_digits) != 10:
        return jsonify({"success": False, "message": "Phone number must be exactly 10 digits."}), 400
    existing = customerRepo.get_by_phone(salon_id, phone_digits)
    if existing:
        return jsonify({
            "success": False,
            "message": f"A customer with phone {phone_digits} already exists — attached them to the bill instead.",
            "existing": existing,
        }), 409
    gender = str(data.get("gender", "") or "").strip()
    new_id = customerRepo.add_customer(
        account_id=salon_id,
        name=name,
        phone=phone_digits,
        email=str(data.get("email", "") or "").strip(),
        notes=str(data.get("notes", "") or "").strip(),
        gender=gender,
    )
    customer = {
        "id": new_id,
        "name": name,
        "phone": phone_digits,
        "email": str(data.get("email", "") or "").strip(),
        "notes": str(data.get("notes", "") or "").strip(),
        "gender": gender,
    }
    return jsonify({"success": True, "id": new_id, "customer": customer, "message": f"{name} added to your customer list."})


@app.get('/api/customers')
@role_required("admin", "manager")
def api_get_customers():
    salon_id = session.get("id", 1)
    tier, _ = get_salon_tier(salon_id)
    if tier == "studio":
        analytics = customerRepo.get_customer_analytics(salon_id)
        return jsonify({
            "success": True,
            "customers": analytics["customers_with_metrics"],
            "analytics": {k: analytics[k] for k in analytics if k != "customers_with_metrics"},
        })
    customers = customerRepo.get_customers(salon_id)
    return jsonify({"success": True, "customers": customers})


@app.get('/api/customers/<int:customer_id>/details')
@role_required("admin", "manager")
def api_customer_details(customer_id):
    """Retrieve client stats and bill history.
    
    RBAC:
      - Manager: Can view bill history only (financial/revenue totals and visit frequency stats are masked).
      - Admin: Can view full statistics (total revenue, visit frequency, churn/cohort status) AND bill history.
    """
    salon_id = session.get("id", 1)
    user_role = session.get("auth_level", "admin")

    # Find customer
    customers = customerRepo.get_customers(salon_id)
    customer = next((c for c in customers if c["id"] == customer_id), None)
    if not customer:
        return jsonify({"success": False, "message": "Customer not found."}), 404

    phone = str(customer.get("phone") or "").strip()
    bill_history = billRepo.get_bills_by_phone(salon_id, phone) if phone else []

    can_view_stats = (user_role == "admin")

    if can_view_stats:
        total_revenue = sum(int(b.get("grand_total") or 0) for b in bill_history)
        visit_count = len(bill_history)
        last_visit_ts = max((int(b.get("created_at") or 0) for b in bill_history), default=0)
        
        # Calculate visit frequency
        if visit_count <= 1:
            visit_frequency = "New Client" if visit_count == 1 else "No Visits Yet"
        else:
            first_visit_ts = min((int(b.get("created_at") or 0) for b in bill_history), default=0)
            span_days = max(1, (last_visit_ts - first_visit_ts) // 86400)
            avg_interval_days = round(span_days / (visit_count - 1), 1)
            visit_frequency = f"Every ~{avg_interval_days} days ({visit_count} total visits)"

        stats = {
            "total_revenue": total_revenue,
            "visit_count": visit_count,
            "visit_frequency": visit_frequency,
            "last_visit_ts": last_visit_ts,
            "avg_ticket": round(total_revenue / visit_count) if visit_count else 0,
        }
    else:
        stats = None

    return jsonify({
        "success": True,
        "customer": customer,
        "can_view_stats": can_view_stats,
        "stats": stats,
        "bills": bill_history,
    })


@app.put('/api/customers/<int:customer_id>')
@role_required("admin", "manager")
def api_update_customer(customer_id):
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = str(data.get("name", "") or "").strip()
    phone_digits = "".join(ch for ch in str(data.get("phone", "") or "") if ch.isdigit())
    if not name:
        return jsonify({"success": False, "message": "Customer name is required."}), 400
    if phone_digits and len(phone_digits) != 10:
        return jsonify({"success": False, "message": "Phone number must be exactly 10 digits."}), 400

    gender = str(data.get("gender", "") or "").strip()
    ok = customerRepo.update_customer(
        account_id=salon_id,
        customer_id=customer_id,
        name=name,
        phone=phone_digits,
        email=str(data.get("email", "") or "").strip(),
        notes=str(data.get("notes", "") or "").strip(),
        gender=gender,
    )
    if ok:
        return jsonify({"success": True, "message": f"Customer updated successfully."})
    return jsonify({"success": False, "message": "Could not update customer."}), 400


@app.delete('/api/customers/<int:customer_id>')
@role_required("admin", "manager")
def api_delete_customer(customer_id):
    salon_id = session.get("id", 1)
    ok = customerRepo.delete_customer(salon_id, customer_id)
    if ok:
        return jsonify({"success": True, "message": "Customer removed from directory."})
    return jsonify({"success": False, "message": "Could not remove customer."}), 400


@app.get('/api/customers/analytics')
@role_required("admin", "manager")
@tier_required("studio")
def api_get_customer_analytics():
    salon_id = session.get("id", 1)
    analytics = customerRepo.get_customer_analytics(salon_id)
    return jsonify({"success": True, "analytics": analytics})


@app.post('/api/bills')
@login_required
@limiter.limit("60 per minute")
def api_create_bill():
    if not (has_permission("billing", "write") or session.get("auth_level") in ("admin", "manager", "cashier")):
        return jsonify({"success": False, "message": "Permission denied: billing:write required."}), 403

    salon_id = session.get("id", 1)
    data = request.get_json() or {}

    try:
        subtotal = max(0, int(float(data.get("subtotal", 0) or 0)))
        discount = max(0, int(float(data.get("discount", 0) or 0)))
        tax = max(0, int(float(data.get("tax", 0) or 0)))
        grand_total = max(0, int(float(data.get("grand_total", 0) or 0)))
        raw_paid = data.get("amount_paid")
        if raw_paid is not None and str(raw_paid).strip() != "":
            amount_paid = max(0, min(grand_total, int(float(str(raw_paid)))))
        else:
            amount_paid = grand_total
        due_amount = max(0, grand_total - amount_paid)
        payment_status = "PAID" if due_amount == 0 else ("UNPAID" if amount_paid == 0 else "PARTIALLY_PAID")
        tax_enabled = 1 if data.get("tax_enabled", True) else 0
        tax_inclusive = 1 if data.get("tax_inclusive", False) else 0
        tax_rate = float(data.get("tax_rate", 18.0) or 18.0)
        tax_amount = tax
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid numeric figures in invoice."}), 400

    # Spending / Transaction Cap Safeguard (₹5,00,000 max single bill)
    if grand_total > 500000:
        return jsonify({"success": False, "message": "Bill amount exceeds maximum transaction cap of ₹5,00,000."}), 400

    if discount > subtotal:
        return jsonify({"success": False, "message": "Discount amount cannot exceed subtotal."}), 400

    client_phone = str(data.get("client_phone", "") or "").strip()
    client_name = str(data.get("client_name", "Walk-in") or "Walk-in").strip()
    payment_mode = str(data.get("payment_mode", "UPI") or "UPI").strip()
    items = data.get("items", [])
    if not isinstance(items, list):
        items = []

    # Prevent duplicate submissions (debouncing duplicate clicks within 4s window)
    dup_id = billRepo.find_recent_duplicate(salon_id, client_phone, grand_total, window_seconds=4)
    if dup_id:
        return jsonify({"success": True, "bill_id": dup_id, "duplicate_prevented": True})

    bill_id = f"AP-{str(uuid4())[:6].upper()}"
    
    billRepo.create_bill(
        bill_id=bill_id,
        account_id=salon_id,
        client_name=client_name,
        client_phone=client_phone,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        grand_total=grand_total,
        payment_mode=payment_mode,
        items_json=json.dumps(items),
        amount_paid=amount_paid,
        due_amount=due_amount,
        payment_status=payment_status,
        tax_enabled=tax_enabled,
        tax_inclusive=tax_inclusive,
        tax_rate=tax_rate,
        tax_amount=tax_amount
    )

    # Record stylist sales for leaderboard & process product inventory and membership activations
    for item in items:
        if not isinstance(item, dict):
            continue

        item_type = str(item.get("type", "service") or "service").lower()

        # Handle retail product inventory decrement
        if item_type == "product":
            prod_id = item.get("id") or item.get("product_id")
            qty = max(1, int(float(item.get("qty", 1) or 1)))
            if prod_id:
                try:
                    productRepo.adjust_stock(prod_id, salon_id, -qty)
                except Exception as e:
                    logger.warning(f"Failed to decrement product stock for product {prod_id}: {e}")

        # Handle membership sale auto-activation on customer
        if item_type == "membership":
            tier_id = item.get("tier_id") or item.get("id")
            if tier_id and client_phone:
                try:
                    cust = customerRepo.get_by_phone(salon_id, client_phone)
                    if cust:
                        membershipRepo.assign_membership(
                            account_id=salon_id,
                            customer_id=cust["id"],
                            tier_id=tier_id,
                            price_paid=int(float(item.get("price", 0) or 0)),
                            bill_id=bill_id
                        )
                except Exception as e:
                    logger.warning(f"Failed to auto-assign membership {tier_id} for phone {client_phone}: {e}")

        splits = item.get("staff_split")
        if isinstance(splits, list) and len(splits) > 0:
            for sp in splits:
                if isinstance(sp, dict):
                    s_name = sp.get("name") or sp.get("staff")
                    s_amt = int(float(sp.get("amount", 0) or 0))
                    if s_name and s_amt > 0:
                        staffRepo.record_sale(s_name, salon_id, s_amt)
        elif isinstance(splits, dict) and splits.get("enabled"):
            st1 = splits.get("stylist1")
            st2 = splits.get("stylist2")
            r1 = float(splits.get("ratio1", 50) or 50)
            price = int(float(item.get("price", 0) or 0))
            qty = int(float(item.get("qty", 1) or 1))
            line_total = price * qty
            amt1 = int(round(line_total * r1 / 100.0))
            amt2 = max(0, line_total - amt1)
            if st1 and amt1 > 0:
                staffRepo.record_sale(st1, salon_id, amt1)
            if st2 and amt2 > 0:
                staffRepo.record_sale(st2, salon_id, amt2)
        else:
            staff_name = item.get("staff")
            if staff_name:
                price = int(float(item.get("price", 0) or 0))
                qty = int(float(item.get("qty", 1) or 1))
                staffRepo.record_sale(staff_name, salon_id, price * qty)

    # Auto-clean cloud terminal draft if completed from a terminal
    terminal_id = data.get("terminal_id")
    if terminal_id:
        try:
            terminalRepo.delete_draft(salon_id, terminal_id)
            if socketio:
                socketio.emit("terminal_cleared", {"salon_id": salon_id, "terminal_id": int(terminal_id)})
        except Exception:
            pass

    return jsonify({
        "success": True,
        "bill_id": bill_id,
        "grand_total": grand_total,
        "amount_paid": amount_paid,
        "due_amount": due_amount,
        "payment_status": payment_status
    })


@app.get('/api/bills')
@login_required
def api_get_bills():
    salon_id = session.get("id", 1)
    status = request.args.get("status")
    q = request.args.get("q")
    limit = min(max(1, request.args.get("limit", 20, type=int)), 100)
    offset = max(0, request.args.get("offset", 0, type=int))
    return jsonify(billRepo.get_bills_filtered(salon_id, status=status, q=q, limit=limit, offset=offset))


@app.post('/api/bills/<bill_id>/pay')
@login_required
def api_settle_bill_due(bill_id):
    if not (has_permission("billing", "write") or session.get("auth_level") in ("admin", "manager", "cashier")):
        return jsonify({"success": False, "message": "Permission denied: billing:write required."}), 403

    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    try:
        amount = int(float(data.get("amount", 0) or 0))
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid settlement amount."}), 400

    if amount <= 0:
        return jsonify({"success": False, "message": "Settlement amount must be greater than zero."}), 400

    payment_mode = str(data.get("payment_mode", "Cash") or "Cash").strip()
    notes = str(data.get("notes", "Due settlement") or "Due settlement").strip()
    received_by = session.get("username", "Staff")

    res = billRepo.record_payment(
        bill_id=bill_id,
        account_id=salon_id,
        amount=amount,
        payment_mode=payment_mode,
        received_by=received_by,
        notes=notes
    )
    if not res.get("success"):
        return jsonify(res), 400
    return jsonify(res)


@app.get('/api/bills/<bill_id>/payments')
@login_required
def api_get_bill_payments(bill_id):
    salon_id = session.get("id", 1)
    payments = billRepo.get_bill_payments(bill_id, salon_id)
    return jsonify({"success": True, "bill_id": bill_id, "payments": payments})


@app.get('/api/customers/<phone>/dues')
@login_required
def api_get_customer_dues(phone):
    salon_id = session.get("id", 1)
    dues = billRepo.get_customer_dues(salon_id, phone)
    total_due = sum(int(d.get("due_amount", 0) or 0) for d in dues)
    return jsonify({"success": True, "phone": phone, "dues": dues, "total_due": total_due})


@app.route('/api/settings/printer', methods=['GET', 'POST', 'PUT', 'PATCH'])
@login_required
def api_settings_printer():
    salon_id = session.get("id", 1)
    if request.method == 'GET':
        return jsonify({"success": True, "printer_settings": authRepo.get_printer_settings(salon_id)})
    
    if not (has_permission("settings", "write") or session.get("auth_level") in ("admin", "manager")):
        return jsonify({"success": False, "message": "Permission denied: settings:write required."}), 403

    data = request.get_json() or {}
    clean_settings = {
        "paper_width": str(data.get("paper_width", "3inch")).strip().lower(),
        "auto_cut": bool(data.get("auto_cut", True)),
        "header_text": str(data.get("header_text", "") or "").strip(),
        "footer_text": str(data.get("footer_text", "") or "").strip(),
    }
    if clean_settings["paper_width"] not in ("2inch", "3inch", "4inch"):
        clean_settings["paper_width"] = "3inch"

    authRepo.update_printer_settings(salon_id, clean_settings)
    return jsonify({"success": True, "message": "Printer settings saved.", "printer_settings": clean_settings})


@app.route('/api/settings/whatsapp', methods=['GET', 'POST', 'PUT', 'PATCH'])
@login_required
def api_settings_whatsapp():
    salon_id = session.get("id", 1)
    if request.method == 'GET':
        return jsonify({"success": True, "whatsapp_settings": authRepo.get_whatsapp_settings(salon_id)})
    
    if not (has_permission("settings", "write") or session.get("auth_level") in ("admin", "manager")):
        return jsonify({"success": False, "message": "Permission denied: settings:write required."}), 403

    data = request.get_json() or {}
    clean_settings = {
        "enabled": bool(data.get("enabled", True)),
        "provider": str(data.get("provider", "mock")).strip().lower(),
        "sender_phone": str(data.get("sender_phone", "") or "").strip(),
        "template_id": str(data.get("template_id", "booking_confirmation") or "booking_confirmation").strip(),
    }
    authRepo.update_whatsapp_settings(salon_id, clean_settings)
    return jsonify({"success": True, "message": "WhatsApp notification settings saved.", "whatsapp_settings": clean_settings})


# ================= POS TERMINAL MANAGEMENT & MULTI-TERMINAL APIS =================

@app.post('/api/terminals/heartbeat')
@login_required
def api_terminal_heartbeat():
    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)
    plan = (salon.plan if salon else "free") or "free"
    data = request.get_json() or {}
    terminal_id = data.get("terminal_id", 1)
    tab_id = str(data.get("tab_id") or "").strip()
    if not tab_id:
        return jsonify({"allowed": False, "message": "tab_id is required"}), 400

    account_id = session.get("account_id", 0)
    account_name = session.get("username", "Staff")
    open_terminal_ids = data.get("open_terminal_ids")

    res = terminalRepo.heartbeat(
        salon_id=salon_id,
        terminal_id=terminal_id,
        tab_id=tab_id,
        account_id=account_id,
        account_name=account_name,
        plan=plan,
        open_terminal_ids=open_terminal_ids
    )
    return jsonify(res)


@app.post('/api/terminals/release')
@login_required
def api_terminal_release():
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    tab_id = str(data.get("tab_id") or "").strip()
    terminal_id = data.get("terminal_id")
    if tab_id:
        terminalRepo.release_session(salon_id, tab_id, terminal_id)
    return jsonify({"success": True})


@app.post('/api/terminals/takeover')
@login_required
def api_terminal_takeover():
    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)
    plan = (salon.plan if salon else "free") or "free"
    data = request.get_json() or {}
    terminal_id = data.get("terminal_id", 1)
    tab_id = str(data.get("tab_id") or "").strip()
    if not tab_id:
        return jsonify({"allowed": False, "message": "tab_id is required"}), 400

    account_id = session.get("account_id", 0)
    account_name = session.get("username", "Staff")

    res = terminalRepo.takeover_terminal(
        salon_id=salon_id,
        terminal_id=terminal_id,
        tab_id=tab_id,
        account_id=account_id,
        account_name=account_name,
        plan=plan
    )
    try:
        if socketio:
            socketio.emit("terminal_taken_over", {
                "salon_id": salon_id,
                "terminal_id": int(terminal_id),
                "new_tab_id": tab_id,
                "account_name": account_name
            })
    except Exception:
        pass
    return jsonify(res)


@app.get('/api/terminals/status')
@login_required
def api_terminal_status():
    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)
    plan = (salon.plan if salon else "free") or "free"
    limit = get_terminal_limit(plan)
    active = terminalRepo.get_active_sessions(salon_id)
    return jsonify({
        "success": True,
        "tier": plan,
        "limit": limit,
        "active_terminals": active,
    })


@app.get('/api/terminals/drafts')
@login_required
def api_get_terminal_drafts():
    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)
    plan = (salon.plan if salon else "free") or "free"
    is_studio = "studio" in plan.lower()

    if not is_studio:
        return jsonify({
            "success": True,
            "cloud_sync": False,
            "tier": plan,
            "drafts": [],
            "message": "Cloud-synced terminal drafts are exclusive to the Studio plan."
        })

    drafts = terminalRepo.get_drafts(salon_id)
    return jsonify({
        "success": True,
        "cloud_sync": True,
        "tier": plan,
        "drafts": drafts
    })


@app.post('/api/terminals/drafts')
@login_required
def api_save_terminal_draft():
    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)
    plan = (salon.plan if salon else "free") or "free"
    is_studio = "studio" in plan.lower()

    if not is_studio:
        return jsonify({
            "success": False,
            "cloud_sync": False,
            "tier": plan,
            "message": "Draft saving server-side is available only on the Studio plan. Pro uses browser cookie caching."
        }), 403

    data = request.get_json() or {}
    terminal_id = data.get("terminal_id", 1)
    terminal_name = str(data.get("terminal_name") or f"Terminal #{terminal_id}").strip()
    cart_data = data.get("cart_data", {})
    account_id = session.get("account_id", 0)
    account_name = session.get("username", "Staff")

    terminalRepo.save_draft(
        salon_id=salon_id,
        terminal_id=terminal_id,
        terminal_name=terminal_name,
        cart_data=cart_data,
        account_id=account_id,
        account_name=account_name
    )

    try:
        if socketio:
            socketio.emit("terminal_sync", {
                "salon_id": salon_id,
                "terminal_id": int(terminal_id),
                "terminal_name": terminal_name,
                "cart_data": cart_data,
                "updated_by": account_name,
                "updated_at": int(datetime.now().timestamp())
            })
    except Exception:
        pass

    return jsonify({"success": True, "message": "Terminal draft saved to cloud."})


@app.delete('/api/terminals/drafts/<int:terminal_id>')
@login_required
def api_delete_terminal_draft(terminal_id):
    salon_id = session.get("id", 1)
    terminalRepo.delete_draft(salon_id, terminal_id)
    try:
        if socketio:
            socketio.emit("terminal_cleared", {
                "salon_id": salon_id,
                "terminal_id": int(terminal_id)
            })
    except Exception:
        pass
    return jsonify({"success": True})



@app.get('/api/appointments')
@login_required
def api_get_appointments():
    salon_id = session.get("id", 1)
    date_str = request.args.get("date")
    return jsonify(appointmentRepo.get_appointments(salon_id, date_str))


@app.post('/api/appointments')
@login_required
def api_create_appointment():
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    new_id = appointmentRepo.create_appointment(
        account_id=salon_id,
        client=data.get("client", ""),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        service=data.get("service", ""),
        time_slot=data.get("time", ""),
        date_str=data.get("date", date.today().isoformat()),
        staff=data.get("staff", "Any Stylist"),
        price=data.get("price", 0),
        duration=data.get("duration", 30),
        status=data.get("status", "Confirmed"),
        notes=data.get("notes", "")
    )
    return jsonify({"success": True, "id": new_id})


@app.patch('/api/appointments/<int:apt_id>/status')
@login_required
def api_update_appointment_status(apt_id):
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    appointmentRepo.update_status(apt_id, salon_id, data.get("status", "Confirmed"))
    return jsonify({"success": True})


# ================= STAFF MANAGEMENT =================

@app.get('/api/staff')
@role_required("admin", "manager")
def api_get_staff():
    return jsonify(staffRepo.get_staff(session.get("id", 1)))


@app.post('/api/staff')
@role_required("admin", "manager")
def api_add_staff():
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = str(data.get("name", "") or "").strip()
    role = str(data.get("role", "") or "").strip() or "Stylist"
    phone = "".join(ch for ch in str(data.get("phone", "") or "") if ch.isdigit())
    gender = str(data.get("gender", "") or "").strip()
    email = str(data.get("email", "") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Staff name is required."}), 400
    if phone and len(phone) != 10:
        return jsonify({"success": False, "message": "Phone number must be exactly 10 digits."}), 400
    new_id = staffRepo.add_staff(salon_id, name, role, phone, gender, email)
    return jsonify({"success": True, "id": new_id, "message": f"{name} added to the team."})


@app.put('/api/staff/<int:staff_id>')
@role_required("admin", "manager")
def api_update_staff(staff_id):
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = str(data.get("name", "") or "").strip()
    role = str(data.get("role", "") or "").strip() or "Stylist"
    phone = "".join(ch for ch in str(data.get("phone", "") or "") if ch.isdigit())
    gender = str(data.get("gender", "") or "").strip()
    email = str(data.get("email", "") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Staff name is required."}), 400
    if phone and len(phone) != 10:
        return jsonify({"success": False, "message": "Phone number must be exactly 10 digits."}), 400
    staffRepo.update_staff(staff_id, salon_id, name, role, phone, gender, email)
    return jsonify({"success": True, "message": f"{name}'s profile updated."})


@app.delete('/api/staff/<int:staff_id>')
@role_required("admin", "manager")
def api_delete_staff(staff_id):
    salon_id = session.get("id", 1)
    ok, message = staffRepo.delete_staff(staff_id, salon_id)
    return jsonify({"success": ok, "message": message}), (200 if ok else 409)


# ================= ANALYTICS REPORTS =================

def _report_window():
    """Parse from/to ISO dates into unix timestamps (default: last 30 days)."""
    end = datetime.now()
    start = end - timedelta(days=30)
    from_str = request.args.get("from", "").strip()
    to_str = request.args.get("to", "").strip()
    if from_str:
        try:
            start = datetime.strptime(from_str, "%Y-%m-%d")
        except ValueError:
            pass
    if to_str:
        try:
            to_dt = datetime.strptime(to_str, "%Y-%m-%d")
            end = to_dt + timedelta(days=1) - timedelta(seconds=1)
        except ValueError:
            pass
    return start, end


@app.get('/api/reports')
@role_required("admin", "manager")
@tier_required("studio")
def api_reports():
    salon_id = session.get("id", 1)
    start, end = _report_window()
    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())
    return jsonify({
        "range": {
            "from": start.strftime("%Y-%m-%d"),
            "to": end.strftime("%Y-%m-%d"),
        },
        "summary": reportRepo.summary(salon_id, start_ts, end_ts),
        "revenue_by_day": reportRepo.revenue_by_day(salon_id, start_ts, end_ts),
        "revenue_by_hour": reportRepo.revenue_by_hour(salon_id, start_ts, end_ts),
        "top_services": reportRepo.top_services(salon_id, start_ts, end_ts),
        "staff_leaderboard": reportRepo.staff_leaderboard(salon_id, start_ts, end_ts),
        "payment_split": reportRepo.payment_split(salon_id, start_ts, end_ts),
        "category_split": reportRepo.category_split(salon_id, start_ts, end_ts),
        "appointments": reportRepo.appointments_in_range(salon_id, start_ts, end_ts),
    })


# Public Client Portal APIs
@app.get('/api/public/services')
def api_public_services():
    salon_id = request.args.get("salon_id", type=int) or 1
    return jsonify(serviceRepo.get_booking_services(salon_id))


@app.post('/api/public/booking')
def api_public_booking():
    data = request.get_json() or {}
    salon_id = int(data.get("salon_id") or 1)
    new_id = appointmentRepo.create_appointment(
        account_id=salon_id,
        client=data.get("name", ""),
        phone=data.get("phone", ""),
        email=data.get("email", ""),
        service=data.get("service", ""),
        time_slot=data.get("slot", ""),
        date_str=data.get("date", date.today().isoformat()),
        staff=data.get("stylist", "Any Available Stylist"),
        price=data.get("price", 0),
        duration=data.get("duration", 30),
        status="Confirmed",
        notes=data.get("notes", "")
    )

    # Trigger WhatsApp confirmation notice abstraction
    try:
        from whatsapp import send_booking_confirmation
        salon_obj = authRepo.get_salon(salon_id)
        salon_data = asdict(salon_obj) if salon_obj else {}
        send_booking_confirmation(data, salon_data)
    except Exception as exc:
        logger.warning(f"WhatsApp confirmation trigger failed: {exc}")

    return jsonify({"success": True, "booking_id": f"BK-{new_id:04d}"})


# ================= SETTINGS =================

@app.route('/settings')
@login_required
def settings():
    if not (has_permission("settings", "read") or has_permission("accounts", "read") or session.get("auth_level") in ("admin", "manager")):
        flash("Your role doesn't have permission to access salon settings.", "error")
        return redirect(url_for("billing"))

    salon_id = session.get("id", 1)
    salon = authRepo.get_salon(salon_id)
    accounts = authRepo.get_accounts(salon_id)
    roles = authRepo.get_roles(salon_id)
    all_perms = authRepo.get_permissions()
    default_role_id = authRepo.get_default_role_id(salon_id)

    # Never expose team passwords to the client
    safe_accounts = [{**acc, "password": "********"} for acc in accounts]
    salon_data = asdict(salon) if salon else {}
    subscriptions = authRepo.get_subscriptions(salon_id)
    deletion_request = authRepo.get_pending_deletion_request(salon_id)

    # Selective Data Serialization:
    # Check if user has permission to view financial billing details & subscriptions
    can_view_billing = has_permission("billing", "write") or has_permission("billing", "read") or session.get("auth_level") == "admin"
    if not can_view_billing:
        for key in ("plan", "created_on", "expires_on"):
            salon_data.pop(key, None)
        subscriptions = []
        deletion_request = None

    return render_template(
        'service/settings.html',
        salon=salon_data,
        accounts=safe_accounts,
        primary_account_id=authRepo.get_primary_account_id(salon_id),
        subscriptions=subscriptions,
        deletion_request=deletion_request,
        max_team_seats=get_seat_limit(salon.plan if salon else ""),
        roles=roles,
        system_permissions=all_perms,
        default_role_id=default_role_id,
        can_view_billing=can_view_billing,
        can_manage_roles=has_permission("roles", "manage") or session.get("auth_level") == "admin",
        can_manage_accounts=has_permission("accounts", "write") or session.get("auth_level") == "admin",
        tax_settings=authRepo.get_tax_settings(salon_id),
        printer_settings=authRepo.get_printer_settings(salon_id),
        whatsapp_settings=authRepo.get_whatsapp_settings(salon_id),
    )


@app.route('/api/settings/profile', methods=['POST', 'PUT', 'PATCH'])
@app.route('/api/settings/profile/', methods=['POST', 'PUT', 'PATCH'])
@role_required("admin")
def api_update_profile():
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    owner_name = (data.get("owner_name") or "").strip()
    salon_name = (data.get("salon_name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    if not all([owner_name, salon_name, email, phone]):
        return jsonify({"success": False, "message": "All profile fields are required."}), 400

    extra = {}

    # Salon Address — exclusive to the Pro tier and above.
    if "address" in data:
        salon = authRepo.get_salon(salon_id)
        plan = (salon.plan if salon else "") or ""
        if plan not in ADDRESS_FEATURE_TIERS:
            if (data.get("address") or "").strip() != ((salon.address if salon else "") or ""):
                label = " / ".join(t.title() for t in ADDRESS_FEATURE_TIERS)
                return jsonify({
                    "success": False,
                    "message": f"The salon address field is exclusive to the {label} plan — upgrade to unlock it.",
                    "upgrade_required": True,
                }), 403
            # Unchanged address on a locked tier: drop it so the rest of the profile still saves.
        else:
            extra["address"] = (data.get("address") or "").strip()

    # Weekly opening/closing schedule (optional field).
    if "opening_hours" in data:
        opening_hours_json = sanitize_opening_hours(data.get("opening_hours"))
        if opening_hours_json is None:
            return jsonify({"success": False, "message": "Opening hours are invalid — check each day's open/close times."}), 400
        extra["opening_hours"] = opening_hours_json

    # Location (map pin) — exclusive to the Pro tier and above.
    loc = data.get("location", None)
    if isinstance(loc, dict) and loc.get("latitude") is not None and loc.get("longitude") is not None:
        salon = authRepo.get_salon(salon_id)
        plan = (salon.plan if salon else "") or ""
        if plan not in LOCATION_FEATURE_TIERS:
            label = " / ".join(t.title() for t in LOCATION_FEATURE_TIERS)
            return jsonify({
                "success": False,
                "message": f"The salon location feature is exclusive to the {label} plan — upgrade to unlock it.",
                "upgrade_required": True,
            }), 403
        try:
            extra["location"] = {
                "latitude": float(loc["latitude"]),
                "longitude": float(loc["longitude"]),
            }
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Invalid map coordinates."}), 400
    elif loc is False:
        extra["location"] = False

    ok = authRepo.update_salon_profile(salon_id, owner_name, salon_name, email, phone, extra=extra)
    if not ok:
        return jsonify({"success": False, "message": "That email or phone is already linked to another salon."}), 400
    return jsonify({"success": True, "message": "Salon profile updated."})


# Studio-exclusive salon branding: logo is stored in Supabase Storage.
ALLOWED_LOGO_MIMES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}


@app.post('/api/settings/logo')
@role_required("admin")
@tier_required("studio")
def api_upload_logo():
    """Handle salon logo image uploads (Studio tier only).

    Uploads to Supabase Storage and stores the public URL in the database.
    Falls back to base64 data URL if storage is unavailable.
    """
    salon_id = session.get("id", 1)
    file = request.files.get("logo")
    if not file or not file.filename:
        return jsonify({"success": False, "message": "Choose a logo image to upload."}), 400

    mime = (file.mimetype or "").lower()
    if mime not in ALLOWED_LOGO_MIMES:
        return jsonify({"success": False, "message": "Logo must be a PNG, JPG, WEBP or SVG image."}), 400

    blob = file.read()
    if not blob:
        return jsonify({"success": False, "message": "The selected file is empty."}), 400
    if len(blob) > MAX_LOGO_SIZE_BYTES:
        return jsonify({"success": False, "message": "Logo is too large — the maximum size is 2 MB."}), 400

    # Automatically downscale & compress logo image to save bandwidth and storage
    blob, mime = compress_image_blob(blob, mime, max_dim=600, quality=85)

    # Try Supabase Storage first
    public_url = upload_logo_to_storage(salon_id, blob, mime)
    if public_url:
        authRepo.set_logo_from_storage(salon_id, public_url)
        return jsonify({"success": True, "message": "Salon logo updated.", "logo": public_url})

    # Fallback to base64 data URL if storage fails
    data_url = f"data:{mime};base64,{base64.b64encode(blob).decode('ascii')}"
    authRepo.update_salon_logo(salon_id, data_url)
    return jsonify({"success": True, "message": "Salon logo updated (local).", "logo": data_url})


@app.delete('/api/settings/logo')
@role_required("admin")
@tier_required("studio")
def api_remove_logo():
    """Clear the salon logo (Studio tier only)."""
    authRepo.clear_logo(session.get("id", 1))
    return jsonify({"success": True, "message": "Salon logo removed."})


@app.post('/api/settings/password')
@login_required
def api_change_password():
    salon_id = session.get("id", 1)
    username = session.get("username", "")
    data = request.get_json() or {}
    current = (data.get("current_password") or "").strip()
    new = (data.get("new_password") or "").strip()
    confirm = (data.get("confirm_password") or "").strip()
    if len(new) < 6:
        return jsonify({"success": False, "message": "New password must be at least 6 characters."}), 400
    if new != confirm:
        return jsonify({"success": False, "message": "New password and confirmation do not match."}), 400
    ok, message = authRepo.change_password(salon_id, username, current, new)
    if ok:
        session["password"] = new
    return jsonify({"success": ok, "message": message}), (200 if ok else 400)


@app.route('/api/settings/payment-methods', methods=['GET'])
@login_required
def api_get_payment_methods():
    salon_id = session.get("id", 1)
    methods = authRepo.get_payment_methods(salon_id)
    if isinstance(methods, dict) and "custom_methods" not in methods:
        methods["custom_methods"] = []
    return jsonify({"success": True, "methods": methods})


@app.route('/api/settings/payment-methods', methods=['POST', 'PUT', 'PATCH'])
@role_required("admin")
def api_update_payment_methods():
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    methods = data.get("methods", data)
    
    # Sanitize custom payment methods: unique, non-empty, max 15 methods, max 40 chars each
    raw_custom = methods.get("custom_methods", [])
    custom_methods = []
    if isinstance(raw_custom, list):
        seen = set()
        for item in raw_custom:
            name = str(item).strip()[:40]
            if name and name.lower() not in seen and name.upper() not in {"UPI", "CASH", "CARD"}:
                seen.add(name.lower())
                custom_methods.append(name)
            if len(custom_methods) >= 15:
                break

    sanitized = {
        "upi": str(methods.get("upi", "")).strip()[:100],
        "card_terminal": str(methods.get("card_terminal", "")).strip()[:100],
        "custom_methods": custom_methods,
    }
    authRepo.update_payment_methods(salon_id, sanitized)
    return jsonify({"success": True, "message": "Payment methods updated.", "methods": sanitized})


@app.route('/api/settings/taxes', methods=['GET'])
@login_required
def api_get_tax_settings():
    salon_id = session.get("id", 1)
    tax_settings = authRepo.get_tax_settings(salon_id)
    return jsonify({"success": True, "tax_settings": tax_settings})


@app.route('/api/settings/taxes', methods=['POST', 'PUT', 'PATCH'])
@login_required
def api_update_tax_settings():
    if not (session.get("auth_level") == "admin" or has_permission("settings", "write") or has_permission("billing", "write")):
        return jsonify({"success": False, "message": "Unauthorized to update tax settings."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    settings = data.get("tax_settings", data)

    enabled = bool(settings.get("enabled", True))
    tax_name = str(settings.get("tax_name", "GST") or "GST").strip()[:30]
    try:
        tax_rate = max(0.0, min(100.0, float(settings.get("tax_rate", 18.0) if settings.get("tax_rate") is not None else 18.0)))
    except (ValueError, TypeError):
        tax_rate = 18.0

    tax_type = str(settings.get("tax_type", "exclusive") or "exclusive").strip().lower()
    if tax_type not in ("exclusive", "inclusive"):
        tax_type = "exclusive"

    tax_number = str(settings.get("tax_number", "") or "").strip()[:50]
    split_tax = bool(settings.get("split_tax", True))

    sanitized = {
        "enabled": enabled,
        "tax_name": tax_name,
        "tax_rate": tax_rate,
        "tax_type": tax_type,
        "tax_number": tax_number,
        "split_tax": split_tax,
    }
    authRepo.update_tax_settings(salon_id, sanitized)
    return jsonify({"success": True, "message": "Tax master settings saved.", "tax_settings": sanitized})


# ================= RBAC: ROLES & PERMISSIONS API =================

@app.get('/api/settings/permissions')
@login_required
def api_get_permissions():
    """Return all atomic permissions categorized by module."""
    perms = authRepo.get_permissions()
    # Group by module
    modules = {}
    for p in perms:
        mod = p.get("module", "General")
        modules.setdefault(mod, []).append(p)
    return jsonify({"success": True, "permissions": perms, "grouped": modules})


@app.get('/api/settings/roles')
@login_required
def api_get_roles():
    """List all custom & system roles for this salon with member counts and permissions."""
    if not (has_permission("roles", "manage") or has_permission("accounts", "read") or session.get("auth_level") in ("admin", "manager")):
        return jsonify({"success": False, "message": "Permission denied."}), 403
    salon_id = session.get("id", 1)
    roles = authRepo.get_roles(salon_id)
    default_role_id = authRepo.get_default_role_id(salon_id)
    return jsonify({"success": True, "roles": roles, "default_role_id": default_role_id})


@app.post('/api/settings/roles')
@login_required
def api_create_role():
    """Create a new custom role."""
    if not (has_permission("roles", "manage") or session.get("auth_level") == "admin"):
        return jsonify({"success": False, "message": "Only administrators can manage roles."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = (data.get("role_name") or "").strip()
    description = (data.get("description") or "").strip()
    permissions = data.get("permissions") or []
    res = authRepo.create_role(salon_id, name, description, permissions)
    return jsonify(res), (200 if res.get("success") else 400)


@app.patch('/api/settings/roles/<int:role_id>')
@login_required
def api_update_role(role_id):
    """Update role details and assigned permission toggles."""
    if not (has_permission("roles", "manage") or session.get("auth_level") == "admin"):
        return jsonify({"success": False, "message": "Only administrators can manage roles."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    name = (data.get("role_name") or "").strip()
    description = (data.get("description") or "").strip()
    permissions = data.get("permissions") or []
    res = authRepo.update_role(salon_id, role_id, name, description, permissions)
    return jsonify(res), (200 if res.get("success") else 400)


@app.delete('/api/settings/roles/<int:role_id>')
@login_required
def api_delete_role(role_id):
    """Delete a custom role (supports ?reassign_to=<id> if members are assigned)."""
    if not (has_permission("roles", "manage") or session.get("auth_level") == "admin"):
        return jsonify({"success": False, "message": "Only administrators can delete roles."}), 403
    salon_id = session.get("id", 1)
    reassign_to = request.args.get("reassign_to")
    if not reassign_to and request.is_json:
        reassign_to = (request.get_json() or {}).get("reassign_to")
    res = authRepo.delete_role(salon_id, role_id, reassign_to_role_id=reassign_to)
    return jsonify(res), (200 if res.get("success") else 400)


@app.put('/api/settings/default-role')
@login_required
def api_set_default_role():
    """Set the fallback / default role for newly invited team members."""
    if not (has_permission("roles", "manage") or session.get("auth_level") == "admin"):
        return jsonify({"success": False, "message": "Only administrators can configure default roles."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    role_id = data.get("role_id")
    if not role_id:
        return jsonify({"success": False, "message": "role_id is required."}), 400
    res = authRepo.set_default_role_id(salon_id, int(role_id))
    return jsonify(res), (200 if res.get("success") else 400)


# ================= TEAM ACCOUNTS MANAGEMENT =================

@app.get('/api/settings/accounts')
@login_required
def api_get_accounts():
    if not (has_permission("accounts", "read") or session.get("auth_level") in ("admin", "manager")):
        return jsonify({"success": False, "message": "Permission denied."}), 403
    salon_id = session.get("id", 1)
    accounts = [{**acc, "password": "********"} for acc in authRepo.get_accounts(salon_id)]
    tier, _salon = get_salon_tier(salon_id)
    return jsonify({
        "accounts": accounts,
        "primary_account_id": authRepo.get_primary_account_id(salon_id),
        "max_seats": get_seat_limit(tier),
        "tier": tier,
    })


@app.post('/api/settings/accounts')
@login_required
def api_add_account():
    if not (has_permission("accounts", "write") or session.get("auth_level") == "admin"):
        return jsonify({"success": False, "message": "Insufficient permissions to add team accounts."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    tier, _salon = get_salon_tier(salon_id)
    role_id = data.get("role_id")
    result = authRepo.add_account(
        salon_id,
        data.get("email", ""),
        data.get("password", ""),
        auth_level=data.get("auth_level"),
        role_id=role_id,
        seat_limit=get_seat_limit(tier),
    )
    return jsonify(result), (200 if result["success"] else 400)


@app.patch('/api/settings/accounts/<int:row_id>')
@login_required
def api_update_account(row_id):
    if not (has_permission("accounts", "write") or session.get("auth_level") == "admin"):
        return jsonify({"success": False, "message": "Insufficient permissions to modify team accounts."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    new_password = (data.get("password") or "").strip() or None
    role_id = data.get("role_id")
    result = authRepo.update_account(
        salon_id, row_id,
        data.get("email", ""),
        auth_level=data.get("auth_level"),
        role_id=role_id,
        password=new_password,
    )
    if result["success"]:
        # Keep the session in sync when the logged-in user edits their own account
        me = next((a for a in authRepo.get_accounts(salon_id) if a["id"] == row_id), None)
        if me and me["username"] == session.get("username", ""):
            if new_password:
                session["password"] = new_password
            session["auth_level"] = me["auth_level"]
            session["role_id"] = me.get("role_id")
            session["permissions"] = list(authRepo.get_account_permissions(salon_id, row_id))
    return jsonify(result), (200 if result["success"] else 400)


@app.delete('/api/settings/accounts/<int:row_id>')
@login_required
def api_delete_account(row_id):
    if not (has_permission("accounts", "write") or session.get("auth_level") == "admin"):
        return jsonify({"success": False, "message": "Insufficient permissions to delete team accounts."}), 403
    salon_id = session.get("id", 1)
    result = authRepo.delete_account(salon_id, row_id)
    return jsonify(result), (200 if result["success"] else 400)


def _csv_response(filename, header, rows):
    """Stream rows as a downloadable CSV attachment."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get('/api/settings/export/<dataset>')
@role_required("admin")
@tier_required("studio")
def api_export_data(dataset):
    salon_id = session.get("id", 1)
    stamp = date.today().isoformat()
    if dataset == "services":
        rows = serviceRepo.get_services(salon_id)
        return _csv_response(
            f"services-{stamp}.csv",
            ["id", "name", "category", "price", "duration", "staff", "description", "active"],
            [[r["id"], r["name"], r["category"], r["price"], r["duration"], r["staff"], r["description"], r["active"]] for r in rows],
        )
    if dataset == "categories":
        cats = categoryRepo.get_categories(salon_id)
        usage = {}
        for s in serviceRepo.get_services(salon_id):
            key = str(s["category"]).strip().lower()
            usage[key] = usage.get(key, 0) + 1
        return _csv_response(
            f"categories-{stamp}.csv",
            ["id", "name", "services_in_category", "created_at"],
            [[c["id"], c["name"], usage.get(str(c["name"]).strip().lower(), 0), c["created_at"]] for c in cats],
        )
    if dataset == "customers":
        rows = customerRepo.get_customers(salon_id)
        return _csv_response(
            f"customers-{stamp}.csv",
            ["id", "name", "phone", "email", "gender", "notes", "created_at"],
            [[r["id"], r["name"], r["phone"], r["email"], r.get("gender", ""), r["notes"], r["created_at"]] for r in rows],
        )
    if dataset == "appointments":
        rows = appointmentRepo.get_appointments(salon_id)
        return _csv_response(
            f"appointments-{stamp}.csv",
            ["id", "client", "phone", "email", "service", "time", "date", "staff", "price", "duration", "status", "notes"],
            [[r["id"], r["client"], r["phone"], r["email"], r["service"], r["time"], r["date"], r["staff"], r["price"], r["duration"], r["status"], r["notes"]] for r in rows],
        )
    if dataset == "staff":
        rows = staffRepo.get_staff(salon_id)
        return _csv_response(
            f"staff-{stamp}.csv",
            ["id", "name", "role", "phone", "gender", "email", "total_revenue", "services_done", "created_on"],
            [[r["id"], r["name"], r["role"], r.get("phone", ""), r.get("gender", ""), r.get("email", ""), r.get("total_revenue", 0), r.get("services_done", 0), r.get("created_on", "")] for r in rows],
        )
    if dataset in ("bills", "invoices"):
        rows = billRepo.get_recent_bills(salon_id, limit=1000000)
        return _csv_response(
            f"invoices-{stamp}.csv",
            ["id", "client_name", "client_phone", "subtotal", "discount", "tax", "grand_total", "payment_mode", "created_at"],
            [[r["id"], r["client_name"], r["client_phone"], r["subtotal"], r["discount"], r["tax"], r["grand_total"], r["payment_mode"], r["created_at"]] for r in rows],
        )
    return jsonify({"success": False, "message": "Unknown dataset."}), 404


@app.get('/api/settings/export/template/<dataset>')
@role_required("admin")
@tier_required("studio")
def api_import_template(dataset):
    """Downloadable sample CSVs showing the exact mass-upload format."""
    if dataset == "customers":
        return _csv_response(
            "customers-upload-template.csv",
            ["name", "phone", "email", "gender", "notes"],
            [
                ["Ananya Sharma", "9876543210", "ananya@gmail.com", "Female", "Prefers weekend slots"],
                ["Rahul Verma", "9811112222", "rahul@gmail.com", "Male", ""],
            ],
        )
    if dataset == "services":
        return _csv_response(
            "services-upload-template.csv",
            ["name", "category", "price", "duration", "staff", "description", "active"],
            [
                ["Signature Haircut", "Haircuts", 450, 30, "Any Stylist", "Includes wash & blowdry", 1],
                ["Express Facial", "Spa & Facial", 900, 40, "Any Stylist", "", 1],
            ],
        )
    if dataset == "staff":
        return _csv_response(
            "staff-upload-template.csv",
            ["name", "role", "phone", "gender", "email"],
            [
                ["Marcus Vance", "Senior Stylist", "9876501234", "Male", "marcus@aurasalon.com"],
                ["Priya Nair", "Colorist", "9876505678", "Female", "priya@aurasalon.com"],
            ],
        )
    if dataset in ("invoices", "bills"):
        return _csv_response(
            "invoices-upload-template.csv",
            ["id", "client_name", "client_phone", "subtotal", "discount", "tax", "grand_total", "payment_mode", "items", "created_at"],
            [
                ["AP-9801A1", "Ananya Sharma", "9876543210", 1200, 100, 198, 1298, "UPI", "Executive Men's Haircut, Luxury Organic Hair Spa", "2026-10-01"],
                ["AP-9801A2", "Rahul Verma", "9811112222", 750, 0, 135, 885, "Cash", "Women's Signature Layer Cut", "2026-10-02"],
            ],
        )
    return jsonify({"success": False, "message": "Unknown template."}), 404


@app.post('/api/settings/import/<dataset>')
@login_required
@tier_required("studio")
def api_import_data(dataset):
    """Mass upload customers, services, staff, or invoices from a CSV file."""
    if session.get("auth_level") != "admin":
        return jsonify({"success": False, "message": "Only the salon owner can import data."}), 403
    salon_id = session.get("id", 1)
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"success": False, "message": "Attach a CSV file to upload."}), 400
    if not file.filename.lower().endswith(".csv"):
        return jsonify({"success": False, "message": "Only .csv files are supported."}), 400
    try:
        text = file.read().decode("utf-8-sig")
        raw_rows = list(csv.DictReader(io.StringIO(text)))
    except Exception:
        return jsonify({"success": False, "message": "Could not read that CSV file."}), 400
    # Normalize headers (lowercase, trimmed) so "Name", "NAME" etc. all work
    rows = [
        {(k or "").strip().lower(): (v or "") for k, v in row.items() if k is not None}
        for row in raw_rows
    ]
    upload_mode = (request.form.get("mode") or "conservative").strip().lower()
    if upload_mode not in ("conservative", "destructive"):
        upload_mode = "conservative"

    if dataset == "customers":
        result = customerRepo.bulk_add_customers(salon_id, rows, mode=upload_mode)
    elif dataset == "services":
        result = serviceRepo.bulk_add_services(salon_id, rows)
    elif dataset == "staff":
        result = staffRepo.bulk_add_staff(salon_id, rows)
    elif dataset in ("invoices", "bills"):
        result = billRepo.bulk_add_bills(salon_id, rows)
    else:
        return jsonify({"success": False, "message": "Unknown dataset."}), 404
    mode_text = " (all previous customers replaced)" if (dataset == "customers" and upload_mode == "destructive") else ""
    message = f"Import complete{mode_text} — {result['added']} added, {result['skipped']} skipped."
    if result.get("categories_registered"):
        message += f" {result['categories_registered']} new service category(ies) registered."
    if result.get("errors"):
        message += " Issues: " + "; ".join(result["errors"][:3])
    return jsonify({"success": True, "message": message, **result})


@app.post('/api/settings/delete-request')
@login_required
def api_delete_request():
    if session.get("auth_level") != "admin":
        return jsonify({"success": False, "message": "Only the salon owner can request account deletion."}), 403
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    confirm = (data.get("confirm") or "").strip().upper()
    if confirm != "DELETE":
        return jsonify({"success": False, "message": "Type DELETE to confirm this request."}), 400
    salon = authRepo.get_salon(salon_id)
    reason = (data.get("reason") or "").strip()
    authRepo.request_account_deletion(salon_id, salon.email if salon else "", reason)
    try:
        mailer.send(Message(
            subject="AuraPOS — Account Deletion Request",
            recipients=["salonbillingsoftware@gmail.com"],
            body=(
                f"Salon #{salon_id} ({salon.salon_name if salon else 'Unknown'}) has requested account deletion.\n"
                f"Contact email: {salon.email if salon else '-'}\n"
                f"Plan: {salon.plan if salon else '-'}\n"
                f"Reason: {reason or '—'}"
            ),
        ))
    except Exception as e:
        print("Mail error (safe fallback):", e)
    return jsonify({
        "success": True,
        "message": "Deletion request submitted. Our support team will contact you within 48 hours.",
    })


# ================= ADMIN CONSOLE (/admin) =================

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    """Gate an admin route: pages bounce to /admin, API routes get a 401 JSON."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            if request.path.startswith("/admin/api/"):
                return jsonify({"success": False, "message": "Admin authentication required."}), 401
            return redirect(url_for("admin.admin_home"))
        return view(*args, **kwargs)
    return wrapped


def _fmt_date(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d %b %Y")
    except (TypeError, ValueError):
        return "—"


@admin_bp.get("/")
def admin_home():
    if not session.get("is_admin"):
        return render_template(
            "admin/admin_login.html",
            admin_user=ADMIN_USER,
            login_enabled=bool(ADMIN_PASSWORD),
            using_default=bool(ADMIN_PASSWORD) and ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD,
        )

    q = (request.args.get("q") or "").strip()
    try:
        salons = adminRepo.list_salons()
    except Exception as exc:
        salons = []
        flash(f"Could not load salons: {exc}", "error")

    if q:
        ql = q.lower().lstrip("#")

        def _match(s):
            hay = " ".join(str(s.get(k) or "") for k in ("salon_name", "name", "email", "phone")).lower()
            return ql in hay or (ql.isdigit() and str(s.get("id")) == ql)

        salons = [s for s in salons if _match(s)]

    now_ts = int(datetime.now().timestamp())
    rows = []
    for s in salons:
        plan = (s.get("plan") or "free").lower()
        expires_on = s.get("expires_on")
        rows.append({
            **s,
            "plan_label": TIER_PLANS.get(plan, {}).get("label", (plan or "unknown").title()),
            "cycle": s.get("billing_cycle") or "—",
            "created_str": _fmt_date(s.get("created_on")),
            "expires_str": _fmt_date(expires_on) if expires_on else "—",
            "is_expired": bool(expires_on) and int(expires_on) < now_ts,
            "revenue_str": f"₹{int(s.get('revenue_total') or 0):,}",
        })

    stats = {
        "total": len(rows),
        "pro": sum(1 for r in rows if r.get("plan") == "pro"),
        "studio": sum(1 for r in rows if r.get("plan") == "studio"),
        "free": sum(1 for r in rows if (r.get("plan") or "free") not in ("pro", "studio")),
        "expired": sum(1 for r in rows if r.get("is_expired")),
    }

    try:
        metrics = adminRepo.get_platform_metrics()
    except Exception:
        metrics = {}

    try:
        table_counts = adminRepo.get_database_table_counts()
    except Exception:
        table_counts = {}

    try:
        audit_logs = adminRepo.get_audit_logs(30)
    except Exception:
        audit_logs = []

    try:
        announcement_raw = adminRepo.get_setting("platform_announcement", "{}")
        announcement = json.loads(announcement_raw) if announcement_raw else {}
    except Exception:
        announcement = {}

    try:
        maintenance_raw = adminRepo.get_setting("platform_maintenance", "{}")
        maintenance = json.loads(maintenance_raw) if maintenance_raw else {}
    except Exception:
        maintenance = {}

    db_engine = "PostgreSQL (Supabase Local)" if os.environ.get("USE_POSTGRES") else "Supabase Data API"

    return render_template(
        "admin/admin_dashboard.html",
        salons=rows,
        stats=stats,
        metrics=metrics,
        table_counts=table_counts,
        audit_logs=audit_logs,
        announcement=announcement,
        maintenance=maintenance,
        db_engine=db_engine,
        q=q,
        public_open=public_signup_state(),
        admin_user=session.get("admin_user", ADMIN_USER),
        using_default_admin_pwd=ADMIN_PASSWORD == DEFAULT_ADMIN_PASSWORD,
    )


@admin_bp.post("/login")
@limiter.limit("3 per 10 seconds", override_defaults=True)
def admin_login():
    if not ADMIN_PASSWORD:
        flash("Admin login is disabled — set ADMIN_PASSWORD in the environment.", "error")
        return redirect(url_for("admin.admin_home"))

    data = request.form if request.form else (request.get_json(silent=True) or {})
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")

    user_ok = hmac.compare_digest(username.encode("utf-8"), ADMIN_USER.encode("utf-8"))
    pass_ok = hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))
    if not (user_ok and pass_ok):
        flash("Invalid admin credentials.", "error")
        return redirect(url_for("admin.admin_home"))

    session["is_admin"] = True
    session["admin_user"] = username or ADMIN_USER
    try:
        adminRepo.add_audit_log(session["admin_user"], "LOGIN", "SuperAdmin Console", "Successful login")
    except Exception:
        pass
    return redirect(url_for("admin.admin_home"))


@admin_bp.post("/logout")
def admin_logout():
    user = session.get("admin_user", ADMIN_USER)
    try:
        adminRepo.add_audit_log(user, "LOGOUT", "SuperAdmin Console", "Signed out")
    except Exception:
        pass
    session.pop("is_admin", None)
    session.pop("admin_user", None)
    return redirect(url_for("admin.admin_home"))


@admin_bp.post("/public-toggle")
@admin_required
def admin_public_toggle():
    current = public_signup_state()
    new_state = not current
    if not adminRepo.set_setting(AdminRepository.SETTING_ACCEPTING_PUBLIC, "true" if new_state else "false"):
        return jsonify({"success": False, "message": "Could not save the setting — check database connectivity."}), 502
    message = ("Public sign-ups are now OPEN — Pro/Studio purchases are enabled."
               if new_state else
               "Public sign-ups are CLOSED — Pro/Studio purchases stay blocked (beta).")
    adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "TOGGLE_PUBLIC", "Registration", f"Public open: {new_state}")
    return jsonify({"success": True, "accepting_public": new_state, "message": message})


@admin_bp.post("/grant-plan")
@admin_required
def admin_grant_plan():
    data = request.get_json(silent=True) or {}
    try:
        salon_id = int(data.get("salon_id") or 0)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "Invalid salon id."}), 400
    plan = (data.get("plan") or "").strip().lower()
    cycle = (data.get("cycle") or "monthly").strip().lower()
    try:
        days = int(float(str(data.get("days") or 0)))
    except (TypeError, ValueError):
        days = 0

    if plan not in ("pro", "studio", "free"):
        return jsonify({"success": False, "message": "Plan must be pro, studio or free."}), 400
    if plan == "free":
        cycle = "trial"
    elif cycle not in ("monthly", "yearly"):
        return jsonify({"success": False, "message": "Cycle must be monthly or yearly."}), 400

    salon = authRepo.get_salon(salon_id)
    if not salon:
        return jsonify({"success": False, "message": f"Salon #{salon_id} not found."}), 404

    now_ts = int(datetime.now().timestamp())
    plan_id = plan if cycle != "yearly" else f"{plan}_yearly"
    tier, resolved_cycle, _pricing = resolve_plan(plan_id)
    expires_ts = (now_ts + days * 86400) if days > 0 else expires_for(resolved_cycle, now_ts)

    if not authRepo.update_salon_plan(salon_id, tier, resolved_cycle, expires_ts):
        return jsonify({"success": False, "message": "Plan update failed — salon row not found."}), 502

    persisted = authRepo.get_salon(salon_id)
    if (
        not persisted
        or persisted.plan != tier
        or persisted.billing_cycle != resolved_cycle
        or int(persisted.expires_on or 0) != int(expires_ts)
    ):
        return jsonify({
            "success": False,
            "message": "Plan update could not be verified in the database.",
        }), 502

    try:
        authRepo.record_subscription(
            sub_id=f"admin_{str(uuid4())[:12]}",
            salon_id=salon_id,
            amount=0,
            plan=tier,
            cycle=resolved_cycle,
            receipt=f"granted-by:{session.get('admin_user', ADMIN_USER)}",
            email=salon.email or "",
            phone=salon.phone or "",
        )
    except Exception as exc:
        print("Admin grant subscription log failed:", exc)

    adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "GRANT_PLAN", f"Salon #{salon_id} ({salon.salon_name})", f"{tier.upper()} ({resolved_cycle}) until {_fmt_date(expires_ts)}")
    label = TIER_PLANS.get(tier, {}).get("label", tier.title())
    return jsonify({
        "success": True,
        "message": f"{salon.salon_name or ('Salon #' + str(salon_id))} → {label} (until {_fmt_date(expires_ts)}).",
    })


@admin_bp.get("/api/salon/<int:salon_id>")
@admin_required
def admin_salon_details(salon_id):
    try:
        details = adminRepo.salon_details(salon_id)
    except Exception as exc:
        return jsonify({"success": False, "message": f"Error loading salon #{salon_id}: {exc}"}), 500
    if not details:
        return jsonify({"success": False, "message": f"Salon #{salon_id} not found."}), 404
    return jsonify({"success": True, **details})


@admin_bp.post("/api/salon/<int:salon_id>/update")
@admin_required
def admin_update_salon(salon_id):
    data = request.get_json(silent=True) or {}
    salon = authRepo.get_salon(salon_id)
    if not salon:
        return jsonify({"success": False, "message": f"Salon #{salon_id} not found."}), 404
    
    updates = {}
    for k in ["salon_name", "name", "email", "phone", "address", "booking_slug"]:
        if k in data and str(data[k]).strip():
            updates[k] = str(data[k]).strip()
    
    if "phone" in updates:
        phone_clean = "".join(ch for ch in updates["phone"] if ch.isdigit())
        if len(phone_clean) == 10:
            updates["phone"] = phone_clean

    if not updates:
        return jsonify({"success": False, "message": "No valid fields provided to update."}), 400
        
    ok = adminRepo.update_salon(salon_id, updates)
    if ok:
        adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "UPDATE_SALON", f"Salon #{salon_id}", f"Updated {', '.join(updates.keys())}")
        return jsonify({"success": True, "message": f"Salon #{salon_id} updated successfully!"})
    return jsonify({"success": False, "message": "Failed to update salon in database."}), 500


@admin_bp.post("/api/salon/<int:salon_id>/reset-password")
@admin_required
def admin_reset_password(salon_id):
    data = request.get_json(silent=True) or {}
    new_password = str(data.get("password") or "").strip()
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400
    
    salon = authRepo.get_salon(salon_id)
    if not salon:
        return jsonify({"success": False, "message": f"Salon #{salon_id} not found."}), 404
        
    ok = adminRepo.reset_owner_password(salon_id, new_password)
    if ok:
        adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "RESET_PASSWORD", f"Salon #{salon_id}", "Reset owner login password")
        return jsonify({"success": True, "message": f"Password reset successfully for owner of {salon.salon_name}."})
    return jsonify({"success": False, "message": "Failed to reset password."}), 500


@admin_bp.post("/api/salon/<int:salon_id>/delete")
@admin_required
def admin_delete_salon(salon_id):
    salon = authRepo.get_salon(salon_id)
    if not salon:
        return jsonify({"success": False, "message": f"Salon #{salon_id} not found."}), 404
        
    salon_name = salon.salon_name
    ok = adminRepo.delete_salon(salon_id)
    if ok:
        adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "DELETE_SALON", f"Salon #{salon_id}", f"Wiped salon {salon_name}")
        return jsonify({"success": True, "message": f"Salon #{salon_id} ({salon_name}) deleted completely."})
    return jsonify({"success": False, "message": "Failed to delete salon."}), 500


@admin_bp.post("/api/salon/<int:salon_id>/withhold")
@admin_required
def admin_withhold_salon(salon_id):
    data = request.get_json(silent=True) or {}
    reason = str(data.get("reason") or "").strip()
    salon = authRepo.get_salon(salon_id)
    if not salon:
        return jsonify({"success": False, "message": f"Salon #{salon_id} not found."}), 404

    # Expire salon access to withhold terminal operations
    now_ts = int(datetime.now().timestamp())
    authRepo.update_salon_plan(salon_id, salon.plan or "free", salon.billing_cycle or "trial", now_ts - 1)

    # Deliver Account Withheld notification email via Resend
    recipient = (salon.email or "").strip()
    if recipient:
        send_account_withheld_email(
            recipient_email=recipient,
            salon_name=salon.salon_name,
            owner_name=salon.name or "Salon Owner",
            reason=reason or "Subscription payment authorization failed or account verification was withheld by platform administrators.",
        )

    adminRepo.add_audit_log(
        session.get("admin_user", ADMIN_USER),
        "WITHHOLD_SALON",
        f"Salon #{salon_id} ({salon.salon_name})",
        f"Withheld access. Reason: {reason or 'Administrative withhold'}"
    )

    return jsonify({
        "success": True,
        "message": f"Account #{salon_id} ({salon.salon_name}) access withheld and notification sent to {recipient or 'owner'}."
    })


@admin_bp.get("/api/salon/<int:salon_id>/export")
@admin_required
def admin_export_salon(salon_id):
    export_data = adminRepo.export_salon(salon_id)
    if not export_data:
        return jsonify({"success": False, "message": f"Salon #{salon_id} not found."}), 404
    
    slug = export_data.get("salon", {}).get("booking_slug") or f"salon_{salon_id}"
    resp = Response(
        json.dumps(export_data, indent=2, default=str),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename=aurapos_backup_{slug}_{int(datetime.now().timestamp())}.json"}
    )
    adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "EXPORT_SALON_JSON", f"Salon #{salon_id}", "Downloaded full JSON backup")
    return resp


@admin_bp.get("/export-csv")
@admin_required
def admin_export_csv():
    salons = adminRepo.list_salons()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Salon Name", "Owner Name", "Email", "Phone", "Plan",
        "Billing Cycle", "Created Date", "Expires Date", "Seats", "Bills Count", "Total Revenue"
    ])
    for s in salons:
        writer.writerow([
            s.get("id"),
            s.get("salon_name"),
            s.get("name"),
            s.get("email"),
            s.get("phone"),
            s.get("plan"),
            s.get("billing_cycle"),
            _fmt_date(s.get("created_on")),
            _fmt_date(s.get("expires_on")),
            s.get("accounts_count", 1),
            s.get("bills_count", 0),
            s.get("revenue_total", 0),
        ])
    
    adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "EXPORT_ALL_CSV", "Platform", f"Exported {len(salons)} salons to CSV")
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=aurapos_salons_{date.today().isoformat()}.csv"}
    )


@admin_bp.post("/impersonate/<int:salon_id>")
@admin_required
def admin_impersonate(salon_id):
    salon = authRepo.get_salon(salon_id)
    if not salon:
        return jsonify({"success": False, "message": f"Salon #{salon_id} not found."}), 404
    
    details = adminRepo.salon_details(salon_id)
    accounts = details.get("accounts") if details else []
    admin_acc = next((a for a in accounts if a.get("auth_level") == "admin"), None) or (accounts[0] if accounts else None)
    
    username = admin_acc.get("username") if admin_acc else salon.email
    session["impersonating"] = True
    session["impersonating_admin"] = session.get("admin_user", ADMIN_USER)
    session["id"] = salon_id
    session["username"] = username
    session["auth_level"] = "admin"
    
    adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "IMPERSONATE", f"Salon #{salon_id}", f"Logged in as {salon.salon_name}")
    return jsonify({"success": True, "redirect_url": url_for("dashboard")})


@app.route("/admin/exit-impersonation")
def admin_exit_impersonation():
    if session.get("impersonating"):
        session.pop("impersonating", None)
        admin_user = session.pop("impersonating_admin", ADMIN_USER)
        session["is_admin"] = True
        session["admin_user"] = admin_user
        session.pop("id", None)
        session.pop("username", None)
        session.pop("auth_level", None)
        flash("Exited impersonation mode. Welcome back to SuperAdmin console.", "info")
    return redirect(url_for("admin.admin_home"))


@admin_bp.post("/announcement")
@admin_required
def admin_set_announcement():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or "").strip()
    b_type = str(data.get("type") or "info").strip().lower()
    active = bool(data.get("active", False))
    
    payload = {
        "message": message,
        "type": b_type if b_type in ("info", "warning", "success") else "info",
        "active": active and bool(message),
        "updated_at": int(datetime.now().timestamp()),
        "updated_by": session.get("admin_user", ADMIN_USER),
    }
    adminRepo.set_setting("platform_announcement", json.dumps(payload))
    adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "ANNOUNCEMENT", "Global", f"Banner: {message[:30]}... (active={payload['active']})")

    # Real-time WebSocket event broadcast to all connected clients
    try:
        socketio.emit("announcement_update", payload)
    except Exception as exc:
        logger.debug(f"Socket announcement broadcast error: {exc}")

    return jsonify({"success": True, "announcement": payload, "message": "Announcement broadcast updated!"})


@admin_bp.post("/maintenance-toggle")
@admin_required
def admin_maintenance_toggle():
    data = request.get_json(silent=True) or {}
    active = bool(data.get("active", False))
    message = str(data.get("message") or "Scheduled platform maintenance in progress. We'll be back shortly.").strip()
    payload = {
        "active": active,
        "message": message,
        "updated_at": int(datetime.now().timestamp()),
        "updated_by": session.get("admin_user", ADMIN_USER),
    }
    adminRepo.set_setting("platform_maintenance", json.dumps(payload))
    adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "MAINTENANCE_TOGGLE", "Global", f"Maintenance active={active}")

    # Real-time WebSocket event broadcast to all connected clients
    try:
        socketio.emit("maintenance_update", payload)
    except Exception as exc:
        logger.debug(f"Socket maintenance broadcast error: {exc}")

    return jsonify({"success": True, "maintenance": payload, "message": f"Maintenance mode {'enabled' if active else 'disabled'}."})


@app.get("/api/platform-status")
def api_platform_status():
    """Public read-only health & status for live client hydration and fallback polling."""
    ann_raw = adminRepo.get_setting("platform_announcement", "{}")
    maint_raw = adminRepo.get_setting("platform_maintenance", "{}")
    try:
        ann = json.loads(ann_raw) if ann_raw else {}
    except Exception:
        ann = {}
    try:
        maint = json.loads(maint_raw) if maint_raw else {}
    except Exception:
        maint = {}
    return jsonify({
        "success": True,
        "announcement": ann,
        "maintenance": maint,
        "timestamp": int(datetime.now().timestamp())
    })


@socketio.on("connect")
def handle_socket_connect():
    """Initial push of live platform announcement & maintenance state upon client connection."""
    try:
        ann_raw = adminRepo.get_setting("platform_announcement", "{}")
        maint_raw = adminRepo.get_setting("platform_maintenance", "{}")
        ann = json.loads(ann_raw) if ann_raw else {}
        maint = json.loads(maint_raw) if maint_raw else {}
        emit("platform_state", {"announcement": ann, "maintenance": maint})
    except Exception as exc:
        logger.debug(f"Socket connection handshake error: {exc}")


@admin_bp.get("/api/health")
@admin_required
def admin_health_check():
    start = datetime.now()
    try:
        counts = adminRepo.get_database_table_counts()
        duration_ms = round((datetime.now() - start).total_seconds() * 1000, 2)
        engine = "PostgreSQL (Supabase local)" if os.environ.get("USE_POSTGRES") else "Supabase REST"
        return jsonify({
            "success": True,
            "status": "healthy",
            "latency_ms": duration_ms,
            "engine": engine,
            "database_url": os.environ.get("DATABASE_URL", "default"),
            "table_counts": counts,
        })
    except Exception as exc:
        return jsonify({"success": False, "status": "unhealthy", "error": str(exc)}), 500


@admin_bp.post("/create-account")
@admin_required
def admin_create_account():
    """Manually create a salon + owner account with a custom plan & validity."""
    data = request.get_json(silent=True) or {}
    owner_name = str(data.get("owner_name") or "").strip()
    salon_name = str(data.get("salon_name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    phone = "".join(ch for ch in str(data.get("phone") or "") if ch.isdigit())
    password = str(data.get("password") or "")
    plan = (data.get("plan") or "free").strip().lower()
    cycle = (data.get("cycle") or "").strip().lower()
    try:
        days = int(float(str(data.get("days") or 0)))
    except (TypeError, ValueError):
        days = 0

    if not all([owner_name, salon_name, email, phone, password]):
        return jsonify({"success": False, "message": "Owner name, salon name, email, phone and password are all required."}), 400
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify({"success": False, "message": "Please enter a valid email address."}), 400
    if len(phone) != 10:
        return jsonify({"success": False, "message": "Phone number must be exactly 10 digits."}), 400
    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters."}), 400
    if plan not in ("free", "pro", "studio"):
        return jsonify({"success": False, "message": "Plan must be free, pro or studio."}), 400
    if cycle not in ("", "monthly", "yearly", "trial"):
        return jsonify({"success": False, "message": "Cycle must be monthly, yearly or trial."}), 400
    if days and (days < 1 or days > 3650):
        return jsonify({"success": False, "message": "Validity must be between 1 and 3650 days."}), 400

    if authRepo.check_exists(email, phone):
        return jsonify({"success": False, "message": "An account with this email or phone already exists."}), 409

    if not cycle:
        cycle = "trial" if plan == "free" else "monthly"

    now_ts = int(datetime.now().timestamp())
    tier = plan if plan in ("pro", "studio") else "free"
    plan_id = "free" if tier == "free" else (f"{tier}_{cycle}" if cycle == "yearly" else tier)
    resolved_tier, resolved_cycle, _pricing = resolve_plan(plan_id)
    expires_ts = (now_ts + days * 86400) if days else expires_for(resolved_cycle, now_ts)

    try:
        salon_id = authRepo.create_auth(
            owner_name, salon_name, phone, email, password,
            plan=plan_id, created_on=now_ts,
        )
    except Exception as exc:
        return jsonify({"success": False, "message": f"Could not create account: {exc}"}), 502

    if days:
        if not authRepo.update_salon_plan(salon_id, resolved_tier, resolved_cycle, expires_ts):
            return jsonify({
                "success": False,
                "message": "Account was created, but its custom plan validity could not be saved.",
            }), 502

    persisted = authRepo.get_salon(salon_id)
    if (
        not persisted
        or persisted.plan != resolved_tier
        or persisted.billing_cycle != resolved_cycle
        or int(persisted.expires_on or 0) != int(expires_ts)
    ):
        return jsonify({
            "success": False,
            "message": "Account was created, but its subscription state could not be verified.",
        }), 502

    try:
        authRepo.record_subscription(
            sub_id=f"admin_{str(uuid4())[:12]}",
            salon_id=salon_id,
            amount=0,
            plan=resolved_tier,
            cycle=resolved_cycle,
            receipt=f"created-by:{session.get('admin_user', ADMIN_USER)}",
            email=email,
            phone=phone,
        )
    except Exception as exc:
        print("Admin create subscription logging failed:", exc)

    adminRepo.add_audit_log(session.get("admin_user", ADMIN_USER), "CREATE_SALON", f"Salon #{salon_id} ({salon_name})", f"Owner {email} · {resolved_tier.upper()}")
    label = TIER_PLANS.get(resolved_tier, {}).get("label", resolved_tier.title())
    return jsonify({
        "success": True,
        "salon_id": salon_id,
        "message": f"{salon_name} created (owner {email}) → {label} · valid until {_fmt_date(expires_ts)}.",
    })


app.register_blueprint(admin_bp)


# ================= PRODUCTION ERROR HANDLERS =================

@app.errorhandler(RateLimitExceeded)
def ratelimit_handler(e):
    logger.warning(f"Rate limit exceeded: {request.remote_addr} on {request.path}")
    if request.blueprint == "admin" or request.path.startswith("/admin"):
        flash("Too many attempts — please wait 10 seconds and try again.", "error")
        return redirect(url_for("admin.admin_home"))
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({
            "error": "Too Many Requests",
            "message": f"Rate limit exceeded: {e.description}. Please slow down.",
            "status": 429
        }), 429
    flash("Too many requests — please wait a moment before trying again.", "warning")
    return redirect(request.referrer or url_for("dashboard"))


@app.errorhandler(413)
def request_entity_too_large(e):
    logger.warning(f"File upload size limit exceeded: {request.remote_addr} on {request.path}")
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({
            "error": "Payload Too Large",
            "message": "File size exceeds the allowed 5 MB upload limit.",
            "status": 413
        }), 413
    flash("Uploaded file is too large (maximum size is 5 MB).", "error")
    return redirect(request.referrer or url_for("dashboard"))


@app.errorhandler(404)
def page_not_found(e):
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({
            "error": "Not Found",
            "message": "The requested API endpoint was not found.",
            "status": 404
        }), 404
    return render_template('page_not_found.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    import traceback
    tb = traceback.format_exc()
    logger.error(f"Internal Server Error (500) on {request.path}:\n{tb}")
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unexpected server error occurred. Our engineering team has been notified.",
            "status": 500
        }), 500
    return render_template('page_not_found.html'), 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    if isinstance(e, RateLimitExceeded):
        return ratelimit_handler(e)
    import traceback
    tb = traceback.format_exc()
    logger.error(f"Unhandled Exception on {request.path}: {e}\n{tb}")
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({
            "error": "Internal Server Error",
            "message": str(e) if app.debug else "An unexpected error occurred.",
            "status": 500
        }), 500
    return render_template('page_not_found.html'), 500


if __name__ == '__main__':
    print("Hello!, Press Ctrl+C to exit.")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)


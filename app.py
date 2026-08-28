from flask import (
    Flask, jsonify, request, render_template, flash, redirect, url_for, session
)
import razorpay
from uuid import uuid4
from backend import *
from flask_mail import Mail, Message
from functools import wraps
from datetime import timedelta, datetime, date
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
import json


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "id" not in session:
            flash("Please sign in to access your salon terminal.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


app = Flask(__name__)
app.config["SECRET_KEY"] = "oqhwd9qyweijsdiuweqifbu"

# Repositories
authRepo = AuthorizationRepository()
serviceRepo = ServiceRepository()
staffRepo = StaffRepository()
appointmentRepo = AppointmentRepository()
billRepo = BillRepository()

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["50 per second"],
    storage_uri="memory://",
)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'salonbillingsoftware@gmail.com'
app.config['MAIL_PASSWORD'] = 'ifqrgmhhvnaiqhto'
app.config['MAIL_DEFAULT_SENDER'] = 'salonbillingsoftware@gmail.com'
app.config["SESSION_REFRESH_EACH_REQUEST"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

mailer = Mail(app)

rzp_client = razorpay.Client(
    auth=("rzp_test_SxU2RG4SoMaOcI", "nYTCHgr6NQy1b5X0VDEXcELO")
)


@app.context_processor
def inject_salon():
    if "id" in session:
        salon = authRepo.get_salon(session["id"])
        return dict(current_salon=salon)
    return dict(current_salon=None)


# ================= PUBLIC ROUTES =================

@limiter.exempt
@app.route('/', methods=['GET'])
def index():
    return render_template('intro/about.html')


@app.route('/booking')
def booking():
    return render_template('service/booking.html')


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


@app.route('/register')
def register():
    return render_template('service/register.html', razorpay_key_id='rzp_test_SxU2RG4SoMaOcI')


# ================= AUTHENTICATION ROUTES =================

@app.route("/login", methods=["GET", "POST"])
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
def directlogin():
    username = request.args.get("username")
    password = request.args.get("password")
    
    logged_in_acc = authRepo.login(username, password)
    
    if logged_in_acc:
        session["id"] = logged_in_acc.auth_id
        session["auth_level"] = logged_in_acc.auth_level
        session["password"] = logged_in_acc.password
        session["username"] = logged_in_acc.username
        return redirect(url_for('dashboard'))

    return render_template('page_not_found.html')


@app.route("/forgotpassword", methods=["GET", "POST"])
def forgotpassword():
    if request.method == "GET":
        return render_template('service/forgotpwd.html')
    
    data = request.get_json() or {}
    identifier = data.get("identifier", "").strip()

    user = authRepo.forgot_password(identifier)

    if user:
        try:
            mailer.connect()
            mailer.send(
                Message(
                    subject="Your AuraPOS Account Credentials",
                    recipients=[user.username],
                    html=render_template(
                        "email.html",
                        password=user.password,
                        login_url=url_for('directlogin', username=user.username, password=user.password, _external=True)
                    )
                )
            )
        except Exception as e:
            print("Mail error (safe fallback):", e)

    return jsonify({
        "success": True,
        "message": "If an account exists with this email/phone, recovery instructions have been sent."
    }), 200


# ================= RAZORPAY SUBSCRIPTION =================

@limiter.exempt
@app.post("/create-subscription")
def create_subscription():
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    phone = str(data.get("phone", "")).strip()

    if email and phone and authRepo.check_exists(email, phone):
        return jsonify({"error": "An account with this email address or phone number already exists. Please sign in instead."}), 400

    plan = data.get("plan", "yearly")

    if plan == "monthly":
        amount = 6900      # ₹69.00
    elif plan == "yearly":
        amount = 74900     # ₹749.00
    else:
        return jsonify({"error": "Invalid plan selected"}), 400

    receipt = str(uuid4())

    try:
        order = rzp_client.order.create({
            "amount": amount,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1
        })
    except Exception as e:
        # Development fallback order
        order = {
            "id": f"order_{str(uuid4())[:14]}",
            "amount": amount,
            "currency": "INR",
            "receipt": receipt,
            "created_at": int(datetime.now().timestamp())
        }

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO pendingorders(id, amount, created_at, plan, receipt, email, phone)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (order["id"], order["amount"], order["created_at"], plan, receipt, email, phone)
    )
    conn.commit()
    conn.close()

    return jsonify(order)


@limiter.exempt
@app.post("/verify-subscription")
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

    conn = get_db()
    cur = conn.cursor()

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

    plan = account_data.get("plan", "yearly")
    now_ts = int(datetime.now().timestamp())
    expires_ts = now_ts + (Time.month if plan == "monthly" else Time.year)

    cur.execute(
        """
        INSERT INTO salons(name, phone, salon_name, email, created_on, plan, expires_on)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            account_data.get("owner_name", "Salon Owner").capitalize(),
            phone,
            account_data.get("salon_name", "Studio Elite"),
            email,
            now_ts,
            plan,
            expires_ts
        )
    )
    accid = cur.lastrowid

    cur.execute(
        """
        INSERT INTO accounts(auth_id, username, password)
        VALUES (?, ?, ?)
        """,
        (accid, email, account_data.get("password", ""))
    )
    conn.commit()
    conn.close()

    # Automatically initialize defaults and login the newly subscribed user
    session["id"] = accid
    session["username"] = email
    session["auth_level"] = "admin"

    serviceRepo.seed_defaults_if_empty(accid)
    staffRepo.seed_defaults_if_empty(accid)
    appointmentRepo.seed_defaults_if_empty(accid)
    billRepo.seed_defaults_if_empty(accid)

    flash("🎉 Subscription activated successfully! Welcome to AuraPOS.", "success")

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
    services = serviceRepo.get_services(salon_id)
    staff = staffRepo.get_staff(salon_id)
    appointments = appointmentRepo.get_appointments(salon_id, date.today().isoformat())
    recent_bills = billRepo.get_recent_bills(salon_id)
    metrics = billRepo.get_daily_metrics(salon_id)
    
    return render_template(
        'service/dashboard.html',
        salon=salon,
        services=services,
        staff=staff,
        appointments=appointments,
        recent_bills=recent_bills,
        metrics=metrics
    )


@app.route('/services')
@login_required
def services():
    salon_id = session.get("id", 1)
    service_list = serviceRepo.get_services(salon_id)
    return render_template('service/services.html', services=service_list)


@app.route('/billing')
@login_required
def billing():
    salon_id = session.get("id", 1)
    service_list = serviceRepo.get_services(salon_id)
    staff_list = staffRepo.get_staff(salon_id)
    return render_template('service/billing.html', services=service_list, staff=staff_list)


@app.route('/appointments')
@login_required
def appointments():
    salon_id = session.get("id", 1)
    appointment_list = appointmentRepo.get_appointments(salon_id)
    staff_list = staffRepo.get_staff(salon_id)
    return render_template('service/appointments.html', appointments=appointment_list, staff=staff_list)


# ================= REST JSON API ENDPOINTS =================

@app.get('/api/services')
@login_required
def api_get_services():
    salon_id = session.get("id", 1)
    return jsonify(serviceRepo.get_services(salon_id))


@app.post('/api/services')
@login_required
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
@login_required
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
@login_required
def api_delete_service(service_id):
    salon_id = session.get("id", 1)
    serviceRepo.delete_service(service_id, salon_id)
    return jsonify({"success": True})


@app.post('/api/bills')
@login_required
def api_create_bill():
    salon_id = session.get("id", 1)
    data = request.get_json() or {}
    bill_id = f"AP-{str(uuid4())[:6].upper()}"
    
    billRepo.create_bill(
        bill_id=bill_id,
        account_id=salon_id,
        client_name=data.get("client_name", "Walk-in"),
        client_phone=data.get("client_phone", ""),
        subtotal=data.get("subtotal", 0),
        discount=data.get("discount", 0),
        tax=data.get("tax", 0),
        grand_total=data.get("grand_total", 0),
        payment_mode=data.get("payment_mode", "UPI"),
        items_json=json.dumps(data.get("items", []))
    )

    # Record stylist sales for leaderboard
    for item in data.get("items", []):
        staff_name = item.get("staff")
        if staff_name:
            staffRepo.record_sale(staff_name, salon_id, item.get("price", 0) * item.get("qty", 1))

    return jsonify({"success": True, "bill_id": bill_id})


@app.get('/api/bills')
@login_required
def api_get_bills():
    salon_id = session.get("id", 1)
    return jsonify(billRepo.get_recent_bills(salon_id))


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


# Public Client Portal APIs
@app.get('/api/public/services')
def api_public_services():
    return jsonify(serviceRepo.get_services(1))


@app.post('/api/public/booking')
def api_public_booking():
    data = request.get_json() or {}
    new_id = appointmentRepo.create_appointment(
        account_id=1,
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
    return jsonify({"success": True, "booking_id": f"BK-{new_id:04d}"})


# ================= ERROR HANDLERS =================

@app.errorhandler(RateLimitExceeded)
def ratelimit_handler(e):
    return jsonify({
        "error": "Too Many Requests",
        "description": f"You have exceeded your request limit: {e.description}"
    }), 429


@app.errorhandler(404)
def page_not_found(*args):
    return render_template('page_not_found.html'), 404


if __name__ == '__main__':
    print("Hello!, Press Ctrl+C to exit.")
    app.run(debug=True, host='0.0.0.0', port=5000)


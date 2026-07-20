from flask import Flask, jsonify, request, render_template, flash, redirect, url_for, session
import razorpay
from uuid import uuid4
from backend import *


app = Flask(__name__)
app.config["SECRET_KEY"] = "oqhwd9qyweijsdiuweqifbu"
authRepo = AuthorizationRepository()

rzp_client = razorpay.Client(
    auth=("rzp_test_SxU2RG4SoMaOcI", "nYTCHgr6NQy1b5X0VDEXcELO")
)

@app.route('/', methods=['GET'])
def index():
    return render_template('intro/about.html')

@app.route('/services')
def services():
    return render_template('service/services.html')

@app.route('/billing')
def billing():
    return render_template('service/billing.html')

@app.route('/billing-data')
def billing_data():
    return {
        "services": [
            {
                "id": 1,
                "name": "Hair Cut",
                "price": 250
            },
            {
                "id": 2,
                "name": "Hair Spa",
                "price": 900
            }
        ],
        "staff": [
            {
                "id": 1,
                "name": "Rahul"
            },
            {
                "id": 2,
                "name": "Priya"
            }
        ],
        "customers": [
            {
                "id": 1,
                "name": "John Doe",
                "phone": "9876543210"
            }
        ]
    }

@app.route('/contact')
def contact():
    return

@app.route('/privacy')
def privacy_policy():
    return render_template('intro/privacy.html')

@app.route('/register')
def register():
    return render_template('service/register.html', razorpay_key_id='rzp_test_SxU2RG4SoMaOcI')

@app.route('/dashboard')
def dashboard():
    return render_template('service/dashboard.html')




@app.post("/verify-subscription")
def verify_subscription():
    data = request.get_json()["payment"]
    account_data = request.get_json()["formData"]
    conn = get_db()
    cur = conn.cursor()
    

    try:
        # Verify Razorpay signature
        rzp_client.utility.verify_payment_signature({
            "razorpay_order_id": data["razorpay_order_id"],
            "razorpay_payment_id": data["razorpay_payment_id"],
            "razorpay_signature": data["razorpay_signature"],
        })

    except razorpay.errors.SignatureVerificationError:
        return jsonify({
            "success": False,
            "message": "Signature verification failed."
        }), 400

    # ------------------------------------------------------------------
    # Look up the order in your database.
    # When you created the order, you should have stored:
    #   - order_id
    #   - selected plan (monthly/yearly)
    #   - pending user information
    # ------------------------------------------------------------------
    pendingOrder = cur.execute(
        "SELECT * FROM pendingorders WHERE id = ?", (data["razorpay_order_id"],)
    ).fetchone()
    cur.execute(
        "INSERT INTO subscriptions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (pendingOrder[0],pendingOrder[1],pendingOrder[2],pendingOrder[3],pendingOrder[4],pendingOrder[5],pendingOrder[6], pendingOrder[7], )
    )
    cur.execute(
        "DELETE FROM pendingorders WHERE id = ?", (pendingOrder[0],)
    )

    accid = cur.execute(
        "INSERT INTO salons(name, phone, salon_name, email, created_on, plan, expires_on) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            account_data["owner_name"].capitalize(),
            account_data["phone"], account_data["salon_name"],
            account_data["email"], int(datetime.now().timestamp()),
            account_data["plan"], int(datetime.now().timestamp())+Time.month if account_data["plan"]=="monthly" else int(datetime.now().timestamp())+12*Time.month,
        )
    ).lastrowid

    cur.execute(
        """INSERT INTO accounts(auth_id, username, password) VALUES (?, ?, ?) """,
        (accid, account_data["email"], account_data["password"],)
    )
        
    conn.close()



    return jsonify({
        "success": True,
        "redirect": url_for("dashboard")
    })

@app.post("/create-subscription")
def create_subscription():
    data = request.get_json()

    plan = data["plan"]

    if plan == "monthly":
        amount = 6900      # ₹149.00
    elif plan == "yearly":
        amount = 74900     # ₹1609.00
    else:
        return jsonify({"error": "Invalid plan"}), 400

    receipt = str(uuid4())

    order = rzp_client.order.create({
        "amount": amount,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1
    })

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """INSERT INTO pendingorders(id, amount, created_at, plan, receipt, email, phone) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (order["id"], order["amount"], order["created_at"], data["plan"], receipt ,data["email"], data["phone"])
    )

    conn.close()

    return jsonify(order)

@app.route('/home')
def home():
    return "Hi"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        logged_in_acc = authRepo.login(username, password)

        if logged_in_acc:
            session["id"] = logged_in_acc.auth_id
            session["auth_level"] = logged_in_acc.auth_level

            return redirect(url_for('dashboard'))

        flash("Invalid username or password.", "error")

    return render_template("service/login.html")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

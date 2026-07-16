from flask import Flask, jsonify, request, render_template, flash, redirect, url_for
import razorpay
from uuid import uuid4


app = Flask(__name__)
app.config["SECRET_KEY"] = "oqhwd9qyweijsdiuweqifbu"

rzp_client = razorpay.Client(
    auth=("rzp_test_SxU2RG4SoMaOcI", "nYTCHgr6NQy1b5X0VDEXcELO")
)

@app.route('/', methods=['GET'])
def index():
    return render_template('base.html')

@app.route('/services')
def services():
    return

@app.route('/billing')
def billing():
    return

@app.route('/contact')
def contact():
    return

@app.route('/register')
def register():
    return render_template('service/register.html', razorpay_key_id='rzp_test_SxU2RG4SoMaOcI')


@app.post("/verify-subscription")
def verify_subscription():
    data = request.get_json()

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
    """
    order = PendingOrder.query.filter_by(
        razorpay_order_id=data["razorpay_order_id"]
    ).first()

    if order is None:
        return jsonify({
            "success": False,
            "message": "Unknown order."
        }), 404

    # Calculate expiry
    if order.plan == "monthly":
        expires_at = datetime.utcnow() + timedelta(days=30)
    else:
        expires_at = datetime.utcnow() + timedelta(days=365)

    # Create/activate account
    user = User(
        salon_name=order.salon_name,
        owner_name=order.owner_name,
        email=order.email,
        username=order.username,
        subscription_type=order.plan,
        subscription_started=datetime.utcnow(),
        subscription_expires=expires_at,
        razorpay_payment_id=data["razorpay_payment_id"],
        razorpay_order_id=data["razorpay_order_id"],
    )

    db.session.add(user)

    # Remove pending order
    db.session.delete(order)

    db.session.commit()"""

    return jsonify({
        "success": True,
        "redirect": url_for("dashboard")
    })

@app.post("/create-subscription")
def create_subscription():
    data = request.get_json()

    plan = data["plan"]

    if plan == "monthly":
        amount = 14900      # ₹149.00
    elif plan == "yearly":
        amount = 160900     # ₹1609.00
    else:
        return jsonify({"error": "Invalid plan"}), 400

    receipt = str(uuid4())

    order = rzp_client.order.create({
        "amount": amount,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1
    })

    return jsonify(order)

@app.route('/home')
def home():
    return "Hi"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Authenticate here...
        if username == "admin" and password == "password":
            return redirect(url_for("home"))

        flash("Invalid username or password.", "error")

    return render_template("service/login.html")


if __name__ == '__main__':
    app.run(debug=True)

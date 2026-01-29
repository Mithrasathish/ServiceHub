from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import date

app = Flask(__name__)
app.secret_key = "servicehub_secret"

# ---------------- DATABASE ---------------- #

def get_db():
    conn = sqlite3.connect(
        "servicehub.db",
        timeout=10,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn

def get_admin_payment():
    conn = get_db()
    payment = conn.execute(
        "SELECT * FROM admin_payment LIMIT 1"
    ).fetchone()
    conn.close()
    return payment


def create_tables():
    conn = get_db()

    # USERS TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        mobile TEXT,
        address TEXT
    )
    """)

    # PROVIDERS TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS providers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        service_type TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    # ADMIN TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS admin_payment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        upi_id TEXT,
        bank_name TEXT,
        account_number TEXT,
        ifsc TEXT
    );
    """)

    # BOOKINGS TABLE (fixed syntax)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        service_category TEXT,
        service_name TEXT,
        price REAL,
        booking_date TEXT,
        provider_id INTEGER,
        status TEXT DEFAULT 'Pending',
        admin_commission REAL DEFAULT 0,
        provider_amount REAL DEFAULT 0
    )
    """)

    
    conn.commit()
    conn.close()

ADMIN_COMMISSION = 0.10  # 10% as decimal

# ---------------- SERVICE PRICES ---------------- #

SERVICE_PRICES = {
    "Wiring Work": 500,
    "Fan Installation": 300,
    "Light Repair": 200,
    "Switch Replacement": 150,
    "Socket Repair": 180,
    "Tap Repair": 300,
    "Pipe Leakage Fix": 600,
    "Bathroom Fitting": 1200,
    "Water Motor Repair": 800,
    "AC Installation": 1500,
    "AC General Service": 700,
    "Furniture Repair": 800,
    "Custom Furniture": 2000,
    "Wooden Doors and Windows": 1500,
    "Home Cleaning": 500,
    "Office Cleaning": 1000,
    "Bathroom Cleaning": 700
}

SERVICE_CATEGORY = {
    "Wiring Work": "Electrician",
    "Fan Installation": "Electrician",
    "Light Repair": "Electrician",
    "Switch Replacement": "Electrician",
    "Socket Repair": "Electrician",
    "Tap Repair": "Plumber",
    "Pipe Leakage Fix": "Plumber",
    "Bathroom Fitting": "Plumber",
    "Water Motor Repair": "Plumber",
    "AC Installation": "AC",
    "AC General Service": "AC",
    "Furniture Repair": "Carpenter",
    "Custom Furniture": "Carpenter",
    "Wooden Doors and Windows": "Carpenter",
    "Home Cleaning": "Cleaning",
    "Office Cleaning": "Cleaning",
    "Bathroom Cleaning": "Cleaning"
}

# ---------------- HOME ---------------- #

@app.route("/")
def splash():
    return render_template("splash.html")

@app.route("/home")
def home():
    return render_template("home.html")


# ---------------- USER ---------------- #

@app.route("/user_register", methods=["GET", "POST"])
def user_register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        mobile = request.form.get("mobile")
        address = request.form.get("address")

        if not all([name, email, password, mobile, address]):
            return "All fields are required", 400

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO users (name, email, password, mobile, address)
                VALUES (?, ?, ?, ?, ?)
            """, (name, email, password, mobile, address))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Email already exists", 400
        conn.close()
        return redirect(url_for("user_login"))

    return render_template("user_register.html")

@app.route("/user_login", methods=["GET", "POST"])
def user_login():
    next_page = request.args.get("next")
    if request.method == "POST":
        conn = get_db()
        user = conn.execute("""
            SELECT * FROM users WHERE email=? AND password=?
        """, (request.form.get("email"), request.form.get("password"))).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(next_page or url_for("home"))

        return "Invalid Credentials"
    return render_template("user_login.html")

# ---------------- PROVIDER ---------------- #

@app.route("/provider_register", methods=["GET", "POST"])
def provider_register():
    if request.method == "POST":
        name = request.form.get("name")
        service_type = request.form.get("service_type")
        email = request.form.get("email")
        password = request.form.get("password")

        if not all([name, service_type, email, password]):
            return "All fields are required", 400

        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM providers WHERE email = ?",
            (email,)
        ).fetchone()
        if existing:
            conn.close()
            return "Email already registered. Please login.", 400

        conn.execute("""
            INSERT INTO providers (name, service_type, email, password)
            VALUES (?, ?, ?, ?)
        """, (name, service_type, email, password))
        conn.commit()
        conn.close()
        return redirect(url_for("provider_login"))

    return render_template("provider_register.html")

@app.route("/provider_login", methods=["GET", "POST"])
def provider_login():
    if request.method == "POST":
        conn = get_db()
        provider = conn.execute("""
            SELECT * FROM providers WHERE email=? AND password=?
        """, (request.form["email"], request.form["password"])).fetchone()
        conn.close()

        if provider:
            session["provider_id"] = provider["id"]
            session["service_type"] = provider["service_type"]
            return redirect(url_for("provider_dashboard"))

        return "Invalid Credentials"
    return render_template("provider_login.html")

@app.route("/provider_dashboard")
def provider_dashboard():
    if "provider_id" not in session:
        return redirect(url_for("provider_login"))

    conn = get_db()
    bookings = conn.execute("""
        SELECT
            b.id,
            b.service_name,
            b.price,
            b.booking_date,
            b.status,
            b.admin_commission,
            b.provider_amount,
            u.name AS user_name,
            u.mobile AS user_mobile,
            u.address AS user_address
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE b.service_category = ?
    """, (session["service_type"],)).fetchall()
    conn.close()

    admin_payment = get_admin_payment()

    return render_template("provider_dashboard.html", bookings=bookings,admin_payment=admin_payment)


@app.route("/update_booking/<int:booking_id>/<status>")
def update_booking(booking_id, status):
    if "provider_id" not in session:
        return redirect(url_for("provider_login"))

    conn = get_db()
    conn.execute("""
        UPDATE bookings
        SET status = ?, provider_id = ?
        WHERE id = ?
    """, (status, session["provider_id"], booking_id))
    conn.commit()
    conn.close()
    return redirect(url_for("provider_dashboard"))

@app.route("/complete_booking/<int:booking_id>", methods=["POST"])
def complete_booking(booking_id):
    if "provider_id" not in session:
        return redirect(url_for("provider_login"))

    conn = get_db()
    booking = conn.execute(
        "SELECT price FROM bookings WHERE id=?",
        (booking_id,)
    ).fetchone()

    price_num = float(booking["price"])

    admin_commission = round(price_num * 0.10, 2)
    provider_amount = round(price_num - admin_commission, 2)
         
    conn.execute("""
        UPDATE bookings
        SET 
            status = 'Completed',
            admin_commission = ?,
            provider_amount = ?
        WHERE id = ?
    """, (
        admin_commission,
        provider_amount,
        booking_id
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("provider_dashboard"))


# ---------------- ADMIN ---------------- #

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "admin":
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        return "Invalid Admin Credentials"
    return render_template("admin_login.html")

@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    users = conn.execute("SELECT * FROM users").fetchall()
    providers = conn.execute("SELECT * FROM providers").fetchall()

    bookings = conn.execute("""
        SELECT 
            b.id,
            u.name AS user_name,
            b.service_name,
            b.price,
            b.status,
            b.admin_commission,
            p.name AS provider_name
        FROM bookings b
        LEFT JOIN users u ON b.user_id = u.id
        LEFT JOIN providers p ON b.provider_id = p.id
        ORDER BY b.id DESC
    """).fetchall()

    total_profit = conn.execute("""
        SELECT COALESCE(SUM(admin_commission), 0) AS profit
        FROM bookings
        WHERE status = 'Completed'
    """).fetchone()["profit"]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        users=users,
        providers=providers,
        bookings=bookings,
        total_profit=total_profit
    )

@app.route("/admin_payment", methods=["GET", "POST"])
def admin_payment():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db()

    if request.method == "POST":
        upi_id = request.form["upi_id"]
        bank_name = request.form["bank_name"]
        account_number = request.form["account_number"]
        ifsc = request.form["ifsc"]

        existing = conn.execute(
            "SELECT id FROM admin_payment LIMIT 1"
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE admin_payment
                SET upi_id=?, bank_name=?, account_number=?, ifsc=?
                WHERE id=?
            """, (upi_id, bank_name, account_number, ifsc, existing["id"]))
        else:
            conn.execute("""
                INSERT INTO admin_payment
                (upi_id, bank_name, account_number, ifsc)
                VALUES (?, ?, ?, ?)
            """, (upi_id, bank_name, account_number, ifsc))

        conn.commit()

    payment = conn.execute(
        "SELECT * FROM admin_payment LIMIT 1"
    ).fetchone()

    conn.close()

    return render_template("admin_payment.html", payment=payment)

# ---------------- BOOK SERVICE ---------------- #

@app.route("/book_service", methods=["GET", "POST"])
def book_service():
    if "user_id" not in session:
        return redirect(url_for("user_login", next=request.url))

    service = request.args.get("service")
    price = SERVICE_PRICES.get(service, "")
    category = SERVICE_CATEGORY.get(service, "")

    if request.method == "POST":
        conn = get_db()
        conn.execute("""
            INSERT INTO bookings (user_id, service_category, service_name, price, booking_date)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            category,
            request.form["service"],
            request.form["price"], #or int() if you only use integers
            request.form["booking_date"]
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("my_bookings"))

    return render_template("book_service.html",
                           service=service,
                           price=price,
                           today=date.today())


# ---------------- MY BOOKINGS ---------------- #

@app.route("/my_bookings")
def my_bookings():
    if "user_id" not in session:
        return redirect(url_for("user_login"))

    conn = get_db()
    bookings = conn.execute("""
        SELECT b.service_name, b.price, b.booking_date, b.status,
               p.name AS provider_name
        FROM bookings b
        LEFT JOIN providers p ON b.provider_id = p.id
        WHERE b.user_id=?
    """, (session["user_id"],)).fetchall()
    conn.close()

    return render_template("my_bookings.html", bookings=bookings)




# ---------------- SERVICES ---------------- #

@app.route("/electrician")
def electrician(): return render_template("electrician.html")

@app.route("/plumber")
def plumber(): return render_template("plumber.html")

@app.route("/ac")
def ac(): return render_template("ac.html")

@app.route("/carpenter")
def carpenter(): return render_template("carpenter.html")

@app.route("/cleaning")
def cleaning(): return render_template("cleaning.html")

# ---------------- LOGOUT ---------------- #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/about")
def about():
    return render_template("about.html")



# ---------------- RUN ---------------- #

if __name__ == "__main__":
    create_tables()
    app.run(debug=True, use_reloader=False) 
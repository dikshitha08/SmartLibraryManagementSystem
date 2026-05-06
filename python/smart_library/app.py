from flask import Flask, render_template, request, redirect, session,flash
import sqlite3, os, random
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret"

UPLOAD_FOLDER = os.path.join("static", "uploads")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
def get_db():
    conn = sqlite3.connect("library.db")
    conn.row_factory = sqlite3.Row
    return conn
# ---------------- DB ----------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    # OWNER
    cur.execute("""
    CREATE TABLE IF NOT EXISTS owner(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT,
        phone TEXT,
        password TEXT,
        library TEXT,
        address TEXT
    )
    """)

    # CUSTOMER
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customer(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT,
        phone TEXT,
        password TEXT
    )
    """)

    # BOOKS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS books(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        name TEXT,
        author TEXT,
        summary TEXT,
        quantity INTEGER DEFAULT 0,
        price INTEGER DEFAULT 0,
        max_days INTEGER DEFAULT 7,
        fine_per_day INTEGER DEFAULT 1,
        image TEXT
    )
    """)

    # BORROW
    cur.execute("""
    CREATE TABLE IF NOT EXISTS borrow(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER,
        customer_name TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        payment TEXT,
        borrow_date TEXT,
        return_date TEXT,
        status TEXT,
        otp TEXT,
        fine INTEGER DEFAULT 0
    )
    """)

    # REVIEWS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book_id INTEGER,
        customer_name TEXT,
        rating INTEGER,
        review TEXT
    )
    """)

    conn.commit()
    conn.close()
# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")

# ---------------- OWNER ----------------
@app.route("/owner_signup", methods=["GET","POST"])
def owner_signup():
    if request.method == "POST":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO owner(username,email,phone,password,library,address)
        VALUES(?,?,?,?,?,?)
        """, (
            request.form["username"],
            request.form["email"],
            request.form["phone"],
            request.form["password"],
            request.form["library"],
            request.form["address"]
        ))
        conn.commit()
        conn.close()
        return redirect("/owner_login")
    return render_template("owner_signup.html")


@app.route("/owner_login", methods=["GET","POST"])
def owner_login():
    if request.method == "POST":
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM owner WHERE username=? AND password=?",
                    (request.form["username"], request.form["password"]))
        user = cur.fetchone()
        conn.close()

        if user:
            session.clear()
            session["user_type"] = "owner"
            session["owner_id"] = user["id"]
            return redirect("/owner_dashboard")
        else:
         flash("❌ Invalid username or password")

    return render_template("owner_login.html")


@app.route("/owner_dashboard")
def owner_dashboard():
    if session.get("user_type") != "owner":
        return redirect("/owner_login")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books WHERE owner_id=?", (session["owner_id"],))
    books = cur.fetchall()
    conn.close()

    return render_template("owner_dashboard.html", books=books)

# ---------------- ADD BOOK ----------------
@app.route("/add_book_page")
def add_book_page():

    if session.get("user_type") != "owner":
        return redirect("/owner_login")

    return render_template("add_book.html")
@app.route("/add_book", methods=["POST"])
def add_book():

    if session.get("user_type") != "owner":
        return redirect("/owner_login")

    img = request.files.get("image")

    path = ""

    # 🔥 IMAGE UPLOAD
    if img and img.filename:

        from werkzeug.utils import secure_filename

        filename = str(random.randint(1000,9999)) + "_" + secure_filename(img.filename)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        print("IMAGE OBJECT:", img)
        print("FILENAME:", filename)
        print("FILEPATH:", filepath)

        img.save(filepath)

        path = "uploads/" + filename

        print("PATH SAVED IN DB:", path)

    conn = get_db()

    cur = conn.cursor()

    cur.execute("""
    INSERT INTO books(
        owner_id,
        name,
        author,
        summary,
        quantity,
        price,
        max_days,
        fine_per_day,
        image
    )
    VALUES(?,?,?,?,?,?,?,?,?)
    """, (

        session["owner_id"],

        request.form["name"],

        request.form["author"],

        request.form["summary"],

        int(request.form["quantity"]),

        int(request.form["price"]),

        int(request.form["max_days"]),

        int(request.form["fine_per_day"]),

        path
    ))

    conn.commit()

    conn.close()

    flash("✅ Book added successfully!")

    return redirect("/add_book_page")
# ---------------- ANALYTICS ----------------
@app.route("/analytics")
def analytics():
    if session.get("user_type") != "owner":
        return redirect("/owner_login")

    owner_id = session.get("owner_id")

    conn = get_db()
    cur = conn.cursor()

    # ✅ total books
    cur.execute("SELECT COUNT(*) FROM books WHERE owner_id=?", (owner_id,))
    total_books = cur.fetchone()[0] or 0

    # ✅ total borrows
    cur.execute("""
        SELECT COUNT(*) FROM borrow 
        JOIN books ON borrow.book_id = books.id
        WHERE books.owner_id = ?
    """, (owner_id,))
    total_borrows = cur.fetchone()[0] or 0

    # ✅ income (better logic: based on approved borrows)
    cur.execute("""
     SELECT SUM(books.price) 
     FROM borrow
    JOIN books ON borrow.book_id = books.id
    WHERE borrow.status='Approved' AND books.owner_id=?
    """, (session["owner_id"],))

    income = cur.fetchone()[0] or 0

    # ✅ fines collected
    cur.execute("""
        SELECT SUM(fine) FROM borrow 
        JOIN books ON borrow.book_id = books.id
        WHERE books.owner_id = ?
    """, (owner_id,))
    fines = cur.fetchone()[0] or 0

    # ✅ cash payments (owner-specific)
    cur.execute("""
        SELECT COUNT(*) FROM borrow
        JOIN books ON borrow.book_id = books.id
        WHERE borrow.payment='Cash' AND books.owner_id=?
    """, (owner_id,))
    cash = cur.fetchone()[0] or 0

    # ✅ upi payments (owner-specific)
    cur.execute("""
        SELECT COUNT(*) FROM borrow
        JOIN books ON borrow.book_id = books.id
        WHERE borrow.payment='UPI' AND books.owner_id=?
    """, (owner_id,))
    upi = cur.fetchone()[0] or 0

    conn.close()

    return render_template("analytics.html",
        total_books=total_books,
        total_borrows=total_borrows,
        income=income,
        fines=fines,
        cash=cash,
        upi=upi
    )
# ---------------- REQUEST SYSTEM ----------------
@app.route("/requests")
def requests_page():
    if session.get("user_type") != "owner":
        return redirect("/owner_login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            borrow.id,
            borrow.customer_name,
            borrow.status,
            borrow.otp,
            books.name AS name
        FROM borrow
        JOIN books ON borrow.book_id = books.id
        WHERE books.owner_id = ? AND borrow.status = 'Pending'
    """, (session["owner_id"],))

    data = cur.fetchall()
    conn.close()

    return render_template("requests.html", data=data)
# ---------------- APPROVE (DISABLED - OTP REQUIRED) ----------------
@app.route("/approve/<int:id>")
def approve(id):
    # 🔒 Block direct approval
    return "❌ Use OTP to approve"


# ---------------- REJECT ----------------
@app.route("/reject/<int:id>")
def reject(id):
    if session.get("user_type") != "owner":
        return redirect("/owner_login")

    conn = get_db()
    cur = conn.cursor()

    # 🔥 prevent double action
    cur.execute("SELECT status FROM borrow WHERE id=?", (id,))
    row = cur.fetchone()

    if not row or row["status"] != "Pending":
        conn.close()
        return "❌ Already processed"

    cur.execute("UPDATE borrow SET status='Rejected' WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect("/requests")


# ---------------- OTP VERIFY + APPROVE ----------------
@app.route("/verify_otp/<int:id>", methods=["POST"])
def verify_otp(id):

    conn = get_db()
    cur = conn.cursor()

    entered_otp = request.form["otp"]

    # 🔥 GET REAL OTP
    cur.execute(
        "SELECT * FROM borrow WHERE id=?",
        (id,)
    )

    data = cur.fetchone()

    if entered_otp == data["otp"]:

        # ✅ APPROVE
        cur.execute(
            "UPDATE borrow SET status='Approved' WHERE id=?",
            (id,)
        )

        conn.commit()
        conn.close()

        flash("✅ OTP Verified Successfully")

    else:

        conn.close()

        flash("❌ Wrong OTP")

    return redirect("/requests")
# ---------------- RETURN + PAYMENT ----------------
@app.route("/return_book/<int:id>")
def return_book(id):
    if session.get("user_type") != "owner":
        return redirect("/owner_login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT book_id FROM borrow WHERE id=?", (id,))
    row = cur.fetchone()

    if row:
        cur.execute("UPDATE borrow SET status='Returned' WHERE id=?", (id,))
        cur.execute("UPDATE books SET quantity = quantity + 1 WHERE id=?", (row["book_id"],))

    conn.commit()
    conn.close()
    return redirect("/customers")


@app.route("/pay_return/<int:id>", methods=["POST"])
def pay_return(id):
    if session.get("user_type") != "owner":
        return redirect("/owner_login")

    payment = request.form["payment"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT book_id FROM borrow WHERE id=?", (id,))
    row = cur.fetchone()

    if row:
        cur.execute("UPDATE borrow SET status='Returned', payment=? WHERE id=?", (payment, id))
        cur.execute("UPDATE books SET quantity = quantity + 1 WHERE id=?", (row["book_id"],))

    conn.commit()
    conn.close()
    return redirect("/customers")
#---------edit _book------
@app.route("/edit_book/<int:id>", methods=["GET", "POST"])
def edit_book(id):
    if session.get("user_type") != "owner":
        return redirect("/owner_login")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("""
            UPDATE books
            SET name=?, author=?, summary=?, quantity=?, price=?, max_days=?, fine_per_day=?
            WHERE id=?
        """, (
            request.form["name"],
            request.form["author"],
            request.form["summary"],
            request.form["quantity"],
            request.form["price"],
            request.form["max_days"],
            request.form["fine_per_day"],
            id
        ))

        conn.commit()
        conn.close()

        flash("✅ Book updated successfully!")
        return redirect("/owner_dashboard")

    cur.execute("SELECT * FROM books WHERE id=?", (id,))
    book = cur.fetchone()
    conn.close()

    return render_template("edit_book.html", book=book)
# ---------------- CUSTOMERS ----------------
@app.route("/customers")
def customers():
    if session.get("user_type") != "owner":
        return redirect("/owner_login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT borrow.id, borrow.customer_name,
               books.name as book,
               borrow.borrow_date, borrow.return_date, borrow.status,
               books.fine_per_day
        FROM borrow
        JOIN books ON borrow.book_id = books.id
        WHERE books.owner_id = ?
    """, (session["owner_id"],))

    rows = cur.fetchall()
    data = []
    today = datetime.today()

    for r in rows:
        fine = 0
        if r["status"] != "Returned":
            due = datetime.strptime(r["return_date"], "%Y-%m-%d")
            if today > due:
                days = (today - due).days
                fine = days * r["fine_per_day"]
                cur.execute("UPDATE borrow SET fine=? WHERE id=?", (fine, r["id"]))

        data.append({**dict(r), "fine": fine})

    conn.commit()
    conn.close()

    return render_template("customers.html", data=data)

# ---------------- CUSTOMER ----------------
import re
from flask import request, redirect, render_template, flash

@app.route("/customer_signup", methods=["GET","POST"])
def customer_signup():
    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        # 🔐 PASSWORD VALIDATION
        if len(password) < 6:
            flash("❌ Password must be at least 6 characters")
            return redirect("/customer_signup")

        if not re.search(r"\d", password):
            flash("❌ Add at least 1 number 🔢")
            return redirect("/customer_signup")

        if not re.search(r"[!@#$%^&*]", password):
            flash("❌ Add at least 1 special character 🔐")
            return redirect("/customer_signup")

        # ✅ SAVE DATA
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO customer(username,email,phone,password)
        VALUES(?,?,?,?)
        """, (username, email, phone, password))

        conn.commit()
        conn.close()

        flash("✅ Account created successfully!")
        return redirect("/customer_login")

    return render_template("customer_signup.html")

@app.route("/customer_login", methods=["GET","POST"])
def customer_login():

    if request.method == "POST":

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT * FROM customer
            WHERE username=? AND password=?
        """, (
            request.form["username"],
            request.form["password"]
        ))

        user = cur.fetchone()

        conn.close()

        if user:

            # 🔥 IMPORTANT SESSION DATA
            session["user_type"] = "customer"

            # 🔥 THIS IS THE MAIN FIX
            session["customer_name"] = user["username"]

            return redirect("/libraries")

    return render_template("customer_login.html")
# ---------------- LIBRARIES ----------------
@app.route("/libraries")
def libraries():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, library, address FROM owner")
    libs = cur.fetchall()

    conn.close()

    return render_template("libraries.html", libs=libs)
# ---------------- BOOKS + BORROW ----------------
# ---------------- BOOK DETAIL ----------------
@app.route("/book/<int:id>")
def book_detail(id):
    if not session.get("user_type"):
        return redirect("/customer_login")

    conn = get_db()
    cur = conn.cursor()

    # 🔥 get book
    cur.execute("SELECT * FROM books WHERE id=?", (id,))
    book = cur.fetchone()

    if not book:
        conn.close()
        return "❌ Book not found"

    borrowed = False
    pending = False
    remaining_days = None

    if session.get("user_type") == "customer":

        # ✅ check approved borrow
        cur.execute("""
            SELECT return_date FROM borrow 
            WHERE book_id=? AND customer_name=? AND status='Approved'
        """, (id, session["customer_name"]))
        row = cur.fetchone()

        if row:
            borrowed = True

            from datetime import datetime
            today = datetime.today()
            return_date = datetime.strptime(row["return_date"], "%Y-%m-%d")

            remaining_days = (return_date - today).days

        # ✅ check pending request
        cur.execute("""
            SELECT 1 FROM borrow
            WHERE book_id=? AND customer_name=? AND status='Pending'
        """, (id, session["customer_name"]))

        if cur.fetchone():
            pending = True

    # 🔥 reviews
    cur.execute("SELECT * FROM reviews WHERE book_id=? ORDER BY id DESC", (id,))
    reviews = cur.fetchall()

    # 🔥 rating
    cur.execute("SELECT AVG(rating) FROM reviews WHERE book_id=?", (id,))
    avg = cur.fetchone()
    avg_rating = round(avg[0], 1) if avg and avg[0] else None

    conn.close()

    return render_template(
        "book_detail.html",
        book=book,
        borrowed=borrowed,
        pending=pending,
        remaining_days=remaining_days,
        reviews=reviews,
        avg_rating=avg_rating
    )
# ---------------- OLD BORROW (SAFE VERSION) ----------------
@app.route("/old_borrow/<int:book_id>", methods=["POST"])
def old_borrow(book_id):
    if session.get("user_type") != "customer":
        return redirect("/customer_login")

    conn = get_db()
    cur = conn.cursor()

    # 🔥 get book
    cur.execute("SELECT quantity, max_days FROM books WHERE id=?", (book_id,))
    book = cur.fetchone()

    if not book:
        conn.close()
        return "❌ Book not found"

    if book["quantity"] <= 0:
        conn.close()
        return "❌ Book Out of Stock"

    # 🔥 get form data safely
    from_date = request.form.get("from_date")
    to_date = request.form.get("to_date")

    if not from_date or not to_date:
        conn.close()
        return "❌ Missing dates"

    from datetime import datetime
    try:
        d1 = datetime.strptime(from_date, "%Y-%m-%d")
        d2 = datetime.strptime(to_date, "%Y-%m-%d")
    except:
        conn.close()
        return "❌ Invalid date format"

    # ❌ invalid date
    if d2 <= d1:
        conn.close()
        return "❌ Invalid date selection"

    # ❌ exceed max days
    if (d2 - d1).days > book["max_days"]:
        conn.close()
        return "❌ Exceeds max borrow days"

    # 🔥 prevent duplicate pending request
    cur.execute("""
        SELECT 1 FROM borrow
        WHERE book_id=? AND customer_name=? AND status='Pending'
    """, (book_id, session["customer_name"]))

    if cur.fetchone():
        conn.close()
        return "⚠ You already requested this book"

    # 🔥 generate OTP
    import random
    otp = str(random.randint(1000, 9999))

    # 🔥 insert request
    cur.execute("""
        INSERT INTO borrow(
            book_id, customer_name, email, phone, address,
            borrow_date, return_date, status, otp
        )
        VALUES(?,?,?,?,?,?,?,?,?)
    """, (
        book_id,
        session["customer_name"],
        request.form.get("email"),
        request.form.get("phone"),
        request.form.get("address"),
        from_date,
        to_date,
        "Pending",
        otp
    ))

    conn.commit()
    conn.close()

    print("OTP:", otp)

    return redirect("/borrow_history")
#----------top books rated--------
@app.route("/top_books")
def top_books():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT books.*, AVG(reviews.rating) as avg_rating
        FROM books
        JOIN reviews ON books.id = reviews.book_id
        GROUP BY books.id
        ORDER BY avg_rating DESC
        LIMIT 5
    """)

    books = cur.fetchall()
    conn.close()

    return render_template("top_books.html", books=books)
#---------review----------
@app.route("/add_review/<int:id>", methods=["POST"])
def add_review(id):
    if session.get("user_type") != "customer":
        return redirect("/customer_login")

    conn = get_db()
    cur = conn.cursor()

    # 🔥 check if already reviewed
    cur.execute("""
        SELECT * FROM reviews 
        WHERE book_id=? AND customer_name=?
    """, (id, session["customer_name"]))

    existing = cur.fetchone()

    if existing:
        conn.close()
        flash("⚠ You already reviewed this book")
        return redirect(f"/book/{id}")

    cur.execute("""
        INSERT INTO reviews(book_id, customer_name, rating, review)
        VALUES(?,?,?,?)
    """, (
        id,
        session["customer_name"],
        int(request.form["rating"]),
        request.form["review"]
    ))

    conn.commit()
    conn.close()

    flash("✅ Review added!")
    return redirect(f"/book/{id}")
#-------------edit+delete review----------
@app.route("/delete_review/<int:id>")
def delete_review(id):
    if session.get("user_type") != "customer":
        return redirect("/customer_login")

    conn = get_db()
    cur = conn.cursor()

    # 🔐 allow delete only if review belongs to logged-in user
    cur.execute("""
        DELETE FROM reviews
        WHERE id=? AND customer_name=?
    """, (id, session["customer_name"]))

    conn.commit()
    conn.close()

    flash("🗑 Review deleted")
    return redirect(request.referrer)


@app.route("/edit_review/<int:id>", methods=["POST"])
def edit_review(id):
    if session.get("user_type") != "customer":
        return redirect("/customer_login")

    rating = request.form.get("rating")
    review = request.form.get("review", "").strip()

    # 🔒 basic validation
    try:
        rating = int(rating)
    except:
        flash("❌ Invalid rating")
        return redirect(request.referrer)

    if rating < 1 or rating > 5:
        flash("❌ Rating must be between 1 and 5")
        return redirect(request.referrer)

    if not review:
        flash("❌ Review cannot be empty")
        return redirect(request.referrer)

    conn = get_db()
    cur = conn.cursor()

    # 🔐 ensure the review belongs to the logged-in user
    cur.execute("""
        UPDATE reviews
        SET rating=?, review=?
        WHERE id=? AND customer_name=?
    """, (
        rating,
        review,
        id,
        session["customer_name"]
    ))

    conn.commit()

    # 🔍 check if update actually happened
    if cur.rowcount == 0:
        conn.close()
        flash("❌ You are not allowed to edit this review")
        return redirect(request.referrer)

    conn.close()

    flash("✏ Review updated successfully")
    return redirect(request.referrer)
# ---------------- BORROW PAGE ----------------
@app.route("/borrow/<int:id>", methods=["GET", "POST"])
def borrow(id):
    print(request.method)

    if session.get("user_type") != "customer":
        return redirect("/customer_login")

    conn = get_db()
    cur = conn.cursor()

    # 🔥 GET BOOK
    cur.execute("SELECT * FROM books WHERE id=?", (id,))
    book = cur.fetchone()

    if request.method == "POST":

        print("FORM SUBMITTED ✅")

        import random
        from datetime import datetime, timedelta

        otp = str(random.randint(1000, 9999))

        borrow_date = datetime.now().date()

        return_date = borrow_date + timedelta(days=book["max_days"])

        cur.execute("""
            INSERT INTO borrow(
                book_id,
                customer_name,
                email,
                phone,
                address,
                payment,
                borrow_date,
                return_date,
                status,
                otp,
                fine
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (

            id,

            session["customer_name"],

            request.form["email"],
            request.form["phone"],
            request.form["address"],
            request.form["payment"],

            str(borrow_date),
            str(return_date),

            "Pending",

            otp,

            0
        ))

        conn.commit()

        print("DATA INSERTED ✅")

        conn.close()

        return redirect("/borrow_history")

    conn.close()

    return render_template("borrow.html", book=book)
    # 🔥 generate OTP (replace dummy)
    import random
    otp = str(random.randint(1000, 9999))

    # 🔥 insert request (NO stock reduction here)
    cur.execute("""
        INSERT INTO borrow
        (book_id, customer_name, email, phone, address, payment, borrow_date, return_date, status, otp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        id,
        request.form["name"],
        request.form["email"],
        request.form["phone"],
        request.form["address"],
        request.form["payment"],
        from_date,
        to_date,
        "Pending",
        otp
    ))

    conn.commit()
    conn.close()

    print("OTP:", otp)  # 🔥 debug (see in terminal)

    return redirect("/borrow_history")
# ---------------- HISTORY ----------------
from datetime import datetime

@app.route("/borrow_history")
def borrow_history():

    if session.get("user_type") != "customer":
        return redirect("/customer_login")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔥 FETCH CUSTOMER BORROWS
    cur.execute("""
        SELECT 
            borrow.*,
            books.name,
            books.fine_per_day
        FROM borrow
        JOIN books ON borrow.book_id = books.id
        WHERE borrow.customer_name = ?
        ORDER BY borrow.id DESC
    """, (session["customer_name"],))

    rows = cur.fetchall()

    updated_data = []

    today = datetime.now().date()

    for r in rows:

        r = dict(r)

        fine = 0

        # 🔥 AUTO FINE
        if r["status"] == "Approved":

            try:
                return_date = datetime.strptime(
                    r["return_date"],
                    "%Y-%m-%d"
                ).date()

                overdue_days = (today - return_date).days

                if overdue_days > 0:
                    fine = overdue_days * r["fine_per_day"]

            except:
                fine = 0

        r["fine"] = fine

        updated_data.append(r)

    conn.close()

    return render_template(
        "borrow_history.html",
        data=updated_data
    )
#------------------
@app.route("/books/<int:id>")
def books_page(id):
    if session.get("user_type") != "customer":
        return redirect("/customer_login")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM books WHERE owner_id=?", (id,))
    books = cur.fetchall()

    cur.execute("""
        SELECT * FROM books 
        WHERE owner_id=? AND quantity > 0
        ORDER BY quantity DESC LIMIT 3
    """, (id,))
    recommended = cur.fetchall()

    conn.close()

    return render_template("books.html", books=books, recommended=recommended)
# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    init_db()   # ✅ correct place
    app.run(debug=True)
#----------fine------------
from datetime import datetime

def calculate_fine(return_date, fine_per_day):
    today = datetime.today()
    return_date = datetime.strptime(return_date, "%Y-%m-%d")

    overdue_days = (today - return_date).days

    if overdue_days > 0:
        return overdue_days * fine_per_day
    return 0
#----------

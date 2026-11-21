"""Application volontairement vulnérable, réservée à une démonstration locale."""

from flask import Flask, abort, request, render_template, redirect, session, g
import hashlib
import hmac
import sqlite3
import os
import re
import secrets
import time

app = Flask(__name__)
app.secret_key = "demo-secret-key-NOT-FOR-PRODUCTION"
DB_PATH = os.path.join(os.path.dirname(__file__), "demo.db")
DEMO_CARD_NUMBER = "4242424242424242"
DEMO_CARD_CVC = "123"
DEMO_OTP = "123456"

PRODUCT_SEEDS = [
    ("MacBook Air 13″", "Ordinateurs", "1 399 €", "Fin, léger et rapide pour vous accompagner toute la journée.", "💻", 12),
    ("iPhone 15", "Téléphones", "899 €", "Un appareil photo avancé et une autonomie pensée pour le quotidien.", "📱", 24),
    ("Casque Studio Pro", "Audio", "349 €", "Un son immersif avec réduction de bruit adaptative.", "🎧", 18),
    ("Montre Connectée S9", "Montres", "429 €", "Suivez votre activité et restez connecté en un coup d’œil.", "⌚", 9),
    ("Souris MX Precision", "Accessoires", "109 €", "Une souris ergonomique conçue pour la précision et le confort.", "🖱️", 31),
    ("Console PlayBox X", "Gaming", "599 €", "Des performances nouvelle génération pour vos jeux favoris.", "🎮", 7),
    ("SSD Portable 1 To", "Stockage", "99 €", "Un stockage rapide et compact pour vos fichiers importants.", "💾", 42),
    ("Appareil photo Alpha", "Photo", "799 €", "Un hybride polyvalent pour les photos et vidéos 4K.", "📷", 5),
    ("Tablette Air 11″", "Tablettes", "749 €", "Un grand écran lumineux dans un format facile à transporter.", "📟", 14),
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        DROP TABLE IF EXISTS demo_checkouts;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS comments;
        DROP TABLE IF EXISTS products;
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price TEXT NOT NULL,
            description TEXT NOT NULL,
            icon TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            bio TEXT DEFAULT '',
            favorite_product INTEGER DEFAULT 1
        );
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id),
            author TEXT NOT NULL,
            content TEXT NOT NULL
        );
        CREATE TABLE demo_checkouts (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            product_id INTEGER NOT NULL REFERENCES products(id),
            otp_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            expires_at INTEGER NOT NULL
        );
        """
    )
    db.executemany(
        "INSERT INTO products (name, category, price, description, icon, stock) VALUES (?, ?, ?, ?, ?, ?)",
        PRODUCT_SEEDS,
    )
    db.execute(
        "INSERT INTO users (username, password, bio, favorite_product) VALUES (?, ?, ?, ?)",
        ("admin", "SuperSecret123", "Administrateur du site.", 1),
    )
    db.execute(
        "INSERT INTO users (username, password, bio, favorite_product) VALUES (?, ?, ?, ?)",
        ("melek", "motdepasse1", "Etudiante en ingenierie.", 2),
    )
    db.commit()
    db.close()


@app.route("/")
def home():
    return redirect("/catalog" if session.get("username") else "/login")


@app.route("/catalog")
def catalog():
    if "username" not in session:
        return redirect("/login")
    products = get_db().execute(
        "SELECT * FROM products ORDER BY id"
    ).fetchall()
    return render_template("home.html", products=products)


def checkout_page(product, phase, checkout_id=None, error=None):
    return render_template(
        "checkout.html",
        product=product,
        phase=phase,
        checkout_id=checkout_id,
        error=error,
    )


@app.route("/checkout/<int:product_id>")
def checkout(product_id):
    if "username" not in session:
        return redirect("/login")
    product = get_db().execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if product is None:
        abort(404)
    return checkout_page(product, "card")


@app.route("/checkout/<int:product_id>/start", methods=["POST"])
def start_checkout(product_id):
    if "username" not in session:
        return redirect("/login")
    db = get_db()
    product = db.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if product is None:
        abort(404)

    card_number = request.form.get("card_number", "").replace(" ", "")
    expiry = request.form.get("expiry", "")
    cvc = request.form.get("cvc", "")
    if (
        card_number != DEMO_CARD_NUMBER
        or cvc != DEMO_CARD_CVC
        or not re.fullmatch(r"(0[1-9]|1[0-2])/[0-9]{2}", expiry)
    ):
        return checkout_page(
            product,
            "card",
            error="Utilisez uniquement la carte fictive indiquée pour cette démo.",
        ), 400

    expiry_month, expiry_year = expiry.split("/")
    current_time = time.gmtime()
    if (2000 + int(expiry_year), int(expiry_month)) < (
        current_time.tm_year,
        current_time.tm_mon,
    ):
        return checkout_page(
            product, "card", error="La date d’expiration est dépassée."
        ), 400

    checkout_id = secrets.token_urlsafe(32)
    otp_hash = hashlib.sha256(
        "{}:{}".format(checkout_id, DEMO_OTP).encode("utf-8")
    ).hexdigest()
    db.execute(
        """
        INSERT INTO demo_checkouts
            (id, username, product_id, otp_hash, expires_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            checkout_id,
            session["username"],
            product_id,
            otp_hash,
            int(time.time()) + 300,
        ),
    )
    db.commit()
    return checkout_page(product, "otp", checkout_id=checkout_id)


@app.route("/checkout/verify", methods=["POST"])
def verify_checkout():
    if "username" not in session:
        return redirect("/login")
    checkout_id = request.form.get("checkout_id", "")
    db = get_db()
    checkout_record = db.execute(
        """
        SELECT * FROM demo_checkouts
        WHERE id = ? AND username = ?
        """,
        (checkout_id, session["username"]),
    ).fetchone()
    if checkout_record is None:
        abort(404)

    product = db.execute(
        "SELECT * FROM products WHERE id = ?", (checkout_record["product_id"],)
    ).fetchone()
    if checkout_record["status"] != "pending":
        return checkout_page(
            product, "otp", checkout_id=checkout_id,
            error="Cette session de paiement n’est plus active.",
        ), 400
    if checkout_record["expires_at"] < int(time.time()):
        db.execute(
            "UPDATE demo_checkouts SET status = 'expired' WHERE id = ?",
            (checkout_id,),
        )
        db.commit()
        return checkout_page(
            product, "otp", checkout_id=checkout_id,
            error="Le code a expiré. Recommencez le paiement.",
        ), 400

    submitted_code = request.form.get("otp", "")
    submitted_hash = hashlib.sha256(
        "{}:{}".format(checkout_id, submitted_code).encode("utf-8")
    ).hexdigest()
    if not hmac.compare_digest(submitted_hash, checkout_record["otp_hash"]):
        attempts = checkout_record["attempts"] + 1
        status = "failed" if attempts >= 5 else "pending"
        db.execute(
            "UPDATE demo_checkouts SET attempts = ?, status = ? WHERE id = ?",
            (attempts, status, checkout_id),
        )
        db.commit()
        error = (
            "Trop de tentatives. Recommencez le paiement."
            if status == "failed"
            else "Code incorrect. Vérifiez le code de démonstration."
        )
        return checkout_page(
            product, "otp", checkout_id=checkout_id, error=error
        ), 400

    db.execute(
        "UPDATE demo_checkouts SET status = 'completed' WHERE id = ?",
        (checkout_id,),
    )
    db.commit()
    return checkout_page(product, "success")


# --------------------------------------------------------------------------
# VULNERABILITE 1 : SQL INJECTION (login)
# La requete est construite par concatenation de chaines au lieu d'utiliser
# des parametres lies (placeholders "?"). Un attaquant peut injecter du SQL
# directement dans le champ "username" ou "password".
# --------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("username"):
        return redirect("/catalog")
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # VULNERABLE : concatenation directe dans la requete SQL
        query = "SELECT * FROM users WHERE username = '{}' AND password = '{}'".format(
            username, password
        )
        db = get_db()
        cur = db.execute(query)
        user = cur.fetchone()

        if user:
            session["username"] = user["username"]
            return redirect("/catalog")
        else:
            error = "Identifiants invalides. Requete executee : " + query
    return render_template("login.html", error=error)


# --------------------------------------------------------------------------
# La recherche est volontairement vulnérable à un XSS réfléchi (voir template).
# --------------------------------------------------------------------------
@app.route("/search")
def search():
    if "username" not in session:
        return redirect("/login")
    q = request.args.get("q", "")
    results = []
    if q:
        pattern = "%{}%".format(q)
        results = get_db().execute(
            "SELECT * FROM products WHERE name LIKE ? OR category LIKE ? OR description LIKE ? ORDER BY id",
            (pattern, pattern, pattern),
        ).fetchall()
    return render_template("search.html", q=q, results=results)


@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):
    if "username" not in session:
        return redirect("/login")
    db = get_db()
    if request.method == "POST" and session.get("username") == username:
        new_bio = request.form["bio"]
        db.execute("UPDATE users SET bio = ? WHERE username = ?", (new_bio, username))
        db.commit()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user is None:
        abort(404)
    is_owner = session.get("username") == username
    return render_template("profile.html", user=user, is_owner=is_owner)


@app.route("/product/<int:product_id>", methods=["GET", "POST"])
def product(product_id):
    if "username" not in session:
        return redirect("/login")
    db = get_db()
    item = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if item is None:
        abort(404)
    if request.method == "POST":
        author = session["username"]
        content = request.form.get("content", "")
        db.execute(
            "INSERT INTO comments (product_id, author, content) VALUES (?, ?, ?)",
            (product_id, author, content),
        )
        db.commit()
        return redirect("/product/{}".format(product_id))
    comments = db.execute(
        "SELECT * FROM comments WHERE product_id = ? ORDER BY id DESC", (product_id,)
    ).fetchall()
    return render_template("product.html", product=item, comments=comments)


@app.route("/wall")
def wall():
    return redirect("/catalog")


@app.route("/csrf-demo")
def csrf_demo():
    if "username" not in session:
        return redirect("/login")
    db = get_db()
    user = db.execute(
        "SELECT favorite_product FROM users WHERE username = ?",
        (session["username"],),
    ).fetchone()
    favorite = db.execute(
        "SELECT * FROM products WHERE id = ?", (user["favorite_product"],)
    ).fetchone()
    products = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    return render_template(
        "csrf_demo.html", products=products, favorite=favorite
    )


@app.route("/preferences", methods=["POST"])
def update_preference():
    if "username" not in session:
        return redirect("/login")
    try:
        product_id = int(request.form["product_id"])
    except (KeyError, ValueError):
        abort(400, description="Préférence invalide.")
    db = get_db()
    if db.execute("SELECT 1 FROM products WHERE id = ?", (product_id,)).fetchone() is None:
        abort(400, description="Préférence invalide.")
    db.execute(
        "UPDATE users SET favorite_product = ? WHERE username = ?",
        (product_id, session["username"]),
    )
    db.commit()
    return redirect("/csrf-demo")


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password),
            )
            db.commit()
            return redirect("/login")
        except sqlite3.IntegrityError:
            error = "Ce nom d'utilisateur existe deja."
    return render_template("register.html", error=error)


@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/login")
    db = get_db()
    user = db.execute(
        "SELECT favorite_product FROM users WHERE username = ?",
        (session["username"],),
    ).fetchone()
    favorite = db.execute(
        "SELECT * FROM products WHERE id = ?", (user["favorite_product"],)
    ).fetchone()
    return render_template(
        "dashboard.html", username=session["username"], favorite=favorite
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", debug=False, port=5000)

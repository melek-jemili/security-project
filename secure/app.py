"""
DEMO PEDAGOGIQUE - VERSION CORRIGEE
=====================================
Meme fonctionnalites que la version vulnerable, avec les correctifs :
  1. Requetes SQL parametrees (plus de concatenation de chaines)      -> anti SQLi
  2. Pas de filtre Jinja2 "| safe" sur le contenu utilisateur          -> anti XSS
  3. Mots de passe haches (werkzeug) au lieu de texte clair
A lancer en local : python app.py
"""

from flask import Flask, request, render_template, redirect, session, g
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
DB_PATH = os.path.join(os.path.dirname(__file__), "demo.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
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
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS comments;
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            bio TEXT DEFAULT ''
        );
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT,
            content TEXT
        );
        """
    )
    db.execute(
        "INSERT INTO users (username, password, bio) VALUES (?, ?, ?)",
        ("admin", generate_password_hash("SuperSecret123"), "Administrateur du site."),
    )
    db.execute(
        "INSERT INTO users (username, password, bio) VALUES (?, ?, ?)",
        ("melek", generate_password_hash("motdepasse1"), "Etudiante en ingenierie."),
    )
    db.commit()
    db.close()


@app.route("/")
def home():
    return render_template("home.html")


# CORRIGE : requete parametree (placeholders "?") -> le contenu saisi est
# toujours traite comme une simple valeur, jamais comme du SQL executable.
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user and check_password_hash(user["password"], password):
            session["username"] = user["username"]
            return redirect("/dashboard")
        else:
            error = "Identifiants invalides."
    return render_template("login.html", error=error)


# CORRIGE : requete parametree avec LIKE -> plus d'injection possible.
@app.route("/search")
def search():
    q = request.args.get("q", "")
    results = []
    if q:
        db = get_db()
        results = db.execute(
            "SELECT id, username, bio FROM users WHERE username LIKE ?",
            (f"%{q}%",),
        ).fetchall()
    return render_template("search.html", q=q, results=results, error=None)


# CORRIGE : pas de "| safe" dans le template -> Jinja2 echappe automatiquement
# tout caractere HTML special (<, >, ", ...) avant affichage.
@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):
    db = get_db()
    if request.method == "POST" and session.get("username") == username:
        new_bio = request.form["bio"]
        db.execute("UPDATE users SET bio = ? WHERE username = ?", (new_bio, username))
        db.commit()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    is_owner = session.get("username") == username
    return render_template("profile.html", user=user, is_owner=is_owner)


@app.route("/wall", methods=["GET", "POST"])
def wall():
    db = get_db()
    if request.method == "POST":
        author = session.get("username", "anonyme")
        content = request.form["content"]
        db.execute("INSERT INTO comments (author, content) VALUES (?, ?)", (author, content))
        db.commit()
    comments = db.execute("SELECT * FROM comments ORDER BY id DESC").fetchall()
    return render_template("wall.html", comments=comments)


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
                (username, generate_password_hash(password)),
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
    return render_template("dashboard.html", username=session["username"])


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    init_db()  # reset a chaque lancement pour une demo propre
    app.run(debug=True, port=5001)

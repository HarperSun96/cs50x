import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    id = session["user_id"]
    purchase = db.execute(
        "SELECT symbol, name, SUM(shares) as shares, price FROM purchase WHERE id = ? GROUP BY symbol",
        id,
    )
    cash = db.execute("SELECT cash FROM users WHERE id = ?", id)[0]["cash"]
    total = 0
    for item in purchase:
        total += float(item["price"]) * int(item["shares"])
    return render_template(
        "index.html", purchase=purchase, cash=usd(cash), total=usd(total)
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Quote fail")

        shares = request.form.get("shares")
        try:
            shares = int(shares)
        except ValueError:
            return apology("Shares need to be positive integer")
        if shares <= 0:
            return apology("Shares need to be positive integer")
        symbol = quote["symbol"]
        name = quote["name"]
        price = quote["price"]
        rows = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        id = session["user_id"]
        cash_update = rows[0]["cash"] - price * shares
        if cash_update < 0:
            return apology("Not enough buying power")
        else:
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_update, id)
            db.execute(
                "INSERT INTO purchase(id, type, symbol, name, shares, price) VALUES(?, ?, ?, ?, ?, ?)",
                id,
                "BUY",
                symbol,
                name,
                shares,
                price,
            )
            return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    id = session["user_id"]
    history = db.execute(
        "SELECT type, symbol, price, shares, time FROM purchase WHERE id = ? ORDER BY time DESC",
        id,
    )
    for i in history:
        for key in i.keys():
            if key == "price":
                i[key] = usd(i[key])
    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Quote fail", 400)
        else:
            name = quote["name"]
            price = usd(quote["price"])
            symbol = quote["symbol"]
            return render_template("quoted.html", name=name, price=price, symbol=symbol)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password must match password confirmation", 400)
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        # Ensure username exists and password is correct
        if len(rows) != 0:
            return apology("invalid username", 400)
        else:
            db.execute(
                "INSERT INTO users(username, hash) VALUES(?, ?)",
                request.form.get("username"),
                generate_password_hash(request.form.get("password")),
            )
        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    id = session["user_id"]
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Quote fail")
        shares = request.form.get("shares")
        try:
            shares = int(shares)
        except ValueError:
            return apology("Shares need to be positive integer")
        if shares <= 0:
            return apology("Shares need to be positive integer")
        symbol = quote["symbol"]
        name = quote["name"]
        price = quote["price"]
        shares_hold = db.execute(
            "SELECT SUM(shares) as shares FROM purchase WHERE id = ? AND symbol = ? GROUP BY symbol",
            id,
            symbol,
        )[0]["shares"]
        if shares_hold < shares:
            return apology("Not enough shares to sell")

        rows = db.execute("SELECT cash FROM users WHERE id = ?", id)
        cash_update = rows[0]["cash"] + price * shares
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_update, id)
        db.execute(
            "INSERT INTO purchase(id, type, symbol, name, shares, price) VALUES(?, ?, ?, ?, ?, ?)",
            id,
            "SELL",
            symbol,
            name,
            -shares,
            price,
        )
        return redirect("/")
    else:
        symbol = db.execute(
            "SELECT symbol FROM purchase WHERE id = ? GROUP BY symbol", id
        )
        return render_template("sell.html", symbol=symbol)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit Cash"""
    id = session["user_id"]
    if request.method == "POST":
        deposit = request.form.get("deposit")
        rows = db.execute("SELECT cash FROM users WHERE id = ?", id)
        cash_update = rows[0]["cash"] + deposit
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_update, id)
        return redirect("/")
    else:
        return render_template("deposit.html")

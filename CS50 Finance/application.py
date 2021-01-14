import os
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    #Access users portfolio info
    portfolio = db.execute("SELECT stock, number FROM portfolio WHERE user_id = :user_id", user_id=session['user_id'])

    if len(portfolio) == 0:
        return apology("Sorry you currently have no holdings")
    #initialise list
    portfolio_data = []

    for row in portfolio:
        stock = lookup(row['stock'])['symbol']
        shares = int(row['number'])
        name = lookup(row['stock'])['name']
        price = lookup(row['stock'])['price']
        total_value = float(price * shares)
        #appends new vals to list
        portfolio_data.append({"stock": stock, "shares": shares, "company": name, "pps": price, "total_value": total_value})

    #Determine users total cash
    row = db.execute("SELECT cash FROM users WHERE id = :id", id=session['user_id'])
    cash = float(row[0]['cash'])
    return render_template("index.html", portfolio=portfolio_data, cash = cash)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    #Ensure that user submits via post
    if request.method == "POST":

        symbol = request.form.get("symbol")
        quote = lookup(symbol.upper())
        shares = int(request.form.get("shares"))

        #checks
        if not symbol:
            return apology("Please enter symbol", 403)

        if not quote:
            return ("Please enter valid stock symbol")

        if not shares:
           return apology("Plese enter number of shares", 403)

        row = db.execute("SELECT cash FROM users WHERE id = :id", id = session['user_id'])

        #Ensure user has enough cash
        cash = float(row[0]['cash'])

        total_price = float(quote['price'] * shares)

        #store username in var
        username_row = db.execute("SELECT username FROM users WHERE id = :id", id=session['user_id'])

        username = username_row[0]['username']

        #store current number stock
        curr_portfolio = db.execute("SELECT number FROM portfolio WHERE stock = :stock AND user_id = :user_id", stock = symbol, user_id = session['user_id'])

        if cash < total_price:
             return apology("Sorry, you have insufficient funds")
        else:

            #THIS LOGIC IS WHY NO NEW DATA IS BEING ADDED TO THE PORTFOLIO
            #check if user already owns the stock
            if not curr_portfolio:

                db.execute("INSERT INTO portfolio (username, stock, number, price_per_share, cash, user_id) VALUES (:username, :stock, :number, :price_per_share, :cash, :user_id)",
                username=username, stock=symbol, number=shares, price_per_share = quote['price'], cash=cash, user_id=session['user_id'])

            else:
                db.execute("UPDATE portfolio SET number = number + :bought WHERE stock = :symbol", bought = shares, symbol = symbol)

            #Subtract price of shares from the users cash balance
            db.execute("UPDATE users SET cash = cash - :spent WHERE id = :id", spent=total_price, id=session['user_id'])
            curr_date = datetime.now()
            db.execute("INSERT INTO transactions (id, stock, quantity, price, date) VALUES (:id, :stock, :quantity, :price, :date)",
            id=session['user_id'],  stock=symbol,  quantity=shares, price=quote['price'] * shares, date=curr_date)

        return redirect("/")

    else:
        return render_template("buy.html")
@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    history = db.execute("SELECT stock, quantity, price, date FROM transactions WHERE id = :id", id=session['user_id'])

    if len(history) == 0:
        return apology("Sorry you have anys transactions on record")

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
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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
     #Ensure that user is submitting via post
    if request.method == "POST":
     #Look up stock to see if it exists
        search = lookup(request.form.get("symbol"))
     #Ensure that the user enters a stock into the input field
        if not request.form.get("symbol"):
            return apology("Please enter a symbol", 400)
     #If stock does not exist return apology
        if not search:
            return apology("Invalid symbol", 400)

        return render_template("quoted.html", stock=search)

    else:
     #If user acceses via GET then return the form
     return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Ensure that user is reached via post
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)


        # check that the input in confirmation matches the password field
        elif not password == confirmation:
            return apology("passwords must match")


        # request password from from and create hash
        hash = generate_password_hash(password)
        #insert a new user to the database

        rows = db.execute("SELECT username FROM users WHERE username = :username", username = request.form.get("username"))


       #Ensure that this is a unique username
        if len(rows) > 0:
            return apology("username already exists", 403)

       #insert new user into database
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username = request.form.get("username"), hash = hash)

        return redirect("/")

    else:
        return render_template("register.html")

@app.route("/addcash", methods=["GET", "POST"])
def addcash():

    if request.method == "POST":

        curr_user = session['user_id']
        row = db.execute("SELECT cash FROM users WHERE id = :user", user = curr_user)
        balance = row[0]['cash']
        #initialise variables
        cash_added = int(request.form.get("cash"))

        #Ensure cash value is above 50
        if cash_added < 50:
            return apology("Invalid, must add at least £50")

        #add cash to the users table
        db.execute("UPDATE users SET cash = cash + :added WHERE id = :id", added=cash_added, id=session['user_id'])

        #new balance
        row_2 = db.execute("SELECT cash FROM users WHERE id = :id", id=session['user_id'])
        new_balance = row_2[0]['cash']

        return render_template("cashadded.html", balance=balance, cash_added=+int(cash_added), new_balance=new_balance)
    else:
        return render_template("addcash.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":

        #initialise variables
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        quote = lookup(symbol)
        price = quote['price']
        selling_price = shares * price


         #Ensure stock is valid
        if not quote:
            return apology("Please enter valid symbol")

              #Ensure user enters symbol
        if not symbol:
            return apology("Plese enter a symbol")

        #access stock from portfolio
        available = db.execute("SELECT number FROM portfolio WHERE stock = :stock AND user_id = :user_id", stock=symbol, user_id=session['user_id'])

        #store number of stock
        owned = available[0]['number']
        shares_after = owned - shares

        if owned >= shares:
            #subtract sold stock from user portfolio
            portfolio = db.execute("UPDATE portfolio SET number = number - :shares WHERE user_id = :user_id AND stock = :stock", shares=shares, user_id =session['user_id'], stock=symbol)
            #update users cash balance
            db.execute("UPDATE users SET cash = cash + :sold WHERE id = :id", sold=selling_price, id=session['user_id'])
            #add sale to transactions
            curr_date = datetime.now()
            db.execute("INSERT INTO transactions (id, stock, quantity, price, date) VALUES (:id, :stock, :quantity, :price, :date)",
            id=session['user_id'], stock=symbol, quantity=-int(shares), price=selling_price, date=curr_date)
            #delete stock from portfolio
            return redirect("/history")
        else:
            return apology("You do not own enough shares")


    else:

            portfolio = db.execute("SELECT stock FROM portfolio WHERE user_id = :user_id", user_id=session['user_id'])

            return render_template("sell.html", portfolio=portfolio)
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)

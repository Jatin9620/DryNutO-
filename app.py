import os, sqlite3, hmac, hashlib, uuid
from flask import Flask, render_template, request, jsonify, abort

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), "dryonut.db")
KEY_ID, KEY_SECRET = os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET")

# id, name, category, price, mrp, emoji, color, tag, description
_P = [
 ("date-bites","Date Bites – No Refined Sugar","Date Bites",345,425,"🍫","#e9c9a0","Must-try","Soft date bites made with 6 wholesome ingredients and no refined sugar."),
 ("date-apple","Date Bites Apple Pie","Date Bites",345,425,"🍎","#f3d6a4","","Apple & cinnamon date bites. Dessert that loves you back."),
 ("date-choco","Date Bites Dark Choco Orange","Date Bites",345,425,"🍊","#d9b38c","Must-try","Dark chocolate and orange zest for serious cravings."),
 ("date-assorted","Date Bites – Assorted Pack","Date Bites",979,1275,"🎁","#ecd2b0","Value","All flavours in one pack. Perfect for sharing."),
 ("makhana-himalayan","Himalayan Salted Makhana (4×77g)","Roasted Makhana",899,956,"🌸","#efe3cf","Bestseller","Roasted, never fried. Low-calorie and gluten-free."),
 ("makhana-achaari","Achaari Chatka Makhana (4×77g)","Roasted Makhana",849,956,"🌶️","#f2c9a0","","Tangy pickle-spiced roasted makhana."),
 ("makhana-cheesy","Cheesy Cheddar Makhana (4×77g)","Roasted Makhana",849,956,"🧀","#f6dc92","","Crunchy makhana dusted with cheddar."),
 ("panchmeva","Panchmeva Dry Fruits Mix (405g)","Dry Fruit Mixes",469,549,"🥜","#e8caa0","Must-try","Almonds, cashews, raisins, walnuts and more."),
 ("trail-mix","7-in-1 Trail Mix (200g)","Dry Fruit Mixes",299,335,"🥣","#e2c08d","Bestseller","Dry fruits, berries and seeds rich in protein and omega-3."),
 ("berry-mix","8-in-1 Berry Mix (200g)","Dry Fruit Mixes",292,349,"🫐","#d8c3e0","","Eight dried fruits and berries, rich in Vitamin C."),
 ("apricots","Dried Turkish Apricots (200g)","Essentials",689,699,"🍑","#f6c98a","","Naturally sweet and tangy real Turkish apricots."),
 ("chia","Chia Seeds (200g)","Seeds",199,229,"🌱","#cfd8c0","","100% natural, no added preservatives."),
 ("pumpkin","Premium Pumpkin Seeds (200g)","Seeds",199,245,"🎃","#c9dcae","","Natural source of magnesium."),
 ("almonds","California Almonds (500g)","Essentials",449,520,"🌰","#e0bf94","Bestseller","Crunchy premium almonds, zero adulteration."),
]
PRODUCTS = [dict(id=a,name=b,cat=c,price=d,mrp=e,emoji=f,color=g,tag=h,desc=i) for a,b,c,d,e,f,g,h,i in _P]
PMAP = {p["id"]: p for p in PRODUCTS}

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, product_id TEXT, name TEXT, rating INT, text TEXT, ts DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, address TEXT, items TEXT, total REAL, status TEXT, payment_id TEXT, rzp_order TEXT, ts DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, name TEXT, email TEXT, message TEXT, ts DEFAULT CURRENT_TIMESTAMP);""")
    if not c.execute("SELECT 1 FROM reviews").fetchone():
        seed = [("date-bites","Aarushi M.",5,"Tastes like dessert but I don't feel guilty. Ordered thrice already!"),
                ("trail-mix","Rohit K.",4,"Fresh and crunchy. Great office snack."),
                ("makhana-himalayan","Neha S.",5,"Light, crispy and perfectly salted."),
                ("panchmeva","Imran A.",5,"Premium quality, sealed fresh. Delivery in 2 days."),
                ("berry-mix","Priya D.",4,"Loved the berries, kids finished it in a day."),
                ("almonds","Vikram P.",5,"Best almonds I've bought online.")]
        c.executemany("INSERT INTO reviews(product_id,name,rating,text) VALUES(?,?,?,?)", seed); c.commit()
    c.close()

def totals(items):
    sub = sum(PMAP[i]["price"] * q for i, q in items)
    disc = round(sub * (0.10 if sub > 1500 else 0.08 if sub > 899 else 0), 2)
    ship = 0 if sub - disc >= 499 or sub == 0 else 49
    return dict(subtotal=sub, discount=disc, shipping=ship, total=round(sub - disc + ship, 2))

def clean_items(raw):
    out = []
    for it in raw or []:
        if it.get("id") in PMAP and 0 < int(it.get("qty", 0)) <= 50: out.append((it["id"], int(it["qty"])))
    return out

@app.context_processor
def inject(): return dict(PRODUCTS=PRODUCTS)

# ---------- pages ----------
@app.route("/")
def home():
    c = db(); rv = c.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT 3").fetchall(); c.close()
    return render_template("home.html", reviews=rv, cats=sorted({p["cat"] for p in PRODUCTS}))
@app.route("/shop")
def shop(): return render_template("shop.html", cats=sorted({p["cat"] for p in PRODUCTS}))
@app.route("/product/<pid>")
def product(pid):
    p = PMAP.get(pid) or abort(404)
    c = db(); rv = c.execute("SELECT * FROM reviews WHERE product_id=? ORDER BY id DESC", (pid,)).fetchall(); c.close()
    related = [x for x in PRODUCTS if x["cat"] == p["cat"] and x["id"] != pid][:4]
    return render_template("product.html", p=p, reviews=rv, related=related)
@app.route("/reviews")
def reviews():
    c = db(); rv = c.execute("SELECT * FROM reviews ORDER BY id DESC").fetchall(); c.close()
    return render_template("reviews.html", reviews=rv)
@app.route("/about")
def about(): return render_template("about.html")
@app.route("/contact")
def contact(): return render_template("contact.html")
@app.route("/cart")
def cart(): return render_template("cart.html")
@app.route("/checkout")
def checkout(): return render_template("checkout.html", live=bool(KEY_ID and KEY_SECRET))
@app.route("/success/<oid>")
def success(oid):
    c = db(); o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone(); c.close()
    return render_template("success.html", o=o or abort(404))

# ---------- APIs ----------
@app.post("/api/reviews")
def add_review():
    d = request.get_json(force=True)
    pid, name, text = d.get("product_id"), (d.get("name") or "").strip()[:60], (d.get("text") or "").strip()[:500]
    rating = int(d.get("rating", 0))
    if pid not in PMAP or not name or not text or not 1 <= rating <= 5: return jsonify(error="Please fill all fields"), 400
    c = db(); c.execute("INSERT INTO reviews(product_id,name,rating,text) VALUES(?,?,?,?)", (pid, name, rating, text)); c.commit(); c.close()
    return jsonify(ok=True)

@app.post("/api/contact")
def add_msg():
    d = request.get_json(force=True)
    if not all(d.get(k) for k in ("name", "email", "message")): return jsonify(error="All fields required"), 400
    c = db(); c.execute("INSERT INTO messages(name,email,message) VALUES(?,?,?)", (d["name"], d["email"], d["message"])); c.commit(); c.close()
    return jsonify(ok=True)

@app.post("/api/order")
def create_order():
    d = request.get_json(force=True); cu = d.get("customer", {}); items = clean_items(d.get("items"))
    if not items or not all(cu.get(k) for k in ("name", "email", "phone", "address")): return jsonify(error="Incomplete order details"), 400
    t = totals(items); oid = "DON" + uuid.uuid4().hex[:8].upper(); rzp = None; mode = "demo"
    if KEY_ID and KEY_SECRET:
        import razorpay
        rzp = razorpay.Client(auth=(KEY_ID, KEY_SECRET)).order.create(
            {"amount": int(t["total"] * 100), "currency": "INR", "receipt": oid})["id"]; mode = "razorpay"
    c = db(); c.execute("INSERT INTO orders(id,name,email,phone,address,items,total,status,rzp_order) VALUES(?,?,?,?,?,?,?,?,?)",
        (oid, cu["name"], cu["email"], cu["phone"], cu["address"], ",".join(f"{i}x{q}" for i, q in items), t["total"], "pending", rzp)); c.commit(); c.close()
    return jsonify(order_id=oid, mode=mode, amount=int(t["total"] * 100), key=KEY_ID, rzp_order=rzp, totals=t)

def mark_paid(oid, pay_id):
    c = db(); c.execute("UPDATE orders SET status='paid', payment_id=? WHERE id=?", (pay_id, oid)); c.commit(); c.close()

@app.post("/api/verify")  # Razorpay signature verification
def verify():
    d = request.get_json(force=True)
    c = db(); o = c.execute("SELECT * FROM orders WHERE id=?", (d.get("order_id"),)).fetchone(); c.close()
    if not o or not KEY_SECRET: return jsonify(error="Invalid order"), 400
    body = f'{o["rzp_order"]}|{d.get("razorpay_payment_id")}'
    sig = hmac.new(KEY_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, d.get("razorpay_signature", "")): return jsonify(error="Signature mismatch"), 400
    mark_paid(o["id"], d["razorpay_payment_id"]); return jsonify(ok=True)

@app.post("/api/demo-pay")  # Simulated gateway (used only when no Razorpay keys are set)
def demo_pay():
    d = request.get_json(force=True); card = "".join(ch for ch in d.get("card", "") if ch.isdigit())
    if KEY_ID or len(card) != 16: return jsonify(error="Enter a valid 16-digit test card (e.g. 4111 1111 1111 1111)"), 400
    if card.endswith("0002"): return jsonify(error="Card declined (demo)"), 402
    mark_paid(d.get("order_id"), "demo_" + uuid.uuid4().hex[:10]); return jsonify(ok=True)

if __name__ == "__main__":
    init_db(); app.run(debug=True, port=5000)

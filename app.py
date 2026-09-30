from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key')
DB = os.path.join(os.path.dirname(__file__), 'pos.db')


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c


def init_db():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','staff')), active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, sku TEXT UNIQUE NOT NULL,
      category TEXT, size TEXT, color TEXT, price REAL NOT NULL, stock INTEGER DEFAULT 0,
      reorder_level INTEGER DEFAULT 5, supplier_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL);
    CREATE TABLE IF NOT EXISTS suppliers(
      id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, email TEXT, address TEXT);
    CREATE TABLE IF NOT EXISTS sales(
      id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_no TEXT UNIQUE NOT NULL, staff_id INTEGER,
      subtotal REAL NOT NULL, discount REAL DEFAULT 0, tax REAL DEFAULT 0, total REAL NOT NULL,
      payment_method TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(staff_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS sale_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
      qty INTEGER NOT NULL, price REAL NOT NULL, amount REAL NOT NULL,
      FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
      FOREIGN KEY(product_id) REFERENCES products(id));
    CREATE TABLE IF NOT EXISTS returns(
      id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER, product_id INTEGER NOT NULL,
      qty INTEGER NOT NULL, reason TEXT, amount REAL NOT NULL, processed_by INTEGER,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(sale_id) REFERENCES sales(id), FOREIGN KEY(product_id) REFERENCES products(id),
      FOREIGN KEY(processed_by) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS ledger(
      id INTEGER PRIMARY KEY AUTOINCREMENT, entry_type TEXT NOT NULL, reference TEXT,
      description TEXT, amount REAL NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
        c.execute('INSERT INTO users(name,username,password,role) VALUES(?,?,?,?)', ('Administrator','admin',generate_password_hash('admin123'),'admin'))
        c.execute('INSERT INTO users(name,username,password,role) VALUES(?,?,?,?)', ('Billing Staff','staff',generate_password_hash('staff123'),'staff'))
    if not c.execute('SELECT 1 FROM suppliers LIMIT 1').fetchone():
        cur=c.execute('INSERT INTO suppliers(name,phone,email,address) VALUES(?,?,?,?)', ('ABC Textiles','9876543210','supplier@example.com','Coimbatore'))
        sid=cur.lastrowid
        samples=[('Cotton Shirt','TS001','Shirts','M','Blue',799,25,5,sid),('Denim Jeans','TJ001','Jeans','32','Black',1299,18,4,sid),('Cotton Saree','SA001','Sarees','Free','Red',1599,12,3,sid)]
        c.executemany('INSERT INTO products(name,sku,category,size,color,price,stock,reorder_level,supplier_id) VALUES(?,?,?,?,?,?,?,?,?)',samples)
    c.commit(); c.close()


def login_required(role=None):
    def deco(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*a,**kw):
            if 'user_id' not in session: return redirect(url_for('login'))
            if role and session.get('role') != role: return redirect(url_for('dashboard'))
            return fn(*a,**kw)
        return wrapper
    return deco


def invoice():
    return 'INV-' + datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[-10:]

@app.context_processor
def inject():
    return {'current_user': session.get('name'), 'role': session.get('role')}

@app.route('/')
def home(): return redirect(url_for('dashboard')) if 'user_id' in session else redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=request.form['username'].strip(); p=request.form['password']
        c=db(); user=c.execute('SELECT * FROM users WHERE username=? AND active=1',(u,)).fetchone(); c.close()
        if user and check_password_hash(user['password'],p):
            session.update(user_id=user['id'],name=user['name'],role=user['role'])
            return redirect(url_for('dashboard'))
        flash('Invalid username or password','danger')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required()
def dashboard():
    c=db(); stats={
      'products':c.execute('SELECT COUNT(*) n FROM products').fetchone()['n'],
      'staff':c.execute("SELECT COUNT(*) n FROM users WHERE role='staff' AND active=1").fetchone()['n'],
      'sales':c.execute("SELECT COUNT(*) n FROM sales WHERE date(created_at)=date('now')").fetchone()['n'],
      'revenue':c.execute("SELECT COALESCE(SUM(total),0) n FROM sales WHERE date(created_at)=date('now')").fetchone()['n'],
      'low':c.execute('SELECT COUNT(*) n FROM products WHERE stock<=reorder_level').fetchone()['n']}
    recent=c.execute('SELECT * FROM sales ORDER BY id DESC LIMIT 8').fetchall(); c.close()
    return render_template('dashboard.html',stats=stats,recent=recent)

@app.route('/products', methods=['GET','POST'])
@login_required('admin')
def products():
    c=db()
    if request.method=='POST':
        try:
            data=request.form; c.execute('INSERT INTO products(name,sku,category,size,color,price,stock,reorder_level,supplier_id) VALUES(?,?,?,?,?,?,?,?,?)',
              (data['name'],data['sku'],data.get('category'),data.get('size'),data.get('color'),float(data['price']),int(data.get('stock',0)),int(data.get('reorder_level',5)),data.get('supplier_id') or None)); c.commit(); flash('Product added','success')
        except Exception as e: flash(str(e),'danger')
    rows=c.execute('SELECT p.*,s.name supplier FROM products p LEFT JOIN suppliers s ON p.supplier_id=s.id ORDER BY p.id DESC').fetchall(); suppliers=c.execute('SELECT * FROM suppliers').fetchall(); c.close()
    return render_template('products.html',products=rows,suppliers=suppliers)

@app.post('/products/delete/<int:id>')
@login_required('admin')
def product_delete(id):
    c=db(); c.execute('DELETE FROM products WHERE id=?',(id,)); c.commit(); c.close(); flash('Product deleted','success'); return redirect(url_for('products'))

@app.route('/suppliers', methods=['GET','POST'])
@login_required('admin')
def suppliers():
    c=db()
    if request.method=='POST':
        d=request.form; c.execute('INSERT INTO suppliers(name,phone,email,address) VALUES(?,?,?,?)',(d['name'],d.get('phone'),d.get('email'),d.get('address'))); c.commit(); flash('Supplier added','success')
    rows=c.execute('SELECT * FROM suppliers ORDER BY id DESC').fetchall(); c.close(); return render_template('suppliers.html',suppliers=rows)

@app.post('/suppliers/delete/<int:id>')
@login_required('admin')
def supplier_delete(id):
    c=db(); c.execute('DELETE FROM suppliers WHERE id=?',(id,)); c.commit(); c.close(); flash('Supplier deleted','success'); return redirect(url_for('suppliers'))

@app.route('/staff', methods=['GET','POST'])
@login_required('admin')
def staff():
    c=db()
    if request.method=='POST':
        d=request.form
        try:
            c.execute('INSERT INTO users(name,username,password,role) VALUES(?,?,?,?)',(d['name'],d['username'],generate_password_hash(d['password']),d.get('role','staff'))); c.commit(); flash('Staff account created','success')
        except Exception as e: flash(str(e),'danger')
    rows=c.execute('SELECT id,name,username,role,active FROM users ORDER BY id').fetchall(); c.close(); return render_template('staff.html',staff=rows)

@app.post('/staff/toggle/<int:id>')
@login_required('admin')
def staff_toggle(id):
    c=db(); c.execute('UPDATE users SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(id,)); c.commit(); c.close(); return redirect(url_for('staff'))

@app.route('/billing')
@login_required()
def billing():
    c=db(); products=c.execute('SELECT * FROM products WHERE stock>0 ORDER BY name').fetchall(); c.close(); return render_template('billing.html',products=products)

@app.post('/api/bill')
@login_required()
def create_bill():
    data=request.get_json(); items=data.get('items',[]); discount=float(data.get('discount',0)); tax_rate=float(data.get('tax_rate',0)); payment=data.get('payment_method','Cash')
    if not items: return jsonify(error='Cart is empty'),400
    c=db(); subtotal=0; clean=[]
    try:
        for item in items:
            p=c.execute('SELECT * FROM products WHERE id=?',(item['product_id'],)).fetchone(); q=int(item['qty'])
            if not p: raise ValueError('Product not found')
            if q<1 or q>p['stock']: raise ValueError(f"Insufficient stock for {p['name']}")
            amount=p['price']*q; subtotal+=amount; clean.append((p,q,amount))
        discount=min(discount,subtotal); taxable=subtotal-discount; tax=taxable*tax_rate/100; total=taxable+tax; inv=invoice()
        cur=c.execute('INSERT INTO sales(invoice_no,staff_id,subtotal,discount,tax,total,payment_method) VALUES(?,?,?,?,?,?,?)',(inv,session['user_id'],subtotal,discount,tax,total,payment))
        sid=cur.lastrowid
        for p,q,amount in clean:
            c.execute('INSERT INTO sale_items(sale_id,product_id,qty,price,amount) VALUES(?,?,?,?,?)',(sid,p['id'],q,p['price'],amount)); c.execute('UPDATE products SET stock=stock-? WHERE id=?',(q,p['id']))
        c.execute('INSERT INTO ledger(entry_type,reference,description,amount) VALUES(?,?,?,?)',('SALE',inv,f'Bill via {payment}',total)); c.commit()
        return jsonify(ok=True,sale_id=sid,invoice=inv,subtotal=round(subtotal,2),discount=round(discount,2),tax=round(tax,2),total=round(total,2))
    except Exception as e: c.rollback(); return jsonify(error=str(e)),400
    finally: c.close()

@app.route('/invoice/<int:sale_id>')
@login_required()
def invoice_view(sale_id):
    c=db(); sale=c.execute('SELECT s.*,u.name staff FROM sales s LEFT JOIN users u ON s.staff_id=u.id WHERE s.id=?',(sale_id,)).fetchone(); items=c.execute('SELECT si.*,p.name,p.sku FROM sale_items si JOIN products p ON p.id=si.product_id WHERE sale_id=?',(sale_id,)).fetchall(); c.close()
    return render_template('invoice.html',sale=sale,items=items)

@app.route('/returns', methods=['GET','POST'])
@login_required()
def returns():
    c=db()
    if request.method=='POST':
        d=request.form; product_id=int(d['product_id']); qty=int(d['qty']); sale_id=d.get('sale_id') or None
        p=c.execute('SELECT * FROM products WHERE id=?',(product_id,)).fetchone()
        if not p: flash('Product not found','danger')
        else:
            amount=p['price']*qty; c.execute('INSERT INTO returns(sale_id,product_id,qty,reason,amount,processed_by) VALUES(?,?,?,?,?,?)',(sale_id,product_id,qty,d.get('reason'),amount,session['user_id'])); c.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,product_id)); c.execute('INSERT INTO ledger(entry_type,reference,description,amount) VALUES(?,?,?,?)',('RETURN',str(sale_id or ''),f'Return: {p["name"]}',-amount)); c.commit(); flash('Return processed and stock restored','success')
    rows=c.execute('SELECT r.*,p.name,p.sku,u.name processor FROM returns r JOIN products p ON p.id=r.product_id LEFT JOIN users u ON u.id=r.processed_by ORDER BY r.id DESC').fetchall(); products=c.execute('SELECT id,name,sku FROM products ORDER BY name').fetchall(); c.close(); return render_template('returns.html',returns=rows,products=products)

@app.route('/ledger')
@login_required('admin')
def ledger():
    c=db(); rows=c.execute('SELECT * FROM ledger ORDER BY id DESC').fetchall(); total=c.execute('SELECT COALESCE(SUM(amount),0) n FROM ledger').fetchone()['n']; c.close(); return render_template('ledger.html',ledger=rows,total=total)

@app.route('/reports')
@login_required('admin')
def reports():
    c=db(); daily=c.execute("SELECT date(created_at) day, COUNT(*) bills, ROUND(SUM(total),2) revenue FROM sales GROUP BY date(created_at) ORDER BY day DESC LIMIT 30").fetchall(); top=c.execute("SELECT p.name,SUM(si.qty) qty,SUM(si.amount) revenue FROM sale_items si JOIN products p ON p.id=si.product_id GROUP BY p.id ORDER BY qty DESC LIMIT 10").fetchall(); c.close(); return render_template('reports.html',daily=daily,top=top)

@app.route('/api/products')
@login_required()
def api_products():
    c=db(); rows=c.execute('SELECT id,name,sku,price,stock FROM products WHERE stock>0 ORDER BY name').fetchall(); c.close(); return jsonify([dict(x) for x in rows])

init_db()

if __name__=='__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG')=='1', host='0.0.0.0', port=int(os.environ.get('PORT',5000)))
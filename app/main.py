import os
import uuid
import secrets
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)

# Cau hinh thu muc luu anh san pham
UPLOAD_FOLDER = os.path.join(
    app.static_folder, "uploads", "products"
)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Kiem tra duoi file anh
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )

def save_product_image(image):
    """Validate and persist an uploaded product image; return its generated filename."""
    if not image or not image.filename:
        return None
    if not allowed_file(image.filename):
        abort(400, "Chỉ chấp nhận ảnh PNG, JPG, JPEG hoặc WEBP")
    extension = secure_filename(image.filename).rsplit(".", 1)[-1].lower()
    # Verify the file signature, not just its extension.
    signatures = {
        "png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": lambda b: b.startswith(b"\xff\xd8\xff"),
        "jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
        "webp": lambda b: b.startswith(b"RIFF") and b[8:12] == b"WEBP",
    }
    header = image.stream.read(16)
    image.stream.seek(0)
    if not signatures[extension](header):
        abort(400, "Nội dung tệp không phải ảnh hợp lệ")
    filename = f"{uuid.uuid4().hex}.{extension}"
    destination = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        image.save(destination)
    except OSError:
        app.logger.exception("Cannot write product image to %s", destination)
        abort(500, "Không lưu được ảnh. Kiểm tra quyền ghi Docker Volume.")
    return filename


@app.errorhandler(RequestEntityTooLarge)
def image_too_large(error):
    return "Ảnh quá lớn. Giới hạn tải lên là 10 MB.", 413


app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
db = SQLAlchemy(app)
metrics = PrometheusMetrics(app, path='/metrics')

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(80),unique=True,nullable=False)
    password_hash=db.Column(db.String(255),nullable=False)
class Customer(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(160),nullable=False)
    email=db.Column(db.String(160))
    phone=db.Column(db.String(30))
    address=db.Column(db.String(250))
class Product(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(160),nullable=False)
    price=db.Column(db.Numeric(14,2),nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
class Invoice(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    customer_id=db.Column(db.Integer,db.ForeignKey('customer.id'),nullable=False)
    is_cancelled = db.Column(
    db.Boolean,
    nullable=False,
    default=False,
    server_default=db.text('false')
    )
    customer=db.relationship('Customer')
    created_at=db.Column(db.DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)
    items=db.relationship('InvoiceItem',cascade='all, delete-orphan',lazy=True)
    payments=db.relationship('Payment',cascade='all, delete-orphan',lazy=True)
    @property
    def total(self): return sum((i.quantity*i.unit_price for i in self.items),Decimal('0'))
    @property
    def paid(self): return sum((x.amount for x in self.payments),Decimal('0'))
    @property
    def due(self): return self.total-self.paid
    @property
    def status(self):
        if self.is_cancelled:
            return 'Đã hủy'

        if self.due <= 0:
            return 'Đã thanh toán'

        if self.paid > 0:
            return 'Thanh toán một phần'

        return 'Chưa thanh toán'
class InvoiceItem(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    invoice_id=db.Column(db.Integer,db.ForeignKey('invoice.id'),nullable=False)
    product_name=db.Column(db.String(160),nullable=False)
    quantity=db.Column(db.Integer,nullable=False)
    unit_price=db.Column(db.Numeric(14,2),nullable=False)
class Payment(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    invoice_id=db.Column(db.Integer,db.ForeignKey('invoice.id'),nullable=False)
    amount=db.Column(db.Numeric(14,2),nullable=False)
    method=db.Column(db.String(30),nullable=False)
    created_at=db.Column(db.DateTime(timezone=True),default=lambda:datetime.now(timezone.utc),nullable=False)

def login_required(fn):
    @wraps(fn)
    def wrapped(*a,**kw):
        if not session.get('user_id'): return redirect(url_for('login'))
        return fn(*a,**kw)
    return wrapped
@app.before_request
def csrf_guard():
    if request.method == 'POST' and session.get('user_id'):
        if request.endpoint == 'login':
            return

        token = request.form.get('csrf_token')
        expected_token = session.get('csrf_token')

        if not token or not expected_token or not secrets.compare_digest(token, expected_token):
            abort(400, 'CSRF token không hợp lệ')
@app.context_processor
def context(): return {'csrf_token':session.get('csrf_token','')}
@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify(status='ok')
    except Exception: return jsonify(status='unhealthy'),503
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(username=request.form.get('username','')).first()
        if u and check_password_hash(u.password_hash,request.form.get('password','')):
            import secrets
            session.clear();session['user_id']=u.id;session['csrf_token']=secrets.token_urlsafe(32)
            return redirect(url_for('index'))
        flash('Sai tài khoản hoặc mật khẩu')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(username) < 3 or len(username) > 80:
            flash('Tên đăng nhập phải có từ 3 đến 80 ký tự.')
            return redirect(url_for('register'))

        if len(password) < 8 or len(password) > 128:
            flash('Mật khẩu phải có từ 8 đến 128 ký tự.')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user:
            flash('Tên đăng nhập đã tồn tại.')
            return redirect(url_for('register'))

        # Chỉ đăng ký tài khoản khi được cấp mã mời.
        invite_code = request.form.get('invite_code', '')
        expected_code = os.environ.get('REGISTRATION_INVITE_CODE', '')

        import hmac
        if not expected_code or not hmac.compare_digest(
            invite_code, expected_code
        ):
            flash('Mã mời đăng ký không hợp lệ.')
            return redirect(url_for('register'))

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Tạo tài khoản thành công. Hãy đăng nhập.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout',methods=['POST'])
@login_required
def logout(): session.clear();return redirect(url_for('login'))
@app.route('/')
@login_required
def index():
    invoices = Invoice.query.order_by(Invoice.id.desc()).all()

    # Đếm hóa đơn theo trạng thái
    paid_count = sum(
        1 for inv in invoices
        if not inv.is_cancelled and inv.due <= 0
    )

    unpaid_count = sum(
        1 for inv in invoices
        if not inv.is_cancelled and inv.due > 0
    )

    cancelled_count = sum(
        1 for inv in invoices
        if inv.is_cancelled
    )

    # Tổng công nợ, không tính hóa đơn đã hủy
    outstanding = sum(
        (inv.due for inv in invoices if not inv.is_cancelled),
        Decimal('0')
    )

    return render_template(
        'index.html',
        invoices=invoices,
        customers=Customer.query.count(),
        revenue=sum(
            (inv.paid for inv in invoices),
            Decimal('0')
        ),
        outstanding=outstanding,
        paid_count=paid_count,
        unpaid_count=unpaid_count,
        cancelled_count=cancelled_count
    )

@app.route('/customers',methods=['GET','POST'])
@login_required
def customers():
    if request.method=='POST':
        name=request.form.get('name','').strip()
        if not name: abort(400)
        db.session.add(Customer(name=name,email=request.form.get('email','').strip(),phone=request.form.get('phone','').strip(),address=request.form.get('address','').strip()));db.session.commit();return redirect(url_for('customers'))
    return render_template('customers.html',customers=Customer.query.order_by(Customer.id.desc()).all())
@app.route('/customers/<int:id>/edit',methods=['POST'])
@login_required
def edit_customer(id):
    c=db.get_or_404(Customer,id)
    c.name=request.form.get('name','').strip() or c.name
    c.email=request.form.get('email','').strip();c.phone=request.form.get('phone','').strip();c.address=request.form.get('address','').strip()
    db.session.commit();return redirect(url_for('customers'))
@app.route('/customers/<int:id>/delete',methods=['POST'])
@login_required
def delete_customer(id):
    c=db.get_or_404(Customer,id)
    if Invoice.query.filter_by(customer_id=id).first(): flash('Không thể xóa khách hàng có hóa đơn')
    else: db.session.delete(c);db.session.commit()
    return redirect(url_for('customers'))
@app.route('/products',methods=['GET','POST'])
@login_required
def products():
    if request.method == 'POST':
        try:
            price = Decimal(request.form.get('price', ''))
        except:
            abort(400)

        name = request.form.get('name', '').strip()

        if not name or not price.is_finite() or price < 0:
            abort(400)

        image_filename = save_product_image(request.files.get('image'))

        product = Product(
            name=name,
            price=price,
            image_filename=image_filename
        )

        db.session.add(product)
        db.session.commit()

        return redirect(url_for('products'))

    return render_template(
        'products.html',
        products=Product.query.order_by(Product.id.desc()).all()
    )
@app.route('/products/<int:id>/edit',methods=['POST'])
@login_required
def edit_product(id):
    x = db.get_or_404(Product, id)

    try:
        price = Decimal(request.form.get('price', ''))
    except:
        abort(400)

    if not price.is_finite() or price < 0:
        abort(400)

    x.name = request.form.get('name', '').strip() or x.name
    x.price = price

    new_image_filename = save_product_image(request.files.get('image'))
    if new_image_filename:
        x.image_filename = new_image_filename

    db.session.commit()
    return redirect(url_for('products'))
    
@app.route('/products/<int:id>/delete',methods=['POST'])
@login_required
def delete_product(id):
    db.session.delete(db.get_or_404(Product,id));db.session.commit();return redirect(url_for('products'))
@app.route('/invoices/new',methods=['GET','POST'])
@login_required
def new_invoice():
    if request.method=='POST':
        c=db.get_or_404(Customer,int(request.form.get('customer_id',0)))
        ids=request.form.getlist('product_id'); quantities=request.form.getlist('quantity')
        if not ids or len(ids)!=len(quantities): abort(400)
        inv=Invoice(customer_id=c.id)
        for pid,qty in zip(ids,quantities):
            prod=db.get_or_404(Product,int(pid));q=int(qty)
            if q<=0 or q>100000: abort(400)
            inv.items.append(InvoiceItem(product_name=prod.name,unit_price=prod.price,quantity=q))
        db.session.add(inv);db.session.commit();return redirect(url_for('invoice_detail',id=inv.id))
    return render_template('new_invoice.html',customers=Customer.query.all(),products=Product.query.all())
@app.route('/invoices/<int:id>')
@login_required
def invoice_detail(id): return render_template('invoice.html',invoice=db.get_or_404(Invoice,id))
@app.route('/invoices/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_invoice(id):
    inv = db.get_or_404(Invoice, id)

    if inv.is_cancelled:
        flash('Hóa đơn này đã được hủy.')
        return redirect(url_for('invoice_detail', id=id))

    if inv.paid > 0:
        flash('Không thể hủy hóa đơn đã có thanh toán.')
        return redirect(url_for('invoice_detail', id=id))

    if request.form.get('csrf_token') != session.get('csrf_token'):
        abort(400)

    inv.is_cancelled = True
    db.session.commit()

    flash('Hủy hóa đơn thành công.')
    return redirect(url_for('invoice_detail', id=id))
@app.route('/invoices/<int:id>/pay',methods=['POST'])
@login_required
def pay(id):
    inv = db.get_or_404(Invoice, id)
    if inv.is_cancelled:
        flash('Hóa đơn đã hủy không thể thanh toán.')
        return redirect(url_for('invoice_detail', id=id))
    try: amount=Decimal(request.form.get('amount',''))
    except: abort(400)
    method=request.form.get('method','')
    if not amount.is_finite() or amount<=0 or amount>inv.due or method not in ('Tiền mặt','Chuyển khoản'): abort(400,'Thanh toán không hợp lệ')
    db.session.add(Payment(invoice_id=id,amount=amount,method=method));db.session.commit();return redirect(url_for('invoice_detail',id=id))
@app.cli.command('init-db')
def init_db():
    db.create_all()
    username=os.environ['ADMIN_USERNAME'];password=os.environ['ADMIN_PASSWORD']
    if not User.query.filter_by(username=username).first():
        db.session.add(User(username=username,password_hash=generate_password_hash(password)));db.session.commit()
    print('Database initialized')

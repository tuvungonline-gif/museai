"""Local member accounts, approval, sessions and scoped prompt library."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

COOKIE = 'muse_member'


def phone_number(value):
    value = re.sub(r'[\s().-]', '', str(value or ''))
    if value.startswith('+84'): value = '0' + value[3:]
    elif value.startswith('84') and len(value) == 11: value = '0' + value[2:]
    if not re.fullmatch(r'0[35789]\d{8}', value):
        raise ValueError('Số điện thoại Việt Nam không hợp lệ.')
    return value


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ':' + digest


def password_valid(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)


class MemberStore:
    def __init__(self, path, admin_phone, admin_password):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not admin_password or len(admin_password) < 8:
            raise ValueError('Cần mật khẩu Canvas ít nhất 8 ký tự để khởi tạo admin.')
        admin_phone = phone_number(admin_phone)
        with self.db() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, phone TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
                role TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS attempts (key TEXT PRIMARY KEY, count INTEGER, until REAL);
              CREATE TABLE IF NOT EXISTS prompts (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, scope TEXT NOT NULL,
                title TEXT NOT NULL, content TEXT NOT NULL, updated REAL NOT NULL);
            ''')
            if not db.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',
                           (secrets.token_hex(16), admin_phone, password_hash(admin_password), 'admin', 'approved', time.time()))
            self.dummy_hash = password_hash(secrets.token_hex(16))

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection: yield connection
        finally: connection.close()

    def user(self, handler):
        cookies = SimpleCookie()
        try: cookies.load(handler.headers.get('Cookie', ''))
        except Exception: return None
        token = cookies.get(COOKIE)
        if not token: return None
        digest = hashlib.sha256(token.value.encode()).hexdigest()
        with self.db() as db:
            row = db.execute('''SELECT u.id,u.phone,u.role,u.status,s.csrf FROM users u
                JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>? AND u.status='approved' ''',
                (digest, time.time())).fetchone()
        return dict(row) if row else None

    def reply(self, h, status, value, cookie=None):
        body = json.dumps(value, ensure_ascii=False).encode()
        h.send_response(status)
        h.send_header('Content-Type', 'application/json; charset=utf-8')
        h.send_header('Content-Length', str(len(body)))
        h.send_header('Cache-Control', 'no-store')
        h.send_header('X-Content-Type-Options', 'nosniff')
        if cookie is not None:
            secure = '; Secure' if h.headers.get('X-Forwarded-Proto', '').lower() == 'https' else ''
            h.send_header('Set-Cookie', COOKIE + '=' + cookie + '; Path=/; HttpOnly; SameSite=Lax' + secure + ('; Max-Age=604800' if cookie else '; Max-Age=0'))
        h.end_headers()
        if h.command != 'HEAD': h.wfile.write(body)

    def route(self, h, path):
        if not path.startswith('/member-api/'):
            return False
        try:
            self._route(h, path)
        except ValueError as exc:
            self.reply(h, 400, {'error': str(exc)})
        except sqlite3.IntegrityError:
            self.reply(h, 409, {'error': 'Số điện thoại đã được đăng ký.'})
        except sqlite3.Error:
            self.reply(h, 503, {'error': 'Dữ liệu tạm thời không khả dụng. Vui lòng thử lại.'})
        return True

    def _route(self, h, path):
        method = h.command
        data = {}
        if method == 'POST':
            origin = h.headers.get('Origin')
            if origin and urlsplit(origin).netloc != h.headers.get('Host'):
                self.reply(h, 403, {'error': 'Yêu cầu không hợp lệ.'}); return
            if h.headers.get_content_type() != 'application/json':
                raise ValueError('Cần gửi dữ liệu JSON.')
            try: length = int(h.headers.get('Content-Length', '0'))
            except ValueError: length = -1
            if length < 0 or length > 65536 or h.headers.get('Transfer-Encoding'):
                h.close_connection = True
                raise ValueError('Dữ liệu quá lớn.')
            try: data = json.loads(h.rfile.read(length))
            except (ValueError, UnicodeError): raise ValueError('Dữ liệu không hợp lệ.')
            if not isinstance(data, dict): raise ValueError('Dữ liệu không hợp lệ.')
        user = self.user(h)
        if path == '/member-api/me' and method == 'GET':
            self.reply(h, 200, {'user': user, 'members_version': 1}); return
        if path in ('/member-api/register', '/member-api/login') and method == 'POST':
            phone = phone_number(data.get('phone'))
            password = data.get('password')
            if not isinstance(password, str) or not 8 <= len(password) <= 128:
                raise ValueError('Mật khẩu cần từ 8 đến 128 ký tự.')
            now = time.time()
            ip = h.headers.get('CF-Connecting-IP') or h.client_address[0]
            keys = [hashlib.sha256((label + val).encode()).hexdigest() for label, val in [('phone:', phone), ('ip:', ip)]]
            with self.db() as db:
                for key in keys:
                    row = db.execute('SELECT * FROM attempts WHERE key=?', (key,)).fetchone()
                    if row and row['until'] > now and row['count'] >= 20:
                        self.reply(h, 429, {'error': 'Thử quá nhiều lần. Hãy thử lại sau 15 phút.'}); return
                    db.execute('''INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET
                      count=CASE WHEN until<? THEN 1 ELSE count+1 END,
                      until=CASE WHEN until<? THEN excluded.until ELSE until END''', (key, now+900, now, now))
                db.execute('DELETE FROM attempts WHERE until<?', (now,))
            if path.endswith('/register'):
                if password != data.get('password_confirm'):
                    raise ValueError('Hai mật khẩu không trùng nhau.')
                with self.db() as db:
                    db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',
                               (secrets.token_hex(16), phone, password_hash(password), 'member', 'pending', now))
                self.reply(h, 201, {'message': 'Đăng ký thành công. Vui lòng chờ admin duyệt.'}); return
            with self.db() as db:
                row = db.execute('SELECT * FROM users WHERE phone=?', (phone,)).fetchone()
                if not password_valid(password, row['password'] if row else self.dummy_hash):
                    self.reply(h, 401, {'error': 'Số điện thoại hoặc mật khẩu không đúng.'}); return
                if row['status'] != 'approved':
                    self.reply(h, 403, {'error': 'Tài khoản đang chờ duyệt.' if row['status']=='pending' else 'Tài khoản đã bị khóa.'}); return
                token = secrets.token_urlsafe(32)
                db.execute('DELETE FROM sessions WHERE expires<?', (now,))
                db.execute('INSERT INTO sessions VALUES(?,?,?,?)',
                           (hashlib.sha256(token.encode()).hexdigest(), row['id'], secrets.token_urlsafe(24), now+604800))
                db.execute('DELETE FROM attempts WHERE key=?', (keys[0],))
            self.reply(h, 200, {'message': 'Đăng nhập thành công.'}, cookie=token); return
        if not user:
            self.reply(h, 401, {'error': 'Vui lòng đăng nhập.'}); return
        if method == 'POST' and not hmac.compare_digest(h.headers.get('X-CSRF-Token', ''), user['csrf']):
            self.reply(h, 403, {'error': 'Phiên làm việc không hợp lệ. Hãy tải lại trang.'}); return
        if path == '/member-api/logout' and method == 'POST':
            cookies = SimpleCookie(h.headers.get('Cookie', ''))
            digest = hashlib.sha256(cookies[COOKIE].value.encode()).hexdigest()
            with self.db() as db: db.execute('DELETE FROM sessions WHERE token=?', (digest,))
            self.reply(h, 200, {'message': 'Đã đăng xuất.'}, cookie=''); return
        if path == '/member-api/members':
            if user['role'] != 'admin':
                self.reply(h, 403, {'error': 'Chỉ admin được quản lý thành viên.'}); return
            with self.db() as db:
                if method == 'GET':
                    rows = db.execute('SELECT id,phone,role,status,created FROM users ORDER BY created DESC').fetchall()
                    self.reply(h, 200, {'members': [dict(r) for r in rows]}); return
                if method == 'POST':
                    if not isinstance(data.get('id'), str): raise ValueError('Thành viên không hợp lệ.')
                    status = data.get('status')
                    if status not in ('approved', 'blocked', 'pending'): raise ValueError('Trạng thái không hợp lệ.')
                    row = db.execute('SELECT role FROM users WHERE id=?', (data.get('id'),)).fetchone()
                    if not row or row['role'] == 'admin': raise ValueError('Không thể thay đổi tài khoản admin.')
                    db.execute('UPDATE users SET status=? WHERE id=?', (status, data['id']))
                    if status != 'approved': db.execute('DELETE FROM sessions WHERE user_id=?', (data['id'],))
                    self.reply(h, 200, {'message': 'Đã cập nhật thành viên.'}); return
        if path == '/member-api/prompts':
            with self.db() as db:
                if method == 'GET':
                    if user['role'] == 'admin': rows = db.execute('SELECT p.*,u.phone AS owner_phone FROM prompts p JOIN users u ON p.owner=u.id ORDER BY updated DESC').fetchall()
                    else: rows = db.execute("SELECT * FROM prompts WHERE scope='shared' OR owner=? ORDER BY updated DESC", (user['id'],)).fetchall()
                    self.reply(h, 200, {'prompts': [dict(r) for r in rows]}); return
                if method == 'POST':
                    ident = data.get('id')
                    if ident is not None and not isinstance(ident, str): raise ValueError('Lời nhắc không hợp lệ.')
                    existing = db.execute('SELECT * FROM prompts WHERE id=?', (ident,)).fetchone() if ident else None
                    if ident and not existing:
                        self.reply(h, 404, {'error': 'Không tìm thấy lời nhắc.'}); return
                    if existing and user['role'] != 'admin' and existing['owner'] != user['id']:
                        self.reply(h, 403, {'error': 'Bạn chỉ được sửa lời nhắc của mình.'}); return
                    if data.get('action') == 'delete':
                        if not existing: raise ValueError('Thiếu lời nhắc cần xóa.')
                        db.execute('DELETE FROM prompts WHERE id=?', (ident,))
                    else:
                        title, content = data.get('title'), data.get('content')
                        if not isinstance(title, str) or not title.strip() or len(title)>200: raise ValueError('Tiêu đề cần từ 1 đến 200 ký tự.')
                        if not isinstance(content, str) or not content.strip() or len(content)>50000: raise ValueError('Nội dung cần từ 1 đến 50.000 ký tự.')
                        scope = data.get('scope', 'private')
                        if scope not in ('shared', 'private'): raise ValueError('Phạm vi không hợp lệ.')
                        if scope == 'shared' and user['role'] != 'admin':
                            self.reply(h, 403, {'error': 'Chỉ admin được tạo thư viện chung.'}); return
                        if existing: db.execute('UPDATE prompts SET title=?,content=?,scope=?,updated=? WHERE id=?', (title.strip(), content.strip(), scope, time.time(), ident))
                        else: db.execute('INSERT INTO prompts VALUES(?,?,?,?,?,?)', (secrets.token_hex(16), user['id'], scope, title.strip(), content.strip(), time.time()))
                    self.reply(h, 200, {'message': 'Đã cập nhật thư viện.'}); return
        self.reply(h, 404, {'error': 'Không tìm thấy chức năng.'})

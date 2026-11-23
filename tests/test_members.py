import http.client
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from member_auth import MemberStore
spec = importlib.util.spec_from_file_location('member_canvas', ROOT / 'canvas_server.py')
canvas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canvas)


class MembersTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'index.html').write_text('<body>Canvas</body>')
        canvas.ROOT, canvas.MEMBERS_ENABLED, canvas.PUBLIC_CANVAS = self.root, True, True
        canvas.API_KEY = 'must-stay-private'
        canvas.MEMBER_STORE = MemberStore(self.root / 'members.sqlite3', '0900000000', 'owner-password')
        self.site = canvas.ThreadingHTTPServer(('127.0.0.1', 0), canvas.Handler)
        threading.Thread(target=self.site.serve_forever, daemon=True).start()
        self.cookies, self.csrf = {}, {}

    def tearDown(self):
        self.site.shutdown(); self.site.server_close(); self.temp.cleanup()

    def request(self, path, data=None, who=None, origin=None, csrf=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.site.server_port, timeout=10)
        headers = {'Content-Type': 'application/json'}
        if who:
            headers['Cookie'] = self.cookies.get(who, '')
            if csrf: headers['X-CSRF-Token'] = self.csrf.get(who, '')
        if origin: headers['Origin'] = origin
        conn.request('POST' if data is not None else 'GET', path, json.dumps(data) if data is not None else None, headers)
        r = conn.getresponse()
        status, body, cookie = r.status, r.read().decode(), r.getheader('Set-Cookie')
        if cookie and who: self.cookies[who] = cookie.split(';')[0]
        conn.close()
        try: body = json.loads(body)
        except ValueError: pass
        return status, body, cookie

    def login(self, phone, password='member-password'):
        r = self.request('/member-api/login', {'phone': phone, 'password': password}, phone)
        if r[0] == 200: self.csrf[phone] = self.request('/member-api/me', who=phone)[1]['user']['csrf']
        return r

    def register(self, phone):
        return self.request('/member-api/register', {'phone': phone, 'password': 'member-password', 'password_confirm': 'member-password'})

    def approve(self, phone):
        self.login('0900000000', 'owner-password')
        users = self.request('/member-api/members', who='0900000000')[1]['members']
        ident = next(u['id'] for u in users if u['phone'] == phone)
        self.assertEqual(self.request('/member-api/members', {'id': ident, 'status': 'approved'}, '0900000000')[0], 200)
        return ident

    def test_approval_lock_and_secrets(self):
        self.assertEqual(self.request('/')[0], 303)
        self.assertEqual(self.request('/employee-api/v1/models')[0], 401)
        self.assertEqual(self.request('/member-api/register', {'phone':'0911111111','password':'member-password','password_confirm':'wrong'})[0],400)
        self.assertEqual(self.register('0911111111')[0], 201)
        self.assertEqual(self.login('+84911111111')[0], 403)
        ident = self.approve('0911111111')
        self.assertEqual(self.login('0911111111')[0], 200)
        self.assertEqual(self.request('/', who='0911111111')[0], 200)
        self.assertEqual(self.request('/members', who='0911111111')[0], 403)
        self.assertEqual(self.request('/member-api/members', who='0911111111')[0], 403)
        self.assertNotIn('must-stay-private',self.request('/config.js', who='0911111111')[1])
        self.assertEqual(self.request('/member-api/members', {'id':ident,'status':'blocked'}, '0900000000')[0], 200)
        self.assertEqual(self.request('/employee-api/v1/models', who='0911111111')[0], 401)
        self.assertEqual(self.login('0911111111')[0], 403)
        self.assertNotIn(b'member-password', (self.root / 'members.sqlite3').read_bytes())

    def test_prompt_scope_permissions_and_csrf(self):
        for p in ('0911111111', '0922222222'):
            self.register(p); self.approve(p); self.login(p)
        admin,a,b = '0900000000','0911111111','0922222222'
        shared={'title':'Chung','content':'Cả nhóm thấy','scope':'shared'}
        private={'title':'Riêng','content':'Chủ và admin','scope':'private'}
        self.assertEqual(self.request('/member-api/prompts', shared, a)[0],403)
        self.assertEqual(self.request('/member-api/prompts', shared, admin, csrf=False)[0],403)
        self.assertEqual(self.request('/member-api/prompts', shared, admin, origin='https://evil.example')[0],403)
        self.assertEqual(self.request('/member-api/prompts', shared, admin)[0],200)
        self.assertEqual(self.request('/member-api/prompts', private, a)[0],200)
        pa=self.request('/member-api/prompts',who=a)[1]['prompts']
        pb=self.request('/member-api/prompts',who=b)[1]['prompts']
        self.assertEqual(len(pa),2); self.assertEqual(len(pb),1)
        own=next(p for p in pa if p['scope']=='private')
        self.assertEqual(self.request('/member-api/prompts',dict(private,id=own['id']),b)[0],403)
        self.assertEqual(self.request('/member-api/prompts',{'id':own['id'],'action':'delete'},b)[0],403)
        self.assertEqual(len(self.request('/member-api/prompts',who=admin)[1]['prompts']),2)
        self.assertEqual(self.request('/member-api/prompts',{'id':own['id'],'action':'delete'},admin)[0],200)
        self.assertEqual(self.request('/member-api/logout',{},a)[0],200)
        self.assertEqual(self.request('/member-api/prompts',who=a)[0],401)

    def test_admin_bootstrap_is_not_claimable(self):
        self.assertEqual(self.register('0900000000')[0],409)
        self.register('0911111111')
        MemberStore(self.root/'members.sqlite3','0911111111','different-password')
        self.assertEqual(self.login('0900000000','owner-password')[0],200)
        users=self.request('/member-api/members',who='0900000000')[1]['members']
        self.assertEqual(sum(u['role']=='admin' for u in users),1)
        self.assertEqual(self.request('/member-api/members',{'id':next(u['id'] for u in users if u['role']=='admin'),'status':'blocked'},'0900000000')[0],400)
        self.assertEqual(self.login('0911111111')[0],403)

    def test_throttle_cookie_flags(self):
        self.register('0911111111'); self.approve('0911111111')
        cookie=self.login('0911111111')[2]
        self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Lax',cookie)
        for _ in range(20): self.login('0911111111','wrong-password')
        self.assertEqual(self.login('0911111111')[0],429)

    def test_account_profile_scope_and_future_billing_are_inert(self):
        admin,a,b='0900000000','0911111111','0922222222'
        for phone in (a,b):
            self.register(phone);self.approve(phone);self.login(phone)
        self.assertEqual(self.request('/account',who=a)[0],200)
        info=self.request('/member-api/account',who=a)[1]
        self.assertEqual(info['account']['phone'],a)
        self.assertFalse(info['billing_enabled'])
        self.assertEqual(info['payments'],[])
        self.assertNotIn('admin_notes',info['account'])
        accounts=self.request('/member-api/accounts',who=admin)[1]['accounts']
        bid=next(x['id'] for x in accounts if x['phone']==b)
        attack={'id':bid,'display_name':'Thành viên A','email':'a@example.test','company':'Vườn A',
                'role':'admin','status':'approved','plan_code':'paid','admin_notes':'forged','phone':'0999999999'}
        self.assertEqual(self.request('/member-api/account',attack,a)[0],200)
        after=self.request('/member-api/account',who=a)[1]['account']
        self.assertEqual(after['display_name'],'Thành viên A')
        self.assertEqual(after['phone'],a)
        self.assertEqual(after['role'],'member')
        self.assertEqual(after['plan_code'],'none')
        self.assertEqual(self.request('/member-api/account',who=b)[1]['account']['display_name'],'')
        self.assertEqual(self.request('/member-api/accounts',who=a)[0],403)
        self.assertEqual(self.request('/member-api/accounts',attack,a)[0],403)
        self.assertEqual(self.request('/member-api/accounts',{'id':bid,'display_name':'Thành viên B','admin_notes':'Chỉ admin thấy'},admin)[0],200)
        own=self.request('/member-api/account',who=b)[1]['account']
        self.assertEqual(own['display_name'],'Thành viên B')
        self.assertNotIn('admin_notes',own)
        rows=self.request('/member-api/accounts',who=admin)[1]['accounts']
        self.assertEqual(next(x for x in rows if x['id']==bid)['admin_notes'],'Chỉ admin thấy')
        self.assertEqual(self.request('/member-api/account',{'email':'bad-address'},a)[0],400)
        self.assertEqual(self.request('/member-api/account',{'company':'x'},a,csrf=False)[0],403)
        self.assertIn('"MEMBER_ROLE": "member"',self.request('/config.js',who=a)[1])
        self.assertIn('"MEMBER_ROLE": "admin"',self.request('/config.js',who=admin)[1])
        MemberStore(self.root/'members.sqlite3',admin,'owner-password')
        self.assertEqual(self.request('/member-api/account',who=a)[1]['account']['company'],'Vườn A')
        with canvas.MEMBER_STORE.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT count(*) FROM payment_history').fetchone()[0],0)

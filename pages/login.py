from nicegui import ui, app
import asyncio
from service.auth import verify_user, get_user_permissions, login_locked

# =========================================================
# GLOBAL CSS
# =========================================================

from components.theme import THEME_CSS, THEME_FONTS

GLOBAL_CSS = THEME_FONTS + THEME_CSS + """
body { margin:0; overflow:hidden; }
.login-page {
    position:relative; width:100%; min-height:100vh; min-height:100dvh; height:100dvh;
    display:grid; grid-template-columns:minmax(0,1fr) 460px; background:var(--sm-vine-deep);
}
.login-bg-img {
    position:relative; min-height:100%;
    background:url('/static/login_bg.jpg') center/cover no-repeat;
}
.login-bg-img::after { content:''; position:absolute; inset:0; background:rgba(20,59,43,.28); }
.login-side {
    background:var(--sm-surface); display:flex; flex-direction:column; justify-content:center;
    padding:48px 44px; gap:0; min-width:0;
}
.login-card { box-shadow:none !important; background:transparent !important; padding:0 !important; width:100%; gap:0; }
.login-header { display:flex; flex-direction:column; align-items:flex-start; gap:0; margin-bottom:26px; }
.logo-glow { width:52px; height:52px; border-radius:12px; object-fit:contain; }
.title { margin-top:18px; font-family:var(--sm-display); font-weight:700; font-size:30px; line-height:1.1; letter-spacing:.04em; color:var(--sm-ink); }
.subtitle { margin-top:10px; color:var(--sm-ink-2); font-size:15px; line-height:1.5; max-width:34ch; }
.input-box { width:100%; margin-top:14px; }
.custom-input { width:100%; }
.custom-input .q-field__control { height:52px !important; border-radius:var(--sm-r-m) !important; background:var(--sm-sunken) !important; }
.custom-input .q-field__native, .custom-input input { color:var(--sm-ink) !important; font-size:15px !important; font-weight:500; }
.custom-input .q-field__label { color:var(--sm-ink-3) !important; }
.custom-input .q-icon { color:var(--sm-ink-3) !important; font-size:20px !important; }
.custom-input.q-field--focused .q-field__control { background:#fff !important; }
.custom-input.q-field--outlined.q-field--focused .q-field__control:after { border-color:var(--sm-vine) !important; }
.q-icon { font-family:'Material Icons' !important; }
.login-btn.q-btn {
    width:100%; height:52px; margin-top:22px; border-radius:var(--sm-r-m);
    background:var(--sm-vine) !important; color:#fff !important; font-weight:700; font-size:15px;
    text-transform:none; box-shadow:none;
}
.login-btn.q-btn:hover { background:var(--sm-vine-deep) !important; }
.login-foot { margin-top:22px; font-size:12px; line-height:1.5; color:var(--sm-ink-3); }
@media (max-width:860px) {
    body { overflow-y:auto; }
    .login-page { grid-template-columns:1fr; grid-template-rows:150px auto; }
    .login-side { padding:28px 22px 36px; justify-content:flex-start; }
    .title { font-size:32px; }
}
@media (max-width:480px) {
    .login-side { padding:20px 14px 28px; }
}
"""
def check_login():
    if not app.storage.user.get('username'):
        ui.navigate.to('/login')
        return False
    return True

@ui.page('/login')
def login_page():
    if app.storage.user.get('username'):
        ui.navigate.to('/')
        return

    ui.add_head_html(f"<style>{GLOBAL_CSS}</style>")

    with ui.element('div').classes('login-page'):
        # Nền ảnh gốc sắc nét
        ui.element('div').classes('login-bg-img')

        with ui.element('div').classes('login-side'), ui.card().classes('login-card'):
            with ui.column().classes('login-header'):
                ui.image('/static/logo.png').classes('logo-glow')
                ui.label('SMIOT').classes('title')
                ui.label('Quan sát, điều khiển và phục hồi 10 nhà màng dưa lưới.').classes('subtitle')

            username = ui.input('Tên đăng nhập').props('outlined autocomplete=username').classes('custom-input input-box')
            with username.add_slot('prepend'):
                ui.icon('person')

            password = ui.input('Mật khẩu', password=True, password_toggle_button=True).props(
                'outlined autocomplete=current-password').classes('custom-input input-box')
            with password.add_slot('prepend'):
                ui.icon('lock')

            login_btn = ui.button('Đăng nhập').props('no-caps unelevated').classes('login-btn')
            ui.label('Thiết bị trong hệ thống là thiết bị ảo. Quên mật khẩu, liên hệ quản trị viên để đặt lại.').classes('login-foot')

            async def do_login():
                from nicegui import run
                if not (username.value or '').strip() or not password.value:
                    ui.notify('Nhập tên đăng nhập và mật khẩu.', color='warning')
                    return
                if login_locked(username.value):
                    ui.notify('Đăng nhập sai quá nhiều lần. Thử lại sau 15 phút.', color='negative')
                    return
                login_btn.props('loading')
                try:
                    # Xác thực từ DB thật; băm PBKDF2 chạy ở luồng phụ để không chặn /healthz.
                    user = await run.io_bound(verify_user, username.value, password.value)
                    permissions = await run.io_bound(get_user_permissions, user['id']) if user else []
                except Exception as exc:
                    login_btn.props(remove='loading')
                    ui.notify(f'Không kết nối được cơ sở dữ liệu ({type(exc).__name__}). Thử lại sau.', color='negative')
                    return
                if not user:
                    ui.notify('Sai tên đăng nhập hoặc mật khẩu', color='negative')
                    login_btn.props(remove='loading')
                    return

                # Lưu vào storage
                app.storage.user['user_id'] = user['id']
                app.storage.user['username'] = user['username']
                app.storage.user['fullname'] = user['fullname']
                app.storage.user['role'] = user['role']
                app.storage.user['avatar'] = user.get('avatar', 'admin.png')
                app.storage.user['permissions'] = permissions

                login_btn.props(remove='loading')
                ui.navigate.to('/')

            login_btn.on_click(do_login)
            password.on('keydown.enter', lambda _: do_login())

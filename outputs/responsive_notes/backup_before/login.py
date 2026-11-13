from nicegui import ui, app
import asyncio
from service.auth import verify_user, get_user_permissions

# =========================================================
# GLOBAL CSS
# =========================================================

GLOBAL_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@300;400;500;600;700;800&display=swap');

*{
    font-family:'Be Vietnam Pro',sans-serif;
    box-sizing:border-box;
}

body{
    margin:0;
    overflow:hidden;
    background:#f8fafc;
}

.login-page{
    position:relative;
    width:100%;
    height:100vh;
    display:flex;
    justify-content:center;
    align-items:center;
    overflow:hidden;
}

.login-bg-img {
    position:absolute;
    inset:0;
    width:100%;
    height:100%;
    background-image:url('/static/login_bg.jpg');
    background-size:cover;
    background-position:center;
    z-index:1;
}

.login-card{
    position:relative;
    overflow:hidden;
    z-index:5;
    width:420px;
    max-width:92%;
    padding:35px 32px;
    border-radius:32px;
    background:rgba(255,255,255,0.75);
    border:1px solid rgba(255,255,255,0.6);
    backdrop-filter:blur(20px);
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.06), 0 1px 3px rgba(15, 23, 42, 0.02);
    animation:fadeUp .5s ease;
}

.login-card::before{
    content:'';
    position:absolute;
    inset:0;
    border-radius:32px;
    padding:1px;
    background: linear-gradient(135deg, rgba(255,255,255,0.8), rgba(255,255,255,0.2));
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite:xor;
    mask-composite:exclude;
    pointer-events:none;
}

@keyframes fadeUp{
    from{ opacity:0; transform:translateY(25px); }
    to{ opacity:1; transform:translateY(0); }
}

.login-header{
    width:100%;
    display:flex;
    flex-direction:column;
    align-items:center;
    text-align:center;
    margin-bottom:20px;
}

.logo-glow{
    width:92px;
    height:92px;
    border-radius:24px;
    object-fit:cover;
    box-shadow: 0 8px 24px rgba(59,130,246,0.15);
}

.title{
    margin-top:16px;
    color:#0f172a;
    font-size:28px;
    font-weight:800;
    letter-spacing:0.5px;
}

.subtitle{
    margin-top:6px;
    color:#475569;
    font-size:13px;
    line-height:20px;
}

.input-box{
    width:100%;
    margin-top:16px;
}

.custom-input{
    width:100%;
}

.custom-input .q-field__control{
    height:56px !important;
    border-radius:16px !important;
    background:rgba(15, 23, 42, 0.03) !important;
    border:1px solid #e2e8f0;
    padding:0 14px;
    transition:.25s;
}

.custom-input .q-field__native,
.custom-input input{
    color:#0f172a !important;
    font-size:15px !important;
    font-weight:500;
}

.custom-input .q-field__label{
    color:#64748b !important;
}

.custom-input .q-icon{
    color:#64748b !important;
    font-size:20px !important;
}

.custom-input .q-field__prepend{ padding-right:10px; }
.custom-input .q-field__append{ padding-left:10px; }

.custom-input .q-field__control:hover{
    border:1px solid #cbd5e1;
    background:rgba(15, 23, 42, 0.05) !important;
}

.custom-input.q-field--focused .q-field__control{
    border:1px solid #3b82f6 !important;
    background:#ffffff !important;
    box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1);
}

.q-icon{ font-family:'Material Icons' !important; }

.remember-row{
    width:100%;
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-top:14px;
}

.remember-link{
    color:#2563eb;
    text-decoration:none;
    font-size:13px;
    font-weight:500;
}

.remember-link:hover{
    text-decoration:underline;
}

.login-btn{
    width:100%;
    height:54px;
    margin-top:24px;
    border-radius:16px;
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    color:white !important;
    font-weight:700;
    font-size:15px;
    transition:.25s;
}

.login-btn:hover{
    transform:translateY(-1px);
    box-shadow: 0 8px 20px rgba(37, 99, 235, 0.25);
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

        with ui.card().classes('login-card'):
            with ui.column().classes('login-header'):
                ui.image('/static/logo.png').classes('logo-glow')
                    
                ui.label('SMART FARM').classes('title')
                ui.label('Smart Monitoring & Automation System').classes('subtitle')

            username = ui.input('Username').props('outlined').classes('custom-input input-box')
            with username.add_slot('prepend'):
                ui.icon('person').classes('text-slate-500')

            password = ui.input('Password', password=True, password_toggle_button=True).props('outlined').classes('custom-input input-box')
            with password.add_slot('prepend'):
                ui.icon('lock').classes('text-slate-500')

            with ui.row().classes('remember-row'):
                remember = ui.checkbox('Remember me').style('color:#475569')
                ui.link('Forgot password?', '#').classes('remember-link')

            login_btn = ui.button('LOGIN').classes('login-btn')

            async def do_login():
                login_btn.props('loading')
                await asyncio.sleep(0.5)

                # Xác thực từ DB thật
                user = verify_user(username.value, password.value)
                if not user:
                    ui.notify('Sai tên đăng nhập hoặc mật khẩu', color='negative')
                    login_btn.props(remove='loading')
                    return

                # Load permissions từ DB
                permissions = get_user_permissions(user['id'])

                # Lưu vào storage
                app.storage.user['user_id'] = user['id']
                app.storage.user['username'] = user['username']
                app.storage.user['fullname'] = user['fullname']
                app.storage.user['role'] = user['role']
                app.storage.user['avatar'] = user.get('avatar', 'admin.png')
                app.storage.user['permissions'] = permissions
                app.storage.user['remember'] = remember.value

                ui.notify('Đăng nhập thành công!', color='positive')
                login_btn.props(remove='loading')
                ui.navigate.to('/')

            login_btn.on_click(do_login)
            password.on('keydown.enter', lambda _: do_login())

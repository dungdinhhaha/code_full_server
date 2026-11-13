"""
pages/permission.py — Trang Quản Lý Phân Quyền (DB Thật 100%)
Kết nối trực tiếp SQLite, CRUD user & permissions thực tế.
"""

from nicegui import ui, app
from pages.home import CUSTOM_CSS, sidebar, global_topbar
from pages.login import check_login
from service.auth import (
    get_all_users, get_user_by_id, get_all_permissions,
    get_user_permissions, set_user_permissions,
    create_user, update_user, delete_user,
    ROLE_PRESETS, FIXED_FARMS, FARM_PRESETS,
    get_user_farms, set_user_farms, get_all_farms
)

# ─────────────────────────────────────────────
# PERMISSION PAGE CSS
# ─────────────────────────────────────────────
PERM_CSS = """
.perm-user-item {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 14px; border: 1px solid #e8ecf0;
    border-radius: 12px; cursor: pointer;
    transition: all 0.15s ease;
}
.perm-user-item:hover { background: #f8fafc; }
.perm-user-item.selected {
    border-left: 4px solid #4361ee;
    background: #f0f4ff;
    border-color: #4361ee;
}

.perm-module-card {
    border: 1px solid #e8ecf0;
    border-radius: 12px;
    padding: 16px;
    transition: border-color 0.2s;
}
.perm-module-card:hover { border-color: rgba(67,97,238,0.3); }

.preset-btn {
    padding: 6px 16px; border-radius: 8px;
    font-size: 12px; font-weight: 600;
    cursor: pointer; border: 1px solid #e8ecf0;
    transition: all 0.15s;
}
.preset-btn:hover { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.08); }

.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 4px; }
.custom-scrollbar:hover::-webkit-scrollbar-thumb { background-color: #94a3b8; }

.perm-detail-panel {
    animation: fadeIn 0.2s ease;
}
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}
"""

# Module colors cho checkbox groups
MODULE_CONFIG = {
    "home":     {"icon": "🏠", "label": "Home / Monitoring",  "color": "#4361ee"},
    "inverter": {"icon": "🔌", "label": "Inverter Control",   "color": "#10b981"},
    "plc":      {"icon": "⚙️", "label": "PLC / Pump Control", "color": "#f59e0b"},
    "admin":    {"icon": "🔒", "label": "Administration",     "color": "#ef4444"},
}


@ui.page('/permission')
def trang_permission():
    if not check_login(): return

    # Chỉ admin mới được vào trang này
    role = app.storage.user.get('role', '')
    permissions = app.storage.user.get('permissions', [])
    if role != 'admin' and 'manage_users' not in permissions:
        ui.notify('Bạn không có quyền truy cập trang này', color='negative')
        ui.navigate.to('/')
        return

    ui.add_head_html(f"<style>{CUSTOM_CSS}{PERM_CSS}</style>")
    sidebar(active="Permission")

    # State cho selected user
    selected_user_id = {'value': None}
    # Containers sẽ được dùng để refresh UI
    user_list_container = None
    config_container = None

    with ui.element("div").classes("main-content"):
        # Top bar
        global_topbar("Cấu Hình Phân Quyền", "🔑")

        with ui.element("div").classes("content-area"):
            # ── Layout 2 cột: 1 trái (user list) + 2 phải (form) ──
            with ui.element("div").style(
                "display:grid;grid-template-columns:1fr 2fr;gap:24px;align-items:start"
            ):
                # ══════════════════════════════════════
                # CỘT TRÁI: Danh sách User
                # ══════════════════════════════════════
                with ui.element("div").classes("card").style("display:flex;flex-direction:column"):
                    with ui.element("div").style("display:flex;justify-content:space-between;align-items:center;margin-bottom:16px"):
                        ui.label("Danh sách User").style("font-weight:700;font-size:15px;color:#1a1a2e")

                        def show_add_dialog():
                            with ui.dialog() as dlg, ui.card().style("width:380px;border-radius:16px;padding:24px"):
                                ui.label("Thêm User Mới").style("font-weight:700;font-size:16px;margin-bottom:16px")
                                new_username = ui.input("Username").style("width:100%")
                                new_fullname = ui.input("Tên hiển thị").style("width:100%")
                                new_password = ui.input("Mật khẩu", password=True).style("width:100%")
                                new_role = ui.select(
                                    ["admin", "operator", "viewer"],
                                    value="operator", label="Role"
                                ).style("width:100%")

                                with ui.row().style("width:100%;justify-content:flex-end;gap:8px;margin-top:16px"):
                                    ui.button("Hủy", on_click=dlg.close).style(
                                        "background:#e8ecf0;color:#555;padding:8px 16px;border-radius:8px;"
                                        "font-weight:600;font-size:13px"
                                    ).props("flat")

                                    def do_add():
                                        if not new_username.value or not new_password.value or not new_fullname.value:
                                            ui.notify("Vui lòng điền đầy đủ", color="warning")
                                            return
                                        result = create_user(
                                            new_username.value, new_password.value,
                                            new_fullname.value, new_role.value
                                        )
                                        if result:
                                            ui.notify(f"Đã thêm user '{new_username.value}'", color="positive")
                                            dlg.close()
                                            render_user_list.refresh()
                                        else:
                                            ui.notify("Username đã tồn tại!", color="negative")

                                    ui.button("Thêm", on_click=do_add).style(
                                        "background:#4361ee;color:white;padding:8px 16px;border-radius:8px;"
                                        "font-weight:600;font-size:13px"
                                    ).props("flat")
                            dlg.open()

                        ui.button("+ Thêm").style(
                            "background:#4361ee;color:white;padding:6px 12px;border-radius:8px;"
                            "font-size:12px;font-weight:600"
                        ).props("flat").on_click(show_add_dialog)

                    # Search box
                    search_input = ui.input(placeholder="Tìm kiếm user...").style(
                        "width:100%;margin-bottom:12px"
                    ).props("outlined dense")

                    # User list (refreshable)
                    @ui.refreshable
                    def render_user_list():
                        users = get_all_users()
                        search_term = search_input.value.lower() if search_input.value else ""

                        with ui.element("div").classes("custom-scrollbar").style(
                            "display:flex;flex-direction:column;gap:8px;max-height:calc(100vh - 320px);overflow-y:auto;padding-right:4px"
                        ):
                            for u in users:
                                if search_term and search_term not in u["username"].lower() and search_term not in u["fullname"].lower():
                                    continue

                                is_selected = selected_user_id['value'] == u["id"]
                                cls = "perm-user-item selected" if is_selected else "perm-user-item"

                                def select_user(uid=u["id"]):
                                    selected_user_id['value'] = uid
                                    render_user_list.refresh()
                                    render_config_panel.refresh()

                                with ui.element("div").classes(cls).on('click', select_user):
                                    # Avatar
                                    name_parts = u["fullname"].split()
                                    init_str = "+".join(name_parts[:2]) if name_parts else u["username"]
                                    role_colors = {"admin": "4361ee", "operator": "10b981", "viewer": "6b7280"}
                                    bg_color = role_colors.get(u["role"], "6b7280")
                                    import datetime
                                    now = datetime.datetime.now()
                                    is_online = False
                                    if u.get("last_active"):
                                        try:
                                            la_dt = datetime.datetime.strptime(u["last_active"], "%Y-%m-%d %H:%M:%S")
                                            if (now - la_dt).total_seconds() < 120:
                                                is_online = True
                                        except: pass

                                    with ui.element("div").style("position:relative"):
                                        ui.image(
                                            f"https://ui-avatars.com/api/?name={init_str}&background={bg_color}&color=fff"
                                        ).style("width:40px;height:40px;border-radius:50%;flex-shrink:0")
                                        
                                        # Dấu chấm trạng thái nhấp nháy trên Avatar
                                        dot_class = "dot-green" if is_online else "dot-red"
                                        ui.element("div").classes(dot_class).style(
                                            "position:absolute;bottom:0;right:0;width:10px;height:10px;border-radius:50%;border:2px solid white"
                                        )

                                    with ui.element("div").style("flex:1;min-width:0"):
                                        ui.label(u["username"]).style("font-weight:600;font-size:13px;color:#1a1a2e")
                                        ui.label(u["fullname"]).style("font-size:11px;color:#999")

                                    with ui.element("div").style("text-align:right"):
                                        role_badge_styles = {
                                            "admin": "background:#fae8ff;color:#9333ea",
                                            "operator": "background:#dbeafe;color:#2563eb",
                                            "viewer": "background:#f1f5f9;color:#6b7280",
                                        }
                                        ui.label(u["role"].capitalize()).style(
                                            f"{role_badge_styles.get(u['role'], '')};padding:2px 8px;"
                                            f"border-radius:12px;font-size:10px;font-weight:700;text-transform:uppercase"
                                        )
                                        ui.label(f"{u['perm_count']} quyền").style("font-size:10px;color:#aaa;margin-top:2px")

                    render_user_list()
                    search_input.on('change', lambda: render_user_list.refresh())

                # ══════════════════════════════════════
                # CỘT PHẢI: Form Cấu Hình
                # ══════════════════════════════════════
                @ui.refreshable
                def render_config_panel():
                    uid = selected_user_id['value']

                    if uid is None:
                        # Chưa chọn user
                        with ui.element("div").classes("card").style(
                            "display:flex;flex-direction:column;align-items:center;justify-content:center;"
                            "min-height:400px;color:#aaa"
                        ):
                            ui.label("🔑").style("font-size:48px;margin-bottom:16px;opacity:0.3")
                            ui.label("Chọn 1 user bên trái để cấu hình quyền").style(
                                "font-size:14px;font-weight:500"
                            )
                        return

                    # Load user data
                    user = get_user_by_id(uid)
                    if not user:
                        ui.label("User không tồn tại").style("color:#ef4444")
                        return

                    all_perms = get_all_permissions()
                    user_perms = get_user_permissions(uid)
                    user_farms = get_user_farms(uid)
                    all_farms = get_all_farms()

                    # State cho checkboxes
                    perm_states = {p["key"]: p["key"] in user_perms for p in all_perms}
                    farm_states = {f["key"]: f["key"] in user_farms for f in all_farms}

                    with ui.element("div").classes("card perm-detail-panel"):
                        # ── Header ──
                        with ui.element("div").style(
                            "display:flex;justify-content:space-between;align-items:center;"
                            "margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #f0f0f0"
                        ):
                            with ui.element("div"):
                                ui.label("Cấu Hình Quyền Truy Cập").style("font-weight:700;font-size:15px;color:#1a1a2e")
                                ui.html(
                                    f'<div style="font-size:12px;color:#aaa;margin-top:4px">'
                                    f'Đang chỉnh sửa cho: <span style="font-weight:600;color:#4361ee">{user["username"]}</span>'
                                    f'</div>'
                                )

                            with ui.element("div").style("display:flex;gap:8px"):
                                def do_cancel():
                                    render_config_panel.refresh()

                                ui.button("Hủy", on_click=do_cancel).style(
                                    "background:#e8ecf0;color:#555;padding:8px 16px;border-radius:8px;"
                                    "font-weight:600;font-size:13px"
                                ).props("flat")

                                def do_save():
                                    selected = [k for k, v in perm_states.items() if v]
                                    set_user_permissions(uid, selected)
                                    selected_farms = [k for k, v in farm_states.items() if v]
                                    set_user_farms(uid, selected_farms)
                                    ui.notify(f"Đã lưu quyền + farm cho '{user['username']}'", color="positive")
                                    render_user_list.refresh()

                                ui.button("Lưu Thay Đổi", on_click=do_save).style(
                                    "background:#4361ee;color:white;padding:8px 16px;border-radius:8px;"
                                    "font-weight:600;font-size:13px;box-shadow:0 4px 12px rgba(67,97,238,0.2)"
                                ).props("flat")

                        # ── Thông tin cơ bản ──
                        fullname_input = ui.input("Tên hiển thị", value=user["fullname"]).style("width:100%").props("outlined dense")
                        with ui.element("div").style("display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px"):
                            role_select = ui.select(
                                ["admin", "operator", "viewer"],
                                value=user["role"], label="Role"
                            ).props("outlined dense")
                            pw_input = ui.input("Mật khẩu mới (để trống = giữ nguyên)", password=True).props("outlined dense")

                        def do_update_info():
                            update_user(
                                uid,
                                fullname=fullname_input.value if fullname_input.value else None,
                                role=role_select.value if role_select.value else None,
                                password=pw_input.value if pw_input.value else None,
                            )
                            ui.notify("Đã cập nhật thông tin", color="positive")
                            render_user_list.refresh()

                        ui.button("Cập nhật thông tin", on_click=do_update_info).style(
                            "margin-top:12px;background:#f0f4ff;color:#4361ee;padding:8px 16px;"
                            "border-radius:8px;font-weight:600;font-size:12px;border:1px solid #e8ecf0"
                        ).props("flat")

                        # ── Preset Buttons ──
                        ui.label("CHỌN NHANH THEO ROLE").style(
                            "font-size:10px;font-weight:700;color:#aaa;letter-spacing:0.08em;"
                            "text-transform:uppercase;margin-top:20px;margin-bottom:8px"
                        )
                        with ui.element("div").style("display:flex;gap:8px"):
                            for preset_name, preset_perms in ROLE_PRESETS.items():
                                colors = {
                                    "admin": ("background:#fae8ff;color:#9333ea;border-color:#f0abfc", "#9333ea"),
                                    "operator": ("background:#dbeafe;color:#2563eb;border-color:#93c5fd", "#2563eb"),
                                    "viewer": ("background:#f1f5f9;color:#6b7280;border-color:#cbd5e1", "#6b7280"),
                                }
                                style_str = colors.get(preset_name, ("", ""))[0]

                                def apply_preset(perms=preset_perms):
                                    for k in perm_states:
                                        perm_states[k] = k in perms
                                    render_config_panel.refresh()

                                ui.button(preset_name.capitalize(), on_click=apply_preset).classes("preset-btn").style(style_str).props("flat")

                        # ── Bảng Checkbox Quyền ──
                        ui.label("QUYỀN CHỨC NĂNG").style(
                            "font-size:10px;font-weight:700;color:#aaa;letter-spacing:0.08em;"
                            "text-transform:uppercase;margin-top:20px;margin-bottom:12px"
                        )

                        # Group permissions by module
                        modules = {}
                        for p in all_perms:
                            mod = p["module"]
                            if mod not in modules:
                                modules[mod] = []
                            modules[mod].append(p)

                        with ui.element("div").style("display:grid;grid-template-columns:1fr 1fr;gap:16px"):
                            for mod_key, mod_perms in modules.items():
                                config = MODULE_CONFIG.get(mod_key, {"icon": "📋", "label": mod_key, "color": "#666"})
                                is_admin_mod = mod_key == "admin"

                                with ui.element("div").classes("perm-module-card").style(
                                    f"{'opacity:0.6' if is_admin_mod and user['role'] != 'admin' else ''}"
                                ):
                                    ui.label(f"{config['icon']}  {config['label']}").style(
                                        f"font-weight:600;font-size:13px;color:{config['color']};margin-bottom:12px"
                                    )

                                    for p in mod_perms:
                                        disabled = is_admin_mod and user["role"] != "admin"

                                        def toggle_perm(e, key=p["key"]):
                                            perm_states[key] = e.value

                                        cb = ui.checkbox(
                                            p["label"],
                                            value=perm_states.get(p["key"], False),
                                            on_change=toggle_perm
                                        ).style(f"font-size:13px;{'opacity:0.5' if disabled else ''}")

                                        if disabled:
                                            cb.props("disable")

                        # ── Phân Quyền Farm ──
                        ui.label("PHÂN QUYỀN FARM").style(
                            "font-size:10px;font-weight:700;color:#aaa;letter-spacing:0.08em;"
                            "text-transform:uppercase;margin-top:20px;margin-bottom:12px"
                        )

                        with ui.element("div").classes("perm-module-card"):
                            ui.label("🏡  Cho phép truy cập Farm").style(
                                "font-weight:600;font-size:13px;color:#10b981;margin-bottom:12px"
                            )
                            ui.label("User sẽ chỉ thấy các Farm được tích ở đây trong dropdown Topbar.").style(
                                "font-size:11px;color:#94a3b8;margin-bottom:12px"
                            )

                            with ui.element("div").style("display:grid;grid-template-columns:1fr 1fr;gap:8px"):
                                for farm in all_farms:
                                    def toggle_farm(e, fkey=farm["key"]):
                                        farm_states[fkey] = e.value

                                    ui.checkbox(
                                        f"{farm['emoji']}  {farm['label']}",
                                        value=farm_states.get(farm["key"], False),
                                        on_change=toggle_farm
                                    ).style("font-size:13px")

                        # --- Footer (Save/Cancel) ---
                        with ui.element("div").style(
                            "border-top:1px solid #f0f0f0;padding-top:16px;margin-top:20px;"
                            "display:flex;justify-content:space-between;align-items:center"
                        ):
                            def do_delete():
                                with ui.dialog() as confirm_dlg, ui.card().style("border-radius:16px;padding:24px"):
                                    ui.label(f"Xác nhận xóa user '{user['username']}'?").style(
                                        "font-weight:600;font-size:15px;margin-bottom:16px"
                                    )
                                    ui.label("Hành động này không thể hoàn tác.").style("font-size:13px;color:#ef4444")
                                    with ui.row().style("width:100%;justify-content:flex-end;gap:8px;margin-top:16px"):
                                        ui.button("Hủy", on_click=confirm_dlg.close).style(
                                            "background:#e8ecf0;color:#555;padding:8px 16px;border-radius:8px;"
                                            "font-weight:600;font-size:13px"
                                        ).props("flat")

                                        def confirm_delete():
                                            delete_user(uid)
                                            selected_user_id['value'] = None
                                            ui.notify(f"Đã xóa user '{user['username']}'", color="positive")
                                            confirm_dlg.close()
                                            render_user_list.refresh()
                                            render_config_panel.refresh()

                                        ui.button("Xóa", on_click=confirm_delete).style(
                                            "background:#ef4444;color:white;padding:8px 16px;border-radius:8px;"
                                            "font-weight:600;font-size:13px"
                                        ).props("flat")
                                confirm_dlg.open()

                            ui.button("🗑 Xóa User", on_click=do_delete).style(
                                "color:#ef4444;font-size:13px;font-weight:600;"
                                "background:transparent;padding:8px 12px;border-radius:8px"
                            ).props("flat")

                            with ui.element("div").style("display:flex;gap:8px"):
                                ui.button("Hủy", on_click=lambda: render_config_panel.refresh()).style(
                                    "background:#e8ecf0;color:#555;padding:8px 16px;border-radius:8px;"
                                    "font-weight:600;font-size:13px"
                                ).props("flat")
                                ui.button("Lưu Thay Đổi", on_click=do_save).style(
                                    "background:#4361ee;color:white;padding:8px 16px;border-radius:8px;"
                                    "font-weight:600;font-size:13px;box-shadow:0 4px 12px rgba(67,97,238,0.2)"
                                ).props("flat")

                render_config_panel()

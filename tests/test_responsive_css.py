"""Kiểm tra chuỗi CSS responsive (không cần MongoDB/MQTT).

Chỉ kiểm tra sự hiện diện của các quy tắc trong chuỗi CSS; không đo bố cục thật.
"""
import unittest

from pages.chart import CHART_CSS
from pages.home import CUSTOM_CSS
from pages.incident import INC_CSS
from pages.login import GLOBAL_CSS
from pages.permission import PERM_CSS
from pages.project import PROJECT_CSS


def _mobile_block(css: str) -> str:
    """Trả về nội dung khối @media (max-width: 768px) đầu tiên (đến @media kế tiếp)."""
    head = "@media (max-width: 768px) {"
    assert head in css, "thiếu khối @media (max-width: 768px)"
    body = css.split(head, 1)[1]
    return body.split("@media", 1)[0]


class HomeFrameResponsiveTest(unittest.TestCase):
    def test_mobile_resets_main_content_padding(self):
        block = _mobile_block(CUSTOM_CSS)
        self.assertIn("padding-left: 0", block)
        self.assertIn("height: 100dvh", block)

    def test_sidebar_hide_selector_is_direct_child(self):
        self.assertIn(".sidebar > div:last-child", CUSTOM_CSS)
        self.assertNotIn(".sidebar div:last-child", CUSTOM_CSS)

    def test_bottom_nav_scrolls_horizontally(self):
        block = _mobile_block(CUSTOM_CSS)
        self.assertIn("overflow-x: auto", block)
        self.assertIn("flex: 0 0 auto", block)

    def test_topbar_wraps_on_mobile(self):
        block = _mobile_block(CUSTOM_CSS)
        self.assertIn("flex-wrap: wrap", block)

    def test_wide_table_wrapper_exists(self):
        self.assertIn(".tbl-scroll", CUSTOM_CSS)
        self.assertIn("overflow-x: auto", CUSTOM_CSS)

    def test_small_screen_and_touch_rules_present(self):
        self.assertIn("@media (max-width: 480px)", CUSTOM_CSS)
        self.assertIn(".q-menu", CUSTOM_CSS)
        self.assertIn("@media (hover: none)", CUSTOM_CSS)


class IncidentResponsiveTest(unittest.TestCase):
    def test_incident_has_mobile_media(self):
        self.assertIn("@media (max-width:768px)", INC_CSS)
        self.assertIn("min-height:40px", INC_CSS)

    def test_question_table_breakpoint_widened(self):
        self.assertIn("@media (max-width:900px) { .inc-qtable", INC_CSS)


class ChartResponsiveTest(unittest.TestCase):
    def test_chart_has_mobile_media(self):
        self.assertIn("@media (max-width:768px)", CHART_CSS)
        self.assertIn(".dd-grid{grid-template-columns:1fr}", CHART_CSS)


class LoginResponsiveTest(unittest.TestCase):
    def test_login_page_uses_dvh_and_scrolls(self):
        self.assertIn("height:100dvh", GLOBAL_CSS)
        self.assertIn("overflow-y:auto", GLOBAL_CSS)

    def test_login_small_screen_media(self):
        self.assertIn("@media (max-width:480px)", GLOBAL_CSS)


class PermissionProjectResponsiveTest(unittest.TestCase):
    def test_permission_layout_collapses(self):
        self.assertIn(".perm-layout", PERM_CSS)
        self.assertIn("@media (max-width: 1024px)", PERM_CSS)
        self.assertIn(".perm-grid2 { grid-template-columns: 1fr !important; }", PERM_CSS)

    def test_project_grids_collapse(self):
        self.assertIn(".pj-kpi", PROJECT_CSS)
        self.assertIn(".pj-users{ min-width:520px; }", PROJECT_CSS)


if __name__ == "__main__":
    unittest.main()

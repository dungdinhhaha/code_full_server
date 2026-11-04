"""Legacy route redirected to the integrated lot and harvest view."""

from nicegui import ui


@ui.page("/traceability")
def traceability_redirect():
    ui.navigate.to("/mongodb-lab")

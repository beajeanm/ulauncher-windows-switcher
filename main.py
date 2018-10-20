import hashlib
import os
import time
import gi
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.event import ItemEnterEvent
from ulauncher.api.shared.event import KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem

gi.require_version('Gtk', '3.0')
gi.require_version('Wnck', '3.0')
from gi.repository import Gtk
from gi.repository import Wnck

CACHE_DIR = (os.getenv('XDG_CACHE_HOME', os.getenv('HOME') + '/.cache')) + '/ulauncher_window_switcher'


def is_hidden_window(window):
    state = window.get_state()
    return state & Wnck.WindowState.SKIP_PAGER or state & Wnck.WindowState.SKIP_TASKLIST


def list_windows():
    screen = Wnck.Screen.get_default()
    # We need to force the update as screen is populated lazily by default
    screen.force_update()
    # We need to wait for all events to be processed
    while Gtk.events_pending():
        Gtk.main_iteration()
    return [window for window in screen.get_windows() if not is_hidden_window(window)]


def store_icon_file(icon, name):
    # Some app have crazy names, ensure we use something reasonable
    file_name = hashlib.sha224(name).hexdigest()
    icon_full_path = CACHE_DIR + '/' + file_name + '.png'
    icon.savev(icon_full_path, 'png', [], [])
    return icon_full_path


def activate(window):
    workspace = window.get_workspace()
    # We need to first activate the workspace, otherwise windows on a different workspace might not become visible
    workspace.activate(int(time.time()))
    window.activate(int(time.time()))


def is_matching(window, keyword):
    # Assumes UTF-8 input
    ascii_keyword = keyword.encode().lower()
    return ascii_keyword in window.get_name().lower() or ascii_keyword in window.get_application().get_name().lower()


def render_window(window):
    window_name = window.get_name()
    app_name = window.get_application().get_name()
    return ExtensionResultItem(icon=store_icon_file(window.get_icon(), app_name),
                               name=app_name,
                               description=window_name,
                               on_enter=ExtensionCustomAction(window.get_xid(), keep_app_open=False))


class WindowSwitcherExtension(Extension):

    def __init__(self):
        super(WindowSwitcherExtension, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())
        # Ensure the icon cache directory is created
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        keyword = event.get_argument()
        if keyword is None:
            keyword = ''
        return RenderResultListAction(
            [render_window(window) for window in list_windows() if is_matching(window, keyword)])


class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        for window in list_windows():
            if window.get_xid() == event.get_data():
                activate(window)
        Wnck.shutdown()


if __name__ == '__main__':
    WindowSwitcherExtension().run()

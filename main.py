import hashlib
import os
import time
import gi
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.client.Extension import Extension
from ulauncher.api.shared.action.ExtensionCustomAction import ExtensionCustomAction
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.event import ItemEnterEvent, KeywordQueryEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem

gi.require_version('Gtk', '3.0')
gi.require_version('Wnck', '3.0')
from gi.repository import Gtk
from gi.repository import Wnck

XDG_FALLBACK = os.path.join(os.getenv('HOME'), '.cache')
XDG_CACHE = os.getenv('XDG_CACHE_HOME', XDG_FALLBACK)
CACHE_DIR = os.path.join(XDG_CACHE,  'ulauncher_window_switcher')


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


def activate(window):
    workspace = window.get_workspace()
    if workspace is not None:
        # We need to first activate the workspace, otherwise windows on a different workspace might not become visible
        workspace.activate(int(time.time()))

    window.activate(int(time.time()))


class WindowItem:

    def __init__(self, window, previous_selection):
        self.id = window.get_xid()
        self.app_name = window.get_application().get_name()
        self.title = window.get_name()
        self.icon = self.retrieve_or_save_icon(window.get_icon())
        self.is_last = window.get_xid() == previous_selection

    def retrieve_or_save_icon(self, icon):
        # Some app have crazy names, ensure we use something reasonable
        file_name = hashlib.sha224(self.app_name.encode('utf-8')).hexdigest()
        icon_full_path = CACHE_DIR + '/' + file_name + '.png'
        if not os.path.isfile(icon_full_path):
            icon.savev(icon_full_path, 'png', [], [])
        return icon_full_path

    def to_extension_item(self):
        return ExtensionResultItem(icon=self.icon,
                                   name=self.app_name,
                                   description=self.title,
                                   selected_by_default=self.is_last,
                                   on_enter=ExtensionCustomAction(self.id, keep_app_open=False))

    def is_matching(self, keyword):
        # Assumes UTF-8 input
        ascii_keyword = keyword.encode('utf-8').lower()
        return ascii_keyword in self.app_name.encode('utf-8').lower() or ascii_keyword in self.title.encode('utf-8').lower()


class WindowSwitcherExtension(Extension):

    def __init__(self):
        super(WindowSwitcherExtension, self).__init__()
        self.selection = None
        self.previous_selection = None
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())
        self.subscribe(ItemEnterEvent, ItemEnterEventListener())
        # Ensure the icon cache directory is created
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        query = event.get_argument()
        if query is None:
            # The extension has just been triggered, let's initialize the windows list.
            # (Or we delete all previously typed characters, but we can safely ignore that case)
            query = ''
            extension.items = [WindowItem(window, extension.previous_selection) for window in list_windows()]
        matching_items = [window_item.to_extension_item() for window_item in extension.items if
                          window_item.is_matching(query)]
        return RenderResultListAction(matching_items)


class ItemEnterEventListener(EventListener):
    def on_event(self, event, extension):
        for window in list_windows():
            if window.get_xid() == event.get_data():
                previous_selection = extension.selection
                extension.previous_selection = previous_selection
                extension.selection = window.get_xid()
                activate(window)
        Wnck.shutdown()


if __name__ == '__main__':
    WindowSwitcherExtension().run()

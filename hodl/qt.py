from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5.QtCore import *

import electroncash.version
from electroncash.i18n import _
from electroncash.plugins import BasePlugin, hook
from electroncash_gui.qt.util import destroyed_print_error
from electroncash.util import finalization_print_error



class Timer(QObject):
    update_sig = pyqtSignal()

    def __init__(self, parent, window, widget):
        super().__init__(parent=parent)

        self.window = window
        self.widget = widget
        self.update_sig.connect(self.on_update)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(2500)
        self.timer.timeout.connect(self.update_sig)

    def on_update(self):
        if not self.window.network or not self.window.network.is_connected():
            return

        self.widget.rescan_contracts()

class Plugin(BasePlugin):
    electrumcash_qt_gui = None
    # There's no real user-friendly way to enforce this.  So for now, we just calculate it, and ignore it.
    is_version_compatible = True

    def __init__(self, parent, config, name):
        BasePlugin.__init__(self, parent, config, name)
        self.network=None
        self.wallet_windows = {}
        self.hodl_tabs = {}
        self.hodl_tab= {}
        self.timers = {}

    def fullname(self):
        return 'HODL'

    def diagnostic_name(self):
        return "HODL"

    def description(self):
        return _("HODL Plugin")

    def on_close(self):
        """
        BasePlugin callback called when the wallet is disabled among other things.
        """
        for window in list(self.wallet_windows.values()):
            self.close_wallet(window.wallet)

    @hook
    def balance_label_extra(self, window):
        wallet_name = window.wallet.basename()
        if self.timers[wallet_name].timer:
            self.timers[wallet_name].timer.stop()
            self.timers[wallet_name].timer.start()

    @hook
    def update_contact(self, address, new_entry, old_entry):
        print("update_contact", address, new_entry, old_entry)

    @hook
    def delete_contacts(self, contact_entries):
        print("delete_contacts", contact_entries)

    @hook
    def init_qt(self, qt_gui):
        """
        Hook called when a plugin is loaded (or enabled).
        """
        self.electrumcash_qt_gui = qt_gui
        # We get this multiple times.  Only handle it once, if unhandled.
        if len(self.wallet_windows):
            return
        # These are per-wallet windows.
        for window in self.electrumcash_qt_gui.windows:
            self.load_wallet(window.wallet, window)

    @hook
    def load_wallet(self, wallet, window):
        """
        Hook called when a wallet is loaded and a window opened for it.
        """
        wallet_name = window.wallet.basename()
        self.wallet_windows[wallet_name] = window
        self.add_ui_for_wallet(wallet_name, window)
        self.refresh_ui_for_wallet(wallet_name)

    @hook
    def close_wallet(self, wallet):

        wallet_name = wallet.basename()
        window = self.wallet_windows[wallet_name]
        del self.wallet_windows[wallet_name]
        self.remove_ui_for_wallet(wallet_name, window)

    @staticmethod
    def _get_icon() -> QtGui.QIcon:
        import os
        path = os.path.dirname(os.path.abspath(__file__))
        if ".zip" in path:
            import zipfile
            zip_path = os.path.split(path)[0]
            zip_dir = os.path.split(zip_path)[0]
            unzip_path = os.path.join(zip_dir, 'hodl')
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extract("icons.rcc", unzip_path)
            rcpath = os.path.join(unzip_path,"icons.rcc")
        else:
            rcpath = os.path.join(path, "..", "icons.rcc")
        QtCore.QResource.registerResource(rcpath)
        icon = QtGui.QIcon(":/diamond.png")
        return icon

    def add_ui_for_wallet(self, wallet_name, window):
        from .ui import Manage
        widget = Manage(window, self, wallet_name, password=None, manager=None)
        tab = window.create_list_tab(widget)
        self.hodl_tabs[wallet_name] = tab
        self.hodl_tab[wallet_name] = widget
        window.tabs.addTab(tab, self._get_icon(), _('HODL'))
        self.timers[wallet_name] = Timer(None, window, widget)

    def remove_ui_for_wallet(self, wallet_name, window):
        wallet_tab = self.hodl_tabs.get(wallet_name, None)
        widget = self.hodl_tab.get(wallet_name)
        if wallet_tab is not None:
            if widget and callable(getattr(widget, 'kill_join', None)):
                widget.kill_join()  # kill thread, wait for up to 2.5 seconds for it to exit
            if widget and callable(getattr(widget, 'clean_up', None)):
                widget.clean_up()  # clean up wallet and stop its threads
            del self.hodl_tab[wallet_name]
            del self.hodl_tabs[wallet_name]
            if wallet_tab:
                i = window.tabs.indexOf(wallet_tab)
                window.tabs.removeTab(i)
                wallet_tab.deleteLater()
                self.print_error("Removed UI for", wallet_name)
        self.timers[wallet_name].timer.stop()
        del self.timers[wallet_name]


    def refresh_ui_for_wallet(self, wallet_name):
        wallet_tab = self.hodl_tabs.get(wallet_name)
        if wallet_tab:
            wallet_tab.update()
        wallet_tab = self.hodl_tab.get(wallet_name)
        if wallet_tab:
            wallet_tab.update()

    def switch_to(self, mode, wallet_name, password, manager):
        window=self.wallet_windows[wallet_name]
        try:
            l = mode(window, self, wallet_name, password=password, manager=manager)
            tab = window.create_list_tab(l)
            destroyed_print_error(tab)  # track object lifecycle
            finalization_print_error(tab)  # track object lifecycle

            old_tab = self.hodl_tabs.get(wallet_name, None)
            i = window.tabs.indexOf(old_tab)

            self.hodl_tabs[wallet_name] = tab
            self.hodl_tab[wallet_name] = l
            if old_tab:
                window.tabs.removeTab(i)
                old_tab.searchable_list.deleteLater()
                old_tab.deleteLater()
            window.tabs.insertTab(i,tab, self._get_icon(), _('HODL'))
            window.tabs.setCurrentIndex(i)
        except Exception as e:
            self.print_error(repr(e))
            return

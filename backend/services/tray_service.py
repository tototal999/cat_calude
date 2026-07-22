"""Small Windows tray wrapper; UI work is always marshalled back to Tk."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from config import policy


class TrayService:
    def __init__(self, icon_path: Path, dispatch: Callable[[str], None]) -> None:
        self._icon_path = icon_path
        self._dispatch = dispatch
        self._icon = None

    def start(self) -> bool:
        """Start the tray icon in a daemon thread; return False if unavailable."""
        try:
            import pystray
            from PIL import Image
            image = Image.open(self._icon_path)
        except (ImportError, OSError):
            return False

        items = [
            pystray.MenuItem('顯示貓', lambda _icon, _item: self._dispatch('show')),
            pystray.MenuItem('隱藏貓', lambda _icon, _item: self._dispatch('hide')),
            pystray.Menu.SEPARATOR,
        ]
        # Keep the tray in step with the right-click menu under company policy.
        # pystray inspects the action's signature, so bind the id with a closure
        # rather than a default argument (a 3-parameter lambda is rejected).
        def dispatcher(action_id):
            return lambda _icon, _item: self._dispatch(action_id)

        for feature_id, label in (('quick_question', '快速提問'), ('documents', '文件助手')):
            if policy.is_enabled(feature_id):
                items.append(pystray.MenuItem(label, dispatcher(feature_id)))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem('結束', lambda _icon, _item: self._dispatch('quit')))
        menu = pystray.Menu(*items)
        self._icon = pystray.Icon('ClaudeCat', image, 'ClaudeCat', menu)
        threading.Thread(target=self._icon.run, daemon=True).start()
        return True

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
            self._icon = None

"""Small Windows tray wrapper; UI work is always marshalled back to Tk."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable


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

        menu = pystray.Menu(
            pystray.MenuItem('顯示貓', lambda _icon, _item: self._dispatch('show')),
            pystray.MenuItem('隱藏貓', lambda _icon, _item: self._dispatch('hide')),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('快速提問', lambda _icon, _item: self._dispatch('quick_question')),
            pystray.MenuItem('文件助手', lambda _icon, _item: self._dispatch('documents')),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('結束', lambda _icon, _item: self._dispatch('quit')),
        )
        self._icon = pystray.Icon('ClaudeCat', image, 'ClaudeCat', menu)
        threading.Thread(target=self._icon.run, daemon=True).start()
        return True

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
            self._icon = None

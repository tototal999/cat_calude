"""
P1-0 前置驗證：pywebview + tkinter 執行緒共存（Windows）
=========================================================

驗證 spec 附錄 B-1 的核心假設，三項全過才解鎖 Part 1：
  1. tkinter 視窗的 frame 計數在 webview 開啟期間持續跳動（貓不被卡）
  2. webview 按鈕（自動模擬）呼叫 Python 約 1 秒拿到回傳（橋接可用、不凍結）
  3. 關閉 webview 後 tkinter 視窗仍存活 10 秒且持續跳動

執行緒模型（依 spec 1.2 定案）：pywebview 佔主執行緒，tkinter 跑背景執行緒。

全自動：webview 顯示後自動觸發橋接呼叫，6 秒後自動關窗，無需人工操作。
結果以 QA_RESULT 格式印出。

Run: python verify_pywebview_tk.py   （需 pip install pywebview）
"""
from __future__ import annotations

import threading
import time

import webview

# ---- tkinter cat stand-in: frame counter in a background thread -----------

frame_count = 0
tk_alive = True
tk_error: str | None = None
samples: list[tuple[float, int]] = []   # (timestamp, frame_count)


def tk_thread() -> None:
    global frame_count, tk_alive, tk_error
    try:
        import tkinter as tk
        root = tk.Tk()
        root.title('tk cat stand-in')
        root.geometry('220x80+50+50')
        root.wm_attributes('-topmost', True)
        label = tk.Label(root, text='frame 0', font=('Segoe UI', 16))
        label.pack(expand=True)

        def tick() -> None:
            global frame_count
            frame_count += 1
            label.configure(text=f'frame {frame_count}')
            root.after(100, tick)   # 10 fps, same order as the real cat

        tick()
        root.mainloop()
    except Exception as exc:   # noqa: BLE001 - report any failure verbatim
        tk_error = repr(exc)
    finally:
        tk_alive = False


def sampler_thread() -> None:
    """Record frame_count once a second for stall analysis."""
    while tk_alive:
        samples.append((time.time(), frame_count))
        time.sleep(1)


# ---- webview side ----------------------------------------------------------

bridge_latency: float | None = None


class Api:
    def ping(self) -> str:
        time.sleep(1)          # simulate ~1s of Python work
        return 'pong'


HTML = """
<!doctype html><html><body style="font-family:sans-serif">
<h3>pywebview bridge test</h3>
<button id="b" onclick="callPy()">call python</button>
<div id="out">(auto-clicking soon)</div>
<script>
function callPy() {
  const t0 = performance.now();
  pywebview.api.ping().then(r => {
    document.getElementById('out').innerText =
      r + ' in ' + Math.round(performance.now() - t0) + ' ms';
  });
}
</script>
</body></html>
"""


def drive_webview(window: webview.Window) -> None:
    """Auto-click the bridge button, then close the window. Always closes,
    even if a step fails - otherwise webview.start() would block forever."""
    global bridge_latency
    try:
        time.sleep(2)          # let the page finish loading
        t0 = time.time()
        window.evaluate_js(
            'pywebview.api.ping().then(r => { window.__pong = r; })')
        while time.time() - t0 < 10:
            if window.evaluate_js('window.__pong || null') == 'pong':
                bridge_latency = time.time() - t0
                break
            time.sleep(0.2)
        time.sleep(2)          # keep webview open a moment longer
    except Exception as exc:   # noqa: BLE001
        print('drive_webview error:', repr(exc))
    finally:
        window.destroy()


def main() -> None:
    threading.Thread(target=tk_thread, daemon=True).start()
    threading.Thread(target=sampler_thread, daemon=True).start()
    time.sleep(1)              # let tk get going

    window = webview.create_window('webview test', html=HTML, js_api=Api(),
                                   width=420, height=240, x=320, y=50)
    webview_open_t = time.time()
    threading.Thread(target=drive_webview, args=(window,), daemon=True).start()
    webview.start()            # blocks main thread until window.destroy()
    webview_close_t = time.time()

    # -- item 3: tk must stay alive 10s after webview closes ----------------
    post_close_start = frame_count
    time.sleep(10)
    post_close_frames = frame_count - post_close_start

    # -- item 1: min frames/second while webview was open --------------------
    in_window = [(t, c) for t, c in samples
                 if webview_open_t <= t <= webview_close_t]
    stalls = []
    for (t1, c1), (t2, c2) in zip(in_window, in_window[1:]):
        stalls.append((c2 - c1) / max(t2 - t1, 1e-6))
    min_fps = min(stalls) if stalls else 0.0

    ok1 = min_fps >= 5          # 10fps nominal; >=5 means no visible freeze
    ok2 = bridge_latency is not None and bridge_latency < 3
    ok3 = tk_alive and post_close_frames >= 50 and tk_error is None

    print(f'QA_RESULT|STATUS:{"PASS" if ok1 else "FAIL"}'
          f'|EXPECTED:tk >=5 fps while webview open'
          f'|ACTUAL:min {min_fps:.1f} fps across {len(stalls)} samples')
    print(f'QA_RESULT|STATUS:{"PASS" if ok2 else "FAIL"}'
          f'|EXPECTED:bridge round-trip ~1s (<3s)'
          f'|ACTUAL:{bridge_latency:.2f}s' if bridge_latency is not None else
          'QA_RESULT|STATUS:FAIL|EXPECTED:bridge round-trip ~1s|ACTUAL:no pong received')
    print(f'QA_RESULT|STATUS:{"PASS" if ok3 else "FAIL"}'
          f'|EXPECTED:tk alive 10s after webview close'
          f'|ACTUAL:alive={tk_alive} frames+={post_close_frames} err={tk_error}')
    print('P1-0 VERDICT:', 'GO' if (ok1 and ok2 and ok3) else 'NO-GO')


if __name__ == '__main__':
    main()

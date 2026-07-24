import os
import sys
import time
import threading
import uvicorn
import webview
import subprocess

# Self-installing missing desktop packages
def install_dependencies():
    packages = ["pystray", "plyer", "pyngrok", "Pillow"]
    needed = []
    for p in packages:
        try:
            if p == "Pillow":
                __import__("PIL")
            else:
                __import__(p)
        except ImportError:
            needed.append(p)
            
    if needed:
        print(f"[Setup] Dang tu dong cai dat thu vien phu tro: {needed}...")
        try:
            # Run pip install in non-interactive mode
            subprocess.check_call([sys.executable, "-m", "pip", "install", *needed])
            print("[Setup] Da hoan thanh cai dat thu vien.")
        except Exception as e:
            print(f"[Setup Error] Khong the tu dong cai dat: {str(e)}")

# Ensure dependencies are present
install_dependencies()

# Now safe to import
from pyngrok import ngrok
import pystray
from PIL import Image, ImageDraw
from backend.main import app
from backend.config import settings

# Set AppUserModelID so Windows toast notifications display custom App Name instead of "Python"
try:
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Hội thoại Đa kênh (Omnichannel)")
except Exception:
    pass

# Global window references
window = None
should_reopen = False
exit_program = False

def run_api_server():
    """Runs the FastAPI server locally on port 8000."""
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

def create_image():
    """Loads app_logo.ico or generates a fallback icon for the System Tray."""
    icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "app_logo.ico"))
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except Exception:
            pass
    image = Image.new('RGB', (64, 64), color=(37, 99, 235))
    dc = ImageDraw.Draw(image)
    dc.rectangle((12, 12, 52, 52), fill=None, outline=(255, 255, 255), width=2)
    dc.rectangle((22, 22, 42, 42), fill=(255, 255, 255))
    return image

def on_open_ui(icon, item):
    """Callback when clicking 'Open UI' in System Tray."""
    global should_reopen
    should_reopen = True

def on_exit(icon, item):
    """Callback when clicking 'Exit completely' in System Tray."""
    global exit_program
    exit_program = True
    if window:
        try:
            window.destroy()
        except:
            pass
    icon.stop()

def create_app_window():
    """Creates the PyWebView browser window pointing to localhost API."""
    global window
    window = webview.create_window(
        title="Omnichannel Sales Dashboard",
        url="http://127.0.0.1:8000",
        width=1180,
        height=800,
        resizable=True,
        min_size=(900, 600)
    )

if __name__ == "__main__":
    frontend_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend/out"))
    if not os.path.exists(frontend_out) or not os.listdir(frontend_out):
        print("=" * 70)
        print("LOI: Chua tim thay ma nguon tinh Next.js trong thu muc 'frontend/out'!")
        print("Vui long thuc hien build truoc bang cach chay cac lenh:")
        print("  cd frontend")
        print("  npm run build")
        print("\nSau do, chay lai file 'run_desktop.py' de mo phan mem.")
        print("=" * 70)
        sys.exit(1)

    print("[1/3] Dang khoi chay API server & Co so du lieu...")
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    time.sleep(1.5)

    # Start ngrok tunnel automatically on port 8000
    tunnel = None
    if settings.NGROK_AUTHTOKEN:
        print("[2/3] Dang thiet lap ngrok authtoken...")
        ngrok.set_auth_token(settings.NGROK_AUTHTOKEN)
    else:
        print("[2/3] Khong thiet lap NGROK_AUTHTOKEN (Chay ngrok che do nac danh)...")

    try:
        tunnel = ngrok.connect(8000)
        print(f"")
        print(f"============================================================")
        print(f"[Ngrok Tunnel] Duong dan Webhook Cong Khai Cua Ban:")
        print(f"  {tunnel.public_url}/api/facebook/webhook")
        print(f"-> Sao chep link nay vao Callback URL cua Facebook App nhe!")
        print(f"============================================================")
        print(f"")
    except Exception as e:
        print(f"[Ngrok Warning] Khong the tu dong mo ngrok (Co the vi trung session hoac thieu config): {str(e)}")

    # Initialize System Tray Icon
    icon_image = create_image()
    tray_menu = pystray.Menu(
        pystray.MenuItem("Open", on_open_ui),
        pystray.MenuItem("Exit", on_exit)
    )
    
    icon_obj = pystray.Icon(
        "omnichannel_chat",
        icon_image,
        "Omnichannel Chat - Facebook Page Sync",
        menu=tray_menu
    )
    
    # Run pystray in a background thread to prevent blocking main thread
    tray_thread = threading.Thread(target=icon_obj.run, daemon=True)
    tray_thread.start()

    print("[3/3] Dang khoi tao cua so ung dung Desktop (PyWebView)...")
    
    # Window lifecycle event loop
    while not exit_program:
        create_app_window()
        webview.start()
        
        # When browser window is closed (click "X"), pywebview returns.
        # If exit_program is False, it means the user only closed the UI but wants the app
        # to run in the background (System Tray). We sleep and wait for reopen/exit clicks.
        should_reopen = False
        if not exit_program:
            print("[Status] Cua so giao dien da dong. Phan mem dang chay an duoi System Tray (Khay he thong)...")
            
        while not exit_program and not should_reopen:
            time.sleep(0.5)

    # Disconnect ngrok tunnel if it was started
    if tunnel:
        try:
            ngrok.disconnect(tunnel.public_url)
        except:
            pass

    print("Da dong toan bo tien trinh he thong. Hen gap lai ban!")

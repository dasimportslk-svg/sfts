import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ============================================================
# OPTIONAL OLED
# ============================================================

OLED_AVAILABLE = False
oled = None
oled_lock = threading.Lock()

try:
    from PIL import Image, ImageDraw, ImageFont
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306

    try:
        serial = i2c(
            port=1,
            address=0x3C
        )

        oled = ssd1306(
            serial,
            width=128,
            height=64
        )

        OLED_AVAILABLE = True

    except Exception:
        OLED_AVAILABLE = False
        oled = None

except Exception:
    OLED_AVAILABLE = False
    oled = None


if OLED_AVAILABLE:
    try:
        font_small = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            9
        )

        font_tiny = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            7
        )

    except Exception:
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()


def oled_disable():
    global OLED_AVAILABLE
    OLED_AVAILABLE = False


def oled_clear():
    if not OLED_AVAILABLE or oled is None:
        return

    try:
        with oled_lock:
            oled.clear()
    except Exception:
        oled_disable()


def oled_show(
    title,
    line1="",
    line2="",
    percent=None
):
    if not OLED_AVAILABLE or oled is None:
        return

    try:
        img = Image.new(
            "1",
            (128, 64),
            0
        )

        draw = ImageDraw.Draw(img)

        draw.text(
            (2, 1),
            str(title)[:20],
            font=font_small,
            fill=255
        )

        draw.line(
            (0, 13, 127, 13),
            fill=255
        )

        draw.text(
            (2, 17),
            str(line1)[:21],
            font=font_small,
            fill=255
        )

        draw.text(
            (2, 29),
            str(line2)[:21],
            font=font_tiny,
            fill=255
        )

        if percent is not None:

            percent = max(
                0,
                min(100, float(percent))
            )

            draw.rectangle(
                (2, 40, 125, 51),
                outline=255
            )

            width = int(
                119 * percent / 100
            )

            if width > 0:
                draw.rectangle(
                    (4, 42, 4 + width, 49),
                    fill=255
                )

            draw.text(
                (47, 54),
                f"{percent:.0f}%",
                font=font_tiny,
                fill=255
            )

        else:

            dots = int(
                time.time() * 4
            ) % 4

            draw.text(
                (2, 43),
                "." * dots,
                font=font_small,
                fill=255
            )

        with oled_lock:
            oled.display(img)

    except Exception:
        oled_disable()


def oled_idle():
    oled_show(
        "DH SFTP",
        "Laptop File Transfer",
        "READY"
    )


def oled_connecting(ip):
    oled_show(
        "CONNECTING",
        ip,
        "SFTP PORT 22"
    )


def oled_connected(ip):
    oled_show(
        "CONNECTED",
        ip,
        "SFTP READY"
    )


def oled_error(text):
    oled_show(
        "SFTP ERROR",
        str(text)[:21],
        "CHECK CONNECTION"
    )


def oled_download(
    filename,
    percent,
    transferred,
    total
):
    if not OLED_AVAILABLE or oled is None:
        return

    try:

        img = Image.new(
            "1",
            (128, 64),
            0
        )

        draw = ImageDraw.Draw(img)

        draw.text(
            (2, 1),
            "DOWNLOADING",
            font=font_small,
            fill=255
        )

        draw.line(
            (0, 13, 127, 13),
            fill=255
        )

        name = os.path.basename(
            filename
        )

        if len(name) > 21:
            name = name[:18] + "..."

        draw.text(
            (2, 17),
            name,
            font=font_tiny,
            fill=255
        )

        if total > 0:

            size_text = (
                f"{transferred / 1048576:.1f}/"
                f"{total / 1048576:.1f}MB"
            )

        else:

            size_text = "TRANSFERRING..."

        draw.text(
            (2, 29),
            size_text[:21],
            font=font_tiny,
            fill=255
        )

        percent = max(
            0,
            min(100, float(percent))
        )

        draw.rectangle(
            (2, 40, 125, 51),
            outline=255
        )

        width = int(
            119 * percent / 100
        )

        if width > 0:

            draw.rectangle(
                (4, 42, 4 + width, 49),
                fill=255
            )

        draw.text(
            (47, 54),
            f"{percent:.0f}%",
            font=font_tiny,
            fill=255
        )

        with oled_lock:
            oled.display(img)

    except Exception:
        oled_disable()


def oled_complete(filename):
    oled_show(
        "COMPLETE",
        os.path.basename(filename)[:21],
        "DOWNLOAD FINISHED"
    )


# ============================================================
# PARAMIKO
# ============================================================

try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except Exception:
    PARAMIKO_AVAILABLE = False


# ============================================================
# GLOBAL SFTP STATE
# ============================================================

ssh_client = None
sftp = None

current_path = "."
current_items = []

download_running = False


# ============================================================
# MAIN WINDOW
# ============================================================

root = tk.Tk()

root.title(
    "DH Laptop SFTP Transfer"
)

root.geometry(
    "900x620"
)

root.minsize(
    700,
    500
)


# ============================================================
# VARIABLES
# ============================================================

ip_var = tk.StringVar(
    value="172.18.57.102"
)

path_var = tk.StringVar(
    value="."
)

progress_var = tk.DoubleVar(
    value=0
)


# ============================================================
# SFTP DISCONNECT
# ============================================================

def disconnect_sftp():

    global ssh_client
    global sftp

    try:
        if sftp is not None:
            sftp.close()
    except Exception:
        pass

    try:
        if ssh_client is not None:
            ssh_client.close()
    except Exception:
        pass

    sftp = None
    ssh_client = None


# ============================================================
# SFTP CONNECT
# ============================================================

def connect_sftp(
    ip,
    username,
    password
):

    global ssh_client
    global sftp

    if not PARAMIKO_AVAILABLE:

        return (
            False,
            "Paramiko is not installed."
        )

    try:

        oled_connecting(ip)

        disconnect_sftp()

        ssh_client = paramiko.SSHClient()

        ssh_client.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )

        ssh_client.connect(
            hostname=ip,
            port=22,
            username=username,
            password=password,
            timeout=10,
            banner_timeout=10,
            auth_timeout=10
        )

        sftp = ssh_client.open_sftp()

        oled_connected(ip)

        return True, ""

    except Exception as e:

        disconnect_sftp()

        oled_error(str(e))

        return False, str(e)


# ============================================================
# FORMAT SIZE
# ============================================================

def format_size(size):

    try:
        size = int(size)
    except Exception:
        return ""

    if size < 1024:
        return f"{size} B"

    if size < 1048576:
        return f"{size / 1024:.1f} KB"

    if size < 1073741824:
        return f"{size / 1048576:.1f} MB"

    return f"{size / 1073741824:.2f} GB"


# ============================================================
# GET REMOTE FILES
# ============================================================

def get_remote_items(path):

    import stat

    items = []

    entries = sftp.listdir_attr(
        path
    )

    for attr in entries:

        name = attr.filename

        if name in [".", ".."]:
            continue

        try:

            is_dir = stat.S_ISDIR(
                attr.st_mode
            )

        except Exception:

            is_dir = False

        if path in [
            "",
            "."
        ]:

            item_path = name

        else:

            item_path = (
                path.rstrip("/") +
                "/" +
                name
            )

        items.append({
            "name": name,
            "path": item_path,
            "is_dir": is_dir,
            "size": attr.st_size
        })

    items.sort(
        key=lambda x: (
            not x["is_dir"],
            x["name"].lower()
        )
    )

    return items


# ============================================================
# REFRESH
# ============================================================

def refresh_files():

    global current_items

    if sftp is None:
        return

    try:

        current_items = get_remote_items(
            current_path
        )

        tree.delete(
            *tree.get_children()
        )

        for item in current_items:

            if item["is_dir"]:

                name = (
                    "[FOLDER] " +
                    item["name"]
                )

                kind = "Folder"
                size = ""

            else:

                name = (
                    "[FILE] " +
                    item["name"]
                )

                kind = "File"

                size = format_size(
                    item["size"]
                )

            tree.insert(
                "",
                "end",
                values=(
                    name,
                    kind,
                    size
                )
            )

        path_var.set(
            current_path
        )

    except Exception as e:

        messagebox.showerror(
            "SFTP Error",
            str(e)
        )


# ============================================================
# BACK
# ============================================================

def go_back():

    global current_path

    if current_path in [
        ".",
        "/",
        ""
    ]:

        return

    path = current_path.rstrip(
        "/"
    )

    parent = os.path.dirname(
        path
    )

    if not parent:
        parent = "."

    current_path = parent

    refresh_files()


# ============================================================
# OPEN FOLDER
# ============================================================

def open_selected(event=None):

    global current_path

    selected = tree.selection()

    if not selected:
        return

    index = tree.index(
        selected[0]
    )

    if index >= len(current_items):
        return

    item = current_items[index]

    if item["is_dir"]:

        current_path = item["path"]

        refresh_files()


# ============================================================
# GET SELECTED FILE
# ============================================================

def get_selected_file():

    selected = tree.selection()

    if not selected:
        return None

    index = tree.index(
        selected[0]
    )

    if index >= len(current_items):
        return None

    item = current_items[index]

    if item["is_dir"]:
        return None

    return item


# ============================================================
# DOWNLOAD
# ============================================================

def download_file():

    global download_running

    if download_running:
        return

    if sftp is None:

        messagebox.showwarning(
            "Not Connected",
            "Connect to laptop first."
        )

        return

    item = get_selected_file()

    if not item:

        messagebox.showwarning(
            "Select File",
            "Please select a file."
        )

        return

    destination = filedialog.askdirectory(
        title="Choose Pi Destination Folder",
        initialdir="/home/pi"
    )

    if not destination:
        return

    filename = item["name"]

    local_path = os.path.join(
        destination,
        filename
    )

    if os.path.exists(
        local_path
    ):

        answer = messagebox.askyesno(
            "File Exists",
            filename +
            "\n\nAlready exists.\n\n"
            "Overwrite?"
        )

        if not answer:
            return

    download_running = True

    download_button.config(
        state="disabled"
    )

    refresh_button.config(
        state="disabled"
    )

    back_button.config(
        state="disabled"
    )

    connect_button.config(
        state="disabled"
    )

    progress_var.set(
        0
    )

    percent_label.config(
        text="0%"
    )

    speed_label.config(
        text="Starting..."
    )

    threading.Thread(
        target=download_worker,
        args=(
            item["path"],
            local_path,
            item["size"],
            filename
        ),
        daemon=True
    ).start()


# ============================================================
# DOWNLOAD WORKER
# ============================================================

def download_worker(
    remote_path,
    local_path,
    total_size,
    filename
):

    global download_running

    start_time = time.time()
    last_oled_time = 0

    try:

        def callback(
            transferred,
            total
        ):

            nonlocal last_oled_time

            if total > 0:

                percent = (
                    transferred /
                    total
                ) * 100

            else:

                percent = 0

            elapsed = (
                time.time() -
                start_time
            )

            if elapsed > 0:

                speed = (
                    transferred /
                    elapsed
                )

            else:

                speed = 0

            if speed >= 1048576:

                speed_text = (
                    f"{speed / 1048576:.2f}"
                    " MB/s"
                )

            else:

                speed_text = (
                    f"{speed / 1024:.1f}"
                    " KB/s"
                )

            root.after(
                0,
                update_progress,
                percent,
                speed_text
            )

            now = time.time()

            if (
                now - last_oled_time >= 0.12
                or transferred >= total
            ):

                last_oled_time = now

                oled_download(
                    filename,
                    percent,
                    transferred,
                    total
                )

        sftp.get(
            remote_path,
            local_path,
            callback=callback,
            prefetch=True
        )

        oled_complete(
            filename
        )

        root.after(
            0,
            download_finished,
            True,
            local_path
        )

    except Exception as e:

        oled_error(
            str(e)
        )

        root.after(
            0,
            download_finished,
            False,
            str(e)
        )

    finally:

        download_running = False


# ============================================================
# UPDATE PROGRESS
# ============================================================

def update_progress(
    percent,
    speed
):

    progress_var.set(
        percent
    )

    percent_label.config(
        text=f"{percent:.1f}%"
    )

    speed_label.config(
        text=speed
    )


# ============================================================
# DOWNLOAD FINISHED
# ============================================================

def download_finished(
    success,
    message
):

    download_button.config(
        state="normal"
    )

    refresh_button.config(
        state="normal"
    )

    back_button.config(
        state="normal"
    )

    connect_button.config(
        state="normal"
    )

    if success:

        progress_var.set(
            100
        )

        percent_label.config(
            text="100%"
        )

        speed_label.config(
            text="Completed"
        )

        messagebox.showinfo(
            "Download Complete",
            "File downloaded successfully.\n\n" +
            message
        )

    else:

        messagebox.showerror(
            "Download Error",
            message
        )


# ============================================================
# LOGIN WINDOW
# ============================================================

def login_window():

    login = tk.Toplevel(
        root
    )

    login.title(
        "SFTP Connection"
    )

    login.geometry(
        "400x300"
    )

    login.resizable(
        False,
        False
    )

    login.transient(
        root
    )

    login.grab_set()

    tk.Label(
        login,
        text="Laptop IP Address",
        font=("Arial", 11, "bold")
    ).pack(
        pady=(18, 5)
    )

    ip_entry = tk.Entry(
        login,
        font=("Arial", 12),
        width=28
    )

    ip_entry.pack()

    ip_entry.insert(
        0,
        ip_var.get()
    )

    tk.Label(
        login,
        text="Windows Username",
        font=("Arial", 11, "bold")
    ).pack(
        pady=(12, 5)
    )

    user_entry = tk.Entry(
        login,
        font=("Arial", 12),
        width=28
    )

    user_entry.pack()

    tk.Label(
        login,
        text="Windows Password",
        font=("Arial", 11, "bold")
    ).pack(
        pady=(12, 5)
    )

    pass_entry = tk.Entry(
        login,
        font=("Arial", 12),
        width=28,
        show="*"
    )

    pass_entry.pack()

    status_label = tk.Label(
        login,
        text="Ready"
    )

    status_label.pack(
        pady=8
    )

    def do_connect():

        ip = ip_entry.get().strip()
        username = user_entry.get().strip()
        password = pass_entry.get()

        if not ip:

            messagebox.showwarning(
                "IP Required",
                "Enter laptop IP address.",
                parent=login
            )

            return

        if not username:

            messagebox.showwarning(
                "Username Required",
                "Enter Windows username.",
                parent=login
            )

            return

        connect_button_login.config(
            state="disabled"
        )

        status_label.config(
            text="Connecting..."
        )

        def worker():

            ok, error = connect_sftp(
                ip,
                username,
                password
            )

            def finish():

                connect_button_login.config(
                    state="normal"
                )

                if ok:

                    ip_var.set(
                        ip
                    )

                    connection_status.config(
                        text="Connected: " + ip
                    )

                    login.grab_release()
                    login.destroy()

                    global current_path

                    current_path = "."

                    refresh_files()

                else:

   

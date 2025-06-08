import customtkinter as ctk
import os
import subprocess
import json
import shutil
import zipfile
from tkinter import filedialog, messagebox
from PIL import Image
import ctypes
import requests
import threading
import re
import sys
import hashlib
import tempfile
import time

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "launcher_config.json")

# Add the Scripts directory to PATH if not already present
scripts_dir = os.path.join(sys.prefix, 'Scripts')
if scripts_dir not in os.environ['PATH']:
    os.environ['PATH'] = scripts_dir + os.pathsep + os.environ['PATH']

# GitHub repository information
GITHUB_REPO = "notif4ir/FNFML"  # Your GitHub repo
GITHUB_RAW_URL = "https://raw.githubusercontent.com/notif4ir/FNFML/refs/heads/main"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}"

def save_path(path):
    with open(config_path, "w") as f:
        json.dump({"base_path": path}, f)

def load_path():
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f).get("base_path", "")
    return ""

def get_folders(path):
    return [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]

def find_exe(path):
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(".exe"):
                return os.path.join(root, file)
    return None

def get_icon_from_exe(exe_path, size=(64, 64)):
    try:
        # First check for custom icon
        mod_folder = os.path.dirname(exe_path)
        custom_icon_path = os.path.join(mod_folder, "custom_icon.png")
        if os.path.exists(custom_icon_path):
            try:
                img = Image.open(custom_icon_path)
                img = img.resize(size, Image.LANCZOS)
                return img
            except Exception as e:
                print(f"Failed to load custom icon: {e}")

        # Try to get icon from exe
        try:
            import win32gui
            import win32ui
            import win32con
            import win32api

            # Get the icon
            ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
            ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)
            
            large, small = win32gui.ExtractIconEx(exe_path, 0, 1)
            win32gui.DestroyIcon(small[0])
            
            # Get the icon info
            ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
            ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)
            
            # Create DC
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
            hdc = hdc.CreateCompatibleDC()
            
            # Select the bitmap
            hdc.SelectObject(hbmp)
            
            # Draw the icon
            hdc.DrawIcon((0, 0), large[0])
            
            # Convert to PIL Image
            bmpstr = hbmp.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGBA',
                (ico_x, ico_y),
                bmpstr, 'raw', 'BGRA', 0, 1
            )
            
            # Clean up
            win32gui.DestroyIcon(large[0])
            hdc.DeleteDC()
            win32gui.ReleaseDC(0, hdc.GetHandleOutput())
            hbmp.DeleteObject()
            
            # Resize to requested size
            img = img.resize(size, Image.LANCZOS)
            return img
            
        except Exception as e:
            print(f"Failed to get icon from exe: {e}")
            # Fall back to shell32 method
            try:
                large, small = ctypes.c_void_p(), ctypes.c_void_p()
                ctypes.windll.shell32.ExtractIconExW(exe_path, 0, ctypes.byref(large), ctypes.byref(small), 1)
                hicon = large.value if large.value else small.value
                if not hicon:
                    return None

                hdc = ctypes.windll.user32.GetDC(0)
                bmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc, size[0], size[1])
                memdc = ctypes.windll.gdi32.CreateCompatibleDC(hdc)
                oldbmp = ctypes.windll.gdi32.SelectObject(memdc, bmp)

                ctypes.windll.user32.DrawIconEx(memdc, 0, 0, hicon, size[0], size[1], 0, 0, 0x0003)

                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ('biSize', ctypes.c_uint32),
                        ('biWidth', ctypes.c_int32),
                        ('biHeight', ctypes.c_int32),
                        ('biPlanes', ctypes.c_uint16),
                        ('biBitCount', ctypes.c_uint16),
                        ('biCompression', ctypes.c_uint32),
                        ('biSizeImage', ctypes.c_uint32),
                        ('biXPelsPerMeter', ctypes.c_int32),
                        ('biYPelsPerMeter', ctypes.c_int32),
                        ('biClrUsed', ctypes.c_uint32),
                        ('biClrImportant', ctypes.c_uint32)
                    ]

                bmpinfo = ctypes.create_string_buffer(40)
                ctypes.windll.gdi32.GetDIBits(memdc, bmp, 0, size[1], None, bmpinfo, 0)

                bih = BITMAPINFOHEADER.from_buffer_copy(bmpinfo)
                buf_size = bih.biSizeImage if bih.biSizeImage != 0 else size[0]*size[1]*4
                buf = ctypes.create_string_buffer(buf_size)

                ctypes.windll.gdi32.GetDIBits(memdc, bmp, 0, size[1], buf, bmpinfo, 0)

                img = Image.frombuffer('BGRA', size, buf, 'raw', 'BGRA', 0, 1).convert('RGBA')

                ctypes.windll.gdi32.SelectObject(memdc, oldbmp)
                ctypes.windll.gdi32.DeleteObject(bmp)
                ctypes.windll.gdi32.DeleteDC(memdc)
                ctypes.windll.user32.ReleaseDC(0, hdc)
                ctypes.windll.user32.DestroyIcon(hicon)

                return img
            except Exception as e:
                print(f"Failed to get icon using shell32: {e}")
                return None
    except Exception as e:
        print(f"Error in get_icon_from_exe: {e}")
        return None

def get_icon_from_ico_folder(path, size=(64,64)):
    try:
        # First check for custom icon
        custom_icon_path = os.path.join(path, "custom_icon.png")
        if os.path.exists(custom_icon_path):
            try:
                img = Image.open(custom_icon_path)
                img = img.resize(size, Image.LANCZOS)
                return img
            except Exception as e:
                print(f"Failed to load custom icon: {e}")

        # Try to find and load .ico files
        for file in os.listdir(path):
            if file.lower().endswith(".ico"):
                try:
                    # Try using win32gui for better .ico support
                    import win32gui
                    import win32ui
                    import win32con
                    import win32api
                    
                    ico_path = os.path.join(path, file)
                    large, small = win32gui.ExtractIconEx(ico_path, 0, 1)
                    win32gui.DestroyIcon(small[0])
                    
                    # Get the icon info
                    ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
                    ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)
                    
                    # Create DC
                    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                    hbmp = win32ui.CreateBitmap()
                    hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
                    hdc = hdc.CreateCompatibleDC()
                    
                    # Select the bitmap
                    hdc.SelectObject(hbmp)
                    
                    # Draw the icon
                    hdc.DrawIcon((0, 0), large[0])
                    
                    # Convert to PIL Image
                    bmpstr = hbmp.GetBitmapBits(True)
                    img = Image.frombuffer(
                        'RGBA',
                        (ico_x, ico_y),
                        bmpstr, 'raw', 'BGRA', 0, 1
                    )
                    
                    # Clean up
                    win32gui.DestroyIcon(large[0])
                    hdc.DeleteDC()
                    win32gui.ReleaseDC(0, hdc.GetHandleOutput())
                    hbmp.DeleteObject()
                    
                    # Resize to requested size
                    img = img.resize(size, Image.LANCZOS)
                    return img
                    
                except Exception as e:
                    print(f"Failed to load .ico using win32gui: {e}")
                    # Fall back to PIL
                    try:
                        img = Image.open(os.path.join(path, file)).convert("RGBA")
                        img = img.resize(size, Image.LANCZOS)
                        return img
                    except Exception as e:
                        print(f"Failed to load .ico using PIL: {e}")
                        continue
        return None
    except Exception as e:
        print(f"Error in get_icon_from_ico_folder: {e}")
        return None

def get_file_hash(file_path):
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def check_for_updates():
    """Check if there's a newer version available"""
    try:
        # Get the current file content
        current_file = os.path.abspath(__file__)
        current_hash = get_file_hash(current_file)
        
        # Get the GitHub file content
        response = requests.get(f"{GITHUB_RAW_URL}/fnf.pyw", timeout=5)
        if response.status_code != 200:
            print("Could not reach GitHub, skipping update check")
            return None
            
        # Calculate hash of GitHub content
        github_content = response.content
        github_hash = hashlib.sha256(github_content).hexdigest()
        
        # Compare hashes
        if github_hash != current_hash:
            print("New version found on GitHub")
            return "new_version"  # Return any non-None value to trigger update
        return None
    except (requests.RequestException, Exception) as e:
        print(f"Error checking for updates: {e}")
        return None

def download_update(version, progress_callback):
    """Download the latest version"""
    try:
        # Download directly from raw GitHub URL
        response = requests.get(f"{GITHUB_RAW_URL}/fnf.pyw", stream=True)
        if response.status_code != 200:
            raise Exception("Failed to download update")
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024
        downloaded = 0
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pyw') as temp_file:
            for data in response.iter_content(block_size):
                downloaded += len(data)
                temp_file.write(data)
                if total_size > 0:
                    progress = downloaded / total_size
                    progress_callback(progress)
        
        return temp_file.name
    except Exception as e:
        print(f"Error downloading update: {e}")
        return None

class UpdateWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FNFML")
        self.geometry("400x200")
        self.resizable(False, False)
        
        self.label = ctk.CTkLabel(self, text="Checking for updates...")
        self.label.pack(pady=20)
        
        self.progress = ctk.CTkProgressBar(self, width=300)
        self.progress.pack(pady=20)
        self.progress.set(0)
        
        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.pack(pady=10)
        
        self.update_thread = None
        
    def start_update(self):
        self.update_thread = threading.Thread(target=self._update_process, daemon=True)
        self.update_thread.start()
    
    def _update_process(self):
        try:
            # Check for updates
            self.label.configure(text="Checking for updates...")
            latest_version = check_for_updates()
            
            if not latest_version:
                self.label.configure(text="Starting application...")
                self.after(1000, self.destroy)
                return
            
            # Download update
            self.label.configure(text=f"Downloading new version...")
            def update_progress(progress):
                self.after(0, self.progress.set, progress)
            
            update_file = download_update(latest_version, update_progress)
            if not update_file:
                self.label.configure(text="Starting application...")
                self.after(1000, self.destroy)
                return
            
            # Get current file path
            current_file = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file)
            
            # Create a new file with a different name
            new_file = os.path.join(current_dir, "fnf_new.pyw")
            
            # Copy the new file
            shutil.copy2(update_file, new_file)
            
            # Create a batch file to handle the restart
            batch_file = os.path.join(current_dir, "restart.bat")
            with open(batch_file, 'w') as f:
                f.write('@echo off\n')
                f.write('timeout /t 2 /nobreak > nul\n')  # Wait 2 seconds
                f.write(f'del "{current_file}"\n')  # Delete old file
                f.write(f'ren "{new_file}" "fnf.pyw"\n')  # Rename new file
                f.write(f'start "" "fnf.pyw"\n')  # Start new file
                f.write('del "%~f0"\n')  # Delete this batch file
            
            self.label.configure(text="Update complete!")
            self.status_label.configure(text="Restarting application...")
            
            # Start the batch file and exit
            subprocess.Popen([batch_file], shell=True)
            self.after(1000, self.destroy)
            
        except Exception as e:
            print(f"Update process error: {e}")
            self.label.configure(text="Starting application...")
            self.after(1000, self.destroy)
        finally:
            # Clean up
            try:
                if update_file and os.path.exists(update_file):
                    os.unlink(update_file)
            except:
                pass

def load_settings():
    settings_path = os.path.join(script_dir, "settings.json")
    default_settings = {
        "dark_mode": True,
        "auto_maximize": False,
        "grid_layout": True,
        "auto_update": None  # None means not set yet
    }
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                return json.load(f)
        except:
            return default_settings
    return default_settings

def save_settings(settings):
    settings_path = os.path.join(script_dir, "settings.json")
    with open(settings_path, "w") as f:
        json.dump(settings, f)

class InitialUpdateDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Auto-Update Preference")
        self.geometry("400x200")
        self.resizable(False, False)
        
        # Make it modal
        self.transient(parent)
        self.grab_set()
        
        # Center the window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        # Add message
        self.label = ctk.CTkLabel(
            self,
            text="Would you like to enable automatic updates?\nThe launcher will check for updates on startup.",
            wraplength=350
        )
        self.label.pack(pady=(30, 20))
        
        # Add buttons
        button_frame = ctk.CTkFrame(self)
        button_frame.pack(pady=20)
        
        def set_auto_update(value):
            settings = load_settings()
            settings["auto_update"] = value
            save_settings(settings)
            self.destroy()
        
        self.yes_button = ctk.CTkButton(
            button_frame,
            text="Yes",
            command=lambda: set_auto_update(True),
            width=100,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2"
        )
        self.yes_button.pack(side="left", padx=10)
        
        self.no_button = ctk.CTkButton(
            button_frame,
            text="No",
            command=lambda: set_auto_update(False),
            width=100,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2"
        )
        self.no_button.pack(side="left", padx=10)

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("400x500")
        self.resizable(False, False)
        
        # Store parent reference
        self.parent = parent
        
        # Load current settings
        self.settings = load_settings()
        self.original_settings = self.settings.copy()
        
        # Theme mode
        self.theme_label = ctk.CTkLabel(self, text="Theme Mode:")
        self.theme_label.pack(pady=(20, 5))
        
        self.theme_var = ctk.StringVar(value="dark" if self.settings["dark_mode"] else "light")
        self.theme_switch = ctk.CTkSwitch(
            self, 
            text="Dark Mode", 
            variable=self.theme_var,
            onvalue="dark",
            offvalue="light",
            command=self.check_changes
        )
        self.theme_switch.pack(pady=5)
        
        # Auto maximize
        self.maximize_label = ctk.CTkLabel(self, text="Game Launch Settings:")
        self.maximize_label.pack(pady=(20, 5))
        
        self.maximize_var = ctk.BooleanVar(value=self.settings["auto_maximize"])
        self.maximize_switch = ctk.CTkSwitch(
            self, 
            text="Auto Maximize Game", 
            variable=self.maximize_var,
            command=self.check_changes
        )
        self.maximize_switch.pack(pady=5)
        
        # Layout
        self.layout_label = ctk.CTkLabel(self, text="Layout Settings:")
        self.layout_label.pack(pady=(20, 5))
        
        self.layout_var = ctk.StringVar(value="grid" if self.settings["grid_layout"] else "list")
        self.layout_option = ctk.CTkOptionMenu(
            self,
            values=["Grid Layout", "List Layout"],
            variable=self.layout_var,
            fg_color="#2a2a2a",
            button_color="#8A2BE2",
            button_hover_color="#9932CC",
            command=self.check_changes
        )
        self.layout_option.pack(pady=5)
        
        # Auto Update
        self.update_label = ctk.CTkLabel(self, text="Update Settings:")
        self.update_label.pack(pady=(20, 5))
        
        self.update_var = ctk.BooleanVar(value=self.settings["auto_update"])
        self.update_switch = ctk.CTkSwitch(
            self, 
            text="Auto Update", 
            variable=self.update_var,
            command=self.check_changes
        )
        self.update_switch.pack(pady=5)
        
        # Spacer
        ctk.CTkLabel(self, text="").pack(pady=20)
        
        # Buttons
        self.apply_button = ctk.CTkButton(
            self,
            text="Apply Changes",
            command=self.apply_changes,
            width=180,
            height=40,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2"
        )
        self.apply_button.pack(side="left", padx=10, pady=20)
        
        self.cancel_button = ctk.CTkButton(
            self,
            text="Cancel",
            command=self.cancel_changes,
            width=180,
            height=40,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2"
        )
        self.cancel_button.pack(side="right", padx=10, pady=20)
        
        # Initially hide buttons
        self.apply_button.pack_forget()
        self.cancel_button.pack_forget()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.cancel_changes)
    
    def check_changes(self, *args):
        # Check if any setting has changed
        has_changes = (
            self.settings["dark_mode"] != (self.theme_var.get() == "dark") or
            self.settings["auto_maximize"] != self.maximize_var.get() or
            self.settings["grid_layout"] != (self.layout_var.get() == "Grid Layout") or
            self.settings["auto_update"] != self.update_var.get()
        )
        
        # Show/hide buttons based on changes
        if has_changes:
            self.apply_button.pack(side="left", padx=10, pady=20)
            self.cancel_button.pack(side="right", padx=10, pady=20)
        else:
            self.apply_button.pack_forget()
            self.cancel_button.pack_forget()
    
    def apply_changes(self):
        # Update settings with current values
        self.settings["dark_mode"] = (self.theme_var.get() == "dark")
        self.settings["auto_maximize"] = self.maximize_var.get()
        self.settings["grid_layout"] = (self.layout_var.get() == "Grid Layout")
        self.settings["auto_update"] = self.update_var.get()
        
        # Save settings
        save_settings(self.settings)
        
        # Restart the application
        self.parent.after(100, self.restart_application)
    
    def cancel_changes(self):
        # Restore original settings
        self.settings = self.original_settings.copy()
        save_settings(self.settings)
        self.destroy()
    
    def restart_application(self):
        # Get the current file path
        current_file = os.path.abspath(__file__)
        
        # Create a batch file to restart the application
        batch_file = os.path.join(os.path.dirname(current_file), "restart_settings.bat")
        with open(batch_file, 'w') as f:
            f.write('@echo off\n')
            f.write('timeout /t 1 /nobreak > nul\n')  # Wait 1 second
            f.write(f'start "" "{current_file}"\n')  # Start the application
            f.write('del "%~f0"\n')  # Delete this batch file
        
        # Start the batch file and exit
        subprocess.Popen([batch_file], shell=True)
        self.parent.destroy()

class Launcher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FNF Launcher")
        self.geometry("740x700")
        self.resizable(False, False)

        # Load settings
        self.settings = load_settings()
        ctk.set_appearance_mode("dark" if self.settings["dark_mode"] else "light")

        self.path = load_path()
        if not os.path.exists(self.path):
            self.ask_path()

        self.folders = get_folders(self.path)
        self.filtered = self.folders.copy()

        # Create top frame for search and settings
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(fill="x", padx=20, pady=(20, 10))

        # Add settings button to top frame
        self.settings_button = ctk.CTkButton(
            self.top_frame,
            text="⚙️",
            width=40,
            height=40,
            command=self.show_settings,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2",
            corner_radius=20
        )
        self.settings_button.pack(side="right", padx=(10, 0))

        # Add search to top frame
        self.search = ctk.CTkEntry(self.top_frame, placeholder_text="Search...", width=700)
        self.search.pack(side="left", fill="x", expand=True)
        self.search.bind("<KeyRelease>", self.update_list)

        self.scroll_frame = ctk.CTkScrollableFrame(self, width=700, height=560)
        self.scroll_frame.pack()

        self.import_button = ctk.CTkButton(
            self, 
            text="Import Mod", 
            corner_radius=20, 
            command=self.show_import_ui, 
            width=700,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2"
        )
        self.import_button.pack(pady=10)

        self.progress = ctk.CTkProgressBar(self, width=700)
        self.progress.set(0)
        self.progress.pack(pady=10)
        self.progress.pack_forget()

        self.icon_cache = {}

        self.update_list()

    def ask_path(self):
        path = filedialog.askdirectory(title="Pick your FNFML folder")
        if path:
            self.path = path
            save_path(path)
        else:
            self.destroy()

    def show_settings(self):
        settings_window = SettingsWindow(self)
        settings_window.grab_set()  # Make the settings window modal

    def update_list(self, event=None):
        query = self.search.get().lower()
        self.filtered = [f for f in self.folders if query in f.lower()]
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if self.settings["grid_layout"]:
            self.update_grid_layout()
        else:
            self.update_list_layout()

    def update_grid_layout(self):
        cols = 3
        row = 0
        col = 0
        for folder in self.filtered:
            full_path = os.path.join(self.path, folder)
            exe_path = find_exe(full_path)

            img = None
            if exe_path:
                if exe_path in self.icon_cache:
                    img = self.icon_cache[exe_path]
                else:
                    pil_icon = get_icon_from_exe(exe_path)
                    if not pil_icon:
                        pil_icon = get_icon_from_ico_folder(full_path)
                    if pil_icon:
                        img = ctk.CTkImage(pil_icon, size=(64, 64))
                        self.icon_cache[exe_path] = img

            frame = ctk.CTkFrame(self.scroll_frame, width=220, height=140, corner_radius=15)
            frame.grid(row=row, column=col, padx=10, pady=10)

            def create_launch_func(f):
                return lambda: self.launch_exe(f)

            btn = ctk.CTkButton(
                frame, 
                image=img, 
                text=folder, 
                width=180, 
                height=90, 
                compound="left", 
                command=create_launch_func(folder),
                fg_color="#2a2a2a",
                hover_color="#8A2BE2",
                corner_radius=15
            )
            btn.pack(side="left", padx=(10,0), pady=10)

            # Create a frame for the buttons
            button_frame = ctk.CTkFrame(frame, fg_color="transparent")
            button_frame.place(relx=1.0, rely=0.0, y=10, anchor="ne")

            def create_delete_func(f):
                return lambda: self.delete_mod(f)

            def create_customize_func(f, b):
                return lambda: self.show_customize_menu(f, b)

            # Add both buttons to the button frame
            edit_btn = ctk.CTkButton(
                button_frame,
                text="✎",
                width=30,
                height=30,
                fg_color="transparent",
                hover_color="#8A2BE2",
                corner_radius=15,
                command=create_customize_func(folder, btn)
            )
            edit_btn.pack(side="right", padx=5)

            del_btn = ctk.CTkButton(
                button_frame,
                text="✕",
                width=30,
                height=30,
                fg_color="transparent",
                hover_color="#8A2BE2",
                corner_radius=15,
                command=create_delete_func(folder)
            )
            del_btn.pack(side="right", padx=5)

            col += 1
            if col >= cols:
                col = 0
                row += 1

    def update_list_layout(self):
        for folder in self.filtered:
            full_path = os.path.join(self.path, folder)
            exe_path = find_exe(full_path)

            img = None
            if exe_path:
                if exe_path in self.icon_cache:
                    img = self.icon_cache[exe_path]
                else:
                    pil_icon = get_icon_from_exe(exe_path)
                    if not pil_icon:
                        pil_icon = get_icon_from_ico_folder(full_path)
                    if pil_icon:
                        img = ctk.CTkImage(pil_icon, size=(32, 32))
                        self.icon_cache[exe_path] = img

            frame = ctk.CTkFrame(self.scroll_frame, width=700, height=50, corner_radius=15)
            frame.pack(padx=10, pady=3, fill="x")

            def create_launch_func(f):
                return lambda: self.launch_exe(f)

            btn = ctk.CTkButton(
                frame, 
                image=img, 
                text=folder, 
                width=600, 
                height=40, 
                compound="left", 
                command=create_launch_func(folder),
                fg_color="#2a2a2a",
                hover_color="#8A2BE2",
                corner_radius=15
            )
            btn.pack(side="left", padx=10, pady=5)

            # Create a frame for the buttons
            button_frame = ctk.CTkFrame(frame, fg_color="transparent")
            button_frame.pack(side="right", padx=10, pady=5)

            def create_delete_func(f):
                return lambda: self.delete_mod(f)

            def create_customize_func(f, b):
                return lambda: self.show_customize_menu(f, b)

            # Add both buttons to the button frame
            edit_btn = ctk.CTkButton(
                button_frame,
                text="✎",
                width=30,
                height=30,
                fg_color="transparent",
                hover_color="#8A2BE2",
                corner_radius=15,
                command=create_customize_func(folder, btn)
            )
            edit_btn.pack(side="right", padx=5)

            del_btn = ctk.CTkButton(
                button_frame,
                text="✕",
                width=30,
                height=30,
                fg_color="transparent",
                hover_color="#8A2BE2",
                corner_radius=15,
                command=create_delete_func(folder)
            )
            del_btn.pack(side="right", padx=5)

    def delete_mod(self, folder):
        full = os.path.join(self.path, folder)
        try:
            shutil.rmtree(full)
        except:
            pass
        self.refresh()

    def show_customize_menu(self, folder, btn):
        menu = ctk.CTkToplevel(self)
        menu.title("Customize Mod")
        menu.geometry("300x250")  # Made taller to accommodate new button
        menu.resizable(False, False)
        
        # Make it modal
        menu.transient(self)
        menu.grab_set()
        
        # Center the window
        menu.update_idletasks()
        width = menu.winfo_width()
        height = menu.winfo_height()
        x = (menu.winfo_screenwidth() // 2) - (width // 2)
        y = (menu.winfo_screenheight() // 2) - (height // 2)
        menu.geometry(f'{width}x{height}+{x}+{y}')
        
        # Store the original icon
        original_img = btn.cget("image")
        selected_icon_path = None
        
        # Check if there's a custom icon
        custom_icon_path = os.path.join(self.path, folder, "custom_icon.png")
        has_custom_icon = os.path.exists(custom_icon_path)
        
        # Rename option
        rename_frame = ctk.CTkFrame(menu)
        rename_frame.pack(fill="x", padx=10, pady=10)
        
        rename_label = ctk.CTkLabel(rename_frame, text="Rename Mod:")
        rename_label.pack(side="left", padx=5)
        
        rename_entry = ctk.CTkEntry(rename_frame, width=150)
        rename_entry.insert(0, folder)
        rename_entry.pack(side="left", padx=5)
        
        # Custom icon option
        icon_frame = ctk.CTkFrame(menu)
        icon_frame.pack(fill="x", padx=10, pady=10)
        
        icon_label = ctk.CTkLabel(icon_frame, text="Custom Icon:")
        icon_label.pack(side="left", padx=5)
        
        def select_icon():
            nonlocal selected_icon_path
            icon_path = filedialog.askopenfilename(
                title="Select Icon",
                filetypes=[("Icon files", "*.ico;*.png;*.jpg;*.jpeg")]
            )
            if icon_path:
                try:
                    # Load and resize the image
                    pil_img = Image.open(icon_path)
                    pil_img = pil_img.resize((32, 32), Image.LANCZOS)
                    new_img = ctk.CTkImage(pil_img, size=(32, 32))
                    btn.configure(image=new_img)
                    selected_icon_path = icon_path
                    remove_btn.pack(side="left", padx=5)  # Show remove button when new icon is selected
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load icon: {str(e)}")
        
        icon_btn = ctk.CTkButton(
            icon_frame,
            text="Select Icon",
            width=100,
            command=select_icon,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2"
        )
        icon_btn.pack(side="left", padx=5)

        def remove_icon():
            nonlocal selected_icon_path
            if os.path.exists(custom_icon_path):
                try:
                    os.remove(custom_icon_path)
                except:
                    pass
            selected_icon_path = None
            btn.configure(image=original_img)
            remove_btn.pack_forget()  # Hide remove button
            self.refresh()
        
        remove_btn = ctk.CTkButton(
            icon_frame,
            text="Remove Icon",
            width=100,
            command=remove_icon,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2"
        )
        if has_custom_icon:
            remove_btn.pack(side="left", padx=5)
        
        # Save button
        def save_changes():
            # Handle rename
            new_name = rename_entry.get().strip()
            if new_name and new_name != folder:
                old_path = os.path.join(self.path, folder)
                new_path = os.path.join(self.path, new_name)
                try:
                    os.rename(old_path, new_path)
                    folder = new_name  # Update folder name for icon saving
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to rename: {str(e)}")
                    return
            
            # Handle icon change
            if selected_icon_path:
                try:
                    pil_img = Image.open(selected_icon_path)
                    pil_img = pil_img.resize((32, 32), Image.LANCZOS)
                    icon_dest = os.path.join(self.path, folder, "custom_icon.png")
                    pil_img.save(icon_dest)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save icon: {str(e)}")
                    return
            
            self.refresh()
            menu.destroy()
        
        def on_close():
            # Restore original icon if changes weren't saved
            if selected_icon_path:
                btn.configure(image=original_img)
            menu.destroy()
        
        save_btn = ctk.CTkButton(
            menu,
            text="Save Changes",
            command=save_changes,
            width=200,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2"
        )
        save_btn.pack(pady=20)
        
        # Handle window close
        menu.protocol("WM_DELETE_WINDOW", on_close)

    def launch_exe(self, folder):
        full_path = os.path.join(self.path, folder)
        exe = find_exe(full_path)
        if not exe:
            print("no exe found")
            return

        # Create startup info for maximize if enabled
        startupinfo = None
        if self.settings["auto_maximize"]:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_MAXIMIZE

        subprocess.Popen([exe], cwd=os.path.dirname(exe), startupinfo=startupinfo)
        self.destroy()

    def refresh(self):
        self.folders = get_folders(self.path)
        self.update_list()

    def show_import_ui(self):
        for widget in self.winfo_children():
            widget.pack_forget()

        self.import_label = ctk.CTkLabel(self, text="Enter Mod Name (leave empty to keep original):")
        self.import_label.pack(pady=(250, 10))

        self.import_name_entry = ctk.CTkEntry(self, width=400)
        self.import_name_entry.pack(pady=(0, 20))
        self.import_name_entry.bind("<Return>", self.import_name_entered)
        self.import_name_entry.focus()

        # Create buttons but don't show them yet
        self.import_zip_btn = ctk.CTkButton(
            self, 
            text="Import from ZIP", 
            width=400, 
            command=self.import_zip,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2",
            corner_radius=15
        )
        self.import_folder_btn = ctk.CTkButton(
            self, 
            text="Import from Folder", 
            width=400, 
            command=self.import_folder,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2",
            corner_radius=15
        )
        self.import_gb_btn = ctk.CTkButton(
            self, 
            text="Import from Gamebanana Link", 
            width=400, 
            command=self.import_gamebanana,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2",
            corner_radius=15
        )
        self.import_link_btn = ctk.CTkButton(
            self, 
            text="Import from Link", 
            width=400, 
            command=self.import_from_link,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2",
            corner_radius=15
        )

    def import_name_entered(self, event=None):
        mod_name = self.import_name_entry.get().strip()
        self.mod_name = mod_name if mod_name else None

        self.import_label.pack_forget()
        self.import_name_entry.pack_forget()

        # Show the buttons
        self.import_zip_btn.pack(pady=20)
        self.import_folder_btn.pack(pady=20)
        self.import_gb_btn.pack(pady=20)
        self.import_link_btn.pack(pady=20)

    def show_progress(self, message, progress=0):
        self.progress_label.configure(text=message)
        self.progress.set(progress)

    def import_zip(self):
        zip_paths = filedialog.askopenfilenames(
            title="Select Mod Archives",
            filetypes=[("Archive files", "*.zip;*.rar;*.7z")]
        )
        if not zip_paths:
            self.show_normal_ui()
            return

        self.progress.set(0)
        self.progress.pack()
        self.progress_label = ctk.CTkLabel(self, text="")
        self.progress_label.pack(pady=(0, 5))
        self.import_button.configure(state="disabled")

        threading.Thread(target=self.process_multiple_archives, args=(zip_paths,), daemon=True).start()

    def import_folder(self):
        folder_paths = filedialog.askdirectory(
            title="Select Mod Folders",
            mustexist=True
        )
        if not folder_paths:
            self.show_normal_ui()
            return

        self.progress.set(0)
        self.progress.pack()
        self.progress_label = ctk.CTkLabel(self, text="")
        self.progress_label.pack(pady=(0, 5))
        self.import_button.configure(state="disabled")

        threading.Thread(target=self.process_multiple_folders, args=([folder_paths],), daemon=True).start()

    def process_multiple_archives(self, archive_paths):
        temp_dir = os.path.join(script_dir, "_temp_import")
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            total_archives = len(archive_paths)
            for i, archive_path in enumerate(archive_paths):
                try:
                    self.after(0, lambda p=i/total_archives: self.show_progress(f"Processing archive {i+1}/{total_archives}: {os.path.basename(archive_path)}", p))
                    
                    # Extract archive
                    try:
                        self.extract_archive(archive_path, temp_dir)
                    except Exception as e:
                        self.after(0, lambda: self.show_error(f"Failed to extract {os.path.basename(archive_path)}: {str(e)}"))
                        continue

                    # Find game folder
                    if any(file.endswith('.exe') for file in os.listdir(temp_dir)):
                        game_folder = temp_dir
                    else:
                        game_folder = self.find_game_folder(temp_dir)

                    if not game_folder:
                        self.after(0, lambda: self.show_error(f"No executable found in {os.path.basename(archive_path)}!"))
                        continue

                    # Generate destination name
                    base_name = os.path.splitext(os.path.basename(archive_path))[0]
                    dest_name = self.mod_name if self.mod_name else base_name
                    if i > 0:  # Add number suffix for multiple archives
                        dest_name = f"{dest_name}_{i+1}"
                    dest_path = os.path.join(self.path, dest_name)

                    if os.path.exists(dest_path):
                        shutil.rmtree(dest_path)

                    # Create destination directory
                    os.makedirs(dest_path, exist_ok=True)

                    # Copy files
                    total_files = len(os.listdir(game_folder))
                    for j, item in enumerate(os.listdir(game_folder)):
                        s = os.path.join(game_folder, item)
                        d = os.path.join(dest_path, item)
                        self.after(0, lambda p=(i + j/total_files)/total_archives: 
                            self.show_progress(f"Copying files from {os.path.basename(archive_path)}: {item}", p))
                        if os.path.isdir(s):
                            shutil.copytree(s, d)
                        else:
                            os.makedirs(os.path.dirname(d), exist_ok=True)
                            shutil.copy2(s, d)

                except Exception as e:
                    self.after(0, lambda: self.show_error(f"Error processing {os.path.basename(archive_path)}: {str(e)}"))
                    continue

            self.after(0, self.refresh)
        except Exception as e:
            self.after(0, lambda: self.show_error(f"Error importing mods: {str(e)}"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.after(0, self.finish_import_ui)

    def process_multiple_folders(self, folder_paths):
        try:
            total_folders = len(folder_paths)
            for i, folder_path in enumerate(folder_paths):
                try:
                    self.after(0, lambda p=i/total_folders: self.show_progress(f"Processing folder {i+1}/{total_folders}: {os.path.basename(folder_path)}", p))

                    # Find game folder
                    if any(file.endswith('.exe') for file in os.listdir(folder_path)):
                        game_folder = folder_path
                    else:
                        game_folder = self.find_game_folder(folder_path)

                    if not game_folder:
                        self.after(0, lambda: self.show_error(f"No executable found in {os.path.basename(folder_path)}!"))
                        continue

                    # Generate destination name
                    base_name = os.path.basename(folder_path)
                    dest_name = self.mod_name if self.mod_name else base_name
                    if i > 0:  # Add number suffix for multiple folders
                        dest_name = f"{dest_name}_{i+1}"
                    dest_path = os.path.join(self.path, dest_name)

                    if os.path.exists(dest_path):
                        shutil.rmtree(dest_path)

                    # Create destination directory
                    os.makedirs(dest_path, exist_ok=True)

                    # Copy files
                    total_files = len(os.listdir(game_folder))
                    for j, item in enumerate(os.listdir(game_folder)):
                        s = os.path.join(game_folder, item)
                        d = os.path.join(dest_path, item)
                        self.after(0, lambda p=(i + j/total_files)/total_folders: 
                            self.show_progress(f"Copying files from {os.path.basename(folder_path)}: {item}", p))
                        if os.path.isdir(s):
                            shutil.copytree(s, d)
                        else:
                            os.makedirs(os.path.dirname(d), exist_ok=True)
                            shutil.copy2(s, d)

                except Exception as e:
                    self.after(0, lambda: self.show_error(f"Error processing {os.path.basename(folder_path)}: {str(e)}"))
                    continue

            self.after(0, self.refresh)
        except Exception as e:
            self.after(0, lambda: self.show_error(f"Error importing mods: {str(e)}"))
        finally:
            self.after(0, self.finish_import_ui)

    def finish_import_ui(self):
        self.progress.pack_forget()
        self.progress.set(0)
        if hasattr(self, 'progress_label'):
            self.progress_label.pack_forget()
        self.import_button.configure(state="normal")
        self.show_normal_ui()

    def show_normal_ui(self):
        for widget in self.winfo_children():
            widget.pack_forget()
        self.search.pack(pady=(20, 10))
        self.scroll_frame.pack()
        self.import_button = ctk.CTkButton(
            self, 
            text="Import Mod", 
            corner_radius=20, 
            command=self.show_import_ui, 
            width=700,
            fg_color="#2a2a2a",
            hover_color="#8A2BE2"
        )
        self.import_button.pack(pady=10)

    def import_from_link(self):
        url = ctk.CTkInputDialog(text="Paste the direct download link here:", title="Import from Link").get_input()
        if not url:
            self.show_normal_ui()
            return

        self.progress.set(0)
        self.progress.pack()
        self.import_button.configure(state="disabled")

        threading.Thread(target=self.download_and_extract_link, args=(url,), daemon=True).start()

    def download_and_extract_link(self, url):
        temp_dir = os.path.join(script_dir, "_temp_link")
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            # Get the file extension from the URL
            ext = os.path.splitext(url.split('?')[0])[1].lower()
            if ext not in ['.zip', '.rar', '.7z']:
                ext = '.zip'  # Default to zip if no extension found

            archive_path = os.path.join(temp_dir, f"mod{ext}")

            # Download the file
            r = requests.get(url, stream=True)
            if r.status_code != 200:
                self.show_error(f"Failed to download file (status {r.status_code})")
                self.after(0, self.finish_import_ui)
                return

            total_length = r.headers.get('content-length')
            if total_length is None:
                total_length = 0
            else:
                total_length = int(total_length)

            downloaded = 0
            with open(archive_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_length > 0:
                            progress_val = downloaded / total_length
                            self.after(0, self.progress.set, progress_val)

            try:
                self.extract_archive(archive_path, temp_dir)
            except FileNotFoundError as e:
                if "7z.exe not found" in str(e):
                    self.show_error("7-Zip is required to extract .rar files. Please install 7-Zip from https://www.7-zip.org/")
                else:
                    self.show_error(f"Failed to extract archive: {str(e)}")
                return
            except Exception as e:
                self.show_error(f"Failed to extract archive: {str(e)}")
                return

            # First check if the temp directory itself has an exe
            if any(file.endswith('.exe') for file in os.listdir(temp_dir)):
                game_folder = temp_dir
            else:
                # If not, search in subfolders
                game_folder = self.find_game_folder(temp_dir)

            if not game_folder:
                self.show_error("No executable found in the downloaded mod!")
                return

            dest_name = self.mod_name if hasattr(self, "mod_name") and self.mod_name else f"mod_{int(time.time())}"
            dest_path = os.path.join(self.path, dest_name)
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)

            # Create the destination directory
            os.makedirs(dest_path, exist_ok=True)

            # Copy only the contents of the game folder
            for item in os.listdir(game_folder):
                s = os.path.join(game_folder, item)
                d = os.path.join(dest_path, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d)
                else:
                    # Ensure the parent directory exists
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copy2(s, d)

            self.refresh()
        except Exception as e:
            self.show_error(f"Error downloading or extracting mod:\n{e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.after(0, self.finish_import_ui)

    def find_game_folder(self, path):
        print(f"Searching in: {path}")  # Debug print
        # Check if current folder has an exe
        if any(file.endswith('.exe') for file in os.listdir(path)):
            print(f"Found exe in: {path}")  # Debug print
            return path
        
        # Check subfolders
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                result = self.find_game_folder(item_path)
                if result:
                    return result
        return None

    def import_gamebanana(self):
        url = ctk.CTkInputDialog(text="Paste your Gamebanana mod link here:", title="Gamebanana Import").get_input()
        if not url:
            self.show_normal_ui()
            return

        mod_id, file_id = self.extract_ids(url)
        if not file_id and not mod_id:
            ctk.CTkMessagebox(title="Error", message="Invalid Gamebanana link!", icon="cancel").show()
            self.show_normal_ui()
            return

        if not file_id:
            file_id = mod_id

        self.progress.set(0)
        self.progress.pack()
        self.import_button.configure(state="disabled")

        threading.Thread(target=self.download_and_extract_gb, args=(file_id,), daemon=True).start()

    def extract_ids(self, url):
        m = re.search(r"#FileInfo_(\d+)", url)
        if m:
            return None, m.group(1)
        m2 = re.search(r"/mods/(\d+)", url)
        if m2:
            return m2.group(1), None
        return None, None

    def download_and_extract_gb(self, file_id):
        download_url = f"https://gamebanana.com/dl/{file_id}"
        temp_dir = os.path.join(script_dir, "_temp_gb")
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)

            r = requests.get(download_url, stream=True)
            if r.status_code != 200:
                self.show_error(f"Failed to download mod file (status {r.status_code})")
                self.after(0, self.finish_import_ui)
                return

            total_length = r.headers.get('content-length')
            if total_length is None:
                total_length = 0
            else:
                total_length = int(total_length)

            # Determine file extension from Content-Disposition header or default to .zip
            content_disposition = r.headers.get('Content-Disposition', '')
            ext = '.zip'
            if '.rar' in content_disposition.lower():
                ext = '.rar'
            elif '.7z' in content_disposition.lower():
                ext = '.7z'

            archive_path = os.path.join(temp_dir, f"mod{ext}")
            downloaded = 0
            with open(archive_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_length > 0:
                            progress_val = downloaded / total_length
                            self.after(0, self.progress.set, progress_val)

            try:
                self.extract_archive(archive_path, temp_dir)
            except FileNotFoundError as e:
                if "7z.exe not found" in str(e):
                    self.show_error("7-Zip is required to extract .rar files. Please install 7-Zip from https://www.7-zip.org/")
                else:
                    self.show_error(f"Failed to extract archive: {str(e)}")
                return
            except Exception as e:
                self.show_error(f"Failed to extract archive: {str(e)}")
                return

            # First check if the temp directory itself has an exe
            if any(file.endswith('.exe') for file in os.listdir(temp_dir)):
                game_folder = temp_dir
            else:
                # If not, search in subfolders
                game_folder = self.find_game_folder(temp_dir)

            if not game_folder:
                self.show_error("No executable found in the downloaded mod!")
                return

            dest_name = self.mod_name if hasattr(self, "mod_name") and self.mod_name else f"mod_{file_id}"
            dest_path = os.path.join(self.path, dest_name)
            if os.path.exists(dest_path):
                shutil.rmtree(dest_path)

            # Create the destination directory
            os.makedirs(dest_path, exist_ok=True)

            # Copy only the contents of the game folder
            for item in os.listdir(game_folder):
                s = os.path.join(game_folder, item)
                d = os.path.join(dest_path, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d)
                else:
                    # Ensure the parent directory exists
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copy2(s, d)

            self.refresh()
        except Exception as e:
            self.show_error(f"Error downloading or extracting mod:\n{e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.after(0, self.finish_import_ui)

    def show_error(self, msg):
        messagebox.showerror("Error", msg)

    def extract_archive(self, archive_path, extract_to):
        try:
            if archive_path.lower().endswith('.zip'):
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    # Check if the zip is valid
                    if zip_ref.testzip() is not None:
                        raise zipfile.BadZipFile("Invalid or corrupted ZIP file")
                    
                    # Get the list of files
                    file_list = zip_ref.namelist()
                    
                    # Check if the zip is empty
                    if not file_list:
                        raise ValueError("ZIP file is empty")
                    
                    # Extract all files
                    zip_ref.extractall(extract_to)
                    
            elif archive_path.lower().endswith('.rar'):
                # Path to 7z.exe (update if needed)
                sevenzip_path = r"C:\Program Files\7-Zip\7z.exe"
                if not os.path.exists(sevenzip_path):
                    raise FileNotFoundError("7z.exe not found! Please install 7-Zip and update the path.")
                
                # Use CREATE_NO_WINDOW to hide the console window
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                # Run 7z with error checking
                result = subprocess.run(
                    [sevenzip_path, 'x', '-y', f'-o{extract_to}', archive_path],
                    check=True,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    capture_output=True,
                    text=True
                )
                
                if "Error" in result.stdout or "Error" in result.stderr:
                    raise Exception(f"7-Zip extraction failed: {result.stdout}\n{result.stderr}")
                
            elif archive_path.lower().endswith('.7z'):
                try:
                    import py7zr
                    with py7zr.SevenZipFile(archive_path, mode='r') as sz:
                        # Check if the archive is valid
                        if not sz.test():
                            raise py7zr.Bad7zFile("Invalid or corrupted 7z file")
                        sz.extractall(extract_to)
                except ImportError:
                    # Fallback to 7z.exe if py7zr is not available
                    sevenzip_path = r"C:\Program Files\7-Zip\7z.exe"
                    if not os.path.exists(sevenzip_path):
                        raise FileNotFoundError("7z.exe not found! Please install 7-Zip and update the path.")
                    
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    
                    result = subprocess.run(
                        [sevenzip_path, 'x', '-y', f'-o{extract_to}', archive_path],
                        check=True,
                        startupinfo=startupinfo,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        capture_output=True,
                        text=True
                    )
                    
                    if "Error" in result.stdout or "Error" in result.stderr:
                        raise Exception(f"7-Zip extraction failed: {result.stdout}\n{result.stderr}")
            else:
                raise ValueError("Unsupported archive format")
            
            # Verify extraction
            if not os.listdir(extract_to):
                raise ValueError("Archive extraction resulted in empty directory")
                
        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid or corrupted ZIP file: {str(e)}")
        except zipfile.LargeZipFile as e:
            raise ValueError(f"ZIP file is too large: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to extract archive: {str(e)}")

def main():
    # Check for updates before starting the main application
    update_window = UpdateWindow()
    
    # Check if auto-update preference is set
    settings = load_settings()
    if settings["auto_update"] is None:
        # Show initial dialog
        dialog = InitialUpdateDialog(update_window)
        dialog.wait_window()
        # Reload settings after dialog
        settings = load_settings()
    
    # Only check for updates if auto-update is enabled
    if settings["auto_update"]:
        update_window.start_update()
        update_window.mainloop()
    else:
        update_window.destroy()
    
    # Start the main application
    app = Launcher()
    app.mainloop()

if __name__ == "__main__":
    main()

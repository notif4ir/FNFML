# testing the update thing

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

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, "launcher_config.json")

# Add the Scripts directory to PATH if not already present
scripts_dir = os.path.join(sys.prefix, 'Scripts')
if scripts_dir not in os.environ['PATH']:
    os.environ['PATH'] = scripts_dir + os.pathsep + os.environ['PATH']

# GitHub repository information
GITHUB_REPO = "your-username/FNFML"  # Replace with your actual GitHub repo
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"
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

        import ctypes.wintypes

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
    except Exception:
        return None

def get_icon_from_ico_folder(path, size=(64,64)):
    for file in os.listdir(path):
        if file.lower().endswith(".ico"):
            try:
                img = Image.open(os.path.join(path, file)).convert("RGBA")
                img = img.resize(size, Image.LANCZOS)
                return img
            except:
                continue
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
        # Get the latest release info from GitHub
        response = requests.get(f"{GITHUB_API_URL}/releases/latest", timeout=5)  # Add timeout
        if response.status_code != 200:
            print("Could not reach GitHub, skipping update check")
            return None
        
        latest_version = response.json()["tag_name"]
        current_version = "1.0.0"  # Replace with your current version
        
        if latest_version > current_version:
            return latest_version
        return None
    except (requests.RequestException, Exception) as e:
        print(f"Error checking for updates: {e}")
        return None

def download_update(version, progress_callback):
    """Download the latest version"""
    try:
        # Get the download URL for the latest release
        response = requests.get(f"{GITHUB_API_URL}/releases/latest")
        if response.status_code != 200:
            raise Exception("Failed to get release info")
        
        download_url = response.json()["assets"][0]["browser_download_url"]
        
        # Download the file
        response = requests.get(download_url, stream=True)
        if response.status_code != 200:
            raise Exception("Failed to download update")
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024
        downloaded = 0
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
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
            self.label.configure(text=f"Downloading version {latest_version}...")
            def update_progress(progress):
                self.after(0, self.progress.set, progress)
            
            update_file = download_update(latest_version, update_progress)
            if not update_file:
                self.label.configure(text="Starting application...")
                self.after(1000, self.destroy)
                return
            
            # Extract update
            self.label.configure(text="Installing update...")
            self.progress.set(0)
            
            # Get current file path
            current_file = os.path.abspath(__file__)
            current_dir = os.path.dirname(current_file)
            
            # Create a temporary directory for extraction
            temp_extract_dir = os.path.join(current_dir, "_temp_update")
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir)
            os.makedirs(temp_extract_dir)
            
            try:
                # Extract the update to temp directory
                with zipfile.ZipFile(update_file, 'r') as zip_ref:
                    total_files = len(zip_ref.namelist())
                    for i, file in enumerate(zip_ref.namelist()):
                        zip_ref.extract(file, temp_extract_dir)
                        self.after(0, self.progress.set, (i + 1) / total_files)
                
                # Find the new Python file in the extracted files
                new_py_file = None
                for root, _, files in os.walk(temp_extract_dir):
                    for file in files:
                        if file.endswith('.pyw') or file.endswith('.py'):
                            new_py_file = os.path.join(root, file)
                            break
                    if new_py_file:
                        break
                
                if not new_py_file:
                    raise Exception("Could not find Python file in update")
                
                # Create a new file with a different name
                new_file = os.path.join(current_dir, "fnf_new.pyw")
                
                # Copy the new file
                shutil.copy2(new_py_file, new_file)
                
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
                
            finally:
                # Clean up
                try:
                    os.unlink(update_file)
                    shutil.rmtree(temp_extract_dir)
                except:
                    pass
            
        except Exception as e:
            print(f"Update process error: {e}")
            self.label.configure(text="Starting application...")
            self.after(1000, self.destroy)

class Launcher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FNF Launcher")
        self.geometry("740x700")
        self.resizable(False, False)

        self.path = load_path()
        if not os.path.exists(self.path):
            self.ask_path()

        self.folders = get_folders(self.path)
        self.filtered = self.folders.copy()

        self.search = ctk.CTkEntry(self, placeholder_text="Search...", width=700)
        self.search.pack(pady=(20, 10))
        self.search.bind("<KeyRelease>", self.update_list)

        self.scroll_frame = ctk.CTkScrollableFrame(self, width=700, height=560)
        self.scroll_frame.pack()

        self.import_button = ctk.CTkButton(self, text="Import Mod", corner_radius=20, command=self.show_import_ui, width=700)
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

    def update_list(self, event=None):
        query = self.search.get().lower()
        self.filtered = [f for f in self.folders if query in f.lower()]
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

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

            def launch_func(f=folder):
                self.launch_exe(f)

            btn = ctk.CTkButton(
                frame, 
                image=img, 
                text=folder, 
                width=180, 
                height=90, 
                compound="left", 
                command=launch_func,
                fg_color="#2a2a2a",
                hover_color="#8A2BE2",
                corner_radius=15
            )
            btn.pack(side="left", padx=(10,0), pady=10)

            def delete_mod(f=folder):
                full = os.path.join(self.path, f)
                try:
                    shutil.rmtree(full)
                except:
                    pass
                self.refresh()

            del_btn = ctk.CTkButton(
                frame,
                text="✕",
                width=30,
                height=30,
                fg_color="#2a2a2a",
                hover_color="#8A2BE2",
                corner_radius=15,
                command=delete_mod
            )
            del_btn.place(relx=1.0, rely=0.0, y=10, anchor="ne")

            col += 1
            if col >= cols:
                col = 0
                row += 1

    def launch_exe(self, folder):
        full_path = os.path.join(self.path, folder)
        exe = find_exe(full_path)
        if not exe:
            print("no exe found")
            return

        subprocess.Popen([exe], cwd=os.path.dirname(exe))
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

    def import_name_entered(self, event=None):
        mod_name = self.import_name_entry.get().strip()
        self.mod_name = mod_name if mod_name else None

        self.import_label.pack_forget()
        self.import_name_entry.pack_forget()

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

        self.import_zip_btn.pack(pady=20)
        self.import_folder_btn.pack(pady=20)
        self.import_gb_btn.pack(pady=20)

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

    def import_folder(self):
        folder_path = filedialog.askdirectory()
        if not folder_path:
            self.show_normal_ui()
            return

        self.progress.set(0)
        self.progress.pack()
        self.import_button.configure(state="disabled")

        def do_import():
            try:
                print(f"Selected folder: {folder_path}")
                print(f"Files in folder: {os.listdir(folder_path)}")

                # First check if the selected folder itself has an exe
                if any(file.endswith('.exe') for file in os.listdir(folder_path)):
                    print("Found exe in root folder")
                    game_folder = folder_path
                else:
                    print("No exe in root, searching subfolders")
                    game_folder = self.find_game_folder(folder_path)

                print(f"Game folder found: {game_folder}")

                if not game_folder:
                    self.after(0, lambda: self.show_error("No executable found in the selected folder or its subfolders!"))
                    self.after(0, self.finish_import_ui)
                    return

                dest_name = self.mod_name if self.mod_name else os.path.basename(game_folder)
                dest_path = os.path.join(self.path, dest_name)

                print(f"Destination path: {dest_path}")

                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)

                # Create the destination directory
                os.makedirs(dest_path, exist_ok=True)

                # Copy only the contents of the game folder
                total_files = len(os.listdir(game_folder))
                for i, item in enumerate(os.listdir(game_folder)):
                    s = os.path.join(game_folder, item)
                    d = os.path.join(dest_path, item)
                    print(f"Copying: {s} -> {d}")
                    if os.path.isdir(s):
                        shutil.copytree(s, d)
                    else:
                        # Ensure the parent directory exists
                        os.makedirs(os.path.dirname(d), exist_ok=True)
                        shutil.copy2(s, d)
                    # Update progress
                    self.after(0, lambda p=i/total_files: self.progress.set(p))

                self.after(0, self.refresh)
            except Exception as e:
                self.after(0, lambda: self.show_error(f"Error importing mod:\n{e}"))
            finally:
                self.after(0, self.finish_import_ui)

        threading.Thread(target=do_import, daemon=True).start()

    def import_zip(self):
        zip_path = filedialog.askopenfilename(filetypes=[("Archive files", "*.zip;*.rar;*.7z")])
        if not zip_path:
            self.show_normal_ui()
            return

        self.progress.set(0)
        self.progress.pack()
        self.import_button.configure(state="disabled")

        def do_import():
            temp_dir = os.path.join(script_dir, "_temp_import")
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                os.makedirs(temp_dir)

                self.extract_archive(zip_path, temp_dir)

                # First check if the temp directory itself has an exe
                if any(file.endswith('.exe') for file in os.listdir(temp_dir)):
                    game_folder = temp_dir
                else:
                    # If not, search in subfolders
                    game_folder = self.find_game_folder(temp_dir)

                if not game_folder:
                    self.after(0, lambda: self.show_error("No executable found in the archive!"))
                    return

                dest_name = self.mod_name if self.mod_name else os.path.basename(game_folder)
                dest_path = os.path.join(self.path, dest_name)
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)

                # Create the destination directory
                os.makedirs(dest_path, exist_ok=True)

                # Copy only the contents of the game folder
                total_files = len(os.listdir(game_folder))
                for i, item in enumerate(os.listdir(game_folder)):
                    s = os.path.join(game_folder, item)
                    d = os.path.join(dest_path, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d)
                    else:
                        # Ensure the parent directory exists
                        os.makedirs(os.path.dirname(d), exist_ok=True)
                        shutil.copy2(s, d)
                    # Update progress
                    self.after(0, lambda p=i/total_files: self.progress.set(p))

                self.after(0, self.refresh)
            except Exception as e:
                self.after(0, lambda: self.show_error(f"Error importing mod:\n{e}"))
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.after(0, self.finish_import_ui)

        threading.Thread(target=do_import, daemon=True).start()

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

    def finish_import_ui(self):
        self.progress.pack_forget()
        self.progress.set(0)
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

    def import_mod(self):
        file_path = filedialog.askopenfilename(title="Select Mod Archive", filetypes=[("Archive files", "*.zip;*.rar;*.7z")])
        if not file_path:
            return
        mod_name = os.path.splitext(os.path.basename(file_path))[0]
        mod_path = os.path.join(self.path, mod_name)
        if os.path.exists(mod_path):
            if not messagebox.askyesno("Mod already exists", f"Mod {mod_name} already exists. Overwrite?"):
                return
            shutil.rmtree(mod_path)
        os.makedirs(mod_path)
        try:
            self.extract_archive(file_path, mod_path)
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import mod: {str(e)}")
            if os.path.exists(mod_path):
                shutil.rmtree(mod_path)

    def extract_archive(self, archive_path, extract_to):
        if archive_path.lower().endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
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
            subprocess.run([sevenzip_path, 'x', '-y', f'-o{extract_to}', archive_path], 
                         check=True, 
                         startupinfo=startupinfo,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        elif archive_path.lower().endswith('.7z'):
            import py7zr
            with py7zr.SevenZipFile(archive_path, mode='r') as sz:
                sz.extractall(extract_to)
        else:
            raise ValueError("Unsupported archive format")

def main():
    # Check for updates before starting the main application
    update_window = UpdateWindow()
    update_window.start_update()
    update_window.mainloop()
    
    # Start the main application
    app = Launcher()
    app.mainloop()

if __name__ == "__main__":
    main()

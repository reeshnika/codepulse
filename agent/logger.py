"""
CodePulse Keystroke Logger
Captures developer keystrokes and computes dwell/flight timing metrics.
Filters activity strictly to active coding windows, detects copy-paste actions,
and identifies active programming languages.
"""

import sys
import time
import json
import logging
import platform
from datetime import datetime
from pynput import keyboard

# Graceful import for pygetwindow
try:
    import pygetwindow as gw
except ImportError:
    gw = None
    print("⚠️  pygetwindow not installed. Window filtering fallback active.")

# Safe terminal output encoding with unbuffered line output
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

logger = logging.getLogger(__name__)

CODING_APPS = [
    # Desktop IDEs
    'visual studio code', 'vs code', 'code - oss', 'code-insiders', 'vscodium',
    'cursor', 'windsurf', 'zed',
    'pycharm', 'intellij', 'idea', 'webstorm', 'phpstorm', 'rubymine',
    'clion', 'rider', 'datagrip', 'fleet',
    'sublime text', 'atom', 'eclipse', 'netbeans', 'bluej',
    'notepad++', 'notepad', 'textmate', 'gedit', 'kate',
    'vim', 'neovim', 'emacs', 'nano', 'micro',
    'android studio', 'xcode', 'qt creator', 'code::blocks', 'dev-c++',
    'jupyter', 'jupyterlab', 'rstudio', 'spyder', 'thonny', 'idle', 'idlex',
    
    # Web coding platforms
    'codeforces', 'hackerrank', 'codechef', 'leetcode', 'geeksforgeeks',
    'hackerearth', 'topcoder', 'atcoder', 'codewars', 'exercism',
    'codepen', 'jsfiddle', 'codesandbox', 'stackblitz', 'replit', 'repl.it',
    'colab', 'google colab', 'kaggle', 'gitpod', 'glitch',
    'codesignal', 'coderbyte', 'interviewbit', 'codingame',
    'programiz', 'w3schools', 'tutorialspoint', 'sololearn', 'codedamn',
    'freecodecamp', 'codier', 'frontend mentor',
    'cses', 'spoj', 'usaco', 'kattis', 'vjudge',
    
    # Terminals & shells
    'windows terminal', 'powershell', 'cmd', 'bash', 'zsh',
    'git bash', 'wsl', 'ubuntu', 'debian',
    
    # LMS
    'moodle', 'canvas', 'blackboard', 'coursera', 'udemy',
    'udacity', 'edx', 'khan academy'
]

CODE_EXTENSIONS = (
    # Python
    '.py', '.pyw', '.pyi', '.ipynb',
    # Java / Kotlin / Scala
    '.java', '.kt', '.kts', '.scala', '.groovy',
    # C / C++ / C#
    '.c', '.h', '.cpp', '.cc', '.cxx', '.hpp', '.hxx', '.cs',
    # Web
    '.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx', '.vue', '.svelte',
    '.html', '.htm', '.css', '.scss', '.sass', '.less',
    # Other languages
    '.go', '.rs', '.rb', '.php', '.swift', '.m', '.mm', '.dart',
    '.lua', '.r', '.pl', '.ex', '.exs', '.erl', '.hs', '.clj', '.fs',
    # Data & config
    '.sql', '.sh', '.bash', '.zsh', '.ps1', '.bat',
    '.json', '.xml', '.yaml', '.yml', '.toml', '.ini',
    '.md', '.rst', '.tex'
)

LANG_MAP = {
    # File extensions
    '.py': 'python', '.pyw': 'python', '.pyi': 'python', '.ipynb': 'python',
    '.java': 'java',
    '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp', '.hxx': 'cpp',
    '.c': 'c', '.h': 'c',
    '.cs': 'csharp',
    '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript',
    '.vue': 'vue', '.svelte': 'svelte',
    '.go': 'go',
    '.rs': 'rust',
    '.rb': 'ruby',
    '.php': 'php',
    '.kt': 'kotlin', '.kts': 'kotlin',
    '.swift': 'swift',
    '.m': 'objective-c', '.mm': 'objective-c',
    '.html': 'html', '.htm': 'html',
    '.css': 'css', '.scss': 'scss', '.sass': 'sass', '.less': 'less',
    '.sql': 'sql',
    '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash', '.ps1': 'powershell', '.bat': 'batch',
    '.r': 'r',
    '.scala': 'scala', '.groovy': 'groovy',
    '.dart': 'dart',
    '.lua': 'lua',
    '.zig': 'zig',
    '.json': 'json',
    '.yaml': 'yaml', '.yml': 'yaml',
    '.xml': 'xml',
    '.toml': 'toml', '.ini': 'ini',
    '.md': 'markdown', '.rst': 'rst', '.tex': 'latex',

    # Menu-based IDEs language mapping
    'bluej': 'java',
    'netbeans': 'java',
    'eclipse': 'java',
    'dev-c++': 'cpp',
    'codeblocks': 'cpp',
    'code::blocks': 'cpp',
    'qt creator': 'cpp',
    'clion': 'cpp',
    'rider': 'csharp',
    'android studio': 'kotlin',
    'xcode': 'swift',
}

PLATFORM_MAP = {
    'codeforces': 'competitive',
    'hackerrank': 'competitive',
    'leetcode': 'competitive',
    'codechef': 'competitive',
    'geeksforgeeks': 'competitive',
    'hackerearth': 'competitive',
    'topcoder': 'competitive',
    'atcoder': 'competitive',
    'cses': 'competitive',
    'spoj': 'competitive',
    'usaco': 'competitive',
    'kattis': 'competitive',
    'vjudge': 'competitive',
}

IDE_MAP = {
    'pycharm': 'python',
    'clion': 'cpp',
    'intellij': 'java',
    'idea': 'java',
    'webstorm': 'javascript',
    'phpstorm': 'php',
    'rubymine': 'ruby',
    'rider': 'csharp',
    'datagrip': 'sql',
    'android studio': 'kotlin',
    'xcode': 'swift',
    'bluej': 'java',
    'netbeans': 'java',
    'eclipse': 'java',
    'dev-c++': 'cpp',
    'codeblocks': 'cpp',
    'code::blocks': 'cpp',
    'qt creator': 'cpp',
    'notepad': 'notepad',
}


def get_active_window_title():
    """Returns active window title - uses multiple fallback methods"""
    # Method 1: pygetwindow
    try:
        if gw is not None:
            try:
                active = gw.getActiveWindow()
                if active is not None:
                    title = active.title
                    if title and title.strip():
                        return title.strip()
            except Exception as e:
                pass
    except Exception:
        pass
    
    # Method 2: Windows ctypes (more reliable)
    if platform.system() == 'Windows':
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if title and title.strip():
                        return title.strip()
                
                # Fallback: get window class name
                class_buff = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_buff, 256)
                class_name = class_buff.value
                if class_name:
                    return f"[class:{class_name}]"
        except Exception as e:
            pass
    
    # Method 3: Check for common process names
    if platform.system() == 'Windows':
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            # Try to get process name
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
            if handle:
                try:
                    buff = ctypes.create_unicode_buffer(260)
                    size = ctypes.c_ulong(260)
                    if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buff, ctypes.byref(size)):
                        full_path = buff.value
                        process_name = full_path.split('\\')[-1].lower()
                        return f"[process:{process_name}]"
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass
    
    return ""


def is_coding_app_active():
    """Returns True if a coding app is active - checks title AND process name"""
    try:
        title = ""
        process_name = ""
        
        # Get window title
        if gw is not None:
            try:
                active = gw.getActiveWindow()
                if active is not None and active.title:
                    title = active.title.lower()
            except Exception:
                pass
        
        # Get via ctypes
        if platform.system() == 'Windows':
            try:
                import ctypes
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                
                # Get title
                if not title:
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.lower()
                
                # Get process name
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
                if handle:
                    try:
                        buff = ctypes.create_unicode_buffer(260)
                        size = ctypes.c_ulong(260)
                        if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buff, ctypes.byref(size)):
                            process_name = buff.value.split('\\')[-1].lower()
                    finally:
                        ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                pass
        
        # Combine title and process name for detection
        combined = f"{title} {process_name}"
        
        if not combined.strip():
            return False  # nothing detected → don't log
        
        # Process name mapping (more reliable than title)
        PROCESS_TO_APP = {
            'code.exe': 'vs code',
            'code - insiders.exe': 'vs code',
            'cursor.exe': 'cursor',
            'windsurf.exe': 'windsurf',
            'pycharm64.exe': 'pycharm',
            'pycharm.exe': 'pycharm',
            'idea64.exe': 'intellij',
            'idea.exe': 'intellij',
            'clion64.exe': 'clion',
            'webstorm64.exe': 'webstorm',
            'notepad.exe': 'notepad',
            'notepad++.exe': 'notepad++',
            'sublime_text.exe': 'sublime',
            'atom.exe': 'atom',
            'eclipse.exe': 'eclipse',
            'devenv.exe': 'visual studio',
            'gvim.exe': 'vim',
            'nvim-qt.exe': 'neovim',
            'emacs.exe': 'emacs',
            'qtcreator.exe': 'qt creator',
            'androidstudio64.exe': 'android studio',
            'studio64.exe': 'android studio',
            'chrome.exe': 'chrome',
            'msedge.exe': 'edge',
            'firefox.exe': 'firefox',
            'brave.exe': 'brave',
            'opera.exe': 'opera',
            'whatsapp.exe': 'whatsapp',
            'telegram.exe': 'telegram',
            'discord.exe': 'discord',
            'spotify.exe': 'spotify',
            'vlc.exe': 'vlc',
            'explorer.exe': 'explorer',
        }
        
        # Check process name first
        for proc, app_name in PROCESS_TO_APP.items():
            if process_name == proc:
                # Found process
                if app_name in ('whatsapp', 'telegram', 'discord', 'spotify', 'vlc', 'explorer'):
                    return False  # explicitly excluded
                if app_name in ('chrome', 'edge', 'firefox', 'brave', 'opera'):
                    # Browser - only allow if coding site in title
                    coding_sites = ['leetcode', 'codeforces', 'hackerrank', 'codechef', 
                                   'github', 'geeksforgeeks', 'hackerearth', 'topcoder',
                                   'atcoder', 'cses', 'spoj', 'usaco', 'kattis', 'vjudge',
                                   'codepen', 'replit', 'colab', 'jupyter', 'gitpod',
                                   'stackblitz', 'codesandbox', 'kaggle']
                    return any(site in title for site in coding_sites)
                return True  # it's a coding app
        
        # Fallback: check title
        coding_keywords = [
            'visual studio code', 'vs code', 'code - oss', 'vscodium',
            'cursor', 'windsurf', 'zed',
            'pycharm', 'intellij', 'webstorm', 'phpstorm', 'rubymine',
            'clion', 'rider', 'datagrip', 'fleet',
            'sublime text', 'atom', 'eclipse', 'netbeans', 'bluej',
            'notepad++', 'notepad', 'textmate', 'gedit', 'kate',
            'vim', 'neovim', 'emacs', 'nano',
            'android studio', 'xcode', 'qt creator', 'code::blocks', 'dev-c++',
            'jupyter', 'jupyterlab', 'rstudio', 'spyder', 'thonny', 'idle',
            'codeforces', 'hackerrank', 'codechef', 'leetcode', 'geeksforgeeks',
            'hackerearth', 'topcoder', 'atcoder', 'codewars',
            'codepen', 'jsfiddle', 'codesandbox', 'stackblitz', 'replit',
            'colab', 'kaggle', 'gitpod',
            'powershell', 'cmd', 'bash', 'git bash', 'windows terminal',
            'moodle', 'canvas', 'blackboard', 'coursera', 'udemy', 'edx'
        ]
        
        for keyword in coding_keywords:
            if keyword in title:
                return True
        
        # File extension check
        import re
        code_ext = re.compile(r'\.(py|java|c|cpp|cc|cxx|h|hpp|js|jsx|ts|tsx|go|rs|rb|php|cs|kt|swift|html|css|sql|sh|json|xml|yaml|yml|md)\b')
        if code_ext.search(title):
            return True
        
        # Explicitly excluded apps
        excluded = ['whatsapp', 'telegram', 'spotify', 'discord', 'netflix', 'youtube', 'vlc']
        for ex in excluded:
            if ex in title:
                return False
        
        return False  # default to NOT coding (safer)
        
    except Exception as e:
        return False


def get_active_language(title=None):
    """Detects language, handles untitled VS Code files"""
    try:
        if title is None:
            raw_title = get_active_window_title()
            title = raw_title.lower() if raw_title else ""
        else:
            title = title.lower()

        if not title:
            return 'unknown'

        # Handle Untitled files
        if 'untitled' in title:
            if 'visual studio code' in title or 'vs code' in title or 'code' in title:
                return 'vscode_untitled'
            elif 'notepad' in title:
                return 'notepad_untitled'

        # Handle Visual Studio (not VS Code)
        if 'microsoft visual studio' in title and 'code' not in title:
            return 'visual_studio'

        # Check extensions first (longer extensions first so .cpp matches before .c)
        for ext in sorted(LANG_MAP.keys(), key=len, reverse=True):
            if ext in title:
                return LANG_MAP[ext]

        # Check platforms first
        for plat, lang in PLATFORM_MAP.items():
            if plat in title:
                return lang

        # VS Code without saved file
        if 'visual studio code' in title or 'vs code' in title or 'code - oss' in title or title == 'code':
            return 'vscode'

        # IDE name → language mapping
        ide_lang = {
            'pycharm': 'python',
            'clion': 'cpp',
            'intellij': 'java',
            'idea': 'java',
            'webstorm': 'javascript',
            'phpstorm': 'php',
            'rubymine': 'ruby',
            'rider': 'csharp',
            'datagrip': 'sql',
            'android studio': 'kotlin',
            'xcode': 'swift',
            'bluej': 'java',
            'netbeans': 'java',
            'eclipse': 'java',
            'dev-c++': 'cpp',
            'code::blocks': 'cpp',
            'qt creator': 'cpp'
        }
        for ide, lang in ide_lang.items():
            if ide in title:
                return lang

        # Check IDE names from IDE_MAP
        for ide, lang in IDE_MAP.items():
            if ide in title:
                return lang

        return 'unknown'
    except Exception:
        return 'unknown'


class KeystrokeLogger:
    """Captures keyboard interactions and calculates real-time typing dynamics."""

    def __init__(self, session_id=None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.keystrokes = []
        self.copy_paste_events = []
        self.ctrl_pressed = False
        self.last_active_state = None
        self.is_logging = False
        self.listener = None
        self._last_key_press_time = {}   # key -> timestamp of last press
        self._last_press_time = None       # timestamp of the most recent key press
        self._start_time = None
        self._last_logged_window = None
        self._pressed_keys = set()

    def get_active_language(self):
        """Detects programming language from active window title"""
        return get_active_language()

    def _normalize_key(self, key):
        """Converts pynput Key / KeyCode to a readable string."""
        try:
            if hasattr(key, 'char') and key.char is not None:
                return key.char
            elif hasattr(key, 'name') and key.name is not None:
                return f"Key.{key.name}"
            else:
                return str(key).replace("'", "")
        except Exception:
            return str(key)

    def on_press(self, key):
        """Callback executed on every key press event."""
        # 1. Check if coding app window is focused
        if not is_coding_app_active():
            return

        raw_title = get_active_window_title() or "Unknown"
        if getattr(self, '_last_logged_window', None) != raw_title:
            self._last_logged_window = raw_title
            current_lang = get_active_language(raw_title)
            print(f"🔍 Detected: '{raw_title}' → {current_lang}")

        now = time.time()
        key_char = self._normalize_key(key)

        # Track pressed keys
        if not hasattr(self, '_pressed_keys'):
            self._pressed_keys = set()
        self._pressed_keys.add(key)
        if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            self._pressed_keys.add(keyboard.Key.shift)

        # 2. Detect Ctrl key press
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = True

        # 3. Detect Copy / Paste
        # Also detect: Ctrl+Insert (copy), Shift+Insert (paste), and Ctrl+Shift+V
        is_insert_key = (key == keyboard.Key.insert) or (key_char.lower() in ('insert', 'key.insert'))
        shift_pressed = (keyboard.Key.shift in self._pressed_keys) or any(k in self._pressed_keys for k in (keyboard.Key.shift_l, keyboard.Key.shift_r))

        is_insert_copy = self.ctrl_pressed and (key_char.lower() in ('insert', 'key.insert') or key == keyboard.Key.insert)
        is_insert_paste = shift_pressed and (key_char.lower() in ('insert', 'key.insert') or key == keyboard.Key.insert)
        is_paste_with_format = self.ctrl_pressed and shift_pressed and (key_char.lower() == 'v' or key_char == '\x16')

        is_copy = (self.ctrl_pressed and (key_char.lower() == 'c' or key_char == '\x03')) or is_insert_copy
        is_paste = (self.ctrl_pressed and (key_char.lower() == 'v' or key_char == '\x16')) or is_insert_paste or is_paste_with_format

        if is_copy:
            self.copy_paste_events.append({
                'type': 'copy',
                'timestamp': now,
                'session_id': self.session_id
            })
            print("📋 Copy detected")

        if is_paste:
            self.copy_paste_events.append({
                'type': 'paste',
                'timestamp': now,
                'session_id': self.session_id
            })
            print("📥 Paste detected")

        # 4. Calculate flight_time: time elapsed since previous key press
        if self._last_press_time is not None:
            flight_time = max(0.0, round(now - self._last_press_time, 4))
        else:
            flight_time = 0.0

        # Calculate dwell_time: time since this specific key was last pressed
        if key_char in self._last_key_press_time:
            dwell_time = max(0.0, round(now - self._last_key_press_time[key_char], 4))
        else:
            dwell_time = 0.0

        event = {
            'type': 'press',
            'key': key_char,
            'timestamp': now,
            'dwell_time': dwell_time,
            'flight_time': flight_time,
            'language': self.get_active_language(),
            'session_id': self.session_id
        }

        self.keystrokes.append(event)
        self._last_press_time = now
        self._last_key_press_time[key_char] = now

        # Print debug info every 100 keystrokes
        if len(self.keystrokes) % 100 == 0 and len(self.keystrokes) > 0:
            active_title = get_active_window_title() or 'Unknown'
            print(f"🔍 Active: {active_title[:60]} | Lang: {get_active_language(active_title)}")

        # Stop listening when ESC is pressed
        if key == keyboard.Key.esc:
            print("\n[ESC] pressed. Terminating logger...")
            self.stop_logging()
            return False

    def on_release(self, key):
        """Callback executed on key release."""
        if hasattr(self, '_pressed_keys'):
            self._pressed_keys.discard(key)
            if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                self._pressed_keys.discard(keyboard.Key.shift)

        # Release Ctrl key
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            self.ctrl_pressed = False

        if not is_coding_app_active():
            return

        now = time.time()
        key_char = self._normalize_key(key)

        # Release dwell time: duration between press and release for this key
        press_time = self._last_key_press_time.get(key_char, now)
        dwell_duration = max(0.0, round(now - press_time, 4))

        event = {
            'type': 'release',
            'key': key_char,
            'timestamp': now,
            'dwell_time': dwell_duration,
            'flight_time': 0.0,
            'language': self.get_active_language(),
            'session_id': self.session_id
        }

        self.keystrokes.append(event)

    def get_copy_paste_stats(self):
        """Returns copy-paste statistics"""
        copies = sum(1 for e in self.copy_paste_events if e['type'] == 'copy')
        pastes = sum(1 for e in self.copy_paste_events if e['type'] == 'paste')
        return {
            'total_copy': copies,
            'total_paste': pastes,
            'events': self.copy_paste_events,
            'is_suspicious': pastes > 3
        }

    def get_recent_copy_paste(self, seconds=60):
        """
        Returns copy and paste counts within the last `seconds` seconds.
        Returns: {'recent_copies': X, 'recent_pastes': Y}
        """
        cutoff = time.time() - seconds
        recent_copies = sum(
            1 for e in self.copy_paste_events
            if e.get('type') == 'copy' and e.get('timestamp', 0) >= cutoff
        )
        recent_pastes = sum(
            1 for e in self.copy_paste_events
            if e.get('type') == 'paste' and e.get('timestamp', 0) >= cutoff
        )
        return {
            'recent_copies': recent_copies,
            'recent_pastes': recent_pastes
        }

    def get_recent_paste_count(self, seconds=30):
        """Returns number of paste events in last N seconds"""
        cutoff = time.time() - seconds
        return sum(1 for e in self.copy_paste_events 
                   if e.get('type') == 'paste' and e.get('timestamp', 0) >= cutoff)

    def get_recent_copy_count(self, seconds=30):
        """Returns number of copy events in last N seconds"""
        cutoff = time.time() - seconds
        return sum(1 for e in self.copy_paste_events 
                   if e.get('type') == 'copy' and e.get('timestamp', 0) >= cutoff)

    def get_language_stats(self):
        """Returns keystroke counts per language"""
        stats = {}
        for event in self.keystrokes:
            lang = event.get('language', 'unknown')
            if lang != 'unknown':
                stats[lang] = stats.get(lang, 0) + 1
        return stats

    def start_logging(self):
        """Starts pynput keyboard Listener."""
        self.is_logging = True
        self._start_time = time.time()
        print(f"🔴 Keystroke logging active — Session: {self.session_id}")
        print("🎯 Active app filter: Coding apps only")
        print("Press ESC at any time to finish session.\n")

        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )
        self.listener.start()

        if not hasattr(self, '_last_debug_time'):
            self._last_debug_time = 0

        try:
            while self.is_logging and self.listener.is_alive():
                time.sleep(0.1)
                if time.time() - self._last_debug_time > 20:
                    try:
                        title = get_active_window_title()
                        is_coding = is_coding_app_active()
                        status = "✅ CODING" if is_coding else "❌ IGNORED"
                        print(f"🔍 Window: '{title[:60]}' | {status}")
                    except Exception:
                        pass
                    self._last_debug_time = time.time()
        except KeyboardInterrupt:
            print("\nInterrupted by user.")
            self.stop_logging()
        finally:
            if self.listener and self.listener.is_alive():
                self.listener.stop()

    def stop_logging(self):
        """Stops listener and flushes keystrokes to disk."""
        if not self.is_logging and not self.keystrokes and not self.copy_paste_events:
            return

        self.is_logging = False
        if self.listener and self.listener.is_alive():
            try:
                self.listener.stop()
            except Exception:
                pass

        print(f"\n⏹️ Stopped. {len(self.keystrokes)} keystroke events captured.")
        self.save_data()

    def save_data(self):
        """Saves captured keystrokes, language stats, and copy_paste_stats to keystrokes_<session_id>.json."""
        if not self.keystrokes and not self.copy_paste_events:
            return

        filename = f"keystrokes_{self.session_id}.json"
        data_payload = {
            'session_id': self.session_id,
            'keystrokes': self.keystrokes,
            'copy_paste_stats': self.get_copy_paste_stats(),
            'language_stats': self.get_language_stats()
        }
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data_payload, f, indent=2)
            print(f"💾 Saved session JSON to: {filename}")
        except Exception as e:
            logger.error(f"Error saving data to {filename}: {e}")
            print(f"⚠️ Failed to save {filename}: {e}")

    def get_stats(self):
        """
        Returns full statistics including flight times:
        {total_events, presses, releases, flight_times, avg_flight_time, session_duration}
        """
        if not self.keystrokes:
            return {
                'total_events': 0,
                'presses': 0,
                'releases': 0,
                'flight_times': [],
                'avg_flight_time': 0.0,
                'avg_dwell_time': 0.08,
                'session_duration': 0.0
            }

        presses = [k for k in self.keystrokes if k.get('type') == 'press']
        releases = [k for k in self.keystrokes if k.get('type') == 'release']

        flight_times = []
        for i in range(1, len(presses)):
            ft = presses[i].get('flight_time', 0.0)
            if ft > 0:
                flight_times.append(round(ft, 4))

        dwell_times = [p.get('dwell_time', 0.0) for p in presses if p.get('dwell_time', 0.0) > 0]
        avg_dwell_time = round(sum(dwell_times) / len(dwell_times), 4) if dwell_times else 0.08

        avg_flight_time = round(sum(flight_times) / len(flight_times), 4) if flight_times else 0.0

        if len(self.keystrokes) > 1:
            session_duration = round(self.keystrokes[-1]['timestamp'] - self.keystrokes[0]['timestamp'], 2)
        elif self._start_time:
            session_duration = round(time.time() - self._start_time, 2)
        else:
            session_duration = 0.0

        return {
            'total_events': len(self.keystrokes),
            'presses': len(presses),
            'releases': len(releases),
            'flight_times': flight_times,
            'avg_flight_time': avg_flight_time,
            'avg_dwell_time': avg_dwell_time,
            'session_duration': session_duration
        }

    def get_backspace_count(self):
        """Counts how many times Backspace was pressed during session."""
        backspace_keys = {'Key.backspace', 'Backspace', '\x08', '\b'}
        count = 0
        for event in self.keystrokes:
            if event.get('type') == 'press' and event.get('key') in backspace_keys:
                count += 1
        return count

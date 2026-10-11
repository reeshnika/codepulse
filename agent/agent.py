"""
CodePulse Agent - Real-Time Developer Intelligence Data Collector
Collects developer keystrokes, calculates flow scores, tracks code evolution in VS Code,
extracts behavioral fingerprints, and sends metrics to backend dashboard.
"""

import os
import sys
import time
import json
import logging
import threading
import statistics
from datetime import datetime

# Safe terminal encoding on Windows with unbuffered line output
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

# Ensure project root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logger = logging.getLogger(__name__)

# Resilient HTTP Client: Requests with urllib fallback
try:
    import requests
except ImportError:
    import urllib.request
    import urllib.error
    import json as _json

    class _Response:
        def __init__(self, status_code, content):
            self.status_code = status_code
            self._content = content

        def json(self):
            try:
                return _json.loads(self._content.decode('utf-8'))
            except Exception:
                return {}

    class _RequestsFallback:
        class exceptions:
            class ConnectionError(Exception):
                pass

        @staticmethod
        def post(url, json=None, timeout=5):
            data = _json.dumps(json).encode('utf-8') if json is not None else None
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return _Response(resp.getcode(), resp.read())
            except urllib.error.URLError as e:
                raise _RequestsFallback.exceptions.ConnectionError(e)

        @staticmethod
        def get(url, timeout=2):
            req = urllib.request.Request(url)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return _Response(resp.getcode(), resp.read())
            except urllib.error.URLError as e:
                raise _RequestsFallback.exceptions.ConnectionError(e)

    requests = _RequestsFallback()

# Import Agent Components
try:
    from agent.logger import KeystrokeLogger
    from agent.flow_score import FlowScoreCalculator
    from agent.code_tracker import CodeTracker
    from agent.fingerprint import DeveloperFingerprinter
except ImportError:
    try:
        from logger import KeystrokeLogger
        from flow_score import FlowScoreCalculator
        from code_tracker import CodeTracker
        from fingerprint import DeveloperFingerprinter
    except ImportError as e:
        print(f"⚠️ Could not import agent modules: {e}")
        print("   Current directory:", os.getcwd())
        sys.exit(1)

# Optional window inspection
try:
    import pygetwindow as gw
except ImportError:
    gw = None


def _get_active_window_title():
    """Helper to detect the active window title."""
    try:
        from agent.logger import get_active_window_title
        return get_active_window_title()
    except Exception:
        return ""


class CodePulseAgent:
    """Agent that captures developer telemetry and reports to the CodePulse dashboard."""

    def __init__(self, dashboard_url='http://localhost:5000'):
        self.dashboard_url = dashboard_url.rstrip('/')
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logger = KeystrokeLogger(session_id=self.session_id)
        self.flow_calculator = FlowScoreCalculator()
        self.code_tracker = CodeTracker(session_id=self.session_id)
        self.fingerprinter = DeveloperFingerprinter()
        self.is_running = False
        self.send_interval = 10  # Transmit metrics every 10 seconds
        self._last_known_code = ""

    def read_active_file(self):
        """
        Uses pygetwindow.getActiveWindow() (or ctypes fallback).
        If title contains a code file extension (.py, .java, .c, .cpp, .js),
        tries to read the file contents if full path can be extracted from title.
        Fallback: returns empty string. Uses try/except.
        """
        try:
            code_extensions = ('.py', '.java', '.c', '.cpp', '.js')
            title = _get_active_window_title()

            if not title:
                return ""

            title_lower = title.lower()
            has_ext = any(ext in title_lower for ext in code_extensions)
            if not has_ext:
                return ""

            # Attempt to resolve file path from window title
            candidate_code = ""
            parts = title.split(' - ')
            if parts:
                filename = parts[0].strip(' ●*')
                # If full path directly in title
                if os.path.isabs(filename) and os.path.isfile(filename):
                    try:
                        with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                            candidate_code = f.read()
                    except Exception:
                        pass
                else:
                    # Search in workspace root
                    for root, dirs, files in os.walk(PROJECT_ROOT):
                        dirs[:] = [d for d in dirs if d not in ('venv', '.venv', '.git', '__pycache__', 'node_modules')]
                        if filename in files:
                            full_path = os.path.join(root, filename)
                            try:
                                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    candidate_code = f.read()
                                break
                            except Exception:
                                pass

            # Fallback: clipboard if available via ctypes (Windows)
            if not candidate_code:
                try:
                    import ctypes
                    if ctypes.windll.user32.OpenClipboard(0):
                        try:
                            h_clip_mem = ctypes.windll.user32.GetClipboardData(13)
                            if h_clip_mem:
                                p_clip_mem = ctypes.windll.kernel32.GlobalLock(h_clip_mem)
                                if p_clip_mem:
                                    clip_text = ctypes.c_wchar_p(p_clip_mem).value
                                    ctypes.windll.kernel32.GlobalUnlock(h_clip_mem)
                                    if clip_text and len(clip_text.strip()) > 0:
                                        candidate_code = clip_text
                        finally:
                            ctypes.windll.user32.CloseClipboard()
                except Exception:
                    pass

            if candidate_code:
                self._last_known_code = candidate_code
                return candidate_code

            return self._last_known_code or ""
        except Exception:
            return ""

    def send_heartbeat(self):
        """Sends lightweight heartbeat ping to dashboard so status displays green LIVE."""
        try:
            requests.post(
                f"{self.dashboard_url}/api/agent/heartbeat",
                json={'session_id': self.session_id},
                timeout=3
            )
        except Exception:
            pass

    def start(self):
        """Starts keyboard capture and telemetry reporting loop."""
        print("""
        ============================================================
          🚀 CODEPULSE AGENT
          Developer Intelligence Data Collector

          📡 Sending data to: {}
          🔑 Session ID:      {}
          🎯 Only tracking keystrokes in coding apps (VS Code, Codeforces, HackerRank)

          Press ESC to stop logging
        ============================================================
        """.format(self.dashboard_url, self.session_id))

        self.is_running = True
        self.logger.is_logging = True

        # Launch keystroke logger in daemon background thread
        log_thread = threading.Thread(target=self.logger.start_logging)
        log_thread.daemon = True
        log_thread.start()

        # Send initial registration & heartbeat on start
        self.send_heartbeat()
        try:
            self.send_data(force=True)
        except Exception:
            pass

        # Main loop: send heartbeat every 3s, update code tracker every 3s, send data every 10s
        last_send_time = time.time()
        last_report_time = time.time()
        try:
            while self.is_running:
                time.sleep(3)
                self.send_heartbeat()

                now = time.time()
                # Print in terminal every 30 seconds
                if now - last_report_time >= 30:
                    last_report_time = now
                    from agent.logger import get_active_window_title, get_active_language, is_coding_app_active, CODING_APPS
                    curr_title = get_active_window_title() or 'Unknown'
                    if is_coding_app_active():
                        title_lower = curr_title.lower()
                        app_name = next((app for app in CODING_APPS if app in title_lower), 'coding app')
                        detected_str = app_name
                    else:
                        detected_str = 'IGNORED'
                    curr_lang = get_active_language(curr_title)
                    print(f"🔍 Active: '{curr_title[:60]}' | Detected: {detected_str} | Lang: {curr_lang}")

                # Feature 4: In main loop (every 3 seconds), call self.code_tracker.update_code(...)
                try:
                    code_content = self.read_active_file()
                    if code_content:
                        self.code_tracker.update_code(code_content)
                except Exception as tracker_err:
                    logger.debug(f"Code tracker update error: {tracker_err}")

                if now - last_send_time >= self.send_interval:
                    self.send_data(force=True)
                    last_send_time = now

        except KeyboardInterrupt:
            print("\n🛑 Stopping agent...")
        finally:
            self.stop()

    def send_data(self, force=False):
        """Processes buffer stats, computes flow score, extracts fingerprint, and POSTs to dashboard."""
        try:
            stats = self.logger.get_stats()
            total_keys = stats.get('presses', 0)

            # Edge case: If session has 0 keystrokes, DO NOT send data (prevents Flow Score 0 pollution)
            if total_keys == 0:
                now = time.time()
                current_window = _get_active_window_title() or "Unknown"
                last_win = getattr(self, '_last_warn_win', None)
                last_time = getattr(self, '_last_warn_time', 0)
                if current_window != last_win or (now - last_time >= 60):
                    self._last_warn_time = now
                    self._last_warn_win = current_window
                    print(f"ℹ️  Monitoring for coding activity... Active window: '{current_window}'")
                return

            self.send_heartbeat()
            copy_paste_stats = self.logger.get_copy_paste_stats()
            language_stats = self.logger.get_language_stats()
            code_stats = self.code_tracker.get_evolution_stats()
            session_duration = stats.get('session_duration', 0.0)

            # 1. Typing speed (WPM) using active typing time ONLY
            flight_times = stats.get('flight_times', [])
            # Cap each flight time at 2.0 seconds — anything longer is a break, not typing
            capped_flight_times = [min(ft, 2.0) for ft in flight_times if ft > 0]
            active_time_sum = sum(capped_flight_times) if capped_flight_times else 0.0

            # Better WPM calculation using capped time
            if total_keys > 0 and active_time_sum >= 1.0:
                wpm = (total_keys / 5.0) / (active_time_sum / 60.0)
                wpm = min(120.0, max(0.0, wpm))
            else:
                wpm = 0.0

            stats['active_time_seconds'] = active_time_sum
            stats['active_time'] = active_time_sum
            stats['idle_time_seconds'] = max(0.0, session_duration - active_time_sum)
            stats['wpm'] = wpm

            # Debug info (remove in production)
            print(f"   [DEBUG] total_keys={total_keys}, active_time={active_time_sum:.2f}s, session={session_duration:.2f}s, wpm={wpm:.1f}")

            # 2. Backspace error rate
            backspaces = self.logger.get_backspace_count()
            backspace_rate = backspaces / total_keys if total_keys > 0 else 0.0
            stats['backspace_rate'] = backspace_rate

            # 3. Average pause between keystrokes
            avg_pause = (sum(flight_times) / len(flight_times)) if flight_times else 0.5
            stats['avg_pause'] = avg_pause

            # 4. Standard deviation of flight times (consistency metric)
            if len(flight_times) > 1:
                std_dev_flight_time = statistics.stdev(flight_times)
            else:
                std_dev_flight_time = 0.0

            # 5. Recent copy-paste metrics & real-time penalty (last 30s)
            recent_pastes_30s = self.logger.get_recent_paste_count(30)
            recent_copies_30s = self.logger.get_recent_copy_count(30)

            # Determine paste penalty (30-second window)
            paste_penalty_30s = 0
            if recent_pastes_30s >= 8:
                paste_penalty_30s = 60  # Massive penalty
            elif recent_pastes_30s >= 5:
                paste_penalty_30s = 45
            elif recent_pastes_30s >= 3:
                paste_penalty_30s = 30
            elif recent_pastes_30s >= 1:
                paste_penalty_30s = 15

            # 6. Code evolution clarity metric
            recent_edit_distance = code_stats.get('recent_edit_distance', code_stats.get('avg_edit_distance', 0))
            code_complexity = min(100.0, max(10.0, 40.0 + code_stats.get('total_changes', 0) * 10.0))
            edit_consistency = min(1.0, max(0.2, float(code_stats.get('avg_similarity', 0.8))))

            # 7. AI generation detection
            ai_check = self.flow_calculator.detect_ai_generated(stats, code_stats)
            ai_score = ai_check.get('ai_score', 0.0)

            # 8. Compute Flow Score with real dynamics, code quality & recent keystrokes
            session_data = {
                'typing_speed': wpm,
                'backspace_rate': backspace_rate,
                'avg_pause': avg_pause,
                'code_complexity': code_complexity,
                'edit_consistency': edit_consistency,
                'recent_edit_distance': recent_edit_distance,
                'std_dev_flight_time': std_dev_flight_time,
                'recent_keystrokes': self.logger.keystrokes[-200:],   # NEW
                'ai_score': ai_score
            }
            flow_result = self.flow_calculator.calculate_flow_score(session_data)

            # Apply hard paste penalty (30-second window)
            if paste_penalty_30s > 0:
                original_score = flow_result['score']
                flow_result['score'] = max(0.0, original_score - paste_penalty_30s)
                flow_result['state'] = self.flow_calculator._classify_state(flow_result['score'])

                # Override suggestion
                if paste_penalty_30s >= 45:
                    flow_result['suggestion'] = f'🚨 HEAVY copy-paste detected! Penalty: -{paste_penalty_30s}'
                    flow_result['state'] = 'AI_ASSISTED'
                elif paste_penalty_30s >= 30:
                    flow_result['suggestion'] = f'⚠️ Copy-paste detected! Penalty: -{paste_penalty_30s}'
                else:
                    flow_result['suggestion'] = f'📋 Minor copy-paste. Penalty: -{paste_penalty_30s}'

                flow_result['ai_penalty_applied'] = True
                flow_result['paste_penalty'] = paste_penalty_30s
            else:
                flow_result['paste_penalty'] = 0

            # Feature 5: Developer Fingerprinting
            features = self.fingerprinter.extract_features(stats, code_stats, logger_instance=self.logger)
            fingerprint = self.fingerprinter.generate_fingerprint(features)

            # Build submission payload
            payload = {
                'session_id': self.session_id,
                'user_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'keystroke_stats': stats,
                'copy_paste_stats': copy_paste_stats,
                'language_stats': language_stats,
                'code_stats': code_stats,
                'flow_score': flow_result,
                'paste_penalty': paste_penalty_30s,
                'fingerprint': fingerprint,
                'features': features,
                'keystrokes_sample': self.logger.keystrokes[-20:] if self.logger.keystrokes else []
            }

            # Dispatch to dashboard
            try:
                response = requests.post(
                    f"{self.dashboard_url}/api/submit",
                    json=payload,
                    timeout=5
                )

                if response.status_code in (200, 201):
                    current_time_str = datetime.now().strftime('%H:%M:%S')
                    active_lang = self.logger.get_active_language()
                    comps = flow_result['components']

                    print(f"✅ Data sent at {current_time_str}")
                    print(f"   📊 Flow Score: {flow_result['score']:.1f} ({flow_result['state']})")
                    print(f"   └─ Speed:{comps['speed']:.0f} Acc:{comps['accuracy']:.0f} Foc:{comps['focus']:.0f} Code:{comps.get('code_quality', 0):.0f}")
                    print(f"   ⌨️  Keystrokes: {total_keys}")
                    print(f"   ⏱️  Session: {session_duration:.1f}s (active: {active_time_sum:.1f}s)")
                    print(f"   📝 WPM: {wpm:.1f}")
                    print(f"   🔄 Backspace: {backspace_rate * 100:.1f}%")
                    print(f"   🌐 Language: {active_lang}")
                    if paste_penalty_30s > 0:
                        print(f"   🚨 COPY-PASTE PENALTY: -{paste_penalty_30s} points")
                        print(f"   📋 Last 30s: {recent_copies_30s} copies, {recent_pastes_30s} pastes")
                    elif flow_result.get('ai_penalty_applied', False):
                        print("   ⚠️  AI penalty applied!")

                    # Active window debug every 3 sends
                    if not hasattr(self, '_debug_counter'):
                        self._debug_counter = 0
                    self._debug_counter += 1
                    if self._debug_counter % 3 == 0:
                        try:
                            from agent.logger import get_active_window_title, get_active_language, is_coding_app_active
                            current_title = get_active_window_title() or 'Unknown'
                            is_coding = is_coding_app_active()
                            status = "✅ CODING" if is_coding else "❌ IGNORED"
                            print(f"   🔍 Window: '{current_title[:50]}' | {status} | Lang: {get_active_language()}")
                        except Exception as e:
                            print(f"   🔍 Debug error: {e}")

                    print("   ─────────────────────────────")
                else:
                    print(f"⚠️ Dashboard response: {response.status_code}")

            except requests.exceptions.ConnectionError:
                print("❌ Dashboard not reachable! Ensure server is running: python backend/app.py")
            except Exception as req_err:
                print(f"❌ Error sending data: {req_err}")

        except Exception as e:
            print(f"❌ Error preparing telemetry: {e}")

    def stop(self):
        """Stops logger, saves code snapshots, flushes keystrokes, and pushes final telemetry."""
        if not self.is_running:
            return
        self.is_running = False
        self.logger.stop_logging()
        self.code_tracker.save_snapshots()

        # Transmit final telemetry snapshot if events exist
        if self.logger.keystrokes or self.logger.copy_paste_events:
            self.send_data()

        print("\n🛑 Agent stopped successfully.")


def main():
    """Main execution entrypoint."""
    dashboard_url = 'http://localhost:5000'

    # Check dashboard connectivity
    try:
        response = requests.get(f"{dashboard_url}/api/health", timeout=2)
        if response.status_code != 200:
            print("⚠️ Dashboard responded with an unexpected status.")
            print(f"   Ensure it is running at: {dashboard_url}")
    except Exception:
        print("⚠️ Dashboard is not running!")
        print("   Please start it first: python backend/app.py")
        print("   Then run this agent again.")
        return

    agent = CodePulseAgent(dashboard_url=dashboard_url)
    agent.start()


if __name__ == "__main__":
    main()

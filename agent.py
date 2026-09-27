"""
CodePulse Agent - Collects data and sends to dashboard
"""

try:
    import requests
except ImportError:
    import urllib.request
    import urllib.error
    import json as _json_module

    class _Response:
        def __init__(self, status_code, content):
            self.status_code = status_code
            self._content = content

        def json(self):
            try:
                return _json_module.loads(self._content.decode('utf-8'))
            except Exception:
                return {}

    class _Exceptions:
        class ConnectionError(Exception):
            pass

    class requests:  # simple shim for basic get/post used by this agent
        exceptions = _Exceptions

        @staticmethod
        def post(url, json=None, timeout=5):
            data = None
            if json is not None:
                data = _json_module.dumps(json).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    content = resp.read()
                    return _Response(resp.getcode(), content)
            except urllib.error.URLError as e:
                raise _Exceptions.ConnectionError(e)

        @staticmethod
        def get(url, timeout=2):
            req = urllib.request.Request(url)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    content = resp.read()
                    return _Response(resp.getcode(), content)
            except urllib.error.URLError as e:
                raise _Exceptions.ConnectionError(e)

import json
import time
import threading
from datetime import datetime
import os
import sys

# Try to import local modules
try:
    from data_collector.logger import KeystrokeLogger
    from analyzer.flow_score import FlowScoreCalculator
except ImportError as e:
    print(f"⚠️ Could not import modules: {e}")
    print("   Make sure you're in the right directory.")
    print("   Current directory:", os.getcwd())
    print("   Expected: C:\\codepulse\\codepulse")
    sys.exit(1)

class CodePulseAgent:
    """Agent that collects data and sends to dashboard"""
    
    def __init__(self, dashboard_url='http://localhost:5000'):
        self.dashboard_url = dashboard_url
        self.logger = KeystrokeLogger()
        self.flow_calculator = FlowScoreCalculator()
        self.is_running = False
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.send_interval = 10  # Send data every 10 seconds
        
    def start(self):
        """Start the agent"""
        print("""
        ╔══════════════════════════════════════════════════════════╗
        ║  🚀 CODEPULSE AGENT                                     ║
        ║  Developer Intelligence Data Collector                  ║
        ║                                                         ║
        ║  📡 Sending data to: {}                   ║
        ║  🔑 Session ID: {}                   ║
        ║                                                         ║
        ║  Press ESC to stop logging                              ║
        ╚══════════════════════════════════════════════════════════╝
        """.format(self.dashboard_url, self.session_id[:8]))
        
        self.is_running = True
        
        # Start logger in background
        log_thread = threading.Thread(target=self.logger.start_logging)
        log_thread.daemon = True
        log_thread.start()
        
        # Main loop - send data periodically
        try:
            while self.is_running:
                time.sleep(self.send_interval)
                if self.logger.keystrokes:
                    self.send_data()
                    
        except KeyboardInterrupt:
            print("\n🛑 Stopping agent...")
            self.stop()
        finally:
            self.logger.stop_logging()
            # Send final data
            if self.logger.keystrokes:
                self.send_data()
    
    def send_data(self):
        """Send collected data to dashboard"""
        try:
            # Get stats
            stats = self.logger.get_stats()
            
            if not stats or stats.get('total_events', 0) == 0:
                return
            
            # ============================================
            # ✅ CALCULATE REAL VALUES FROM KEYSTROKE DATA
            # ============================================
            
            # 1. Calculate REAL typing speed (WPM)
            total_keys = stats.get('presses', 0)
            session_duration = stats.get('session_duration', 1)
            if session_duration > 0:
                wpm = (total_keys / 5) / (session_duration / 60)
            else:
                wpm = 0
            
            # 2. Calculate REAL backspace rate
            backspaces = self.logger.get_backspace_count()
            if total_keys > 0:
                backspace_rate = backspaces / total_keys
            else:
                backspace_rate = 0.15
            
            # 3. Calculate REAL average pause
            flight_times = stats.get('flight_times', [])
            if flight_times:
                avg_pause = sum(flight_times) / len(flight_times)
            else:
                avg_pause = 1.5
            
            # 4. Code complexity (placeholder until code tracker is integrated)
            code_complexity = 50
            edit_consistency = 0.75
            
            session_data = {
                'typing_speed': wpm,
                'backspace_rate': backspace_rate,
                'avg_pause': avg_pause,
                'code_complexity': code_complexity,
                'edit_consistency': edit_consistency
            }
            
            flow_result = self.flow_calculator.calculate_flow_score(session_data)
            
            # Prepare payload
            payload = {
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'keystroke_stats': stats,
                'flow_score': flow_result,
                'keystrokes_sample': self.logger.keystrokes[-20:] if self.logger.keystrokes else []
            }
            
            # Send to dashboard
            try:
                response = requests.post(
                    f'{self.dashboard_url}/api/submit',
                    json=payload,
                    timeout=5
                )
                
                if response.status_code == 201:
                    print(f"✅ Data sent at {datetime.now().strftime('%H:%M:%S')}")
                    print(f"   📊 Flow Score: {flow_result['score']:.1f} ({flow_result['state']})")
                    print(f"   ⌨️  Total keystrokes: {stats.get('total_events', 0)}")
                    print(f"   ⏱️  Session: {stats.get('session_duration', 0):.1f}s")
                    print(f"   📝 WPM: {wpm:.1f}")
                    print(f"   🔄 Backspace Rate: {backspace_rate*100:.1f}%")
                    print("   ─────────────────────────────")
                else:
                    print(f"⚠️ Dashboard response: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                print("❌ Dashboard not running! Start it with: python dashboard/app.py")
            except Exception as e:
                print(f"❌ Error sending data: {e}")
                
        except Exception as e:
            print(f"❌ Error preparing data: {e}")
    
    def stop(self):
        """Stop the agent"""
        self.is_running = False
        print("\n🛑 Agent stopped")

def main():
    """Main entry point"""
    # Check if dashboard is running
    try:
        response = requests.get('http://localhost:5000/api/health', timeout=2)
        if response.status_code != 200:
            print("⚠️ Dashboard is not responding properly.")
            print("   Make sure it's running at: http://localhost:5000")
    except:
        print("⚠️ Dashboard is not running!")
        print("   Please start it first: python dashboard/app.py")
        print("   Then run this agent again.")
        return
    
    agent = CodePulseAgent()
    agent.start()

if __name__ == "__main__":
    main()
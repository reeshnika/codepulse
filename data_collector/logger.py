"""
Keystroke Logger - Captures every key press with timing
"""

from pynput import keyboard
import time
import json
from datetime import datetime

class KeystrokeLogger:
    def __init__(self):
        self.keystrokes = []
        self.is_logging = False
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.last_key_time = {}
        
    def on_press(self, key):
        """Called when a key is pressed"""
        try:
            key_char = key.char
        except AttributeError:
            key_char = str(key)
        
        # Calculate timing
        dwell_time = 0
        if key_char in self.last_key_time:
            dwell_time = time.time() - self.last_key_time[key_char]
        
        flight_time = 0
        if self.keystrokes:
            flight_time = time.time() - self.keystrokes[-1]['timestamp']
        
        # Store event
        event = {
            'type': 'press',
            'key': key_char,
            'timestamp': time.time(),
            'dwell_time': dwell_time,
            'flight_time': flight_time,
            'session_id': self.session_id
        }
        
        self.keystrokes.append(event)
        self.last_key_time[key_char] = time.time()
        
        # Stop on ESC
        if key == keyboard.Key.esc:
            self.stop_logging()
            return False
            
    def on_release(self, key):
        """Called when a key is released"""
        try:
            key_char = key.char
        except AttributeError:
            key_char = str(key)
        
        event = {
            'type': 'release',
            'key': key_char,
            'timestamp': time.time(),
            'session_id': self.session_id
        }
        
        self.keystrokes.append(event)
        
    def start_logging(self):
        """Start capturing keystrokes"""
        print(f"🔴 Logging started - Session: {self.session_id}")
        print("Press ESC to stop")
        
        self.is_logging = True
        
        listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )
        listener.start()
        
        try:
            while self.is_logging:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop_logging()
        finally:
            listener.stop()
            
    def stop_logging(self):
        """Stop and save data"""
        self.is_logging = False
        print(f"\n⏹️ Stopped. {len(self.keystrokes)} keys captured")
        self.save_data()
        
    def save_data(self):
        """Save to JSON file"""
        filename = f"keystrokes_{self.session_id}.json"
        with open(filename, 'w') as f:
            json.dump(self.keystrokes, f, indent=2)
        print(f"💾 Saved to: {filename}")
        
    def get_stats(self):
        """Get full statistics including flight times"""
        if not self.keystrokes:
            return {}
        
        presses = [k for k in self.keystrokes if k.get('type') == 'press']
        releases = [k for k in self.keystrokes if k.get('type') == 'release']
        
        flight_times = []
        for i in range(1, len(presses)):
            if presses[i].get('flight_time', 0) > 0:
                flight_times.append(presses[i]['flight_time'])
        
        return {
            'total_events': len(self.keystrokes),
            'presses': len(presses),
            'releases': len(releases),
            'flight_times': flight_times,
            'avg_flight_time': sum(flight_times) / len(flight_times) if flight_times else 0,
            'session_duration': self.keystrokes[-1]['timestamp'] - self.keystrokes[0]['timestamp'] if self.keystrokes else 0
        }
    
    def get_backspace_count(self):
        """Count total backspaces in session"""
        count = 0
        for event in self.keystrokes:
            if event.get('key') == 'Backspace' or event.get('key') == 'Key.backspace':
                count += 1
        return count
"""
Code Tracker - Tracks how code evolves during a coding session
"""

import time
import json
from datetime import datetime

class CodeTracker:
    """Track code changes over time"""
    
    def __init__(self):
        self.snapshots = []
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_code = ""
        self.last_snapshot_time = time.time()
        self.snapshot_interval = 3  # Take snapshot every 3 seconds
        
    def update_code(self, new_code):
        """Update current code and track changes"""
        self.current_code = new_code
        
        # Take snapshot if interval has passed
        if time.time() - self.last_snapshot_time >= self.snapshot_interval:
            self.take_snapshot()
            
    def take_snapshot(self):
        """Capture current code state"""
        if not self.current_code:
            return
            
        snapshot = {
            'code': self.current_code,
            'timestamp': time.time(),
            'datetime': datetime.now().isoformat(),
            'length': len(self.current_code),
            'lines': self.current_code.count('\n') + 1
        }
        
        # Add evolution metrics if we have previous snapshot
        if self.snapshots:
            prev_code = self.snapshots[-1]['code']
            
            # Simple edit distance (will implement full Levenshtein later)
            snapshot['edit_distance'] = self.simple_edit_distance(prev_code, self.current_code)
            snapshot['change_percentage'] = self.calculate_change_percentage(prev_code, self.current_code)
        
        self.snapshots.append(snapshot)
        self.last_snapshot_time = time.time()
        
        print(f"📸 Snapshot taken: {snapshot['length']} chars, {snapshot['lines']} lines")
        
    def simple_edit_distance(self, str1, str2):
        """Simple edit distance for quick calculation"""
        # This is a simplified version - we'll implement full Levenshtein later
        max_len = max(len(str1), len(str2))
        if max_len == 0:
            return 0
        return abs(len(str1) - len(str2))
    
    def calculate_change_percentage(self, str1, str2):
        """Calculate percentage of code changed"""
        if len(str1) == 0:
            return 100 if len(str2) > 0 else 0
        
        distance = self.simple_edit_distance(str1, str2)
        return (distance / max(len(str1), len(str2))) * 100
    
    def save_snapshots(self):
        """Save all snapshots to file"""
        filename = f"code_evolution_{self.session_id}.json"
        with open(filename, 'w') as f:
            json.dump(self.snapshots, f, indent=2)
        print(f"💾 Code evolution saved to: {filename}")
        
    def get_evolution_stats(self):
        """Get statistics about code evolution"""
        if len(self.snapshots) < 2:
            return {
                'total_snapshots': len(self.snapshots),
                'avg_edit_distance': 0,
                'total_changes': 0
            }
            
        distances = [s.get('edit_distance', 0) for s in self.snapshots[1:]]
        changes = [s.get('change_percentage', 0) for s in self.snapshots[1:]]
        
        return {
            'total_snapshots': len(self.snapshots),
            'avg_edit_distance': sum(distances) / len(distances) if distances else 0,
            'avg_change_percentage': sum(changes) / len(changes) if changes else 0,
            'total_changes': len([c for c in changes if c > 0])
        }
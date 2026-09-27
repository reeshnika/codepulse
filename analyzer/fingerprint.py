"""
Developer Fingerprinting - Unique typing signatures
"""

import hashlib
import json

class DeveloperFingerprinter:
    """Create and compare developer fingerprints"""
    
    def __init__(self):
        self.user_profiles = {}
        self.threshold = 85
    
    def extract_features(self, session_data):
        return {
            'avg_flight_time': session_data.get('avg_flight_time', 0),
            'avg_dwell_time': session_data.get('avg_dwell_time', 0),
            'typing_speed': session_data.get('wpm', 0),
            'backspace_rate': session_data.get('backspace_rate', 0),
            'indentation_style': session_data.get('indentation', 'space')
        }
    
    def generate_fingerprint(self, features):
        feature_string = json.dumps(features, sort_keys=True)
        fingerprint = hashlib.sha256(feature_string.encode()).hexdigest()
        return fingerprint[:16]
    
    def identify_user(self, current_features):
        for user_id, profile in self.user_profiles.items():
            stored_fingerprint = profile['fingerprint']
            current_fingerprint = self.generate_fingerprint(current_features)
            
            matches = sum(1 for a, b in zip(stored_fingerprint, current_fingerprint) if a == b)
            similarity = (matches / len(stored_fingerprint)) * 100
            
            if similarity >= self.threshold:
                return user_id
        
        return "Unknown User"
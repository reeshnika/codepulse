"""
Developer Fingerprinting Module for CodePulse
Extracts keystroke & coding features, generates SHA-256 hashes, and matches developer identities.
"""

import json
import hashlib
import logging

logger = logging.getLogger(__name__)


class DeveloperFingerprinter:
    """Extracts behavioral coding signatures and computes unique developer fingerprints."""

    def extract_features(self, stats, code_stats, logger_instance=None):
        """
        Extracts biometric and behavioral features from keystroke and code evolution telemetry.

        Returns:
            dict containing:
            - avg_flight_time
            - avg_dwell_time
            - typing_speed
            - backspace_rate
            - avg_pause
            - avg_edit_distance
            - indentation_style
            - total_session_duration
        """
        stats = stats or {}
        code_stats = code_stats or {}

        # 1. Flight time and pause
        avg_flight = stats.get('avg_flight_time', 0)

        # 2. Dwell time: calculate from logger events if available, or stats
        if logger_instance and hasattr(logger_instance, 'keystrokes'):
            press_dwells = [e.get('dwell_time', 0) for e in logger_instance.keystrokes if e.get('type') == 'press']
            avg_dwell = sum(press_dwells) / max(1, stats.get('presses', 1)) if press_dwells else 0.08
        else:
            avg_dwell = stats.get('avg_dwell_time', 0.08)

        # 3. Typing speed
        typing_speed = stats.get('typing_speed', stats.get('wpm', avg_flight))

        # 4. Backspace rate
        backspace_rate = stats.get('backspace_rate', 0.15)

        # 5. Average pause
        avg_pause = stats.get('avg_pause', avg_flight)

        # 6. Average edit distance from code_stats
        avg_edit = code_stats.get('avg_edit_distance', 0)

        # 7. Indentation style
        indent_style = code_stats.get('indentation_style', 'space')

        # 8. Total session duration
        duration = stats.get('session_duration', 0)

        return {
            'avg_flight_time': round(float(avg_flight), 4),
            'avg_dwell_time': round(float(avg_dwell), 4),
            'typing_speed': round(float(typing_speed), 2),
            'backspace_rate': round(float(backspace_rate), 4),
            'avg_pause': round(float(avg_pause), 4),
            'avg_edit_distance': round(float(avg_edit), 2),
            'indentation_style': indent_style,
            'total_session_duration': round(float(duration), 2)
        }

    def generate_fingerprint(self, features):
        """
        Generates a 16-character SHA-256 fingerprint hash from sorted features JSON string.
        """
        if not isinstance(features, dict):
            features = {}
        feature_string = json.dumps(features, sort_keys=True)
        hash_obj = hashlib.sha256(feature_string.encode('utf-8'))
        return hash_obj.hexdigest()[:16]

    def compare_fingerprints(self, fp1, fp2):
        """
        Compares two fingerprints character-by-character.
        Returns {'similarity': similarity, 'is_match': similarity >= 85}
        """
        if not fp1 or not fp2:
            return {'similarity': 0.0, 'is_match': False}
        length = min(len(fp1), len(fp2))
        if length == 0:
            return {'similarity': 0.0, 'is_match': False}

        matches = sum(1 for a, b in zip(fp1[:length], fp2[:length]) if a == b)
        similarity = (matches / max(len(fp1), len(fp2))) * 100.0
        return {
            'similarity': round(similarity, 2),
            'is_match': similarity >= 85.0
        }

    def identify_user(self, current_features, known_users):
        """
        Identifies user from current features against known users dictionary.
        known_users: dict {user_id: {'fingerprint': hash, ...}}
        Returns matching user_id or 'Unknown'
        """
        if not known_users or not isinstance(known_users, dict):
            return "Unknown"

        current_fp = self.generate_fingerprint(current_features)
        best_user = "Unknown"
        best_similarity = 0.0

        for user_id, user_data in known_users.items():
            if isinstance(user_data, dict):
                target_fp = user_data.get('fingerprint', '')
            else:
                target_fp = str(user_data)

            comparison = self.compare_fingerprints(current_fp, target_fp)
            if comparison['similarity'] > best_similarity:
                best_similarity = comparison['similarity']
                if comparison['is_match']:
                    best_user = user_id

        return best_user

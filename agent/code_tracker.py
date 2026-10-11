"""
Code Tracker and Dynamic Programming Levenshtein Distance
Tracks code evolutions, edit distances, line counts, and similarity metrics.
"""

import os
import json
import time
import logging

logger = logging.getLogger(__name__)


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Computes Levenshtein edit distance between two strings using dynamic programming.
    Time Complexity: O(m * n)
    Space Complexity: O(min(m, n))
    """
    if s1 == s2:
        return 0
    if not s1:
        return len(s2)
    if not s2:
        return len(s1)

    # Ensure s2 is the shorter string for space optimization
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    n = len(s2)
    previous_row = list(range(n + 1))

    for i, c1 in enumerate(s1):
        current_row = [i + 1] * (n + 1)
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row[j + 1] = min(insertions, deletions, substitutions)
        previous_row = current_row

    return previous_row[n]


class CodeTracker:
    """Monitors code changes, snapshot cadence, and diff evolution metrics."""

    def __init__(self, session_id=None, snapshot_interval=3.0):
        self.session_id = session_id or time.strftime("%Y%m%d_%H%M%S")
        self.snapshot_interval = snapshot_interval
        self.snapshots = []
        self.current_code = ""
        self.last_snapshot_time = 0.0

    def take_snapshot(self, code=None):
        """
        Takes an immediate snapshot storing:
        {code, timestamp, length, lines, edit_distance, similarity}
        """
        now = time.time()
        if code is None:
            code = self.current_code

        length = len(code)
        lines = len(code.splitlines()) if code else 0

        if self.snapshots:
            prev_code = self.snapshots[-1]['code']
            edit_dist = levenshtein_distance(prev_code, code)
            max_len = max(len(prev_code), len(code))
            similarity = round(1.0 - (edit_dist / max_len), 4) if max_len > 0 else 1.0
        else:
            edit_dist = 0
            similarity = 1.0

        snapshot = {
            'code': code,
            'timestamp': now,
            'length': length,
            'lines': lines,
            'edit_distance': edit_dist,
            'similarity': similarity
        }

        self.snapshots.append(snapshot)
        self.current_code = code
        self.last_snapshot_time = now
        return snapshot

    def update_code(self, new_code, force=False):
        """
        Updates code buffer and takes a snapshot every 3 seconds
        (or on the very first update, or when force=True).
        """
        if new_code is None:
            new_code = ""
        self.current_code = new_code
        now = time.time()

        if force or (not self.snapshots) or (now - self.last_snapshot_time >= self.snapshot_interval):
            return self.take_snapshot(new_code)
        return None


    def get_evolution_stats(self):
        """
        Calculates cumulative metrics across all code snapshots:
        {total_snapshots, avg_edit_distance, avg_similarity, total_changes}
        """
        total_snapshots = len(self.snapshots)
        if total_snapshots == 0:
            return {
                'total_snapshots': 0,
                'avg_edit_distance': 0.0,
                'avg_similarity': 1.0,
                'total_changes': 0
            }

        if total_snapshots == 1:
            return {
                'total_snapshots': 1,
                'avg_edit_distance': 0.0,
                'avg_similarity': 1.0,
                'total_changes': 0
            }

        distances = [s['edit_distance'] for s in self.snapshots[1:]]
        similarities = [s['similarity'] for s in self.snapshots]

        avg_dist = round(sum(distances) / len(distances), 2) if distances else 0.0
        avg_sim = round(sum(similarities) / len(similarities), 4) if similarities else 1.0
        total_changes = sum(1 for d in distances if d > 0)

        return {
            'total_snapshots': total_snapshots,
            'avg_edit_distance': avg_dist,
            'avg_similarity': avg_sim,
            'total_changes': total_changes
        }

    def save_snapshots(self, filename=None):
        """Saves code evolution snapshots to disk."""
        if not self.snapshots:
            return
        target_file = filename or f"code_snapshots_{self.session_id}.json"
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                json.dump(self.snapshots, f, indent=2)
            print(f"💾 Code snapshots saved to: {target_file}")
        except Exception as e:
            logger.error(f"Failed to save code snapshots to {target_file}: {e}")

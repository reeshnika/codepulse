"""
Flow Score Calculator - Measures developer engagement
"""

class FlowScoreCalculator:
    """Calculate real-time flow state score"""
    
    def __init__(self):
        self.history = []
        
    def calculate_flow_score(self, session_data):
        """
        Calculate flow score (0-100)
        
        Parameters:
        session_data: dict with keys:
            - typing_speed: words per minute
            - backspace_rate: 0-1 (percentage of keys that are backspaces)
            - avg_pause: seconds between keystrokes
            - code_complexity: 0-100
            - edit_consistency: 0-1
        """
        
        # Calculate individual component scores
        speed_score = self._speed_score(session_data.get('typing_speed', 0))
        accuracy_score = self._accuracy_score(session_data.get('backspace_rate', 0.15))
        focus_score = self._focus_score(session_data.get('avg_pause', 2.0))
        clarity_score = self._clarity_score(session_data.get('code_complexity', 50))
        consistency_score = self._consistency_score(session_data.get('edit_consistency', 0.5))
        
        # Weighted average (weights sum to 1)
        weights = {
            'speed': 0.25,
            'accuracy': 0.20,
            'focus': 0.25,
            'clarity': 0.15,
            'consistency': 0.15
        }
        
        raw_score = (
            speed_score * weights['speed'] +
            accuracy_score * weights['accuracy'] +
            focus_score * weights['focus'] +
            clarity_score * weights['clarity'] +
            consistency_score * weights['consistency']
        )
        
        final_score = min(100, max(0, raw_score))
        
        # Store in history
        self.history.append(final_score)
        
        return {
            'score': final_score,
            'state': self._classify_state(final_score),
            'suggestion': self._get_suggestion(final_score),
            'components': {
                'speed': round(speed_score, 1),
                'accuracy': round(accuracy_score, 1),
                'focus': round(focus_score, 1),
                'clarity': round(clarity_score, 1),
                'consistency': round(consistency_score, 1)
            }
        }
    
    def _speed_score(self, wpm):
        """Calculate speed component score"""
        if wpm >= 60:
            return 90 + (wpm - 60) * 0.33
        elif wpm >= 30:
            return 50 + (wpm - 30) * 1.33
        else:
            return wpm * 1.67
    
    def _accuracy_score(self, backspace_rate):
        """Calculate accuracy component score"""
        if backspace_rate <= 0.05:
            return 95
        elif backspace_rate <= 0.10:
            return 80
        elif backspace_rate <= 0.15:
            return 65
        elif backspace_rate <= 0.25:
            return 45
        else:
            return 25
    
    def _focus_score(self, avg_pause):
        """Calculate focus component score"""
        if avg_pause <= 1.0:
            return 90
        elif avg_pause <= 2.0:
            return 75
        elif avg_pause <= 3.5:
            return 55
        elif avg_pause <= 5.0:
            return 35
        else:
            return 20
    
    def _clarity_score(self, complexity):
        """Calculate clarity component score"""
        # Lower complexity is better
        if complexity <= 20:
            return 90
        elif complexity <= 40:
            return 75
        elif complexity <= 60:
            return 55
        elif complexity <= 80:
            return 35
        else:
            return 20
    
    def _consistency_score(self, consistency):
        """Calculate consistency component score"""
        return consistency * 100
    
    def _classify_state(self, score):
        """Classify the flow state"""
        if score >= 85:
            return "FLOW_STATE"
        elif score >= 70:
            return "PRODUCTIVE"
        elif score >= 50:
            return "WORKING"
        elif score >= 30:
            return "STRUGGLING"
        else:
            return "BLOCKED"
    
    def _get_suggestion(self, score):
        """Get actionable suggestion"""
        if score >= 85:
            return "🚀 You're in the zone! Keep going!"
        elif score >= 70:
            return "💪 Good progress! Try tackling complex problems."
        elif score >= 50:
            return "🤔 Working steadily. Consider taking a short break."
        elif score >= 30:
            return "😰 You seem stuck. Try breaking down the problem."
        else:
            return "🧠 Take a break and come back refreshed."
    
    def detect_ai_generated(self, keystroke_data, code_data):
        """
        Detect AI-generated or copy-pasted code.
        Returns a dict with ai_score (0-100) and flags.
        """
        signals = []
        ai_score = 0
        
        # Signal 1: No typing rhythm (instant paste)
        if keystroke_data.get('total_events', 0) < 50 and code_data.get('total_changes', 0) == 0:
            signals.append('copy_paste')
            ai_score += 30
        
        # Signal 2: No backspaces (AI-generated is perfect)
        if keystroke_data.get('backspace_rate', 1) < 0.02:
            signals.append('no_errors')
            ai_score += 25
        
        # Signal 3: No pauses (AI doesn't think)
        if keystroke_data.get('avg_pause', 0) < 0.1:
            signals.append('no_thought')
            ai_score += 25
        
        # Signal 4: Large code insertion with no typing
        if code_data.get('avg_edit_distance', 0) > 100:
            signals.append('large_paste')
            ai_score += 20
        
        return {
            'ai_score': min(100, ai_score),
            'is_ai_generated': ai_score > 50,
            'signals': signals
        }
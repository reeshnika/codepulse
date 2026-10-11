"""
Flow Score Calculator and AI Generation Detector
Quantifies developer cognitive engagement and detects synthetic activity.
"""


class FlowScoreCalculator:
    """Calculates developer flow state score and detects AI-generated code."""

    def __init__(self):
        self.history = []

    def detect_code_quality(self, recent_keystrokes):
        """
        STRICT code detection - only real programming code should get high scores.
        Sentences, paragraphs, and random text should score LOW.
        """
        if not recent_keystrokes or len(recent_keystrokes) < 30:
            return 0  # not enough data → score 0

        # Get last 150 key presses as string
        chars = []
        for k in recent_keystrokes[-150:]:
            if isinstance(k, dict):
                if k.get('type') and k.get('type') != 'press':
                    continue
                raw_key = k.get('key', '')
            elif isinstance(k, str):
                raw_key = k
            else:
                raw_key = str(k)

            if raw_key == 'Key.space':
                chars.append(' ')
            elif raw_key == 'Key.enter':
                chars.append('\n')
            elif raw_key == 'Key.tab':
                chars.append('\t')
            elif raw_key.startswith('Key.'):
                continue
            else:
                chars.append(raw_key)

        recent_keys = ''.join(chars)

        if len(recent_keys) < 20:
            return 0

        # === HARD GATE: Must have code-specific characters ===
        # === HARD GATE: Must have code-specific characters ===
        code_chars = ['{', '}', '(', ')', '[', ']', ';', '=', ':', '<', '>', '_', '+', '-', '*', '/', '%', '&', '|', '!', '`', '"', "'"]
        code_char_count = sum(1 for c in recent_keys if c in code_chars)

        # If almost no code characters, it's NOT code
        if code_char_count < 3:
            return 0  # definitely not code

        # === SIGNAL 1: Programming Keywords (weight 35) ===
        keywords = [
            'def ', 'class ', 'return', 'import ', 'from ', 
            'if ', 'else', 'for ', 'while ', 'print(', 
            'public ', 'private ', 'static ', 'void ', 'int ', 
            'String ', 'func ', 'fn ', 'let ', 'const ', 'var ',
            'self.', 'this.', 'new ', 'try', 'catch', 'except',
            'nil', 'None', 'True', 'False', 'null', 'true', 'false'
        ]
        found_keywords = sum(1 for kw in keywords if kw in recent_keys)

        if found_keywords == 0:
            return 0  # no code keywords → definitely not code

        keyword_score = min(35, 15 + found_keywords * 10)

        # === SIGNAL 2: Structural Characters Ratio (weight 25) ===
        structural = sum(1 for c in recent_keys if c in '(){}[];,=:<>_+*&|!%^/-"\'')
        structural_ratio = structural / max(1, len(recent_keys))

        if structural_ratio < 0.03:
            struct_score = 10
        elif structural_ratio < 0.06:
            struct_score = 18
        else:
            struct_score = 25

        # === SIGNAL 3: Whitespace Pattern (weight 15) ===
        newlines = recent_keys.count('\n')
        tabs = recent_keys.count('\t')
        spaces = recent_keys.count(' ')

        if newlines + tabs >= 1:
            ws_score = 15
        elif spaces >= 3:
            ws_score = 10
        else:
            ws_score = 5

        # === SIGNAL 4: Detect Common Sentence Words (weight -25 penalty) ===
        sentence_words = [' the ', ' and ', ' is ', ' are ', ' was ', ' were ',
                         ' have ', ' has ', ' this is ', ' that is ', ' you ',
                         ' we ', ' they ', ' will ', ' would ', ' could ',
                         ' should ', ' about ', ' because ', ' very ', ' really ']

        sentence_word_count = sum(1 for word in sentence_words if word in recent_keys.lower())
        sentence_penalty = sentence_word_count * 20

        # === SIGNAL 5: Special Gibberish Chars (weight -20 penalty) ===
        gibberish_chars = sum(1 for c in recent_keys if c in '@#$%^&*~`|')
        gibberish_ratio = gibberish_chars / max(1, len(recent_keys))
        gibberish_penalty = 0
        if gibberish_ratio > 0.08:
            gibberish_penalty = 20

        # === FINAL CALCULATION ===
        raw_score = keyword_score + struct_score + ws_score - sentence_penalty - gibberish_penalty

        return max(0, min(100, raw_score))

    def calculate_flow_score(self, session_data):
        """
        Calculates flow score (0-100) based on keystroke and coding dynamics.

        Parameters:
        session_data: dict with keys:
            - typing_speed: float (WPM)
            - backspace_rate: float (0.0 to 1.0)
            - avg_pause: float (seconds)
            - recent_edit_distance: float or int (default 0)
            - std_dev_flight_time: float (default 0.0)
            - recent_keystrokes: list of keystrokes (optional)
            - recent_pastes: int (default 0)
            - ai_score: float (default 0.0)
            - code_complexity: fallback if recent_edit_distance not given
            - edit_consistency: fallback if std_dev_flight_time not given

        Returns:
            dict: {score, state, suggestion, components: {speed, accuracy, focus, clarity, consistency, code_quality}, ai_penalty_applied}
        """
        if not isinstance(session_data, dict):
            session_data = {}

        # Code quality analysis
        recent = session_data.get('recent_keystrokes', [])
        if recent:
            code_quality = self.detect_code_quality(recent)
        elif 'code_quality' in session_data:
            code_quality = float(session_data.get('code_quality') or 0)
        else:
            code_quality = 85.0

        # STRICT CAPS: If code_quality is 0, it's NOT code at all
        if code_quality == 0:
            return {
                'score': 0,
                'state': 'NOT_CODE',
                'suggestion': '⚠️ Not detected as code. Write real programming syntax!',
                'components': {
                    'speed': 0, 'accuracy': 0, 'focus': 0,
                    'clarity': 0, 'consistency': 0, 'code_quality': 0
                },
                'ai_penalty_applied': False
            }

        wpm = float(session_data.get('typing_speed', 0.0) or 0.0)
        backspace_rate = float(session_data.get('backspace_rate', 0.15) if session_data.get('backspace_rate') is not None else 0.15)
        avg_pause = float(session_data.get('avg_pause', 2.0) if session_data.get('avg_pause') is not None else 2.0)

        # Clarity input: recent_edit_distance (fallback to code_complexity if not provided)
        if 'recent_edit_distance' in session_data:
            recent_edit_distance = float(session_data.get('recent_edit_distance') or 0.0)
        elif 'avg_edit_distance' in session_data:
            recent_edit_distance = float(session_data.get('avg_edit_distance') or 0.0)
        elif 'code_complexity' in session_data:
            complexity = float(session_data.get('code_complexity') or 0.0)
            recent_edit_distance = max(0.0, (complexity - 20.0) * 0.5)
        else:
            recent_edit_distance = 0.0

        # Consistency input: std_dev_flight_time (fallback to edit_consistency if not provided)
        if 'std_dev_flight_time' in session_data:
            std_dev_flight_time = float(session_data.get('std_dev_flight_time') or 0.0)
        elif 'edit_consistency' in session_data:
            edit_consistency = float(session_data.get('edit_consistency') or 0.5)
            std_dev_flight_time = max(0.0, (1.0 - edit_consistency) * 0.5)
        else:
            std_dev_flight_time = 0.0

        recent_pastes = int(session_data.get('recent_pastes', 0) or 0)
        ai_score = float(session_data.get('ai_score', 0.0) or 0.0)

        # Quality caps:
        if code_quality < 30:
            cap = 20
        elif code_quality < 50:
            cap = 45
        elif code_quality < 70:
            cap = 70
        else:
            cap = 100

        # 1. Component calculations
        speed_score = self._speed_score(wpm)
        accuracy_score = self._accuracy_score(backspace_rate)
        focus_score = self._focus_score(avg_pause)
        clarity_score = self._clarity_score(recent_edit_distance)
        consistency_score = self._consistency_score(std_dev_flight_time)

        # 2. Weighted sum (weights sum to 1.00)
        raw_score = (
            speed_score * 0.20 +
            accuracy_score * 0.20 +
            focus_score * 0.25 +
            clarity_score * 0.15 +
            consistency_score * 0.20
        )

        # Apply cap based on code quality
        penalized_score = min(raw_score, cap)

        # 3. AI / Copy-Paste Penalties
        ai_penalty_applied = False
        if recent_pastes >= 10:
            penalized_score -= 50.0
            ai_penalty_applied = True
        elif recent_pastes >= 5:
            penalized_score -= 30.0
            ai_penalty_applied = True
        elif recent_pastes >= 3:
            penalized_score -= 15.0
            ai_penalty_applied = True

        if ai_score > 85:
            penalized_score = min(penalized_score, 20.0)
            ai_penalty_applied = True
        elif ai_score > 70:
            penalized_score = min(penalized_score, 40.0)
            ai_penalty_applied = True

        final_score = round(max(0.0, min(100.0, penalized_score)), 1)
        self.history.append(final_score)

        base_state = self._classify_state(final_score)
        state = f"{base_state} (AI-assisted)" if ai_penalty_applied else base_state
        suggestion = self._get_suggestion(final_score, ai_penalty_applied=ai_penalty_applied)

        return {
            'score': final_score,
            'state': state,
            'suggestion': suggestion,
            'components': {
                'speed': round(speed_score, 1),
                'accuracy': round(accuracy_score, 1),
                'focus': round(focus_score, 1),
                'clarity': round(clarity_score, 1),
                'consistency': round(consistency_score, 1),
                'code_quality': round(code_quality, 1)
            },
            'ai_penalty_applied': ai_penalty_applied
        }

    def _speed_score(self, wpm):
        """Calculates typing speed score (0-100)."""
        if wpm >= 80:
            return 100.0
        elif wpm >= 60:
            return 85.0 + (wpm - 60.0) / 20.0 * 15.0
        elif wpm >= 40:
            return 60.0 + (wpm - 40.0) / 20.0 * 25.0
        elif wpm >= 20:
            return 30.0 + (wpm - 20.0) / 20.0 * 30.0
        else:
            return max(0.0, (wpm / 20.0) * 30.0)

    def _accuracy_score(self, backspace_rate):
        """Calculates accuracy score from backspace rate."""
        if backspace_rate <= 0.03:
            return 100.0
        elif backspace_rate <= 0.05:
            return 90.0
        elif backspace_rate <= 0.10:
            return 75.0
        elif backspace_rate <= 0.15:
            return 55.0
        elif backspace_rate <= 0.25:
            return 30.0
        else:
            return 10.0

    def _focus_score(self, avg_pause):
        """Calculates focus score from pause duration."""
        if avg_pause <= 0.5:
            return 100.0
        elif avg_pause <= 1.0:
            return 85.0
        elif avg_pause <= 2.0:
            return 65.0
        elif avg_pause <= 3.5:
            return 40.0
        elif avg_pause <= 5.0:
            return 20.0
        else:
            return 5.0

    def _clarity_score(self, recent_edit_distance):
        """
        Calculates clarity score from recent edit distance.
        Steady growth without rewrites = high score.
        Formula: 100 - min(100, recent_edit_distance * 2)
        """
        return max(0.0, min(100.0, 100.0 - min(100.0, recent_edit_distance * 2.0)))

    def _consistency_score(self, std_dev_flight_time):
        """
        Calculates consistency score from standard deviation of flight times.
        Formula: 100 - (std_dev_flight_time * 200), capped 0-100.
        """
        return max(0.0, min(100.0, 100.0 - (std_dev_flight_time * 200.0)))

    def _classify_state(self, score):
        """Classifies engagement state from numerical score."""
        if score == 0:
            return "NOT_CODE"
        elif score >= 85:
            return "FLOW_STATE"
        elif score >= 70:
            return "PRODUCTIVE"
        elif score >= 50:
            return "WORKING"
        elif score >= 30:
            return "STRUGGLING"
        else:
            return "BLOCKED"

    def _get_suggestion(self, score, ai_penalty_applied=False):
        """Produces actionable user advice for their state."""
        if score == 0:
            return "⚠️ Not detected as code. Write real programming syntax!"
        if ai_penalty_applied:
            return "⚠️ Excessive copy-paste detected. Try typing it out!"
        if score >= 85:
            return "🚀 You're in the flow zone! Keep this momentum."
        elif score >= 70:
            return "⚡ Great rhythm! You're making solid progress."
        elif score >= 50:
            return "👍 Steady progress. Try to maintain your focus."
        elif score >= 30:
            return "☕ Take a quick breather. Review your approach."
        else:
            return "🚶 Step away for 5 minutes. Clear your head."

    def detect_ai_generated(self, keystroke_data, code_data):
        """
        Detects AI-generated or mass pasted code snippets from telemetry anomalies.

        Signals:
            - copy_paste (30): <50 keystroke events with non-empty code changes
            - no_errors (25): backspace_rate < 0.02
            - no_thought (25): avg_pause < 0.1s
            - large_paste (20): avg_edit_distance > 100 characters

        Returns:
            dict: {ai_score (0-100), is_ai_generated (bool), signals (list)}
        """
        if not isinstance(keystroke_data, dict):
            keystroke_data = {}
        if not isinstance(code_data, dict):
            code_data = {}

        signals = []
        ai_score = 0

        # Signal 1 (weight 30): copy_paste — total_events < 50 AND code changes exist
        total_events = keystroke_data.get('total_events', 0)
        code_changes_exist = (
            code_data.get('total_changes', 0) > 0 or
            code_data.get('total_snapshots', 0) > 1 or
            code_data.get('has_changes', False)
        )
        if total_events < 50 and code_changes_exist:
            signals.append('copy_paste')
            ai_score += 30

        # Signal 2 (weight 25): no_errors — backspace_rate < 0.02
        backspace_rate = keystroke_data.get('backspace_rate', 1.0)
        if backspace_rate < 0.02 and total_events > 0:
            signals.append('no_errors')
            ai_score += 25

        # Signal 3 (weight 25): no_thought — avg_pause < 0.1
        avg_pause = keystroke_data.get('avg_pause', 1.5)
        if avg_pause < 0.1 and total_events > 0:
            signals.append('no_thought')
            ai_score += 25

        # Signal 4 (weight 20): large_paste — avg_edit_distance > 100
        avg_edit_dist = code_data.get('avg_edit_distance', 0)
        if avg_edit_dist > 100:
            signals.append('large_paste')
            ai_score += 20

        total_score = min(100, ai_score)

        return {
            'ai_score': total_score,
            'is_ai_generated': total_score >= 50,
            'signals': signals
        }

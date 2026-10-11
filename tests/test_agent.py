"""
Unit tests for updated CodePulse Agent module:
- KeystrokeLogger with coding app filter & copy/paste detection
- FlowScoreCalculator
- CodeTracker & Levenshtein DP
- CodePulseAgent with copy_paste_stats payload
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from agent.logger import KeystrokeLogger, is_coding_app_active, CODING_APPS
from agent.flow_score import FlowScoreCalculator
from agent.code_tracker import CodeTracker, levenshtein_distance
from agent.agent import CodePulseAgent


def test_coding_app_filter():
    with patch('agent.logger.gw') as mock_gw:
        # Mock non-coding window (e.g. Chrome / WhatsApp)
        mock_win = MagicMock()
        mock_win.title = "WhatsApp"
        mock_gw.getActiveWindow.return_value = mock_win
        assert is_coding_app_active() is False

        # Mock coding window (e.g. VS Code)
        mock_win.title = "Visual Studio Code - CodePulse"
        mock_gw.getActiveWindow.return_value = mock_win
        assert is_coding_app_active() is True


def test_keystroke_logger_filtering_and_copy_paste():
    logger = KeystrokeLogger(session_id="test_filter_sess")

    with patch('agent.logger.is_coding_app_active') as mock_active:
        # 1. Non-coding app focused -> Keystrokes ignored
        mock_active.return_value = False
        k = MagicMock()
        k.char = 'x'
        logger.on_press(k)
        logger.on_release(k)
        assert len(logger.keystrokes) == 0

        # 2. Coding app focused -> Keystrokes captured
        mock_active.return_value = True
        logger.on_press(k)
        logger.on_release(k)
        assert len(logger.keystrokes) == 2

        # 3. Test Copy (Ctrl + C)
        k_ctrl = MagicMock()
        k_ctrl.char = None
        from pynput import keyboard
        logger.on_press(keyboard.Key.ctrl_l)
        assert logger.ctrl_pressed is True

        k_c = MagicMock()
        k_c.char = 'c'
        logger.on_press(k_c)
        logger.on_release(k_c)

        # 4. Test Paste (Ctrl + V)
        k_v = MagicMock()
        k_v.char = 'v'
        logger.on_press(k_v)
        logger.on_release(k_v)

        logger.on_release(keyboard.Key.ctrl_l)
        assert logger.ctrl_pressed is False

        cp_stats = logger.get_copy_paste_stats()
        assert cp_stats['total_copy'] == 1
        assert cp_stats['total_paste'] == 1
        assert cp_stats['is_suspicious'] is False


def test_suspicious_paste_detection():
    logger = KeystrokeLogger()
    for _ in range(4):
        logger.copy_paste_events.append({'type': 'paste', 'timestamp': time.time(), 'session_id': 'test'})
    cp_stats = logger.get_copy_paste_stats()
    assert cp_stats['total_paste'] == 4
    assert cp_stats['is_suspicious'] is True


def test_levenshtein_distance():
    assert levenshtein_distance("", "") == 0
    assert levenshtein_distance("hello", "hello") == 0
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("", "code") == 4
    assert levenshtein_distance("python", "") == 6


def test_code_tracker():
    tracker = CodeTracker(snapshot_interval=0.0)
    s1 = tracker.update_code("def foo():\n    pass\n")
    assert s1['edit_distance'] == 0
    assert s1['similarity'] == 1.0

    s2 = tracker.update_code("def foo():\n    return 42\n")
    assert s2['edit_distance'] > 0

    stats = tracker.get_evolution_stats()
    assert stats['total_snapshots'] == 2
    assert stats['total_changes'] == 1


def test_flow_score_calculator():
    calc = FlowScoreCalculator()
    session_data = {
        'typing_speed': 75.0,
        'backspace_rate': 0.04,
        'avg_pause': 0.8,
        'code_complexity': 15,
        'edit_consistency': 0.95
    }
    result = calc.calculate_flow_score(session_data)
    assert result['score'] >= 85.0
    assert result['state'] == "FLOW_STATE"


def test_agent_telemetry_flow_with_copy_paste():
    agent = CodePulseAgent(dashboard_url='http://localhost:5000')

    agent.logger.keystrokes = [
        {'type': 'press', 'key': 'x', 'timestamp': time.time() - 10, 'flight_time': 0.2, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'y', 'timestamp': time.time(), 'flight_time': 0.3, 'dwell_time': 0.1, 'session_id': agent.session_id}
    ]
    agent.logger.copy_paste_events = [
        {'type': 'copy', 'timestamp': time.time(), 'session_id': agent.session_id}
    ]

    with patch('agent.agent.requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_post.return_value = mock_resp

        agent.send_data()
        assert mock_post.called
        payload = mock_post.call_args[1]['json']
        assert 'copy_paste_stats' in payload
        assert payload['copy_paste_stats']['total_copy'] == 1
        assert 'active_time_seconds' in payload['keystroke_stats']
        assert 'idle_time_seconds' in payload['keystroke_stats']


def test_wpm_active_time_calculation():
    agent = CodePulseAgent(dashboard_url='http://localhost:5000')

    now = time.time()
    agent.logger.keystrokes = [
        {'type': 'press', 'key': 'a', 'timestamp': now - 50.0, 'flight_time': 0.0, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'b', 'timestamp': now - 49.5, 'flight_time': 0.5, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'c', 'timestamp': now - 49.0, 'flight_time': 0.5, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'd', 'timestamp': now - 48.5, 'flight_time': 0.5, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'e', 'timestamp': now - 48.0, 'flight_time': 0.5, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'f', 'timestamp': now - 47.5, 'flight_time': 0.5, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'g', 'timestamp': now - 47.0, 'flight_time': 0.5, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'h', 'timestamp': now - 46.5, 'flight_time': 0.5, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'i', 'timestamp': now - 46.0, 'flight_time': 0.5, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'j', 'timestamp': now, 'flight_time': 0.5, 'dwell_time': 0.1, 'session_id': agent.session_id},
    ]

    with patch('agent.agent.requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        agent.send_data()
        assert mock_post.called
        payload = mock_post.call_args[1]['json']
        stats = payload['keystroke_stats']

        # active_time = 9 * 0.5 = 4.5s
        assert pytest.approx(stats['active_time_seconds'], 0.1) == 4.5
        assert stats['idle_time_seconds'] > 40
        # WPM based on active time: (10 / 5) / (4.5 / 60) = 26.67 WPM
        expected_wpm = (10 / 5.0) / (4.5 / 60.0)
        assert pytest.approx(stats['wpm'], 0.1) == expected_wpm

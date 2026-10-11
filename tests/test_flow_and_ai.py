"""
Comprehensive tests for Flow Score calculation, AI/copy-paste penalties,
expanded platforms & languages, and 0-keystroke edge case handling.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from agent.flow_score import FlowScoreCalculator
from agent.logger import KeystrokeLogger, CODING_APPS
from agent.agent import CodePulseAgent


def test_speed_score_tiers():
    calc = FlowScoreCalculator()
    # WPM >= 80 -> 100
    res80 = calc.calculate_flow_score({'typing_speed': 85.0})
    assert res80['components']['speed'] == 100.0

    # WPM 60-80 -> 85-100
    res70 = calc.calculate_flow_score({'typing_speed': 70.0})
    assert 85.0 <= res70['components']['speed'] <= 100.0

    # WPM 40-60 -> 60-85
    res50 = calc.calculate_flow_score({'typing_speed': 50.0})
    assert 60.0 <= res50['components']['speed'] <= 85.0

    # WPM 20-40 -> 30-60
    res30 = calc.calculate_flow_score({'typing_speed': 30.0})
    assert 30.0 <= res30['components']['speed'] <= 60.0

    # WPM < 20 -> 0-30
    res10 = calc.calculate_flow_score({'typing_speed': 10.0})
    assert 0.0 <= res10['components']['speed'] <= 30.0


def test_accuracy_tiers():
    calc = FlowScoreCalculator()
    assert calc._accuracy_score(0.02) == 100.0
    assert calc._accuracy_score(0.04) == 90.0
    assert calc._accuracy_score(0.08) == 75.0
    assert calc._accuracy_score(0.12) == 55.0
    assert calc._accuracy_score(0.20) == 30.0
    assert calc._accuracy_score(0.30) == 10.0


def test_focus_tiers():
    calc = FlowScoreCalculator()
    assert calc._focus_score(0.4) == 100.0
    assert calc._focus_score(0.8) == 85.0
    assert calc._focus_score(1.5) == 65.0
    assert calc._focus_score(3.0) == 40.0
    assert calc._focus_score(4.5) == 20.0
    assert calc._focus_score(6.0) == 5.0


def test_clarity_formula():
    calc = FlowScoreCalculator()
    # 100 - min(100, edit_distance * 2)
    assert calc._clarity_score(0) == 100.0
    assert calc._clarity_score(10) == 80.0
    assert calc._clarity_score(50) == 0.0
    assert calc._clarity_score(100) == 0.0


def test_consistency_formula():
    calc = FlowScoreCalculator()
    # 100 - (std_dev * 200), capped 0-100
    assert calc._consistency_score(0.0) == 100.0
    assert calc._consistency_score(0.1) == 80.0
    assert calc._consistency_score(0.5) == 0.0
    assert calc._consistency_score(1.0) == 0.0


def test_ai_copy_paste_penalties():
    calc = FlowScoreCalculator()

    # Base high flow session: speed=80(100), backspace=0.02(100), pause=0.4(100), clarity=0(100), consistency=0(100) -> 100
    base_data = {
        'typing_speed': 85.0,
        'backspace_rate': 0.02,
        'avg_pause': 0.4,
        'recent_edit_distance': 0,
        'std_dev_flight_time': 0.0
    }

    # 1. No penalty
    res_normal = calc.calculate_flow_score(base_data)
    assert res_normal['score'] == 100.0
    assert res_normal['state'] == 'FLOW_STATE'
    assert not res_normal['ai_penalty_applied']

    # 2. 3 pastes -> -15 penalty
    data_3pastes = dict(base_data, recent_pastes=3)
    res_3pastes = calc.calculate_flow_score(data_3pastes)
    assert res_3pastes['score'] == 85.0
    assert '(AI-assisted)' in res_3pastes['state']
    assert res_3pastes['ai_penalty_applied']
    assert "Excessive copy-paste detected" in res_3pastes['suggestion']

    # 3. 5 pastes -> -30 penalty
    data_5pastes = dict(base_data, recent_pastes=5)
    res_5pastes = calc.calculate_flow_score(data_5pastes)
    assert res_5pastes['score'] == 70.0
    assert '(AI-assisted)' in res_5pastes['state']
    assert res_5pastes['ai_penalty_applied']

    # 4. ai_score > 70 -> capped at 40
    data_ai75 = dict(base_data, ai_score=75.0)
    res_ai75 = calc.calculate_flow_score(data_ai75)
    assert res_ai75['score'] == 40.0
    assert '(AI-assisted)' in res_ai75['state']

    # 5. ai_score > 85 -> capped at 20
    data_ai90 = dict(base_data, ai_score=90.0)
    res_ai90 = calc.calculate_flow_score(data_ai90)
    assert res_ai90['score'] == 20.0
    assert '(AI-assisted)' in res_ai90['state']


def test_logger_get_recent_copy_paste():
    logger = KeystrokeLogger(session_id="test_cp")
    now = time.time()

    # Add old event (>60s ago)
    logger.copy_paste_events.append({'type': 'copy', 'timestamp': now - 120})
    logger.copy_paste_events.append({'type': 'paste', 'timestamp': now - 90})

    # Add recent events (within 60s)
    logger.copy_paste_events.append({'type': 'copy', 'timestamp': now - 10})
    logger.copy_paste_events.append({'type': 'paste', 'timestamp': now - 20})
    logger.copy_paste_events.append({'type': 'paste', 'timestamp': now - 5})

    recent = logger.get_recent_copy_paste(60)
    assert recent['recent_copies'] == 1
    assert recent['recent_pastes'] == 2


def test_expanded_platforms_and_ide_languages():
    logger = KeystrokeLogger(session_id="test_exp")

    # Verify Online judges and IDEs in CODING_APPS
    assert 'cses' in CODING_APPS
    assert 'spoj' in CODING_APPS
    assert 'clion' in CODING_APPS
    assert 'rider' in CODING_APPS
    assert 'windows terminal' in CODING_APPS

    with patch('agent.logger.gw') as mock_gw:
        # Check IDE without extension
        mock_win = MagicMock()
        mock_win.title = "MyProject - PyCharm"
        mock_gw.getActiveWindow.return_value = mock_win
        assert logger.get_active_language() == 'python'

        # Check CLion without extension
        mock_win.title = "Algo - CLion"
        assert logger.get_active_language() == 'cpp'

        # Check Online Judge
        mock_win.title = "CSES - Problem 1068"
        assert logger.get_active_language() == 'competitive'

        # Check Rust extension
        mock_win.title = "main.rs - Zed"
        assert logger.get_active_language() == 'rust'

        # Check VS Code untitled file
        mock_win.title = "Untitled-1 - Visual Studio Code"
        assert logger.get_active_language() == 'vscode_untitled'

        # Check VS Code general window
        mock_win.title = "Welcome - Visual Studio Code"
        assert logger.get_active_language() == 'vscode'


def test_agent_zero_keystrokes_guard():
    agent = CodePulseAgent(dashboard_url='http://localhost:5000')

    with patch('agent.agent.requests.post') as mock_post:
        # Call send_data with 0 keystrokes
        agent.send_data(force=True)
        # Should NOT make any POST request
        assert not mock_post.called


def test_sentence_typing_detection():
    calc = FlowScoreCalculator()
    sentence_keys = [{'type': 'press', 'key': c} for c in "hello this is a test sentence how are you doing today"]

    session_data = {
        'typing_speed': 60.0,
        'backspace_rate': 0.02,
        'avg_pause': 0.6,
        'recent_keystrokes': sentence_keys
    }
    result = calc.calculate_flow_score(session_data)
    assert result['score'] == 0
    assert result['state'] == 'NOT_CODE'
    assert "Not detected as code" in result['suggestion']


def test_gibberish_typing_detection():
    calc = FlowScoreCalculator()
    gibberish_keys = [{'type': 'press', 'key': c} for c in "fvtrfrdes,x.zm/sr.efkmjd@qewasuoixjhxkyerhf"]

    session_data = {
        'typing_speed': 70.0,
        'backspace_rate': 0.05,
        'avg_pause': 0.8,
        'recent_keystrokes': gibberish_keys
    }
    result = calc.calculate_flow_score(session_data)
    assert result['score'] == 0
    assert result['state'] == 'NOT_CODE'
    assert "Not detected as code" in result['suggestion']


def test_real_code_typing():
    calc = FlowScoreCalculator()
    code_keys = [{'type': 'press', 'key': c} for c in 'def hello():\n    print("Hello World")']

    session_data = {
        'typing_speed': 45.0,
        'backspace_rate': 0.06,
        'avg_pause': 1.2,
        'recent_keystrokes': code_keys
    }
    result = calc.calculate_flow_score(session_data)
    assert 60 <= result['score'] <= 85
    assert result['state'] in ('PRODUCTIVE', 'WORKING', 'FLOW_STATE')


def test_fast_real_code_typing():
    calc = FlowScoreCalculator()
    fast_code_keys = [{'type': 'press', 'key': c} for c in 'def calculate_sum(a, b):\n    return a + b\n\nclass DataProcessor:\n    pass\n']

    session_data = {
        'typing_speed': 85.0,
        'backspace_rate': 0.02,
        'avg_pause': 0.4,
        'recent_edit_distance': 0,
        'std_dev_flight_time': 0.05,
        'recent_keystrokes': fast_code_keys
    }
    result = calc.calculate_flow_score(session_data)
    assert 80 <= result['score'] <= 98
    assert result['state'] in ('FLOW_STATE', 'PRODUCTIVE')


def test_agent_copy_paste_penalty_realtime():
    agent = CodePulseAgent(dashboard_url='http://localhost:5000')

    now = time.time()
    agent.logger.keystrokes = [
        {'type': 'press', 'key': 'x', 'timestamp': now - 10, 'flight_time': 0.2, 'dwell_time': 0.1, 'session_id': agent.session_id},
        {'type': 'press', 'key': 'y', 'timestamp': now, 'flight_time': 0.3, 'dwell_time': 0.1, 'session_id': agent.session_id}
    ]
    # 5 pastes in last 30 seconds -> penalty is 45
    agent.logger.copy_paste_events = [
        {'type': 'paste', 'timestamp': now - i * 5, 'session_id': agent.session_id}
        for i in range(5)
    ]

    with patch('agent.agent.requests.post') as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        agent.send_data()
        assert mock_post.called
        payload = mock_post.call_args[1]['json']
        flow_score_data = payload['flow_score']
        # 5 pastes penalty is 45, so penalty was applied
        assert flow_score_data.get('ai_penalty_applied') is True
        assert 'penalty: -45' in flow_score_data['suggestion'].lower()
        assert payload.get('paste_penalty') == 45


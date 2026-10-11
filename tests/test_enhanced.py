"""
Unit tests for CodePulse enhanced features:
- Expanded CODING_APPS
- get_active_language() and get_language_stats()
- Flow score breakdown in agent output
- DeveloperFingerprinter
- Integration with api.py
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from agent.logger import KeystrokeLogger, is_coding_app_active, CODING_APPS
from agent.fingerprint import DeveloperFingerprinter
from agent.code_tracker import CodeTracker
from agent.agent import CodePulseAgent


def test_expanded_coding_apps():
    # Verify desktop and web platforms are in the expanded list
    assert 'eclipse' in CODING_APPS
    assert 'notepad' in CODING_APPS
    assert 'android studio' in CODING_APPS
    assert 'codeforces' in CODING_APPS
    assert 'kaggle' in CODING_APPS


def test_language_detection():
    logger = KeystrokeLogger(session_id="test_lang_sess")

    with patch('agent.logger.gw') as mock_gw:
        # 1. Python file
        mock_win = MagicMock()
        mock_win.title = "test_script.py - VS Code"
        mock_gw.getActiveWindow.return_value = mock_win
        assert logger.get_active_language() == 'python'

        # 2. C++ file
        mock_win.title = "solution.cpp - Codeforces"
        mock_gw.getActiveWindow.return_value = mock_win
        assert logger.get_active_language() == 'cpp'

        # 3. Web platform without extension
        mock_win.title = "Problem A - Codeforces"
        mock_gw.getActiveWindow.return_value = mock_win
        assert logger.get_active_language() in ('competitive', 'multi')


def test_language_stats_collection():
    logger = KeystrokeLogger(session_id="test_lang_stats")

    with patch('agent.logger.is_coding_app_active', return_value=True):
        with patch.object(logger, 'get_active_language', side_effect=['python', 'python', 'javascript']):
            k = MagicMock()
            k.char = 'a'
            logger.on_press(k)
            logger.on_press(k)
            logger.on_press(k)

            stats = logger.get_language_stats()
            assert stats.get('python') == 2
            assert stats.get('javascript') == 1


def test_fingerprint_generation():
    df = DeveloperFingerprinter()
    stats = {'avg_flight_time': 0.15, 'session_duration': 30.0, 'presses': 50}
    code_stats = {'avg_edit_distance': 10}

    features = df.extract_features(stats, code_stats)
    fp = df.generate_fingerprint(features)
    assert len(fp) == 16
    assert isinstance(fp, str)

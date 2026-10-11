"""
Unit tests for CodePulse Features:
- CodeTracker (update_code, get_evolution_stats, save_snapshots)
- DeveloperFingerprinter (extract_features, generate_fingerprint, compare_fingerprints, identify_user)
- Agent integration & /api/users endpoint
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch

from agent.code_tracker import CodeTracker, levenshtein_distance
from agent.fingerprint import DeveloperFingerprinter
from agent.agent import CodePulseAgent
from backend.app import app
from backend.database import init_db


def test_code_tracker_save_snapshots(tmp_path):
    tracker = CodeTracker(session_id="test_snap_sess", snapshot_interval=0.0)
    tracker.update_code("def add(a, b): return a + b")
    tracker.update_code("def add(a, b): return a + b + 1")

    stats = tracker.get_evolution_stats()
    assert stats['total_snapshots'] == 2
    assert stats['total_changes'] == 1

    temp_file = str(tmp_path / "test_snapshots.json")
    tracker.save_snapshots(filename=temp_file)
    assert os.path.exists(temp_file)
    with open(temp_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert len(data) == 2


def test_developer_fingerprinter():
    df = DeveloperFingerprinter()
    keystroke_stats = {
        'flight_times': [0.12, 0.15, 0.11],
        'avg_flight_time': 0.1267,
        'presses': 120,
        'session_duration': 60.0,
        'backspace_rate': 0.05,
        'wpm': 24.0
    }
    code_stats = {
        'avg_edit_distance': 12.5,
        'indentation_style': 'space'
    }

    features = df.extract_features(keystroke_stats, code_stats)
    assert 'avg_flight_time' in features
    assert 'avg_dwell_time' in features
    assert 'typing_speed' in features
    assert 'avg_edit_distance' in features
    assert features['typing_speed'] == 24.0

    # 16 char SHA-256 fingerprint
    fp = df.generate_fingerprint(features)
    assert len(fp) == 16
    assert isinstance(fp, str)

    # Determinism
    fp2 = df.generate_fingerprint(features)
    assert fp == fp2

    # Compare identical
    comp = df.compare_fingerprints(fp, fp)
    assert comp['similarity'] == 100.0
    assert comp['is_match'] is True

    # User identification
    known = {
        'dev_alice': {'fingerprint': fp},
        'dev_bob': {'fingerprint': '0000000000000000'}
    }
    matched_user = df.identify_user(features, known)
    assert matched_user == 'dev_alice'


def test_api_submit_with_fingerprint_and_get_users():
    init_db()
    client = app.test_client()

    payload = {
        'session_id': 'sess_fp_test_123',
        'user_id': 'user_tester_99',
        'fingerprint': 'a1b2c3d4e5f67890',
        'features': {'typing_speed': 45.0},
        'flow_score': {'score': 80.0, 'state': 'PRODUCTIVE'}
    }

    res = client.post('/api/submit', json=payload)
    assert res.status_code == 201

    # Verify /api/users returns stored user with fingerprint
    users_res = client.get('/api/users')
    assert users_res.status_code == 200
    users_data = users_res.get_json()
    assert users_data['status'] == 'success'
    assert any(u['fingerprint'] == 'a1b2c3d4e5f67890' for u in users_data['users'])

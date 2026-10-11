"""
Unit tests for CodePulse Reports & Analytics:
- ReportGenerator (generate_session_pdf, generate_weekly_summary_pdf)
- Endpoints:
  * /api/report/<session_id>
  * /api/export/<session_id>.pdf
  * /api/export/weekly.pdf
  * /api/analytics/weekly
  * /api/analytics/monthly
"""

import os
import json
import pytest
from backend.app import app
from backend.database import init_db
from backend.reports import ReportGenerator

@pytest.fixture
def client():
    app.config['TESTING'] = True
    init_db()
    with app.test_client() as c:
        yield c

def test_report_generator_session_pdf(tmp_path):
    gen = ReportGenerator(data_dir=str(tmp_path))
    session_data = {
        'session_id': 'test_sess_pdf_01',
        'timestamp': '2026-09-28T14:00:00',
        'keystroke_stats': {
            'total_events': 150,
            'presses': 75,
            'session_duration': 120.0,
            'wpm': 40.0,
            'backspace_rate': 0.05
        },
        'flow_score': {
            'score': 82.5,
            'state': 'FLOW_STATE',
            'components': {'speed': 80, 'accuracy': 85, 'focus': 80, 'clarity': 85, 'consistency': 80}
        },
        'code_stats': {'total_changes': 4, 'avg_edit_distance': 15.0, 'avg_similarity': 0.95},
        'copy_paste_stats': {'total_copy': 1, 'total_paste': 2, 'is_suspicious': False},
        'language_stats': {'python': 75},
        'fingerprint': 'fedcba9876543210'
    }

    pdf_out = str(tmp_path / "test_report.pdf")
    gen.generate_session_pdf('test_sess_pdf_01', session_data=session_data, output_path=pdf_out)
    assert os.path.exists(pdf_out)
    assert os.path.getsize(pdf_out) > 1000

def test_report_generator_weekly_pdf(tmp_path):
    # Create sample session file
    sample_session = {
        'session_id': 'sess_week_01',
        'timestamp': '2026-09-28T14:00:00',
        'keystroke_stats': {'session_duration': 60.0, 'total_events': 50},
        'flow_score': {'score': 75.0, 'state': 'PRODUCTIVE'}
    }
    with open(tmp_path / "session_sess_week_01.json", 'w', encoding='utf-8') as f:
        json.dump(sample_session, f)

    gen = ReportGenerator(data_dir=str(tmp_path))
    weekly_pdf = str(tmp_path / "test_weekly.pdf")
    gen.generate_weekly_summary_pdf(days=7, output_path=weekly_pdf)
    assert os.path.exists(weekly_pdf)
    assert os.path.getsize(weekly_pdf) > 1000

def test_api_report_and_analytics_endpoints(client):
    # 1. Weekly analytics
    res = client.get('/api/analytics/weekly')
    assert res.status_code == 200
    data = res.get_json()
    assert 'sessions_count' in data
    assert 'avg_flow_score' in data
    assert 'best_day' in data
    assert 'daily_scores' in data

    # 2. Monthly analytics
    m_res = client.get('/api/analytics/monthly')
    assert m_res.status_code == 200
    m_data = m_res.get_json()
    assert 'sessions_count' in m_data

    # 3. Weekly PDF export
    export_weekly = client.get('/api/export/weekly.pdf')
    assert export_weekly.status_code == 200
    assert export_weekly.mimetype == 'application/pdf'
    assert len(export_weekly.get_data()) > 1000

import pytest
from backend.app import app
from backend.database import init_db, get_db

@pytest.fixture
def client():
    app.config['TESTING'] = True
    init_db()
    with app.test_client() as client:
        yield client

def test_health(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data.get('status') == 'healthy'
    assert 'timestamp' in data

def test_live_initial(client):
    res = client.get('/api/live')
    assert res.status_code == 200
    data = res.get_json()
    assert 'flow_score' in data
    assert 'components' in data
    assert 'state' in data

def test_submit_and_live(client):
    payload = {
        'session_id': 'test_pytest_001',
        'timestamp': '2026-09-27T18:00:00',
        'user_id': 'user_tester',
        'flow_score': {
            'score': 82.4,
            'state': 'FLOW',
            'suggestion': 'Peak flow achieved!',
            'components': {'speed': 80.0, 'accuracy': 90.0, 'focus': 85.0, 'clarity': 80.0, 'consistency': 75.0}
        },
        'keystroke_stats': {
            'presses': 100,
            'total_events': 200,
            'session_duration': 60.0
        },
        'keystrokes_sample': [
            {'key': 'x', 'press_time': 1.0, 'release_time': 1.1, 'flight_time': 0.1, 'dwell_time': 0.1}
        ]
    }
    res = client.post('/api/submit', json=payload)
    assert res.status_code == 201
    
    live_res = client.get('/api/live')
    live_data = live_res.get_json()
    assert live_data['flow_score'] == 82.4
    assert live_data['state'] == 'FLOW'
    assert live_data['wpm'] == 20.0

def test_sessions_list_and_get(client):
    res = client.get('/api/sessions')
    assert res.status_code == 200
    data = res.get_json()
    assert 'sessions' in data
    assert 'total' in data

    single_res = client.get('/api/session/test_pytest_001')
    assert single_res.status_code in [200, 404]

def test_clear_data(client):
    res = client.post('/api/clear')
    assert res.status_code == 200
    live_res = client.get('/api/live')
    assert live_res.get_json()['flow_score'] == 0

def test_index_route(client):
    res = client.get('/')
    assert res.status_code == 200


def test_clear_sessions(client, tmp_path):
    import os
    from backend.routes.api import DATA_DIR
    os.makedirs(DATA_DIR, exist_ok=True)
    dummy_session = os.path.join(DATA_DIR, 'session_test_clear_dummy.json')
    with open(dummy_session, 'w', encoding='utf-8') as f:
        f.write('{"test": true}')

    assert os.path.exists(dummy_session)
    res = client.post('/api/clear-sessions')
    assert res.status_code == 200
    data = res.get_json()
    assert data.get('status') == 'cleared'
    assert data.get('deleted') >= 1
    assert not os.path.exists(dummy_session)

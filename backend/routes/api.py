"""
CodePulse REST API Endpoints
Blueprint for receiving telemetry, serving live data, and managing sessions.
"""

import os
import glob
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from backend.database import get_db

logger = logging.getLogger(__name__)

api = Blueprint('api', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# In-memory store for real-time dashboard updates
latest_data = {
    'flow_score': 0,
    'state': 'IDLE',
    'suggestion': 'Start typing to see your flow score!',
    'components': {
        'speed': 0.0,
        'accuracy': 0.0,
        'focus': 0.0,
        'clarity': 0.0,
        'consistency': 0.0
    },
    'keystrokes': 0,
    'session_time': 0.0,
    'wpm': 0.0
}


@api.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    }), 200


@api.route('/live', methods=['GET'])
def get_live():
    """Return latest in-memory developer telemetry"""
    response_data = dict(latest_data)
    response_data['timestamp'] = datetime.now().isoformat()
    return jsonify(response_data), 200


@api.route('/submit', methods=['POST'])
def submit():
    """
    Receive JSON from telemetry agent, update latest_data,
    and persist record to SQLite database and data/ directory.
    """
    global latest_data

    payload = request.get_json(silent=True)
    if not payload or not isinstance(payload, dict):
        return jsonify({'error': 'Invalid or missing JSON payload'}), 400

    try:
        session_id = payload.get('session_id') or datetime.now().strftime('%Y%m%d_%H%M%S')
        user_id = payload.get('user_id', 'default_user')
        timestamp = payload.get('timestamp') or datetime.now().isoformat()

        # Parse flow score information
        flow_raw = payload.get('flow_score', {})
        if isinstance(flow_raw, dict):
            score = float(flow_raw.get('score', 0))
            state = str(flow_raw.get('state', 'WORKING'))
            suggestion = str(flow_raw.get('suggestion', 'Keep coding!'))
            components = flow_raw.get('components', {
                'speed': 0.0, 'accuracy': 0.0, 'focus': 0.0, 'clarity': 0.0, 'consistency': 0.0
            })
        else:
            try:
                score = float(flow_raw)
            except (ValueError, TypeError):
                score = 0.0
            state = str(payload.get('state', 'WORKING'))
            suggestion = str(payload.get('suggestion', 'Keep coding!'))
            components = payload.get('components', {
                'speed': 0.0, 'accuracy': 0.0, 'focus': 0.0, 'clarity': 0.0, 'consistency': 0.0
            })

        # Parse keystroke stats and calculate WPM/session_time
        stats = payload.get('keystroke_stats', {})
        if isinstance(stats, dict) and stats:
            keystrokes = stats.get('total_events', stats.get('presses', 0))
            session_time = float(stats.get('session_duration', 0))
            presses = stats.get('presses', 0)
            if session_time > 0:
                wpm = (presses / 5.0) / (session_time / 60.0)
            else:
                wpm = 0.0
        else:
            keystrokes = int(payload.get('keystrokes', latest_data.get('keystrokes', 0)))
            session_time = float(payload.get('session_time', latest_data.get('session_time', 0.0)))
            wpm = float(payload.get('wpm', latest_data.get('wpm', 0.0)))

        # Update in-memory real-time state
        latest_data.update({
            'flow_score': round(score, 1),
            'state': state,
            'suggestion': suggestion,
            'components': components,
            'keystrokes': keystrokes,
            'session_time': round(session_time, 1),
            'wpm': round(wpm, 1)
        })

        # Save to SQLite database
        conn = get_db()
        cursor = conn.cursor()
        try:
            # 1. Update or Insert Session
            cursor.execute('SELECT id, start_time FROM sessions WHERE session_id = ?', (session_id,))
            existing_session = cursor.fetchone()
            if existing_session:
                cursor.execute('''
                    UPDATE sessions
                    SET end_time = ?, duration = ?
                    WHERE session_id = ?
                ''', (timestamp, session_time, session_id))
            else:
                cursor.execute('''
                    INSERT INTO sessions (session_id, user_id, start_time, end_time, duration)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_id, user_id, timestamp, timestamp, session_time))

            # 2. Insert Flow Score Record
            speed_val = components.get('speed', 0.0) if isinstance(components, dict) else 0.0
            acc_val = components.get('accuracy', 0.0) if isinstance(components, dict) else 0.0
            focus_val = components.get('focus', 0.0) if isinstance(components, dict) else 0.0
            clarity_val = components.get('clarity', 0.0) if isinstance(components, dict) else 0.0
            consistency_val = components.get('consistency', 0.0) if isinstance(components, dict) else 0.0

            cursor.execute('''
                INSERT INTO flow_scores (
                    session_id, score, state, speed, accuracy,
                    focus, clarity, consistency, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id, score, state, speed_val, acc_val,
                focus_val, clarity_val, consistency_val, timestamp
            ))

            # 3. Insert keystroke samples if present
            keystrokes_list = payload.get('keystrokes_sample') or payload.get('keystrokes_data', [])
            if isinstance(keystrokes_list, list):
                for item in keystrokes_list:
                    if isinstance(item, dict):
                        cursor.execute('''
                            INSERT INTO keystrokes (
                                session_id, key, press_time, release_time, flight_time, dwell_time
                            )
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            session_id,
                            str(item.get('key', '')),
                            float(item.get('press_time', 0.0) or 0.0),
                            float(item.get('release_time', 0.0) or 0.0),
                            float(item.get('flight_time', 0.0) or 0.0),
                            float(item.get('dwell_time', 0.0) or 0.0)
                        ))

            conn.commit()
        except Exception as db_err:
            conn.rollback()
            logger.error(f"Database error during submit: {db_err}")
            raise
        finally:
            conn.close()

        # Save session file in data/ directory
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
        session_file_path = os.path.join(DATA_DIR, f'session_{session_id}.json')
        with open(session_file_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)

        return jsonify({
            'status': 'success',
            'message': 'Telemetry saved successfully',
            'session_id': session_id,
            'timestamp': timestamp
        }), 201

    except Exception as e:
        logger.exception("Error processing /api/submit")
        return jsonify({'error': str(e)}), 500


@api.route('/sessions', methods=['GET'])
def get_sessions():
    """List all session files from data/ folder with summary metrics"""
    sessions = []
    if not os.path.exists(DATA_DIR):
        return jsonify({'sessions': [], 'total': 0, 'timestamp': datetime.now().isoformat()}), 200

    session_files = glob.glob(os.path.join(DATA_DIR, '*.json'))
    for file_path in session_files:
        try:
            stat = os.stat(file_path)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                entry_count = len(data)
                last_entry = data[-1] if data else {}
                flow_val = last_entry.get('flow_score', {})
                flow_score = flow_val.get('score', 0) if isinstance(flow_val, dict) else flow_val
                session_id = last_entry.get('session_id', os.path.splitext(os.path.basename(file_path))[0])
            elif isinstance(data, dict):
                entry_count = 1
                flow_val = data.get('flow_score', {})
                flow_score = flow_val.get('score', 0) if isinstance(flow_val, dict) else flow_val
                session_id = data.get('session_id', os.path.splitext(os.path.basename(file_path))[0])
            else:
                entry_count = 0
                flow_score = 0
                session_id = os.path.splitext(os.path.basename(file_path))[0]

            sessions.append({
                'filename': os.path.basename(file_path),
                'session_id': str(session_id),
                'entries': entry_count,
                'flow_score': flow_score,
                'size_bytes': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        except Exception as parse_err:
            logger.warning(f"Skipping malformed session file {file_path}: {parse_err}")
            continue

    sessions.sort(key=lambda s: s['modified_at'], reverse=True)
    return jsonify({
        'sessions': sessions,
        'total': len(sessions),
        'timestamp': datetime.now().isoformat()
    }), 200


@api.route('/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """Return specific session by ID or filename from data/ or database"""
    # 1. Try file in data/
    clean_id = os.path.basename(session_id)
    candidate_paths = [
        os.path.join(DATA_DIR, clean_id),
        os.path.join(DATA_DIR, f"{clean_id}.json"),
        os.path.join(DATA_DIR, f"session_{clean_id}.json")
    ]

    for path in candidate_paths:
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                return jsonify({
                    'session_id': clean_id,
                    'source': 'file',
                    'data': content
                }), 200
            except Exception as e:
                return jsonify({'error': f'Failed reading session file: {e}'}), 500

    # 2. Try SQLite database
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT * FROM sessions WHERE session_id = ?', (clean_id,))
        session_row = cursor.fetchone()
        if session_row:
            cursor.execute('SELECT * FROM flow_scores WHERE session_id = ? ORDER BY id ASC', (clean_id,))
            flow_rows = [dict(r) for r in cursor.fetchall()]

            cursor.execute('SELECT * FROM keystrokes WHERE session_id = ? ORDER BY id ASC LIMIT 100', (clean_id,))
            keystroke_rows = [dict(r) for r in cursor.fetchall()]

            return jsonify({
                'session_id': clean_id,
                'source': 'database',
                'session': dict(session_row),
                'flow_scores': flow_rows,
                'keystrokes_sample': keystroke_rows
            }), 200
    except Exception as db_err:
        logger.error(f"Database lookup error for session {clean_id}: {db_err}")
    finally:
        conn.close()

    return jsonify({'error': f'Session {session_id} not found'}), 404


@api.route('/clear', methods=['POST'])
def clear_all():
    """Clear in-memory state and flush database records"""
    global latest_data

    # Reset in-memory telemetry
    latest_data = {
        'flow_score': 0,
        'state': 'IDLE',
        'suggestion': 'Start typing to see your flow score!',
        'components': {
            'speed': 0.0,
            'accuracy': 0.0,
            'focus': 0.0,
            'clarity': 0.0,
            'consistency': 0.0
        },
        'keystrokes': 0,
        'session_time': 0.0,
        'wpm': 0.0
    }

    # Reset database tables
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM keystrokes')
        cursor.execute('DELETE FROM flow_scores')
        cursor.execute('DELETE FROM sessions')
        conn.commit()
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Failed to clear database: {e}'}), 500
    finally:
        conn.close()

    return jsonify({
        'status': 'success',
        'message': 'All data cleared successfully'
    }), 200

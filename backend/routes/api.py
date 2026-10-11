"""
CodePulse REST API Endpoints
Blueprint for receiving telemetry, serving live data, and managing sessions.
"""

import os
import time
import glob
import json
import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file
from backend.database import get_db
from backend.reports import ReportGenerator

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
    'wpm': 0.0,
    'paste_penalty': 0
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
            if 'wpm' in stats:
                wpm = float(stats['wpm'])
            elif session_time > 0:
                flight_times = stats.get('flight_times', [])
                active_time = sum(flight_times) if flight_times else float(stats.get('active_time_seconds', session_time))
                if active_time < 1.0:
                    active_time = 1.0
                wpm = min(150.0, (presses / 5.0) / (active_time / 60.0))
            else:
                wpm = 0.0
        else:
            keystrokes = int(payload.get('keystrokes', latest_data.get('keystrokes', 0)))
            session_time = float(payload.get('session_time', latest_data.get('session_time', 0.0)))
            wpm = float(payload.get('wpm', latest_data.get('wpm', 0.0)))

        # Update in-memory real-time state
        paste_penalty_val = 0
        if isinstance(flow_raw, dict) and 'paste_penalty' in flow_raw:
            paste_penalty_val = flow_raw['paste_penalty']
        elif 'paste_penalty' in payload:
            paste_penalty_val = payload['paste_penalty']

        latest_data.update({
            'flow_score': round(score, 1),
            'state': state,
            'suggestion': suggestion,
            'components': components,
            'keystrokes': keystrokes,
            'session_time': round(session_time, 1),
            'wpm': round(wpm, 1),
            'paste_penalty': paste_penalty_val
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

            # 4. Insert or Ignore User Fingerprint
            fingerprint = payload.get('fingerprint')
            if fingerprint:
                user_id_to_store = payload.get('user_id') or session_id
                cursor.execute('''
                    INSERT OR IGNORE INTO users (user_id, fingerprint, created_at)
                    VALUES (?, ?, ?)
                ''', (user_id_to_store, str(fingerprint), timestamp))

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


@api.route('/clear-sessions', methods=['POST'])
def clear_sessions():
    """Deletes all session_*.json files in data/ directory"""
    session_files = glob.glob(os.path.join(DATA_DIR, 'session_*.json'))
    deleted_count = 0
    for file_path in session_files:
        try:
            os.remove(file_path)
            deleted_count += 1
        except Exception as e:
            logger.warning(f"Failed to delete {file_path}: {e}")

    return jsonify({
        'status': 'cleared',
        'deleted': deleted_count
    }), 200


last_agent_heartbeat = {
    'timestamp': None,
    'session_id': None
}


@api.route('/agent/heartbeat', methods=['POST', 'GET'])
def agent_heartbeat():
    """Agent sends heartbeat ping to confirm it is actively running and connected"""
    global last_agent_heartbeat
    data = request.get_json(silent=True) or {}
    last_agent_heartbeat['timestamp'] = time.time()
    last_agent_heartbeat['session_id'] = data.get('session_id')
    return jsonify({
        'status': 'ok',
        'active': True,
        'timestamp': datetime.now().isoformat()
    }), 200


@api.route('/agent/status', methods=['GET'])
def agent_status():
    """Check if agent is connected and recently active"""
    import time
    now = time.time()

    # 1. Check live heartbeat ping (within last 45 seconds)
    if last_agent_heartbeat.get('timestamp') and (now - last_agent_heartbeat['timestamp'] < 45):
        time_diff = now - last_agent_heartbeat['timestamp']
        return jsonify({
            'connected': True,
            'active': True,
            'heartbeat': True,
            'session_id': last_agent_heartbeat.get('session_id'),
            'seconds_ago': int(time_diff),
            'timestamp': datetime.fromtimestamp(last_agent_heartbeat['timestamp']).isoformat(),
            'message': 'Agent is connected and actively monitoring.'
        }), 200

    # 2. Check recent data files
    recent_files = glob.glob(os.path.join(DATA_DIR, '*.json'))
    if recent_files:
        latest = max(recent_files, key=os.path.getmtime)
        file_time = os.path.getmtime(latest)
        time_diff = now - file_time

        if time_diff < 300:
            return jsonify({
                'connected': True,
                'active': True,
                'last_data': os.path.basename(latest),
                'timestamp': datetime.fromtimestamp(file_time).isoformat(),
                'seconds_ago': int(time_diff)
            }), 200
        else:
            return jsonify({
                'connected': True,
                'active': False,
                'last_data': os.path.basename(latest),
                'timestamp': datetime.fromtimestamp(file_time).isoformat(),
                'seconds_ago': int(time_diff),
                'message': 'Agent is idle.'
            }), 200

    return jsonify({
        'connected': False,
        'active': False,
        'message': 'No data received from agent.'
    }), 200


@api.route('/users', methods=['GET'])
def get_users():
    """Returns list of all users from database with their fingerprints"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, user_id, fingerprint, created_at FROM users ORDER BY id DESC')
        users_list = [dict(row) for row in cursor.fetchall()]
        return jsonify({
            'status': 'success',
            'users': users_list,
            'total': len(users_list)
        }), 200
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


def _compute_analytics(days=7):
    """Computes session and flow analytics for the past N days."""
    cutoff = datetime.now() - timedelta(days=days)
    files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    sessions_in_window = []
    daily_buckets = {}
    for i in range(days):
        day_str = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        daily_buckets[day_str] = []

    for f in files:
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(f))
            if mtime >= cutoff:
                with open(f, 'r', encoding='utf-8') as handle:
                    data = json.load(handle)
                if isinstance(data, list):
                    data = data[-1] if data else {}
                if isinstance(data, dict):
                    data['_mtime'] = mtime
                    sessions_in_window.append(data)
                    day_key = mtime.strftime("%Y-%m-%d")
                    score = data.get('flow_score', {}).get('score', 0) if isinstance(data.get('flow_score'), dict) else data.get('flow_score', 0)
                    try:
                        score = float(score)
                    except (ValueError, TypeError):
                        score = 0.0
                    if day_key in daily_buckets:
                        daily_buckets[day_key].append(score)
        except Exception:
            continue

    total_duration = sum(s.get('keystroke_stats', {}).get('session_duration', 0) for s in sessions_in_window)
    scores = []
    for s in sessions_in_window:
        sc = s.get('flow_score', {}).get('score', 0) if isinstance(s.get('flow_score'), dict) else s.get('flow_score', 0)
        try:
            scores.append(float(sc))
        except (ValueError, TypeError):
            pass

    avg_flow = sum(scores) / len(scores) if scores else 0.0

    daily_scores = []
    best_day = "N/A"
    best_score = -1.0
    for day_str in sorted(daily_buckets.keys()):
        s_list = daily_buckets[day_str]
        d_avg = sum(s_list) / len(s_list) if s_list else 0.0
        daily_scores.append({
            'date': day_str,
            'score': round(d_avg, 1),
            'sessions': len(s_list)
        })
        if d_avg > best_score and len(s_list) > 0:
            best_score = d_avg
            best_day = day_str

    return {
        'sessions_count': len(sessions_in_window),
        'total_duration': round(total_duration, 1),
        'avg_flow_score': round(avg_flow, 1),
        'best_day': best_day,
        'daily_scores': daily_scores
    }


@api.route('/report/<session_id>', methods=['GET'])
def get_session_report(session_id):
    """Load session JSON from data/session_<session_id>.json and return full data"""
    clean_id = os.path.basename(session_id)
    candidates = [
        os.path.join(DATA_DIR, f"session_{clean_id}.json"),
        os.path.join(DATA_DIR, f"{clean_id}.json"),
        os.path.join(DATA_DIR, clean_id)
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return jsonify(data), 200
            except Exception as e:
                return jsonify({'error': f'Failed to read report: {e}'}), 500

    return jsonify({'error': f'Session {session_id} not found'}), 404


@api.route('/export/<session_id>.pdf', methods=['GET'])
def export_session_pdf(session_id):
    """Generate and return PDF for a specific session"""
    clean_id = os.path.basename(session_id)
    # Check if session data exists
    candidates = [
        os.path.join(DATA_DIR, f"session_{clean_id}.json"),
        os.path.join(DATA_DIR, f"{clean_id}.json"),
        os.path.join(DATA_DIR, clean_id)
    ]
    session_data = {}
    for path in candidates:
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                break
            except Exception:
                pass

    pdf_path = os.path.join(DATA_DIR, f"codepulse_report_{clean_id}.pdf")
    try:
        generator = ReportGenerator(data_dir=DATA_DIR)
        generator.generate_session_pdf(clean_id, session_data=session_data, output_path=pdf_path)
        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"codepulse_report_{clean_id}.pdf"
        )
    except Exception as e:
        logger.error(f"Error generating session PDF: {e}")
        return jsonify({'error': f'Failed to generate PDF: {e}'}), 500


@api.route('/export/weekly.pdf', methods=['GET'])
def export_weekly_pdf():
    """Generate and return weekly summary PDF"""
    pdf_path = os.path.join(DATA_DIR, "codepulse_weekly_report.pdf")
    try:
        generator = ReportGenerator(data_dir=DATA_DIR)
        generator.generate_weekly_summary_pdf(days=7, output_path=pdf_path)
        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name="codepulse_weekly_report.pdf"
        )
    except Exception as e:
        logger.error(f"Error generating weekly PDF: {e}")
        return jsonify({'error': f'Failed to generate weekly PDF: {e}'}), 500


@api.route('/analytics/weekly', methods=['GET'])
def weekly_analytics():
    """Return weekly telemetry analytics"""
    data = _compute_analytics(days=7)
    return jsonify(data), 200


@api.route('/analytics/monthly', methods=['GET'])
def monthly_analytics():
    """Return monthly telemetry analytics"""
    data = _compute_analytics(days=30)
    return jsonify(data), 200




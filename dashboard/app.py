"""
CodePulse Dashboard - Complete Web Application
Real-time Developer Intelligence Platform
"""

from flask import Flask, render_template, jsonify, request, send_file
import json
import os
import glob
import random
from datetime import datetime
import threading
import time

app = Flask(__name__)

# Configuration
DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Store latest data in memory for quick access
latest_data = {
    'flow_score': 0,
    'wpm': 0,
    'keystrokes': 0,
    'session_time': 0,
    'state': 'IDLE',
    'suggestion': 'Start typing to see your flow score!',
    'components': {
        'speed': 0,
        'accuracy': 0,
        'focus': 0,
        'clarity': 0,
        'consistency': 0
    }
}

# Store session data
sessions_data = {}

# ============================================
# ROUTES - Page Views
# ============================================

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Alternative dashboard route"""
    return render_template('index.html')

@app.route('/sessions')
def sessions_page():
    """Session history page"""
    return render_template('sessions.html')

@app.route('/analytics')
def analytics_page():
    """Detailed analytics page"""
    return render_template('analytics.html')

# ============================================
# API ROUTES - Data Endpoints
# ============================================

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'data_files': len(glob.glob(os.path.join(DATA_DIR, '*.json')))
    })

@app.route('/api/submit', methods=['POST'])
def submit_data():
    """Receive data from the agent"""
    global latest_data
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        # ✅ IMPORTANT: Update latest_data with received flow score
        flow_data = data.get('flow_score', {})
        if flow_data:
            latest_data['flow_score'] = flow_data.get('score', 72)
            latest_data['state'] = flow_data.get('state', 'WORKING')
            latest_data['suggestion'] = flow_data.get('suggestion', 'Keep coding!')
            latest_data['components'] = flow_data.get('components', latest_data['components'])
        
        # Update keystroke stats
        stats = data.get('keystroke_stats', {})
        if stats:
            latest_data['keystrokes'] = stats.get('total_events', 0)
            latest_data['session_time'] = stats.get('session_duration', 0)
            # Calculate WPM from presses and duration
            presses = stats.get('presses', 0)
            duration = stats.get('session_duration', 1)
            if duration > 0:
                latest_data['wpm'] = (presses / 5) / (duration / 60)
        
        # Save to file
        session_id = data.get('session_id', datetime.now().strftime('%Y%m%d_%H%M%S'))
        filename = os.path.join(DATA_DIR, f'session_{session_id}.json')
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({'status': 'success'}), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/live', methods=['GET'])
def live_data():
    """Get live monitoring data"""
    global latest_data
    
    return jsonify({
        'flow_score': latest_data.get('flow_score', 0),
        'wpm': latest_data.get('wpm', 0),
        'keystrokes': latest_data.get('keystrokes', 0),
        'session_time': latest_data.get('session_time', 0),
        'state': latest_data.get('state', 'IDLE'),
        'suggestion': latest_data.get('suggestion', 'Start typing to see your flow score!'),
        'components': latest_data.get('components', {}),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all sessions with summary"""
    sessions = []
    session_files = glob.glob(os.path.join(DATA_DIR, '*.json'))
    
    for file in session_files:
        try:
            with open(file, 'r') as f:
                data = json.load(f)
                
            # Get file stats
            file_stat = os.stat(file)
            
            # Count entries
            if isinstance(data, list):
                entry_count = len(data)
                # Get latest flow score if available
                latest_entry = data[-1] if data else {}
                flow_score = latest_entry.get('flow_score', {}).get('score', 0)
            else:
                entry_count = 1
                flow_score = data.get('flow_score', {}).get('score', 0)
            
            sessions.append({
                'filename': os.path.basename(file),
                'created': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                'entries': entry_count,
                'flow_score': flow_score,
                'size': file_stat.st_size
            })
        except Exception as e:
            continue
    
    # Sort by modified time (newest first)
    sessions.sort(key=lambda x: x['modified'], reverse=True)
    
    return jsonify({
        'sessions': sessions,
        'total': len(sessions),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/session/<filename>', methods=['GET'])
def get_session(filename):
    """Get specific session details"""
    filepath = os.path.join(DATA_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'Session not found'}), 404
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Calculate stats
        if isinstance(data, list):
            total_entries = len(data)
            # Get flow scores
            flow_scores = [entry.get('flow_score', {}).get('score', 0) for entry in data if entry.get('flow_score')]
            avg_flow = sum(flow_scores) / len(flow_scores) if flow_scores else 0
            
            # Get latest entry
            latest = data[-1] if data else {}
        else:
            total_entries = 1
            avg_flow = data.get('flow_score', {}).get('score', 0)
            latest = data
        
        return jsonify({
            'filename': filename,
            'total_entries': total_entries,
            'avg_flow_score': avg_flow,
            'latest': latest,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent/status', methods=['GET'])
def agent_status():
    """Check if agent is connected and sending data"""
    # Check if any recent data was received (within last 5 minutes)
    recent_files = glob.glob(os.path.join(DATA_DIR, '*.json'))
    
    if recent_files:
        latest = max(recent_files, key=os.path.getctime)
        file_time = os.path.getctime(latest)
        current_time = time.time()
        time_diff = current_time - file_time
        
        # If data received in last 5 minutes, agent is active
        if time_diff < 300:  # 5 minutes
            return jsonify({
                'connected': True,
                'active': True,
                'last_data': os.path.basename(latest),
                'timestamp': datetime.fromtimestamp(file_time).isoformat(),
                'seconds_ago': int(time_diff)
            })
        else:
            return jsonify({
                'connected': True,
                'active': False,
                'last_data': os.path.basename(latest),
                'timestamp': datetime.fromtimestamp(file_time).isoformat(),
                'seconds_ago': int(time_diff),
                'message': 'Agent is idle. Start a coding session!'
            })
    
    return jsonify({
        'connected': False,
        'active': False,
        'message': 'No data received from agent. Start the agent with: python agent.py'
    })

# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  🚀 CODEPULSE DASHBOARD                                 ║
    ║  Developer Intelligence Platform                       ║
    ║                                                         ║
    ║  📊 Dashboard: http://localhost:5000                   ║
    ║  📡 API: http://localhost:5000/api/health              ║
    ║                                                         ║
    ║  Press Ctrl+C to stop                                  ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
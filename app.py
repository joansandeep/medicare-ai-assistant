import os
import re
import logging
import random
from datetime import datetime, timedelta
import ipfshttpclient
import requests
from flask import (
    Flask, request, session, redirect, url_for,
    flash, render_template, jsonify
)
from functools import wraps
import mysql.connector
from mysql.connector import pooling, Error as MySQLError
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from src.pipeline import RAGPipeline
from flask import current_app
import PyPDF2




# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(name)s :: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("health-app")

# Diagnostic mode (more explicit flash messages). Set False in production.
DIAGNOSTIC_MODE = True

# ============================================================
# CONFIG HELPERS
# ============================================================
def env(name, default=None):
    return os.environ.get(name, default)

# Load .env file if it exists (for local development only)
try:
    from dotenv import load_dotenv
    # Only load .env in development, not in production
    if not env('RAILWAY_ENVIRONMENT') and not env('RENDER'):
        env_paths = ['.env', '../.env', 'Website/.env']
        env_loaded = False
        
        for path in env_paths:
            if os.path.exists(path):
                load_dotenv(path)
                logger.info(f"✅ Environment variables loaded from {path}")
                env_loaded = True
                break
        
        if not env_loaded:
            logger.warning("⚠️ No .env file found. Using environment variables.")
    else:
        logger.info("🚀 Production environment detected - using environment variables")
        
except ImportError:
    logger.warning("⚠️ python-dotenv not installed. Using environment variables only.")
except Exception as e:
    logger.warning(f"⚠️ Could not load .env file: {e}")

# Production-ready database configuration
DB_CONFIG = {
    'host': env('DB_HOST', 'localhost'),
    'user': env('DB_USER', 'root'),
    'password': env('DB_PASSWORD'),
    'database': env('DB_NAME', 'hospital'),
    'port': int(env('DB_PORT', '3306')),  # Added port support
    'autocommit': True,
    'pool_name': 'mypool',
    'pool_size': int(env('DB_POOL_SIZE', '5')),
    'connect_timeout': int(env('DB_TIMEOUT', '10'))
}

# Use a secure secret key from environment
SECRET_KEY = env('SECRET_KEY') or env('FLASK_SECRET_KEY')
if not SECRET_KEY:
    # Generate a random secret key for development
    import secrets
    SECRET_KEY = secrets.token_hex(32)
    logger.warning("⚠️ Using generated secret key. Set SECRET_KEY environment variable for production.")

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(days=7)

# Production settings
if env('RAILWAY_ENVIRONMENT') or env('RENDER') or env('HEROKU') or env('RENDER_SERVICE_NAME'):
    app.config['DEBUG'] = False
    DIAGNOSTIC_MODE = False
    logger.info("🚀 Running in production mode")
else:
    app.config['DEBUG'] = True
    logger.info("🔧 Running in development mode")

# ============================================================
# DB POOL / CONNECTION
# ============================================================
pool = None
try:
    if DB_CONFIG.get('password'):
        pool = pooling.MySQLConnectionPool(**DB_CONFIG)
        logger.info("✅ Database connection pool created successfully")
    else:
        logger.warning("DB_PASSWORD not set; skipping pool creation and using direct connection fallback.")
except MySQLError as err:
    logger.error(f"❌ DB pool creation failed: {err}. Using direct connection fallback.")

def direct_connect():
    # Production-ready connection without hardcoded passwords
    password = DB_CONFIG.get('password') or env('DB_PASSWORD')
    
    if not password:
        logger.error("❌ DB_PASSWORD environment variable not set")
        return None
    
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=password,
            database=DB_CONFIG['database'],
            port=DB_CONFIG['port'],  # Added port
            autocommit=True,
            connect_timeout=DB_CONFIG['connect_timeout']
        )
        if conn.is_connected():
            return conn
    except MySQLError as e:
        logger.error(f"Database connection failed: {e}")
        return None

def get_db_connection():
    if pool:
        try:
            return pool.get_connection()
        except MySQLError as e:
            logger.error(f"Pool get_connection error: {e}")
    return direct_connect()

# ============================================================
# DECORATORS
# ============================================================
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def column_exists(cursor, table, column):
    cursor.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (column,))
    return cursor.fetchone() is not None

# ============================================================
# SYNTHETIC METRICS (used by /api/health_metrics)
# ============================================================
def synthesize_reading(prev=None):
    def clamp(val, lo, hi): return max(lo, min(hi, val))
    if prev:
        hr = clamp(prev['heart_rate'] + random.randint(-4, 4), 58, 95)
    else:
        hr = random.randint(62, 85)
    blood_sugar = random.randint(85, 120)
    systolic = random.randint(108, 124)
    diastolic = random.randint(70, 82)
    temperature = round(random.uniform(36.5, 37.2), 1)
    spo2 = random.randint(96, 99)
    respiration = random.randint(12, 18)
    return {
        'heart_rate': hr,
        'blood_sugar': blood_sugar,
        'systolic': systolic,
        'diastolic': diastolic,
        'temperature': temperature,
        'spo2': spo2,
        'respiration': respiration
    }

def compute_health_score(avg_hr, avg_blood_sugar, avg_temp, avg_spo2):
    avg_hr = float(avg_hr) if avg_hr is not None else 0.0
    avg_blood_sugar = float(avg_blood_sugar) if avg_blood_sugar is not None else 0.0
    avg_temp = float(avg_temp) if avg_temp is not None else 0.0
    avg_spo2 = float(avg_spo2) if avg_spo2 is not None else 0.0

    score = 100.0
    if avg_hr > 85:
        score -= (avg_hr - 85) * 0.9
    if avg_hr < 60:
        score -= (60 - avg_hr) * 0.6

    if avg_blood_sugar > 126:
        score -= (avg_blood_sugar - 126) * 0.8
    elif avg_blood_sugar > 100:
        score -= (avg_blood_sugar - 100) * 0.4
    if avg_blood_sugar < 70:
        score -= (70 - avg_blood_sugar) * 1.0

    if avg_temp > 37.3:
        score -= (avg_temp - 37.3) * 12
    if avg_temp < 36.2:
        score -= (36.2 - avg_temp) * 10

    score += (avg_spo2 - 96) * 1.0
    return max(40.0, min(100.0, round(score, 1)))

def generate_fallback_daily():
    """Generate 7 days of synthetic daily data"""
    import random
    from datetime import date, timedelta
    
    data = []
    for i in range(7):
        day = date.today() - timedelta(days=6-i)
        data.append({
            'date': day.strftime('%Y-%m-%d'),
            'heart_rate': round(random.uniform(65, 85), 1),
            'temperature': round(random.uniform(36.4, 37.1), 1)
        })
    return data

def generate_fallback_trends():
    """Generate 7 days of synthetic trend data"""
    import random
    from datetime import date, timedelta
    
    data = []
    for i in range(7):
        day = date.today() - timedelta(days=6-i)
        data.append({
            'date': day.strftime('%m-%d'),
            'health_score': round(random.uniform(65, 85), 1)
        })
    return data

# ============================================================
# DB INITIALIZATION
# ============================================================
def init_db():
    conn = get_db_connection()
    if not conn:
        logger.error("❌ Cannot initialize database - no connection")
        return
    try:
        cur = conn.cursor()
        # Users table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            full_name VARCHAR(100),
            role VARCHAR(20) DEFAULT 'patient',
            phone VARCHAR(20),
            dob DATE,
            gender VARCHAR(20),
            address TEXT,
            blood_group VARCHAR(5),
            medical_conditions TEXT,
            allergies TEXT,
            medications TEXT,
            height INT,
            weight INT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME NULL,
            login_attempts INT DEFAULT 0,
            account_locked TINYINT DEFAULT 0,
            lock_until DATETIME NULL,
            UNIQUE INDEX idx_username (username),
            UNIQUE INDEX idx_email (email)
        ) ENGINE=InnoDB
        """)
        
        # Health metrics table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_health_metrics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            recorded_at DATETIME NOT NULL,
            heart_rate INT NOT NULL,
            blood_sugar INT DEFAULT NULL,
            systolic INT NOT NULL,
            diastolic INT NOT NULL,
            temperature DECIMAL(4,1) NOT NULL,
            spo2 TINYINT NOT NULL,
            respiration TINYINT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_time (user_id, recorded_at)
        ) ENGINE=InnoDB
        """)

        # Medicine requests table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS medicine_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            medicine_name VARCHAR(100) NOT NULL,
            quantity INT NOT NULL,
            status ENUM('pending','approved','rejected','completed') DEFAULT 'pending',
            request_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
        """)

        # Emergency contacts table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS emergency_contacts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            relationship VARCHAR(50),
            phone VARCHAR(30) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB
        """)

        # Uploaded files table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            filename VARCHAR(255),
            cid VARCHAR(255),
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
        """)

        # Chat history table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            session_id VARCHAR(255) NOT NULL,
            message_type ENUM('user', 'ai') NOT NULL,
            message_content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            pdf_cid VARCHAR(255) DEFAULT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_session (user_id, session_id),
            INDEX idx_timestamp (timestamp)
        ) ENGINE=InnoDB
        """)

        # Default users
        defaults = [
            ('admin', 'admin@hospital.com', 'admin123', 'Administrator', 'admin'),
            ('demo', 'demo@hospital.com', 'demo123', 'Demo User', 'patient'),
            ('AlbinBiju', 'albin@hospital.com', 'password123', 'Albin Biju', 'patient')
        ]
        
        for username, email, plain_pw, full_name, role in defaults:
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO users (username,email,password,full_name,role,created_at,last_login)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (
                    username, email, generate_password_hash(plain_pw),
                    full_name, role, datetime.now(), datetime.now()
                ))
                logger.info(f"✅ Default user created: {username}")

        conn.commit()
        logger.info("✅ Database initialization completed successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

# ============================================================
# SITE PROTECTION
# ============================================================
# CSRF protection is disabled

# ============================================================
# CONTEXT PROCESSOR
# ============================================================
@app.context_processor
def inject_user():
    now = datetime.now()
    base = {
        'current_time': now.strftime('%Y-%m-%d %H:%M:%S'),
        'current_date': now.strftime('%A, %B %d, %Y'),
        'is_logged_in': 'user_id' in session
    }
    if 'user_id' in session:
        base.update({
            'session': session,
            'display_username': session.get('username'),
            'user_full_name': session.get('full_name') or session.get('username')
        })
    base['ipfs_gateway_base'] = (env('IPFS_GATEWAY_BASE') or
                                 ('https://gateway.pinata.cloud' if (env('PINATA_API_KEY') and env('PINATA_SECRET_KEY')) else 'https://ipfs.io'))
    return base

# ============================================================
# ROUTES: AUTH
# ============================================================
@app.route('/')
def index():
    return redirect(url_for('home_dashboard') if 'user_id' in session else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home_dashboard'))

    if request.method == 'POST':
        username_or_email = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username_or_email or not password:
            flash('Please provide both username and password', 'error')
            return render_template('login.html')

        conn = get_db_connection()
        if not conn:
            flash('Database connection failed. Try again later.', 'error')
            return render_template('login.html')

        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT * FROM users 
                WHERE username=%s OR email=%s
                LIMIT 1
            """, (username_or_email, username_or_email))
            user = cur.fetchone()

            if not user:
                flash('User not found' if DIAGNOSTIC_MODE else 'Invalid username or password', 'error')
                return render_template('login.html')

            if not check_password_hash(user['password'], password):
                flash('Password incorrect' if DIAGNOSTIC_MODE else 'Invalid username or password', 'error')
                return render_template('login.html')

            # Success
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            session['role'] = user['role']
            session['full_name'] = user['full_name'] or user['username']

            if request.form.get('remember') == 'on':
                session.permanent = True

            cur.execute("UPDATE users SET last_login=%s, login_attempts=0 WHERE id=%s",
                        (datetime.now(), user['id']))
            conn.commit()

            flash(f"Welcome back, {user['username']}!", 'success')
            return redirect(url_for('home_dashboard'))
        except Exception as e:
            logger.exception(f"[LOGIN] Exception: {e}")
            flash('Unexpected error during login', 'error')
        finally:
            try:
                cur.close()
                conn.close()
            except:
                pass

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home_dashboard'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        full_name = (request.form.get('full_name') or request.form.get('fullName') or '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '') or request.form.get('confirmPassword', '')

        errors = []
        if not username: errors.append("Username required")
        if not email: errors.append("Email required")
        if not password: errors.append("Password required")
        if password != confirm_password: errors.append("Passwords do not match")
        if password and len(password) < 6: errors.append("Password too short (<6)")
        if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email): errors.append("Invalid email")

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('register.html')

        conn = get_db_connection()
        if not conn:
            flash('Database connection failed. Try again.', 'error')
            return render_template('register.html')

        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id FROM users WHERE username=%s OR email=%s", (username, email))
            if cur.fetchone():
                flash('Username or Email already exists', 'error')
                return render_template('register.html')

            hashed = generate_password_hash(password)
            cur.execute("""
                INSERT INTO users (username,email,password,full_name,role,created_at)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (username, email, hashed, full_name or username, 'patient', datetime.now()))
            conn.commit()

            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            logger.exception(f"[REGISTER] Exception: {e}")
            flash('Registration failed due to error', 'error')
        finally:
            try:
                cur.close()
                conn.close()
            except:
                pass

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    uname = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye, {uname}!', 'success')
    return redirect(url_for('login'))

# ============================================================
# DASHBOARD & OTHER PAGES
# ============================================================
@app.route('/dashboard')
@login_required
def home_dashboard():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
@login_required
def contact():
    return render_template('contact.html')

@app.route('/chatbot')
@login_required
def chatbot():
    current_session_id = session.get('current_chat_session')
    if not current_session_id:
        current_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session['user_id']}"
        session['current_chat_session'] = current_session_id

    # Optional CID attachment via query params (?cid=...&filename=...)
    cid = request.args.get('cid')
    filename = request.args.get('filename') or 'PDF Document'
    if cid:
        # Only attach if not already same CID in context
        ctx = chat_pdf_contexts.get(current_session_id)
        if not ctx or ctx.get('cid') != cid:
            ok, msg = attach_pdf_to_session(current_session_id, session['user_id'], cid, filename)
            if not ok:
                flash(msg, 'error')
            else:
                flash('PDF attached to chat.', 'success')

    chat_sessions = get_user_chat_sessions(session['user_id'])
    current_chat_messages = get_chat_history(session['user_id'], current_session_id)

    return render_template('chatbot.html',
                           current_session_id=current_session_id,
                           chat_sessions=chat_sessions,
                           current_messages=current_chat_messages)

@app.route('/medicine', methods=['GET', 'POST'])
@login_required
def medicine():
    conn = get_db_connection()
    requests_data = []
    if not conn:
        flash('Database connection error', 'error')
        return render_template('Medicine.html', requests=requests_data)
    try:
        cur = conn.cursor(dictionary=True)
        if request.method == 'POST':
            med = request.form.get('medicine_name', '').strip()
            qty = request.form.get('quantity', '').strip()
            if med and qty.isdigit():
                cur.execute("""
                    INSERT INTO medicine_requests (user_id, medicine_name, quantity, request_date)
                    VALUES (%s,%s,%s,%s)
                """, (session['user_id'], med, int(qty), datetime.now()))
                conn.commit()
                flash('Medicine request submitted', 'success')
            else:
                flash('Invalid input', 'error')

        cur.execute("""
            SELECT id, medicine_name, quantity, status, request_date, notes
            FROM medicine_requests
            WHERE user_id=%s
            ORDER BY request_date DESC
        """, (session['user_id'],))
        requests_data = cur.fetchall()
    except Exception as e:
        logger.exception(f"[MEDICINE] Error: {e}")
        flash('Error loading requests', 'error')
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass
    return render_template('Medicine.html', requests=requests_data)
    

@app.route('/cancel_request/<int:request_id>', methods=['POST'])
@login_required
def cancel_request(request_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    try:
        cur = conn.cursor()
        cur.execute('SELECT status, user_id FROM medicine_requests WHERE id=%s', (request_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Request not found'}), 404
        status, user_id = row
        if user_id != session.get('user_id'):
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        if status != 'pending':
            return jsonify({'success': False, 'message': 'Cannot cancel this request'}), 400

        cur.execute('UPDATE medicine_requests SET status="cancelled" WHERE id=%s', (request_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.exception(f"Error cancelling request {request_id}: {e}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass



@app.route('/profile')
@login_required
def profile():
    conn = get_db_connection()
    user = {}
    contacts = []
    if not conn:
        flash('Database error', 'error')
        return render_template('profile.html', user=user, emergency_contacts=contacts)
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
        user = cur.fetchone() or {}
        cur.execute("""
            SELECT id, name, relationship, phone
            FROM emergency_contacts
            WHERE user_id=%s
            ORDER BY created_at DESC
        """, (session['user_id'],))
        contacts = cur.fetchall()
    except Exception as e:
        logger.exception(f"[PROFILE] Error: {e}")
        flash('Error loading profile', 'error')
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass
    return render_template('profile.html', user=user, emergency_contacts=contacts)

@app.route('/report')
@login_required
def report():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            filename VARCHAR(255),
            cid VARCHAR(255),
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
    """)
    # CHANGED: include uploaded_at so template date formatting works
    cur.execute("SELECT filename, cid, uploaded_at FROM uploaded_files WHERE user_id=%s ORDER BY uploaded_at DESC",
                (session['user_id'],))
    files = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('report.html', uploaded_files=files)

# ============================================================
# HEALTH METRICS API (SINGLE DEFINITION - FIXED)
# ============================================================
@app.route('/api/health_metrics', methods=['GET'])
@login_required
def api_health_metrics():
    mode = request.args.get('mode', '').lower().strip()
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'DB fail'}), 500

    try:
        cur = conn.cursor(dictionary=True)
        if mode == 'by_day':
            cur.execute("""
                SELECT DATE(recorded_at) as date,
                       AVG(heart_rate) as heart_rate,
                       AVG(temperature) as temperature,
                       AVG((systolic + diastolic) / 2) as mean_bp
                FROM user_health_metrics 
                WHERE user_id = %s AND recorded_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                GROUP BY DATE(recorded_at)
                ORDER BY DATE(recorded_at)
            """, (session['user_id'],))
            daily_data = cur.fetchall()
            daily_series = []
            trend_days = []
            for row in daily_data:
                daily_series.append({
                    'date': row['date'].strftime('%Y-%m-%d'),
                    'heart_rate': round(float(row['heart_rate'] or 0), 1),
                    'temperature': round(float(row['temperature'] or 0), 1)
                })
                hr = float(row['heart_rate'] or 0)
                temp = float(row['temperature'] or 0)
                bp = float(row['mean_bp'] or 0)
                score = compute_health_score(hr, 0, temp, 98)
                trend_days.append({
                    'date': row['date'].strftime('%m-%d'),
                    'health_score': round(score, 1)
                })

            cur.execute("""
                SELECT * FROM user_health_metrics 
                WHERE user_id = %s 
                ORDER BY recorded_at DESC LIMIT 1
            """, (session['user_id'],))
            latest = cur.fetchone()
            if latest:
                latest_data = {
                    'heart_rate': latest['heart_rate'],
                    'systolic': latest['systolic'],
                    'diastolic': latest['diastolic'],
                    'temperature': float(latest['temperature']),
                    'spo2': latest['spo2'],
                    'health_score': compute_health_score(
                        latest['heart_rate'],
                        0,
                        float(latest['temperature']),
                        latest['spo2']
                    )
                }
            else:
                latest_data = synthesize_reading()
                latest_data['health_score'] = compute_health_score(
                    latest_data['heart_rate'],
                    0,
                    latest_data['temperature'],
                    latest_data['spo2']
                )
            return jsonify({
                'status': 'success',
                'latest': latest_data,
                'daily_series': daily_series if daily_series else generate_fallback_daily(),
                'trend_days': trend_days if trend_days else generate_fallback_trends()
            })
        else:
            # This handles all other cases (including missing or invalid mode)
            return jsonify({'status': 'error', 'message': 'Invalid mode'}), 400

    except Exception as e:
        logger.exception(f"[HEALTH METRICS API] Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

# ============================================================
# Connect to IPFS
# ============================================================

def get_ipfs_client():
    """Get IPFS client with fallback options for deployment"""
    try:
        # Try local IPFS node first (for development)
        if not env('RAILWAY_ENVIRONMENT') and not env('RENDER') and not env('HEROKU') and not env('RENDER_SERVICE_NAME'):
            try:
                client = ipfshttpclient.connect('/ip4/127.0.0.1/tcp/5001')
                # Test connection
                client.version()
                logger.info("✅ Connected to local IPFS node")
                return client, 'local'
            except:
                logger.warning("⚠️ Local IPFS node not available")
        
        # Try Infura IPFS (free tier) - recommended for production
        infura_project_id = env('INFURA_IPFS_PROJECT_ID')
        infura_secret = env('INFURA_IPFS_SECRET')
        
        if infura_project_id and infura_secret:
            try:
                import base64
                auth_string = f"{infura_project_id}:{infura_secret}"
                auth_bytes = auth_string.encode('ascii')
                auth_header = base64.b64encode(auth_bytes).decode('ascii')
                
                client = ipfshttpclient.connect(
                    '/dns/ipfs.infura.io/tcp/5001/https',
                    headers={'Authorization': f'Basic {auth_header}'}
                )
                logger.info("✅ Connected to Infura IPFS")
                return client, 'infura'
            except Exception as e:
                logger.warning(f"⚠️ Infura IPFS connection failed: {e}")
        
        # Try Pinata Cloud (alternative to Infura)
        pinata_api_key = env('PINATA_API_KEY')
        pinata_secret = env('PINATA_SECRET_KEY')
        
        if pinata_api_key and pinata_secret:
            try:
                # Pinata uses direct HTTP API, not IPFS client
                logger.info("✅ Using Pinata Cloud for IPFS")
                return None, 'pinata'
            except Exception as e:
                logger.warning(f"⚠️ Pinata configuration failed: {e}")
        
        # Fallback: Use public gateways (read-only)
        logger.warning("⚠️ No IPFS upload capability available - using read-only mode")
        return None, 'readonly'
        
    except Exception as e:
        logger.error(f"❌ IPFS connection failed: {e}")
        return None, 'none'

def upload_to_pinata(file_content, filename):
    """Upload file to Pinata Cloud"""
    pinata_api_key = env('PINATA_API_KEY')
    pinata_secret = env('PINATA_SECRET_KEY')
    
    if not pinata_api_key or not pinata_secret:
        raise Exception("Pinata API credentials not configured")
    
    url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
    
    headers = {
        'pinata_api_key': pinata_api_key,
        'pinata_secret_api_key': pinata_secret
    }
    
    files = {
        'file': (filename, file_content, 'application/pdf')
    }
    
    response = requests.post(url, files=files, headers=headers, timeout=30)
    response.raise_for_status()
    
    result = response.json()
    return result['IpfsHash']

@app.route("/upload", methods=["POST","GET"])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
    
    client, mode = get_ipfs_client()
    
    if mode == 'none':
        return jsonify({
            "error": "IPFS service unavailable. Please configure IPFS or use alternative file storage."
        }), 503
    
    if mode == 'readonly':
        return jsonify({
            "error": "IPFS upload not available in this deployment. Please configure Infura IPFS or Pinata Cloud."
        }), 503
    
    try:
        # Handle different upload methods
        if mode == 'pinata':
            # Upload via Pinata Cloud
            file_content = file.read()
            file.seek(0)
            cid = upload_to_pinata(file_content, file.filename)
        else:
            res = client.add(file)
            cid = res["Hash"]
        gateway_url = build_gateway_url(cid, mode)
        logger.info(f"✅ File uploaded to IPFS via {mode}: {gateway_url}")
        
        # Save to database
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS uploaded_files (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    filename VARCHAR(255),
                    cid VARCHAR(255),
                    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB
            """)
            cur.execute("SELECT id FROM uploaded_files WHERE user_id=%s AND cid=%s", (session['user_id'], cid))
            exists = cur.fetchone()
            if not exists:
                cur.execute("INSERT INTO uploaded_files (user_id, filename, cid) VALUES (%s, %s, %s)", 
                           (session['user_id'], file.filename, cid))
                conn.commit()
            cur.close()
            conn.close()
        
        return jsonify({
            "cid": cid,
            "filename": file.filename,
            "gateway_url": gateway_url,
            "mode": mode,
            "message": f"File uploaded successfully! CID: {cid}"
        }), 200
        
    except Exception as e:
        logger.error(f"❌ IPFS upload error: {e}")
        return jsonify({
            "error": f"Upload failed: {str(e)}"
        }), 500

def build_gateway_url(cid, mode=None):
    """Return a consistent gateway URL for a CID honoring IPFS_GATEWAY_BASE override."""
    custom = env('IPFS_GATEWAY_BASE')
    if custom:
        return f"{custom.rstrip('/')}/ipfs/{cid}"
    # Fallback priority: pinata (if keys) -> local (if running) -> ipfs.io
    if mode == 'local':
        return f"http://127.0.0.1:8080/ipfs/{cid}"
    if mode == 'pinata':
        return f"https://gateway.pinata.cloud/ipfs/{cid}"
    if mode == 'infura':
        return f"https://ipfs.io/ipfs/{cid}"
    # Auto-detect by credentials
    if env('PINATA_API_KEY') and env('PINATA_SECRET_KEY'):
        return f"https://gateway.pinata.cloud/ipfs/{cid}"
    return f"https://ipfs.io/ipfs/{cid}"

# ============================================================
# RATE LIMITING & SMART FALLBACKS FOR FREE TIER
# ============================================================
import time
import hashlib
from collections import deque
from threading import Lock

class RateLimiter:
    def __init__(self, max_requests=25, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = Lock()
    
    def can_make_request(self):
        with self.lock:
            now = time.time()
            while self.requests and self.requests[0] <= now - self.time_window:
                self.requests.popleft()
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False
    
    def wait_time(self):
        with self.lock:
            if not self.requests:
                return 0
            return max(0, self.time_window - (time.time() - self.requests[0]))

class ResponseCache:
    def __init__(self, max_size=1000):
        self.cache = {}
        self.max_size = max_size
        self.access_times = {}
    
    def get_cache_key(self, query, context=None):
        content = f"{query}||{context or ''}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, query, context=None):
        key = self.get_cache_key(query, context)
        if key in self.cache:
            self.access_times[key] = time.time()
            return self.cache[key]
        return None
    
    def set(self, query, response, context=None):
        key = self.get_cache_key(query, context)
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            del self.cache[oldest_key]
            del self.access_times[oldest_key]
        
        self.cache[key] = response
        self.access_times[key] = time.time()

class MultiAPIManager:
    """Manages multiple inference providers as fallbacks"""
    
    def __init__(self):
        self.providers = [
            {
                'name': 'groq',
                'enabled': bool(env('GROQ_API_KEY')),
                'rate_limiter': RateLimiter(max_requests=25, time_window=60),
                'error_count': 0
            },
            {
                'name': 'openrouter',
                'enabled': bool(env('OPENROUTER_API_KEY')),
                'rate_limiter': RateLimiter(max_requests=200, time_window=60),
                'error_count': 0
            }
        ]
        self.current_provider_index = 0
    
    def get_available_provider(self):
        """Get next available provider"""
        attempts = 0
        while attempts < len(self.providers):
            provider = self.providers[self.current_provider_index]
            
            if not provider['enabled'] or provider['error_count'] > 3:
                self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)
                attempts += 1
                continue
            
            if provider['rate_limiter'].can_make_request():
                return provider
            
            self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)
            attempts += 1
        
        return None
    
    def mark_error(self, provider_name, error):
        for provider in self.providers:
            if provider['name'] == provider_name:
                provider['error_count'] += 1
                logger.error(f"Provider {provider_name} error #{provider['error_count']}: {error}")
                break
    
    def reset_errors(self, provider_name):
        for provider in self.providers:
            if provider['name'] == provider_name:
                provider['error_count'] = 0
                break

def call_groq_api(prompt, max_tokens=500):
    """Primary Groq API call with intelligent RAG enhancement"""
    try:
        # Use existing RAG pipeline or initialize if needed
        pipeline = rag_pipeline if rag_pipeline is not None else initialize_rag_pipeline()
        
        # Analyze if user wants detailed info
        query_lower = prompt.lower()
        wants_details = any(word in query_lower for word in [
            'detailed', 'details', 'explain in detail', 'comprehensive', 'elaborate', 
            'side effects', 'interactions', 'dosage', 'dose', 'how much', 
            'precautions', 'warnings', 'contraindications', 'tell me everything'
        ])
        
        # Check if it's a medicine-related query that might benefit from RAG
        is_medicine_query = any(word in query_lower for word in [
            'paracip', 'paracetamol', 'aspirin', 'ibuprofen', 'medicine', 'medication', 
            'drug', 'tablet', 'capsule', 'syrup', 'what is', 'tell me about',
            'azithromycin', 'cetirizine', 'metformin', 'diclofenac', 'nimesulide',
            'aceclofenac', 'amoxycillin', 'glimepiride', 'pantoprazole', 'omeprazole',
            'atorvastatin', 'losartan', 'cyra', 'domperidone', 'rabeprazole'
        ])
        
        rag_context = None
        use_rag = False
        
        if is_medicine_query:
            # Try to get RAG context for medicine queries
            try:
                rag_context = pipeline.run(prompt, context=None)
                logger.info(f"RAG context retrieved for '{prompt}': {rag_context[:200]}...")
                
                # Check if RAG found relevant information (more strict checking)
                if (rag_context and 
                    len(rag_context.strip()) > 50 and 
                    not rag_context.lower().startswith("i don't have") and
                    not "i don't have information" in rag_context.lower() and
                    not "no information available" in rag_context.lower()):
                    use_rag = True
                    logger.info("✅ RAG found relevant medicine information")
                else:
                    logger.info("⚠️ RAG didn't find specific medicine info, using general AI knowledge")
                    
            except Exception as e:
                logger.warning(f"RAG context retrieval failed: {e}")
                logger.info("📚 Falling back to general AI knowledge")
        
        # Construct the appropriate prompt based on available information
        if use_rag and rag_context:
            # Use RAG-enhanced response for medicines in database
            if wants_details:
                enhanced_prompt = f"""You are a knowledgeable medical assistant. Based on the following medical database information, provide a comprehensive and detailed response about: {prompt}

Medical Database Information:
{rag_context}

Provide thorough information including dosages, uses, precautions, side effects, and interactions. Be detailed but well-organized."""
            else:
                enhanced_prompt = f"""You are a friendly medical assistant. Based on the following medical database information, provide a brief, conversational response about: {prompt}

Medical Database Information:
{rag_context}

Give a concise answer in 2-3 sentences maximum. Just explain what it is and its main use. Don't include detailed dosages, side effects, or precautions unless specifically asked. End by mentioning they can ask for more details if needed."""
        
        elif is_medicine_query:
            # Medicine query but no RAG data - use general AI knowledge
            if wants_details:
                enhanced_prompt = f"""You are a knowledgeable medical assistant. The user is asking about: {prompt}

Please provide helpful general medical information based on your knowledge. Include what you know about dosages, uses, precautions, and interactions when applicable.

If you're not certain about specific details, mention that the user should consult healthcare professionals or official medical sources."""
            else:
                enhanced_prompt = f"""You are a friendly medical assistant. The user is asking about: {prompt}

Please provide a brief, helpful response based on your general medical knowledge. Keep it conversational and mention they can ask for more details if needed. If you're not certain about specific details, suggest consulting healthcare professionals."""
        
        else:
            # Non-medicine queries - use general AI knowledge
            enhanced_prompt = f"""You are a friendly medical assistant. Respond conversationally to: {prompt}

Be helpful and informative using your general medical knowledge. Keep the tone natural and conversational. If they need more details, let them know they can ask for more specific information."""
        
        result = pipeline.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": enhanced_prompt}],
            temperature=0.7,
            max_tokens=max_tokens if wants_details else 200,
            top_p=0.9
        )
        
        response_content = result.choices[0].message.content.strip()
        
        # Return clean response without any source indicators
        return response_content
        
    except Exception as e:
        raise Exception(f"Groq API error: {str(e)}")

def call_openrouter_api(prompt, max_tokens=500):
    """OpenRouter API with intelligent medicine detection"""
    api_key = env('OPENROUTER_API_KEY')
    if not api_key:
        raise Exception("OpenRouter API key not configured")
    
    try:
        # Check if it's a medicine query
        query_lower = prompt.lower()
        is_medicine_query = any(word in query_lower for word in [
            'paracip', 'paracetamol', 'aspirin', 'ibuprofen', 'medicine', 'medication', 
            'drug', 'tablet', 'capsule', 'syrup', 'what is', 'tell me about',
            'azithromycin', 'cetirizine', 'metformin', 'diclofenac', 'nimesulide',
            'cyra', 'domperidone', 'rabeprazole'
        ])
        
        if is_medicine_query:
            system_prompt = f"You are a knowledgeable medical assistant. Provide helpful information about the medical question: {prompt}. Use your general medical knowledge and mention when users should consult healthcare professionals for specific advice."
        else:
            system_prompt = f"You are a friendly medical assistant. Respond conversationally to this health-related question: {prompt}"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "MediCare AI Assistant"
        }
        
        payload = {
            "model": "microsoft/wizardlm-2-8x22b:free",
            "messages": [{"role": "user", "content": system_prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content'].strip()
        
        # Return clean response without source indicators
        return content
        
    except Exception as e:
        raise Exception(f"OpenRouter API error: {str(e)}")

def call_with_fallback(prompt, max_tokens=500):
    """Try multiple inference providers until one succeeds"""
    api_functions = {
        'groq': call_groq_api,
        'openrouter': call_openrouter_api
    }
    
    last_error = None
    
    for attempt in range(len(api_manager.providers)):
        provider = api_manager.get_available_provider()
        
        if not provider:
            logger.error("All inference providers exhausted")
            break
        
        provider_name = provider['name']
        api_function = api_functions.get(provider_name)
        
        if not api_function:
            logger.warning(f"No implementation for provider: {provider_name}")
            continue
        
        try:
            logger.info(f"Trying provider: {provider_name}")
            response = api_function(prompt, max_tokens)
            
            # Success! Reset error count
            api_manager.reset_errors(provider_name)
            logger.info(f"✅ Success with provider: {provider_name}")
            return response, provider_name
            
        except Exception as e:
            api_manager.mark_error(provider_name, e)
            last_error = e
            logger.warning(f"❌ Provider {provider_name} failed: {e}")
            
            # Move to next provider
            api_manager.current_provider_index = (api_manager.current_provider_index + 1) % len(api_manager.providers)
            continue
    
    # All providers failed
    raise Exception(f"All inference providers failed. Last error: {last_error}")

class SmartFallbackResponder:
    def __init__(self):
        self.medicine_responses = {
            "paracetamol": "Paracetamol (Acetaminophen) is a pain reliever and fever reducer. Standard dose: 500-1000mg every 4-6 hours. Maximum daily: 4000mg. Used for headaches, fever, mild pain.",
            "aspirin": "Aspirin is a pain reliever and blood thinner. Dose: 325-650mg every 4 hours. Used for pain, fever, heart disease prevention. Avoid in children.",
            "ibuprofen": "Ibuprofen is an anti-inflammatory. Dose: 200-400mg every 4-6 hours. Max daily: 1200mg. Used for pain, fever, inflammation.",
            "cetirizine": "Cetirizine is an antihistamine. Dose: 10mg once daily. Used for allergies, hives, allergic reactions.",
            "metformin": "Metformin manages blood sugar in diabetes. Dose: 500-1000mg twice daily with meals. First-line treatment for Type 2 diabetes.",
            "azithromycin": "Azithromycin is an antibiotic. Dose: 500mg once daily for 3-5 days. Used for bacterial infections like pneumonia, bronchitis.",
            "diclofenac": "Diclofenac is an anti-inflammatory pain reliever. Dose: 50mg 2-3 times daily. Used for arthritis, muscle pain, inflammation.",
            "omeprazole": "Omeprazole reduces stomach acid. Dose: 20-40mg once daily. Used for heartburn, acid reflux, stomach ulcers."
        }
        
        # General health knowledge for non-medicine queries
        self.health_responses = {
            "fever": "Fever is your body's natural response to infection. Rest, stay hydrated, and consider fever reducers like paracetamol if uncomfortable. See a doctor if fever exceeds 103°F or persists.",
            "headache": "Headaches can be caused by stress, dehydration, or tension. Try rest, hydration, and gentle massage. Persistent or severe headaches should be evaluated by a healthcare provider.",
            "cold": "Common colds are viral infections. Rest, fluids, and over-the-counter medications can help symptoms. Most colds resolve in 7-10 days.",
            "cough": "Coughs can be dry or productive. Stay hydrated, use honey for throat relief, and see a doctor if persistent or accompanied by fever.",
            "diabetes": "Diabetes is a condition where blood sugar levels are too high. Management includes diet, exercise, medication, and regular monitoring.",
            "blood pressure": "Blood pressure measures the force of blood against artery walls. Normal is typically less than 120/80 mmHg. Regular monitoring is important.",
            "exercise": "Regular exercise improves cardiovascular health, strengthens muscles, and boosts mental well-being. Aim for 150 minutes of moderate activity weekly.",
            "diet": "A balanced diet includes fruits, vegetables, whole grains, lean proteins, and healthy fats. Limit processed foods, sugar, and excess sodium.",
            "hormones": "Hormones are chemical messengers that regulate various body functions including growth, metabolism, reproduction, and mood.",
            "capsule": "Capsules are a common dosage form for medications, containing active ingredients in a gelatin or vegetarian shell."
        }
    
    def get_response(self, query):
        """Get intelligent fallback response with medical knowledge"""
        query_lower = query.lower()
        
        # Check specific medicine knowledge first
        for medicine, response in self.medicine_responses.items():
            if medicine in query_lower:
                return f"💊 {response}"
        
        # Check general health knowledge
        for topic, response in self.health_responses.items():
            if topic in query_lower:
                return f"🏥 {response}"
        
        # Greeting
        if any(word in query_lower for word in ["hi", "hello", "hey", "good morning", "good evening"]):
            return "Hello! I'm your MediCare AI Assistant. I can help with medicine information, health questions, and medical guidance. What would you like to know?"
        
        # Medicine-related questions (including unknown medicines)
        medicine_keywords = ["capsule", "tablet", "syrup", "medicine", "medication", "drug", "dose", "dosage", "side effects", "increase", "hormones"]
        is_medicine_question = any(keyword in query_lower for keyword in medicine_keywords)
        
        if is_medicine_question:
            # Try inference providers for medicine questions
            try:
                response, provider_used = call_with_fallback(query)
                return response
            except Exception as e:
                logger.warning(f"All inference providers failed for medicine question: {e}")
                # Provide helpful guidance for unknown medicines
                return f"""I don't have specific information about the medication mentioned in your question: "{query}"

However, I can provide some general guidance:
• For hormone-related questions, it's best to consult an endocrinologist or your healthcare provider
• Many medications can affect hormone levels - both prescribed and over-the-counter
• Always check with your doctor or pharmacist about potential hormonal effects of any medication
• If you're concerned about hormonal changes, discuss this with your healthcare provider

For specific medical advice about medications and hormones, please consult healthcare professionals."""
        
        # Symptoms - try to provide helpful general advice
        symptom_keywords = ["i have", "symptoms", "pain", "headache", "sick", "feel", "hurt", "ache", "sore"]
        if any(word in query_lower for word in symptom_keywords):
            try:
                response, provider_used = call_with_fallback(f"Someone has these symptoms: {query}. What general medical advice can you give?")
                return response
            except:
                return "I understand you're experiencing symptoms. While I can provide general information, it's important to consult a healthcare professional for proper evaluation and treatment. If symptoms are severe or persistent, please seek medical attention."
        
        # Health questions - try to provide general guidance
        health_keywords = ["what is", "how to", "why do", "should i", "is it normal", "can you explain"]
        if any(phrase in query_lower for phrase in health_keywords):
            try:
                response, provider_used = call_with_fallback(f"Medical question: {query}")
                return response
            except:
                return f"I can help with medical questions, but I don't have specific information about '{query}'. I'd recommend consulting a healthcare provider or checking reputable medical sources for accurate information."
        
        # Try inference providers for any other question
        try:
            response, provider_used = call_with_fallback(query)
            return response
        except:
            pass
        
        # Final fallback with helpful suggestions
        return """I'm here to help with medical and health questions! I can assist with:

💊 **Medicine information** (dosages, uses, side effects)
🏥 **Health conditions** (symptoms, treatments, prevention)  
📋 **General wellness** (diet, exercise, lifestyle)
📄 **PDF analysis** (upload medical documents for review)

Try asking specific questions like:
• "What is paracetamol used for?"
• "How to manage diabetes?"
• "What causes high blood pressure?"

What would you like to know?"""

# ============================================================
# INITIALIZE GLOBAL INSTANCES
# ============================================================

# Initialize new multi-API system
api_manager = MultiAPIManager()
response_cache = ResponseCache(max_size=500)
fallback_responder = SmartFallbackResponder()

logger.info("✅ Initialized API management system with smart fallbacks")

# ============================================================
# BACKEND API MONITORING & HEALTH CHECKS
# ============================================================
def check_api_health():
    """Internal health check for monitoring API status"""
    status = {
        'groq': {'enabled': False, 'status': 'not_configured'},
        'openrouter': {'enabled': False, 'status': 'not_configured'},
        'rag_pipeline': {'status': 'not_initialized'},
        'overall': 'degraded'
    }
    
    # Check Groq
    groq_key = env('GROQ_API_KEY')
    if groq_key and groq_key != 'your_groq_key_here' and groq_key.startswith('gsk_'):
        status['groq']['enabled'] = True
        status['groq']['status'] = 'configured'
        logger.info(f"✅ Groq API key found: {groq_key[:20]}...")
    else:
        logger.warning(f"❌ Groq API key issue: key='{groq_key[:20] if groq_key else 'None'}...'")
    
    # Check OpenRouter
    openrouter_key = env('OPENROUTER_API_KEY')
    if openrouter_key and openrouter_key != 'your_openrouter_key_here' and openrouter_key.startswith('sk-'):
        status['openrouter']['enabled'] = True
        status['openrouter']['status'] = 'configured'
        logger.info(f"✅ OpenRouter API key found: {openrouter_key[:20]}...")
    else:
        logger.warning(f"❌ OpenRouter API key issue: key='{openrouter_key[:20] if openrouter_key else 'None'}...'")
    
    # Check RAG Pipeline
    if rag_pipeline is not None:
        status['rag_pipeline']['status'] = 'initialized'
    
    # Overall status
    if status['groq']['enabled'] or status['openrouter']['enabled']:
        status['overall'] = 'operational'
    
    return status

def log_api_usage(provider, success, error=None):
    """Log API usage for monitoring"""
    if success:
        logger.info(f"✅ {provider.upper()} API call successful")
    else:
        logger.warning(f"❌ {provider.upper()} API call failed: {error}")

# ============================================================
# CHAT HISTORY FUNCTIONS
# ============================================================
def save_chat_message(user_id, session_id, message_type, message_content, pdf_cid=None):
    """Save a chat message to the database"""
    conn = get_db_connection()
    if not conn:
        logger.error("Cannot save chat message - no database connection")
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO chat_history (user_id, session_id, message_type, message_content, pdf_cid, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, session_id, message_type, message_content, pdf_cid, datetime.now()))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving chat message: {e}")
        return False
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

def get_chat_history(user_id, session_id=None, limit=50):
    """Retrieve chat history for a user"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor(dictionary=True)
        if session_id:
            cur.execute("""
                SELECT message_type, message_content, timestamp, pdf_cid
                FROM chat_history 
                WHERE user_id = %s AND session_id = %s
                ORDER BY timestamp ASC
                LIMIT %s
            """, (user_id, session_id, limit))
        else:
            cur.execute("""
                SELECT session_id, message_type, message_content, timestamp, pdf_cid
                FROM chat_history 
                WHERE user_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (user_id, limit))
        
        return cur.fetchall()
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        return []
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

def get_user_chat_sessions(user_id, limit=20):
    """Get list of chat sessions for a user"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT session_id, 
                   MAX(timestamp) as last_message,
                   COUNT(*) as message_count,
                   SUBSTRING(MIN(CASE WHEN message_type = 'user' THEN message_content END), 1, 50) as first_user_message
            FROM chat_history 
            WHERE user_id = %s
            GROUP BY session_id
            ORDER BY MAX(timestamp) DESC
            LIMIT %s
        """, (user_id, limit))
        
        return cur.fetchall()
    except Exception as e:
        logger.error(f"Error retrieving chat sessions: {e}")
        return []
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

# ============================================================
# CHATBOT API
# ============================================================
FAISS_PATH = "Website/data/embeddings/faiss_index.bin"
DATA_PATH = "Website/data/processed_data.csv"

# Initialize RAG pipeline after environment is loaded
rag_pipeline = None

def initialize_rag_pipeline():
    """Initialize RAG pipeline with proper environment setup"""
    global rag_pipeline
    if rag_pipeline is None:
        try:
            # Ensure Groq API key is available
            groq_key = env('GROQ_API_KEY')
            if not groq_key:
                logger.error("❌ GROQ_API_KEY not found in environment")
                raise Exception("GROQ_API_KEY environment variable not set")
            
            logger.info(f"✅ Initializing RAG pipeline with Groq key: {groq_key[:20]}...")
            logger.info(f"📊 RAG Data paths: FAISS={FAISS_PATH}, CSV={DATA_PATH}")
            
            # Check if data files exist
            if not os.path.exists(FAISS_PATH):
                logger.warning(f"⚠️ FAISS index not found at {FAISS_PATH}")
            if not os.path.exists(DATA_PATH):
                logger.warning(f"⚠️ CSV data not found at {DATA_PATH}")
            
            rag_pipeline = RAGPipeline(faiss_path=FAISS_PATH, data_path=DATA_PATH)
            logger.info("✅ RAG pipeline initialized successfully")
            
            # Test RAG pipeline with a simple query
            try:
                test_result = rag_pipeline.run("paracetamol", context=None)
                logger.info(f"🧪 RAG Test Query Result: {test_result[:100]}...")
            except Exception as test_e:
                logger.error(f"⚠️ RAG test query failed: {test_e}")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize RAG pipeline: {e}")
            raise e
    return rag_pipeline

@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    try:
        data = request.get_json()
        messages = data.get('messages', [])
        session_id = data.get('session_id')
        
        # Use provided session_id or current session
        if not session_id:
            session_id = session.get('current_chat_session')
            if not session_id:
                session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session['user_id']}"
                session['current_chat_session'] = session_id
        
        user_message = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_message = msg.get('content', '').strip()
                break
        if not user_message:
            return jsonify({'status': 'error', 'content': 'No user message received.'}), 400

        # Track last mentioned medicine in context
        medicine_names = extract_medicine_names_from_text(user_message)
        if medicine_names:
            set_last_medicine_in_context(session_id, medicine_names[-1])
            logger.info(f"Medicine context updated: {medicine_names[-1]} for session {session_id}")

        # If user uses pronouns and no medicine detected, use last context
        pronouns = ['it', 'this', 'that', 'them', 'these', 'those']
        has_pronouns = any(p in user_message.lower() for p in pronouns)
        
        if has_pronouns and not medicine_names:
            last_medicine = get_last_medicine_from_context(session_id)
            if last_medicine:
                # Replace pronoun with last medicine in user_message for processing
                pronoun_pattern = r'\b(?:' + '|'.join(pronouns) + r')\b'
                user_message = re.sub(pronoun_pattern, last_medicine, user_message, flags=re.IGNORECASE)
                logger.info(f"Replaced pronouns with context medicine: {last_medicine}")

        # Save user message to database
        save_chat_message(session['user_id'], session_id, 'user', user_message)
        
        # Check cache first for any query
        cached_response = response_cache.get(user_message)
        if cached_response:
            logger.info("Returning cached response")
            # Save cached AI response
            save_chat_message(session['user_id'], session_id, 'ai', cached_response)
            return jsonify({'status': 'success', 'content': cached_response, 'session_id': session_id})
        
        # Handle context clearing command
        if user_message.lower() in ['clear pdf', 'detach pdf', 'remove pdf', 'clear attachment']:
            clear_pdf_context(session_id)
            reply = "📄 PDF context cleared. You can attach another report."
            save_chat_message(session['user_id'], session_id, 'ai', reply)
            return jsonify({'status': 'success', 'content': reply, 'session_id': session_id})

        # Check for CID in message (PDF processing)
        cid = extract_cid_from_message(user_message)
        logger.info(f"Extracted CID: {cid} from message: {user_message}")

        # If no explicit CID but we have an attached PDF context, answer using it
        if not cid and session_id in chat_pdf_contexts and chat_pdf_contexts[session_id]['text']:
            try:
                pipeline = rag_pipeline if rag_pipeline is not None else initialize_rag_pipeline()
                pdf_text = chat_pdf_contexts[session_id]['text']
                answer = pipeline.run(user_message, context=f"Attached PDF Content:\n{pdf_text}")
                response_cache.set(user_message, answer)
                save_chat_message(session['user_id'], session_id, 'ai', answer,
                                  chat_pdf_contexts[session_id]['cid'])
                return jsonify({'status': 'success', 'content': answer, 'session_id': session_id})
            except Exception as e:
                logger.error(f"Context PDF answer error: {e}")
        
        # Normal CID handling - download and process PDF
        if cid:
            # For PDF queries, use both PDF content AND medicine dataset
            try:
                # Use existing RAG pipeline or initialize if needed
                pipeline = rag_pipeline if rag_pipeline is not None else initialize_rag_pipeline()
                
                pdf_path = download_pdf_from_ipfs(cid)
                pdf_text = extract_text_from_pdf(pdf_path)
                logger.info(f"PDF text for CID {cid}: {pdf_text[:200]}...")
                os.remove(pdf_path)
                question = re.sub(cid, '', user_message).strip()
                if not question:
                    question = "Summarize this PDF and identify any medicines mentioned"
                if not pdf_text.strip():
                    return jsonify({'status': 'error', 'content': f"PDF found (CID: {cid}), but no text could be extracted. Please check the PDF format."})
                
                # Enhanced context combining PDF + medicine dataset
                enhanced_context = f"PDF Document Content:\n{pdf_text}\n\nUser Question: {question}"
                
                # Use RAG with combined context (PDF + medicine dataset)
                answer = pipeline.run(question, context=enhanced_context)
                
                # Cache and save the response
                response_cache.set(user_message, answer)
                ai_response = f"📄 PDF Analysis (CID: {cid}):\n\n{answer}"
                save_chat_message(session['user_id'], session_id, 'ai', ai_response, cid)
                
                return jsonify({'status': 'success', 'content': ai_response, 'session_id': session_id})
            
            except Exception as e:
                logger.error(f"PDF processing error: {e}")
                fallback = f"📄 Found PDF (CID: {cid}), but I'm having trouble processing it right now. Please try again in a moment."
                save_chat_message(session['user_id'], session_id, 'ai', fallback, cid)
                return jsonify({'status': 'error', 'content': fallback, 'session_id': session_id})
        
        # Normal chatbot response - try inference providers
        try:
            # Attempt primary provider (should be Groq)
            answer, provider_used = call_with_fallback(user_message)
            # Cache successful response
            response_cache.set(user_message, answer)
            # Save AI response
            save_chat_message(session['user_id'], session_id, 'ai', answer)
            
            logger.info(f"✅ Response generated using {provider_used}")
            return jsonify({'status': 'success', 'content': answer, 'session_id': session_id})
            
        except Exception as e:
            logger.error(f"All inference providers failed: {e}")
            # Use intelligent fallback response
            fallback_response = fallback_responder.get_response(user_message)
            save_chat_message(session['user_id'], session_id, 'ai', fallback_response)
            return jsonify({'status': 'success', 'content': fallback_response, 'session_id': session_id})
        
    except Exception as e:
        logger.exception(f'[CHAT API] Error: {e}')
        # Final fallback
        fallback_response = fallback_responder.get_response(user_message if 'user_message' in locals() else "error")
        if 'session_id' in locals():
            save_chat_message(session['user_id'], session_id, 'ai', fallback_response)
        return jsonify({'status': 'success', 'content': fallback_response, 'session_id': session_id if 'session_id' in locals() else 'error'})

@app.route('/api/chat_pdf', methods=['POST'])
@login_required
def api_chat_pdf():
    data = request.get_json()
    cid = data.get('cid')
    question = data.get('question')
    if not cid or not question:
        return jsonify({'status': 'error', 'content': 'CID and question required.'}), 400
    
    try:
        # Use existing RAG pipeline or initialize if needed
        pipeline = rag_pipeline if rag_pipeline is not None else initialize_rag_pipeline()
        
        pdf_path = download_pdf_from_ipfs(cid)
        pdf_text = extract_text_from_pdf(pdf_path)
        os.remove(pdf_path)
        answer = pipeline.run(question, context=pdf_text)
        return jsonify({'status': 'success', 'content': answer})
    except Exception as e:
        logger.error(f"Chat PDF error: {e}")
        return jsonify({'status': 'error', 'content': 'Error processing PDF'}), 500

@app.route('/api/chat/history', methods=['GET'])
@login_required
def get_chat_sessions():
    """Get list of chat sessions for the current user"""
    sessions = get_user_chat_sessions(session['user_id'])
    return jsonify({'status': 'success', 'sessions': sessions})

@app.route('/api/chat/history/<session_id>', methods=['GET'])
@login_required
def get_session_history(session_id):
    """Get messages for a specific chat session"""
    messages = get_chat_history(session['user_id'], session_id)
    return jsonify({'status': 'success', 'messages': messages})

@app.route('/api/chat/new_session', methods=['POST'])
@login_required
def create_new_chat_session():
    """Create a new chat session"""
    new_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session['user_id']}"
    session['current_chat_session'] = new_session_id
    return jsonify({'status': 'success', 'session_id': new_session_id})

@app.route('/api/chat/switch_session', methods=['POST'])
@login_required
def switch_chat_session():
    """Switch to an existing chat session"""
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'status': 'error', 'message': 'Session ID required'}), 400
    
    # Verify session belongs to user
    user_sessions = get_user_chat_sessions(session['user_id'])
    if not any(s['session_id'] == session_id for s in user_sessions):
        return jsonify({'status': 'error', 'message': 'Session not found'}), 404
    
    session['current_chat_session'] = session_id
    messages = get_chat_history(session['user_id'], session_id)
    
    return jsonify({
        'status': 'success', 
        'session_id': session_id,
        'messages': messages
    })

@app.route('/api/chat/delete_session', methods=['POST'])
@login_required
def delete_chat_session():
    """Delete a chat session"""
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'status': 'error', 'message': 'Session ID required'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        # Verify session belongs to user and delete
        cur.execute("DELETE FROM chat_history WHERE user_id = %s AND session_id = %s", 
                   (session['user_id'], session_id))
        
        if cur.rowcount == 0:
            return jsonify({'status': 'error', 'message': 'Session not found'}), 404
        
        conn.commit()
        
        # If deleted session was current, create new one
        if session.get('current_chat_session') == session_id:
            new_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session['user_id']}"
            session['current_chat_session'] = new_session_id
        
        return jsonify({'status': 'success', 'message': 'Session deleted'})
    except Exception as e:
        logger.error(f"Error deleting chat session: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to delete session'}), 500
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

@app.route('/api/chat/clear', methods=['POST'])
@login_required
def clear_chat_history():
    """Clear all chat history for the current user"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM chat_history WHERE user_id = %s", (session['user_id'],))
        conn.commit()
        return jsonify({'status': 'success', 'message': 'Chat history cleared'})
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to clear history'}), 500
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

@app.route('/api/system/status', methods=['GET'])
@login_required  
def system_status():
    """Debug endpoint to check system status"""
    status = {
        'faiss_exists': os.path.exists(FAISS_PATH),
        'csv_exists': os.path.exists(DATA_PATH),
        'faiss_path': FAISS_PATH,
        'csv_path': DATA_PATH,
        'rag_initialized': rag_pipeline is not None
    }
    
    # Try to read a few lines from CSV if it exists
    if status['csv_exists']:
        try:
            import pandas as pd
            df = pd.read_csv(DATA_PATH)
            status['csv_shape'] = df.shape
            status['csv_columns'] = list(df.columns)
            status['csv_sample'] = df.head(2).to_dict('records') if not df.empty else []
        except Exception as e:
    return jsonify(status)

def extract_cid_from_message(message):
    # Improved regex to match both IPFS URLs and plain CIDs
    # Matches: Qm... (CID), or .../ipfs/Qm...
    match = re.search(r'(Qm[1-9A-HJ-NP-Za-km-z]{44,})', message)
    if match:
        return match.group(1)
    match = re.search(r'/ipfs/([A-Za-z0-9]+)', message)
    if match:
        return match.group(1)
    # Also match full IPFS gateway URLs
    match = re.search(r'ipfs/(Qm[1-9A-HJ-NP-Za-km-z]{44,})', message)
    if match:
        return match.group(1)
    return None

def download_pdf_from_ipfs(cid):
    """Download PDF from IPFS with multiple gateway fallbacks"""
    gateways = [
        f"http://127.0.0.1:8080/ipfs/{cid}",  # Local IPFS
        f"https://ipfs.io/ipfs/{cid}",        # Official gateway
        f"https://gateway.pinata.cloud/ipfs/{cid}",  # Pinata gateway
        f"https://cloudflare-ipfs.com/ipfs/{cid}",   # Cloudflare gateway
        f"https://dweb.link/ipfs/{cid}",      # Protocol Labs gateway
    ]
    
    for gateway_url in gateways:
        try:
            logger.info(f"Trying to download from: {gateway_url}")
            response = requests.get(gateway_url, timeout=30)
            response.raise_for_status()
            
            temp_path = f"temp_{cid}.pdf"
            with open(temp_path, "wb") as f:
                f.write(response.content)
            
            logger.info(f"✅ Successfully downloaded from {gateway_url}")
            return temp_path
            
        except Exception as e:
            logger.warning(f"❌ Failed to download from {gateway_url}: {e}")
            continue
    
    raise Exception(f"Failed to download CID {cid} from all IPFS gateways")

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text
        if not text.strip():
            logger.error(f"PDF extraction returned empty text for {pdf_path}")
        else:
            logger.info(f"Extracted PDF text length: {len(text)} from {pdf_path}")
    except Exception as e:
        logger.error(f"Error extracting PDF text: {e}")
    return text

# Add this global dictionary for session context tracking
last_medicine_context = {}

def extract_medicine_names_from_text(text):
    """Extract medicine names from text using enhanced keyword matching"""
    medicines_found = []
    text_lower = text.lower()
    
    # Enhanced medicine names list including brand names and variations
    medicine_keywords = [
        'paracetamol', 'paracip', 'dolo', 'crocin', 'calpol',
        'ibuprofen', 'brufen', 'combiflam', 'flexon',
        'diclofenac', 'voveran', 'volini',
        'nimesulide', 'nise', 'nicip',
        'aceclofenac', 'zerodol', 'hifenac',
        'amoxycillin', 'augmentin', 'mox', 'cipmox',
        'azithromycin', 'azithral', 'azee', 'azax',
        'cetirizine', 'cetrizine', 'cetzine', 'alerid',
        'pantoprazole', 'pantocid', 'pantop',
        'metformin', 'glycomet', 'glyciphage',
        'glimepiride', 'amaryl', 'zoryl',
        'omeprazole', 'omez', 'omee',
        'atorvastatin', 'atorva', 'storvas', 'lipitor',
        'losartan', 'losar', 'repace',
        'aspirin', 'disprin', 'ecosprin',
        'cyra', 'domperidone', 'rabeprazole'
    ]
    
    for medicine in medicine_keywords:
        if medicine in text_lower:
            medicines_found.append(medicine)
    
    # Also check for common brand patterns with numbers
    import re
    medicine_patterns = [
        r'\b(dolo)\s*\d*\b',
        r'\b(crocin)\s*\d*\b',
        r'\b(brufen)\s*\d*\b',
        r'\b(\w+)\s*tablet\b',
        r'\b(\w+)\s*capsule\b'
    ]
    
    for pattern in medicine_patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            if match and len(match) > 2:
                medicines_found.append(match)
    
    return list(set(medicines_found))  # Remove duplicates

def get_last_medicine_from_context(session_id):
    """Get last mentioned medicine for a session"""
    return last_medicine_context.get(session_id)

def set_last_medicine_in_context(session_id, medicine):
    """Set last mentioned medicine for a session"""
    last_medicine_context[session_id] = medicine

# Add after last_medicine_context
chat_pdf_contexts = {}  # session_id -> { 'cid': str|None, 'filename': str|None, 'text': str }

def set_pdf_context(session_id, text, cid=None, filename=None):
    chat_pdf_contexts[session_id] = {
        'cid': cid,
        'filename': filename,
        'text': text
    }

def clear_pdf_context(session_id):
    chat_pdf_contexts.pop(session_id, None)

def attach_pdf_to_session(session_id, user_id, cid, filename):
    """
    Internal helper: download + extract + summarize PDF, set context, persist AI summary.
    Returns (success, message)
    """
    try:
        pipeline = rag_pipeline if rag_pipeline is not None else initialize_rag_pipeline()
        pdf_path = download_pdf_from_ipfs(cid)
        pdf_text = extract_text_from_pdf(pdf_path)
        try:
            os.remove(pdf_path)
        except:
            pass
        if not pdf_text.strip():
            msg = f"📄 Attached PDF (CID: {cid}) but no extractable text was found."
            save_chat_message(user_id, session_id, 'ai', msg, cid)
            return True, msg
        set_pdf_context(session_id, pdf_text, cid=cid, filename=filename)
        summary_prompt = f"Provide a concise medical summary of the attached PDF '{filename}'. Highlight medicines, key findings, and notable observations."
        summary = pipeline.run(summary_prompt, context=pdf_text[:12000])
        ai_msg = (f"📎 Attached PDF: {filename}\nCID: {cid}\n\nSummary:\n{summary}\n\n"
                  f"You can now ask follow-up questions (type 'clear pdf' to detach).")
        save_chat_message(user_id, session_id, 'ai', ai_msg, cid)
        return True, ai_msg
    except Exception as e:
        logger.error(f"attach_pdf_to_session error (CID {cid}): {e}")
        return False, "Failed to attach PDF."

@app.route('/api/chat/attach_pdf', methods=['POST'])
@login_required
def api_attach_pdf():
    """
    Attach an existing IPFS PDF (AJAX). Body: { cid, filename (optional), session_id (optional) }
    """
    data = request.get_json() or {}
    cid = data.get('cid')
    filename = data.get('filename') or 'PDF Document'
    session_id = data.get('session_id') or session.get('current_chat_session')
    if not session_id:
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session['user_id']}"
        session['current_chat_session'] = session_id
    if not cid:
        return jsonify({'status': 'error', 'message': 'CID required'}), 400
    ok, msg = attach_pdf_to_session(session_id, session['user_id'], cid, filename)
    return jsonify({'status': 'success' if ok else 'error',
                    'content': msg,
                    'session_id': session_id}), (200 if ok else 500)

@app.route('/api/chat/upload_temp_pdf', methods=['POST'])
@login_required
def upload_temp_pdf():
    """
    Upload PDF inside chatbot WITHOUT IPFS pinning. Form-Data: file
    """
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'File required'}), 400
    f = request.files['file']
    if not f.filename.lower().endswith('.pdf'):
        return jsonify({'status': 'error', 'message': 'Only PDF allowed'}), 400
    session_id = session.get('current_chat_session')
    if not session_id:
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session['user_id']}"
        session['current_chat_session'] = session_id
    try:
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        f.save(tmp.name)
        pdf_text = extract_text_from_pdf(tmp.name)
        try:
            os.remove(tmp.name)
        except:
            pass
        if not pdf_text.strip():
            return jsonify({'status': 'error', 'message': 'No text extracted'}), 400
        pipeline = rag_pipeline if rag_pipeline is not None else initialize_rag_pipeline()
        set_pdf_context(session_id, pdf_text, cid=None, filename=f.filename)
        summary_prompt = f"Summarize this uploaded medical PDF '{f.filename}'. List medicines if any."
        summary = pipeline.run(summary_prompt, context=pdf_text[:12000])
        ai_msg = (f"📎 Temporary PDF Attached (not on IPFS): {f.filename}\n\nSummary:\n{summary}\n\n"
                  f"Ask follow-up questions (type 'clear pdf' to detach).")
        save_chat_message(session['user_id'], session_id, 'ai', ai_msg, None)
        return jsonify({'status': 'success', 'content': ai_msg, 'session_id': session_id})
    except Exception as e:
        logger.error(f"upload_temp_pdf error: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to process PDF'}), 500

# ============================================================
# PROFILE ROUTES
# ============================================================
@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('profile'))
    
    try:
        cur = conn.cursor()
        
        # Get form data
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        dob = request.form.get('dob', '').strip()
        gender = request.form.get('gender', '').strip()
        blood_group = request.form.get('blood_group', '').strip()
        address = request.form.get('address', '').strip()
        height = request.form.get('height', '').strip()
        weight = request.form.get('weight', '').strip()
        medical_conditions = request.form.get('medical_conditions', '').strip()
        allergies = request.form.get('allergies', '').strip()
        medications = request.form.get('medications', '').strip()
        
        # Convert empty strings to None for optional fields
        dob = dob if dob else None
        height = int(height) if height else None
        weight = int(weight) if weight else None
        
        # Update user profile
        cur.execute("""
            UPDATE users SET 
                full_name = %s, phone = %s, dob = %s, gender = %s, 
                blood_group = %s, address = %s, height = %s, weight = %s,
                medical_conditions = %s, allergies = %s, medications = %s
            WHERE id = %s
        """, (full_name, phone, dob, gender, blood_group, address, 
              height, weight, medical_conditions, allergies, medications, 
              session['user_id']))
        
        conn.commit()
        flash('Profile updated successfully!', 'success')
        
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        flash('Error updating profile', 'error')
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass
    
    return redirect(url_for('profile'))

@app.route('/profile/contact', methods=['POST'])
@login_required
def manage_emergency_contact():
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('profile'))
    
    try:
        cur = conn.cursor()
        
        contact_id = request.form.get('contact_id', '').strip()
        name = request.form.get('name', '').strip()
        relationship = request.form.get('relationship', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if not name or not phone:
            flash('Name and phone are required', 'error')
            return redirect(url_for('profile'))
        
        if contact_id:
            # Update existing contact
            cur.execute("""
                UPDATE emergency_contacts 
                SET name = %s, relationship = %s, phone = %s
                WHERE id = %s AND user_id = %s
            """, (name, relationship, phone, contact_id, session['user_id']))
            flash('Emergency contact updated successfully!', 'success')
        else:
            # Add new contact
            cur.execute("""
                INSERT INTO emergency_contacts (user_id, name, relationship, phone)
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], name, relationship, phone))
            flash('Emergency contact added successfully!', 'success')
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"Error managing emergency contact: {e}")
        flash('Error saving contact', 'error')
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass
    
    return redirect(url_for('profile'))

@app.route('/profile/contact/<int:contact_id>/delete', methods=['POST'])
@login_required
def delete_emergency_contact(contact_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cur = conn.cursor()
        
        # Verify contact belongs to user before deleting
        cur.execute("SELECT id FROM emergency_contacts WHERE id = %s AND user_id = %s", 
                   (contact_id, session['user_id']))
        if not cur.fetchone():
            return jsonify({'success': False, 'message': 'Contact not found'}), 404
        
        cur.execute("DELETE FROM emergency_contacts WHERE id = %s AND user_id = %s", 
                   (contact_id, session['user_id']))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Contact deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting emergency contact: {e}")
        return jsonify({'success': False, 'message': 'Error deleting contact'}), 500
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

# ============================================================
# MAIN (APPLICATION STARTUP)
# ============================================================
if __name__ == '__main__':
    port = int(env('PORT', 5000))
    host = env('HOST', '0.0.0.0')

    # Initialize database
    init_db()

    logger.info("🚀 Starting MediCare AI Assistant...")

    # Check API health status
    health_status = check_api_health()
    logger.info("🔧 Backend API Status Check:")
    logger.info(f"   - Groq API: {health_status['groq']['status']}")
    logger.info(f"   - OpenRouter API: {health_status['openrouter']['status']}")
    logger.info(f"   - System Status: {health_status['overall']}")

    if health_status['overall'] == 'degraded':
        logger.warning("⚠️ Running in degraded mode - some APIs not configured")
    else:
        logger.info("✅ All systems operational")

    # Initialize RAG pipeline
    try:
        logger.info("🔄 Initializing RAG pipeline at startup...")
        initialize_rag_pipeline()
        logger.info("✅ RAG pipeline loaded and ready!")
    except Exception as e:
        logger.warning(f"⚠️ RAG pipeline initialization failed: {e}")
        logger.info("📚 Application will use fallback responses for medical queries")

    logger.info(f"🌐 Starting Flask server on {host}:{port}")
    
    # Start the Flask application
    app.run(
        debug=app.config.get('DEBUG', False), 
        host=host, 
        port=port,
        threaded=True
    )

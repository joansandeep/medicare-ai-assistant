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
    'password': env('DB_PASSWORD'),  # Remove default for security
    'database': env('DB_NAME', 'hospital'),
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
if env('RAILWAY_ENVIRONMENT') or env('RENDER') or env('HEROKU'):
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
        if not env('RAILWAY_ENVIRONMENT') and not env('RENDER') and not env('HEROKU'):
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


def create_production_database():
    """Create database and tables for production deployment"""
    
    # Database configuration
    config = {
        'host': os.getenv('DB_HOST'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'port': int(os.getenv('DB_PORT', 3306))
    }
    
    try:
        # For Aiven, connect directly to the defaultdb database
        config['database'] = os.getenv('DB_NAME', 'defaultdb')
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        print(f"✅ Connected to Aiven MySQL database: {config['database']}")
        
        # Create tables
        create_tables(cursor)
        
        # Insert default users
        create_default_users(cursor, conn)
        
        conn.commit()
        print("✅ Production database setup completed successfully!")
        
    except MySQLError as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    
    return True
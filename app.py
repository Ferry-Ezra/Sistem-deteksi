import pymysql
pymysql.install_as_MySQLdb()
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta
import os
import cv2
import requests
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from playwright.sync_api import sync_playwright

try:
    from ultralytics import YOLO
    import torch
    # Batasi penggunaan CPU thread oleh PyTorch agar CPU tidak melonjak tinggi
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
except ImportError:
    YOLO = None

app = Flask(__name__)

# ─── Konfigurasi Aplikasi ─────────────────────────────────────────────────────
app.config['SECRET_KEY']           = os.environ.get('SECRET_KEY') or 'skripsi-yolov8-senjata-tajam-2024'
app.config['MYSQL_HOST']           = 'localhost'
app.config['MYSQL_USER']           = 'root'
app.config['MYSQL_PASSWORD']       = ''
app.config['MYSQL_DB']             = 'tugas_akhir'
app.config['MYSQL_CURSORCLASS']    = 'DictCursor'
app.config['UPLOAD_FOLDER']        = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH']   = 16 * 1024 * 1024  # 16MB
app.config['TELEGRAM_BOT_TOKEN']   = os.environ.get('TELEGRAM_BOT_TOKEN') or '8716598524:AAHi_fuv4FEBL2apwAYVg9PCK1H4-MbFGF0'
app.config['TELEGRAM_CHAT_ID']     = os.environ.get('TELEGRAM_CHAT_ID') or '2058298411'

db = pymysql.connect(
    host="localhost",
    user="root",
    password="",
    database="nama_database"
)

# Load Model YOLO
model_path = os.path.join('model', 'best.pt')
yolo_model = YOLO(model_path) if YOLO and os.path.exists(model_path) else None

# Global state untuk Video Control Simulation
sim_state = {
    'paused': False,
    'current_sec': 0,
    'total_sec': 0,
    'filename': '',
    'speed': 1.0,
    'actual_fps': 0
}

# Pastikan folder uploads dan videos ada

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'avatars'), exist_ok=True)
os.makedirs(os.path.join('static', 'videos'), exist_ok=True)

@app.context_processor
def utility_processor():
    def get_avatar(user_id):
        path = os.path.join('static', 'uploads', 'avatars', f"user_{user_id}.jpg")
        if os.path.exists(path):
            try:
                # Cache bust with modification time
                mtime = int(os.path.getmtime(path))
                return f"{url_for('static', filename=f'uploads/avatars/user_{user_id}.jpg')}?v={mtime}"
            except:
                pass
        return None
    return dict(get_avatar=get_avatar)

@app.after_request
def add_header(response):
    # Mengunci cache browser agar tidak bisa menekan "Back" setelah logout
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ─── Decorator Login Required ────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def petugas_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('peran') != 'petugas' and session.get('role') != 'petugas':
            flash('Akses ditolak. Halaman ini hanya untuk Petugas Minimarket.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ─── AUTH ROUTES ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'petugas':
            return redirect(url_for('dashboard'))
        elif session.get('role') == 'datacenter':
            return redirect(url_for('dc_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, nama, email, kata_sandi, 'petugas' as peran FROM petugas_minimarket WHERE email = %s", (email,))
        user = cur.fetchone()
        
        if not user:
            cur.execute("SELECT id, nama, email, kata_sandi, 'datacenter' as peran FROM pusat_keamanan WHERE email = %s", (email,))
            user = cur.fetchone()
            
        cur.close()
        
        if user and check_password_hash(user['kata_sandi'], password):
            session['user_id']   = user['id']
            session['user_name'] = user['nama']
            session['role']      = user['peran']
            flash(f"Selamat datang, {user['nama']}!", 'success')
            if user['peran'] == 'petugas':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('dc_dashboard'))
        else:
            flash('Email atau password salah.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        nama_toko = request.form.get('nama_toko', '').strip()
        telegram_id = request.form.get('telegram_id', '').strip()
        
        if not name or not email or not password or not nama_toko or not telegram_id:
            flash('Semua field harus diisi.', 'danger')
        else:
            cur = mysql.connection.cursor()
            cur.execute("SELECT id FROM petugas_minimarket WHERE email = %s", (email,))
            user_petugas = cur.fetchone()
            cur.execute("SELECT id FROM pusat_keamanan WHERE email = %s", (email,))
            user_pusat = cur.fetchone()
            
            if user_petugas or user_pusat:
                flash('Email sudah terdaftar.', 'danger')
            else:
                hashed_pw = generate_password_hash(password)
                cur.execute(
                    "INSERT INTO petugas_minimarket (nama, email, kata_sandi, nama_toko, alamat, lintang, bujur, telegram_id) VALUES (%s, %s, %s, %s, NULL, NULL, NULL, %s)",
                    (name, email, hashed_pw, nama_toko, telegram_id)
                )
                mysql.connection.commit()
                flash('Registrasi berhasil! Silakan login.', 'success')
                cur.close()
                return redirect(url_for('login'))
            cur.close()
            
    return render_template('register.html')

# ─── PETUGAS ROUTES ──────────────────────────────────────────────────────────
@app.route('/dashboard')
@petugas_required
def dashboard():
    cur = mysql.connection.cursor()
    
    # Total deteksi hari ini
    cur.execute("""
        SELECT COUNT(*) as total FROM deteksi 
        WHERE DATE(waktu) = CURDATE() AND id_petugas = %s
    """, (session['user_id'],))
    deteksi_hari_ini = cur.fetchone()['total']
    
    # Total laporan deteksi keseluruhan
    cur.execute("SELECT COUNT(*) as total FROM deteksi WHERE id_petugas = %s", (session['user_id'],))
    total_laporan = cur.fetchone()['total']
    
    # Status kamera
    cur.execute("SELECT COUNT(*) as total FROM kamera WHERE status = 'online'")
    kamera_online = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as total FROM kamera")
    total_kamera = cur.fetchone()['total']
    
    # Deteksi terbaru (5 terakhir)
    cur.execute("""
        SELECT d.*, CONCAT('Kamera ', c.id) as camera_name 
        FROM deteksi d
        LEFT JOIN kamera c ON d.id_kamera = c.id
        WHERE d.id_petugas = %s
        ORDER BY d.waktu DESC LIMIT 5
    """, (session['user_id'],))
    deteksi_terbaru = cur.fetchall()
    
    cur.close()
    
    return render_template('petugas/dashboard.html',
                           deteksi_hari_ini=deteksi_hari_ini,
                           total_laporan=total_laporan,
                           kamera_online=kamera_online,
                           total_kamera=total_kamera,
                           deteksi_terbaru=deteksi_terbaru)

@app.route('/kamera')
@petugas_required
def kamera():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM kamera ORDER BY id ASC")
    cameras = cur.fetchall()
    cur.close()

    # Dapatkan daftar rekaman simulasi yang spesifik untuk user ini
    user_video_dir = os.path.join('static', 'videos', str(session['user_id']))
    videos = sorted([f for f in os.listdir(user_video_dir) if f.lower().endswith(('.mp4', '.avi', '.mkv'))]) if os.path.exists(user_video_dir) else []

    return render_template('petugas/kamera.html', cameras=cameras, videos=videos)

@app.route('/upload_video', methods=['POST'])
@petugas_required
def upload_video():

    # MODE RTSP
    rtsp_url = request.form.get('rtsp_url')

    if rtsp_url and rtsp_url.startswith('rtsp://'):
        return redirect(url_for('video_feed', source=rtsp_url))

    # MODE UPLOAD VIDEO
    if 'video' not in request.files:
        flash('Tidak ada file yang dipilih.', 'danger')
        return redirect(url_for('kamera'))

    file = request.files['video']

    if file.filename == '':
        flash('Tidak ada file yang dipilih.', 'danger')
        return redirect(url_for('kamera'))

    if file and file.filename.lower().endswith(('.mp4', '.avi', '.mkv')):
        filename = secure_filename(file.filename)

        user_video_dir = os.path.join(
            'static',
            'videos',
            str(session['user_id'])
        )

        os.makedirs(user_video_dir, exist_ok=True)

        save_path = os.path.join(user_video_dir, filename)

        file.save(save_path)

        flash('Video berhasil diupload.', 'success')

    else:
        flash('Format file tidak didukung. Gunakan mp4, avi, atau mkv.', 'danger')

    return redirect(url_for('kamera'))

@app.route('/delete_video/<filename>', methods=['POST'])
@petugas_required
def delete_video(filename):
    file_path = os.path.join('static', 'videos', str(session['user_id']), secure_filename(filename))
    import time
    if os.path.exists(file_path):
        # Retry up to 5 times due to Windows locking in MJPEG stream
        deleted = False
        for _ in range(5):
            try:
                os.remove(file_path)
                deleted = True
                break
            except PermissionError:
                time.sleep(0.5)
        
        if deleted:
            flash('Video berhasil dihapus.', 'success')
        else:
            flash('Gagal menghapus video karena file sedang digunakan.', 'danger')
    else:
        flash('File tidak ditemukan.', 'danger')
    return redirect(url_for('kamera'))

def send_telegram_alert(jenis_benda, conf_val, filepath, camera_name, latitude='', longitude='', user_chat_id='', nama_toko=''):
    token = app.config.get('TELEGRAM_BOT_TOKEN')
    admin_chat_id = app.config.get('TELEGRAM_CHAT_ID')
    
    if not token:
        print("Telegram Config belum diset. Batal mengirim pesan.")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    
    # --- Pesan untuk Pusat Keamanan (Admin) ---
    if admin_chat_id:
        pesan_admin = f"⚠️ *PERINGATAN ANCAMAN SENJATA* ⚠️\nTerdeteksi : {jenis_benda} ({(conf_val*100):.1f}%)\nNama Toko : {nama_toko}"
        if latitude and longitude:
            pesan_admin += f"\nLokasi : [Buka Google Maps](https://www.google.com/maps?q={latitude},{longitude})"
        
        try:
            with open(filepath, 'rb') as photo:
                payload = {'chat_id': str(admin_chat_id), 'caption': pesan_admin, 'parse_mode': 'Markdown'}
                files = {'photo': photo}
                response = requests.post(url, data=payload, files=files)
                if response.status_code == 200:
                    print(f"Berhasil mengirim notifikasi Telegram ke Admin {admin_chat_id}.")
                else:
                    print(f"Gagal mengirim Telegram ke Admin {admin_chat_id}:", response.text)
        except Exception as e:
            print(f"Error mengirim Telegram ke Admin {admin_chat_id}:", e)

    # --- Pesan untuk Petugas Minimarket (User) ---
    if user_chat_id:
        pesan_user = f"⚠️ *PERINGATAN MINIMARKETMU* ⚠️\nTerdeteksi : {jenis_benda} ({(conf_val*100):.1f}%)\nKamera : {camera_name}"
        try:
            payload = {'chat_id': str(user_chat_id), 'caption': pesan_user, 'parse_mode': 'Markdown'}
            with open(filepath, 'rb') as photo_user:
                files_user = {'photo': photo_user}
                response = requests.post(url, data=payload, files=files_user)
                if response.status_code == 200:
                    print(f"Berhasil mengirim notifikasi Telegram ke User {user_chat_id}.")
                else:
                    print(f"Gagal mengirim Telegram ke User {user_chat_id}:", response.text)
        except Exception as e:
            print(f"Error mengirim Telegram ke User {user_chat_id}:", e)

def generate_frames(video_source, user_id=1):
    global sim_state
    cap = cv2.VideoCapture(video_source, cv2.CAP_FFMPEG)

    if not cap.isOpened():
      print("Gagal membuka RTSP:", video_source)
      return
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0: fps = 30
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    sim_state['total_sec'] = total_frames / fps if total_frames > 0 else 0
    sim_state['paused'] = False
    
    import time
    last_frame_bytes = None
    frame_idx = 0
    last_detection_time = 0
    last_boxes = None
    last_results = None
    
    fps_start_time = time.time()
    frame_count_for_fps = 0

    try:
        while True:
            if sim_state['paused']:
                time.sleep(0.1)
                fps_start_time = time.time()
                frame_count_for_fps = 0
                continue
                
            loop_start = time.time()
            speed = sim_state.get('speed', 1.0)
            
            # Jika dipercepat, lewati beberapa frame pembacaan
            if speed > 1.0:
                skips = int(speed) - 1
                for _ in range(skips):
                    cap.read()
            
            success, frame = cap.read()
            if not success:
                if isinstance(video_source, str) and not str(video_source).startswith(('http', 'rtsp')):
                    sim_state['paused'] = True
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    sim_state['current_sec'] = 0
                    time.sleep(0.1)
                    continue
                else:
                    break
            
            frame_idx += 1

            current_frame = cap.get(cv2.CAP_PROP_POS_FRAMES)
            sim_state['current_sec'] = current_frame / fps if fps > 0 else 0
            
            # Proses frame dengan Frame Skipping cerdas untuk smoothness maksimal
            if yolo_model:
                # is_inference_frame = (frame_idx % 2 == 0)
                is_inference_frame = True
                if is_inference_frame:
                    try:
                        # Menggunakan GPU NVIDIA (device=0) untuk kecepatan maksimal (half=False agar optimal di MX350)
                        results = yolo_model.predict(frame, conf=0.5, verbose=False, imgsz=320, device=0, half=False)
                        last_results = results
                    except Exception as e:
                        # Fallback ke CPU jika CUDA gagal
                        err_msg = f"GPU Error, fallback ke CPU: {e}"
                        print(err_msg)
                        try:
                            with open("gpu_errors.log", "a") as f_log:
                                f_log.write(f"{datetime.now()}: {err_msg}\n")
                        except:
                            pass
                        results = yolo_model.predict(frame, conf=0.5, verbose=False, imgsz=320, device='cpu')
                        last_results = results
                else:
                    # Gunakan hasil deteksi terakhir (jika ada) untuk digambar di frame ini
                    if 'last_results' in locals() and last_results is not None:
                        results = last_results
                    else:
                        results = None

                if results:
                    frame = results[0].plot(img=frame)

                    # ---- Auto Capture & Laporan (Hanya dijalankan pada frame inferensi asli untuk efisiensi) ----
                    if is_inference_frame and len(results[0].boxes) > 0:
                        current_time = time.time()
                        if current_time - last_detection_time > 5.0:  # Cooldown 5 detik
                            last_detection_time = current_time
                            
                            # Ambil objek dengan confidence tertinggi
                            boxes = results[0].boxes
                            best_box = max(boxes, key=lambda x: x.conf[0].item())
                            cls_id = int(best_box.cls[0].item())
                            conf_val = float(best_box.conf[0].item())
                            jenis_benda = yolo_model.names[cls_id]
                            
                            # Simpan gambar bukti
                            filename = f"det_{int(current_time)}.jpg"
                            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                            cv2.imwrite(filepath, frame)
                            
                            # Simpan ke Database
                            with app.app_context():
                                try:
                                    cur = mysql.connection.cursor()
                                    cam_id_val = 1 if sim_state.get('filename') == 'cctv' else None
                                    cur.execute('''
                                        INSERT INTO deteksi (id_kamera, jenis_benda, kepercayaan, bukti, id_petugas)
                                        VALUES (%s, %s, %s, %s, %s)
                                    ''', (cam_id_val, jenis_benda, conf_val, filename, user_id))
                                    
                                    det_id = cur.lastrowid
                                    cur.execute('''
                                        INSERT INTO notifikasi (id_deteksi, jenis_benda, kepercayaan, sudah_dibaca, id_petugas)
                                        VALUES (%s, %s, %s, 0, %s)
                                    ''', (det_id, jenis_benda, conf_val, user_id))
                                
                                    # Ambil telegram_id (sebagai chat id), koordinat & nama_toko khusus milik user/minimarket ini
                                    cur.execute("SELECT telegram_id, alamat, lintang, bujur, nama_toko FROM petugas_minimarket WHERE id = %s", (user_id,))
                                    user_data = cur.fetchone()
                                    u_lat = user_data['lintang'] if user_data and user_data['lintang'] else ''
                                    u_lng = user_data['bujur'] if user_data and user_data['bujur'] else ''
                                    u_chat_id = user_data['telegram_id'] if user_data and user_data['telegram_id'] else ''
                                    u_nama_toko = user_data['nama_toko'] if user_data and user_data['nama_toko'] else 'Minimarket'

                                    mysql.connection.commit()
                                    cur.close()
                                    print(f"Deteksi tersimpan: {jenis_benda} ({conf_val*100:.1f}%)")
                                    
                                    camera_name = "Simulasi CCTV" if sim_state.get('filename') != 'cctv' else "Kamera Utama"
                                    # Kirim Telegram Async agar stream tidak lag
                                    threading.Thread(target=send_telegram_alert, args=(jenis_benda, conf_val, filepath, camera_name, u_lat, u_lng, u_chat_id, u_nama_toko)).start()
                                except Exception as e:
                                    print("Gagal menyimpan ke database:", e)
            
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            
            last_frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + last_frame_bytes + b'\r\n')
                   
            # Hitung aktual FPS
            frame_count_for_fps += 1
            curr_time = time.time()
            if curr_time - fps_start_time >= 1.0:
                sim_state['actual_fps'] = frame_count_for_fps
                frame_count_for_fps = 0
                fps_start_time = curr_time
                
            # Pelambatan (Slow-motion)
            target_delay = (1.0 / fps) / speed
            elapsed = time.time() - loop_start
            if elapsed < target_delay:
                time.sleep(target_delay - elapsed)
                
    finally:
        cap.release()

@app.route('/video_feed')
@login_required
def video_feed():
    global sim_state
    source = request.args.get('source')
    user_id_str = str(session.get('user_id', 1))
    if source and os.path.exists(os.path.join('static', 'videos', user_id_str, source)):
        video_source = os.path.join('static', 'videos', user_id_str, source)
        sim_state['filename'] = source
    else:
        video_source = source if source else 0
        if str(video_source).strip() == '0':
            video_source = 0
        sim_state['filename'] = 'cctv'
        
    user_id = session.get('user_id', 1)
    return Response(generate_frames(video_source, user_id), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/sim_control', methods=['POST'])
@petugas_required
def sim_control():
    global sim_state
    data = request.get_json(silent=True) or {}
    action = data.get('action')
    if action == 'pause':
        sim_state['paused'] = True
    elif action == 'play':
        sim_state['paused'] = False
    return jsonify({'status': 'ok', 'paused': sim_state['paused']})

@app.route('/api/sim_speed', methods=['POST'])
@petugas_required
def sim_speed():
    global sim_state
    data = request.get_json(silent=True) or {}
    sim_state['speed'] = float(data.get('speed', 1.0))
    return jsonify({'status': 'ok'})

@app.route('/api/sim_status', methods=['GET'])
@login_required
def sim_status():
    global sim_state
    
    detecting = False
    det_msg = "Menunggu deteksi..."
    
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT waktu, jenis_benda FROM deteksi WHERE id_petugas = %s ORDER BY waktu DESC LIMIT 1", (session['user_id'],))
        last_det = cur.fetchone()
        cur.close()
        
        if last_det and (datetime.now() - last_det['waktu']).total_seconds() < 5:
            detecting = True
            det_msg = f"⚠ {last_det['jenis_benda']} terdeteksi!"
    except Exception as e:
        pass

    return jsonify({
        'current_sec': sim_state['current_sec'],
        'total_sec': sim_state['total_sec'],
        'paused': sim_state['paused'],
        'filename': sim_state['filename'],
        'detecting': detecting,
        'det_msg': det_msg,
        'actual_fps': sim_state.get('actual_fps', 0)
    })

@app.route('/laporan')
@petugas_required
def laporan():
    tanggal = request.args.get('tanggal', '')
    
    cur = mysql.connection.cursor()
    
    # Total deteksi
    cur.execute("SELECT COUNT(*) as total FROM deteksi WHERE id_petugas = %s", (session['user_id'],))
    total_deteksi = cur.fetchone()['total']
    
    # Query laporan dengan filter tanggal
    if tanggal:
        cur.execute("""
            SELECT d.*, CONCAT('Kamera ', c.id) as camera_name 
            FROM deteksi d
            LEFT JOIN kamera c ON d.id_kamera = c.id
            WHERE DATE(d.waktu) = %s AND d.id_petugas = %s
            ORDER BY d.waktu DESC
        """, (tanggal, session['user_id']))
    else:
        cur.execute("""
            SELECT d.*, CONCAT('Kamera ', c.id) as camera_name 
            FROM deteksi d
            LEFT JOIN kamera c ON d.id_kamera = c.id
            WHERE d.id_petugas = %s
            ORDER BY d.waktu DESC
        """, (session['user_id'],))
    
    laporan_list = cur.fetchall()
    cur.close()
    
    return render_template('petugas/laporan.html',
                           laporan_list=laporan_list,
                           total_deteksi=total_deteksi,
                           tanggal=tanggal)

@app.route('/laporan/hapus/<int:deteksi_id>', methods=['POST'])
@petugas_required
def hapus_laporan(deteksi_id):
    cur = mysql.connection.cursor()
    # Hapus deteksi
    cur.execute("DELETE FROM deteksi WHERE id = %s AND id_petugas = %s", (deteksi_id, session['user_id']))
    mysql.connection.commit()
    cur.close()
    flash('Data deteksi berhasil dihapus.', 'success')
    return redirect(url_for('laporan'))

@app.route('/laporan/hapus-semua', methods=['POST'])
@petugas_required
def hapus_semua_laporan():
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM deteksi WHERE id_petugas = %s", (session['user_id'],))
    mysql.connection.commit()
    cur.close()
    flash('Semua riwayat deteksi berhasil dibersihkan.', 'success')
    return redirect(url_for('laporan'))

@app.route('/notifikasi')
@petugas_required
def notifikasi():
    tanggal = request.args.get('tanggal', '')
    
    cur = mysql.connection.cursor()
    
    if tanggal:
        cur.execute("""
            SELECT n.id, n.id_deteksi, n.waktu, n.bukti, n.sudah_dibaca AS is_read, n.id_petugas,
                   COALESCE(n.jenis_benda, 'Objek Telah Dihapus') as jenis_benda, n.kepercayaan as confidence
            FROM notifikasi n
            WHERE DATE(n.waktu) = %s AND n.id_petugas = %s
            ORDER BY n.waktu DESC
        """, (tanggal, session['user_id']))
    else:
        cur.execute("""
            SELECT n.id, n.id_deteksi, n.waktu, n.bukti, n.sudah_dibaca AS is_read, n.id_petugas,
                   COALESCE(n.jenis_benda, 'Objek Telah Dihapus') as jenis_benda, n.kepercayaan as confidence
            FROM notifikasi n
            WHERE n.id_petugas = %s
            ORDER BY n.waktu DESC
        """, (session['user_id'],))
    
    notif_list = cur.fetchall()
    
    # Mark as read
    cur.execute("""
        UPDATE notifikasi 
        SET sudah_dibaca = TRUE 
        WHERE sudah_dibaca = FALSE AND id_petugas = %s
    """, (session['user_id'],))
    mysql.connection.commit()
    
    cur.close()
    
    return render_template('petugas/notifikasi.html',
                           notif_list=notif_list,
                           tanggal=tanggal)

@app.route('/notifikasi/hapus/<int:notif_id>', methods=['POST'])
@petugas_required
def hapus_notifikasi(notif_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM notifikasi WHERE id = %s AND id_petugas = %s", (notif_id, session['user_id']))
    mysql.connection.commit()
    cur.close()
    flash('Notifikasi berhasil dihapus.', 'success')
    return redirect(url_for('notifikasi'))

@app.route('/notifikasi/hapus-semua', methods=['POST'])
@petugas_required
def hapus_semua_notifikasi():
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM notifikasi WHERE id_petugas = %s", (session['user_id'],))
    mysql.connection.commit()
    cur.close()
    flash('Semua riwayat notifikasi berhasil dibersihkan.', 'success')
    return redirect(url_for('notifikasi'))

@app.route('/pengaturan', methods=['GET', 'POST'])
@petugas_required
def pengaturan():
    from werkzeug.security import generate_password_hash
    cur = mysql.connection.cursor()
    user_id = session.get('user_id')
    
    if request.method == 'POST':
        name = request.form.get('name')
        nama_toko = request.form.get('nama_toko')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        telegram_id = request.form.get('telegram_id')
        alamat = request.form.get('alamat')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        
        if 'avatar' in request.files:
            avatar = request.files['avatar']
            if avatar and avatar.filename != '':
                ext = avatar.filename.rsplit('.', 1)[1].lower() if '.' in avatar.filename else 'jpg'
                if ext in ['jpg', 'jpeg', 'png']:
                    # Resize and save or just save directly (saving directly for simplicity)
                    import cv2
                    import numpy as np
                    
                    try:
                        # Attempt to make it properly square just for elegance if cv2 exists
                        avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars', f"user_{user_id}.jpg")
                        file_bytes = np.frombuffer(avatar.read(), np.uint8)
                        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                        if img is not None:
                            # center crop it
                            h, w = img.shape[:2]
                            min_dim = min(h, w)
                            start_x = w // 2 - min_dim // 2
                            start_y = h // 2 - min_dim // 2
                            cropped_img = img[start_y:start_y+min_dim, start_x:start_x+min_dim]
                            
                            # Reduce size
                            resized_img = cv2.resize(cropped_img, (300, 300), interpolation=cv2.INTER_AREA)
                            cv2.imwrite(avatar_path, resized_img)
                            flash('Foto profil berhasil diunggah.', 'success')
                    except Exception as e:
                        print("Error rendering avatar:", e)
                        pass

        if new_password:
            if new_password != confirm_password:
                flash('Kata sandi baru tidak cocok.', 'danger')
            else:
                hashed_pw = generate_password_hash(new_password)
                cur.execute("UPDATE petugas_minimarket SET nama = %s, nama_toko = %s, kata_sandi = %s, telegram_id = %s, alamat = %s, lintang = %s, bujur = %s WHERE id = %s", 
                            (name, nama_toko, hashed_pw, telegram_id, alamat, latitude, longitude, user_id))
                mysql.connection.commit()
                session['user_name'] = name
                flash('Profil, lokasi, dan kata sandi berhasil diperbarui.', 'success')
        else:
            cur.execute("UPDATE petugas_minimarket SET nama = %s, nama_toko = %s, telegram_id = %s, alamat = %s, lintang = %s, bujur = %s WHERE id = %s", 
                        (name, nama_toko, telegram_id, alamat, latitude, longitude, user_id))
            mysql.connection.commit()
            session['user_name'] = name
            flash('Profil dan lokasi berhasil diperbarui.', 'success')
            
        cur.close()
        return redirect(url_for('pengaturan'))
        
    cur.execute("SELECT email, nama_toko, alamat, telegram_id, lintang as latitude, bujur as longitude FROM petugas_minimarket WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    
    return render_template('petugas/pengaturan.html', user=user)

# ─── API ROUTES ───────────────────────────────────────────────────────────────
@app.route('/api/notif-count')
@login_required
def notif_count():
    cur = mysql.connection.cursor()
    if session.get('role') == 'petugas':
        cur.execute("""
            SELECT COUNT(id) as total FROM notifikasi
            WHERE sudah_dibaca = FALSE AND id_petugas = %s
        """, (session['user_id'],))
    else:
        cur.execute("SELECT COUNT(*) as total FROM notifikasi_pusat WHERE sudah_dibaca = FALSE")
    count = cur.fetchone()['total']
    cur.close()
    return jsonify({'count': count})

@app.route('/api/notif-read/<int:notif_id>', methods=['POST'])
@login_required
def notif_read(notif_id):
    cur = mysql.connection.cursor()
    if session.get('role') == 'petugas':
        cur.execute("UPDATE notifikasi SET sudah_dibaca = TRUE WHERE id = %s", (notif_id,))
    else:
        cur.execute("UPDATE notifikasi_pusat SET sudah_dibaca = TRUE WHERE id = %s", (notif_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

@app.route('/api/notif-recent')
@login_required
def notif_recent():
    cur = mysql.connection.cursor()
    if session.get('role') == 'petugas':
        cur.execute("""
            SELECT n.id, n.waktu, n.sudah_dibaca as is_read,
                   COALESCE(n.jenis_benda, 'Dihapus') as jenis_benda, n.kepercayaan as confidence, n.bukti,
                   CONCAT('Kamera ', c.id) as camera_name
            FROM notifikasi n
            LEFT JOIN deteksi d ON n.id_deteksi = d.id
            LEFT JOIN kamera c ON d.id_kamera = c.id
            WHERE n.id_petugas = %s
            ORDER BY n.waktu DESC
            LIMIT 5
        """, (session['user_id'],))
    else:
        cur.execute("""
            SELECT np.id, np.waktu, np.sudah_dibaca as is_read,
                   lk.jenis_benda, lk.kepercayaan as confidence, lk.bukti,
                   CONCAT('Kamera ', lk.id_kamera) as camera_name
            FROM notifikasi_pusat np
            LEFT JOIN laporan_keamanan lk ON np.id_laporan = lk.id
            ORDER BY np.waktu DESC
            LIMIT 5
        """)
    rows = cur.fetchall()
    cur.close()

    result = []
    for r in rows:
        result.append({
            'id':          r['id'],
            'waktu':       r['waktu'].strftime('%d/%m/%Y %I:%M %p') if r['waktu'] else '',
            'is_read':     bool(r['is_read']),
            'jenis_benda': r['jenis_benda'] or '—',
            'confidence':  round(float(r['confidence']) * 100) if r['confidence'] else 0,
            'camera_name': r['camera_name'] or '—',
            'bukti':       r['bukti'] or ''
        })
    return jsonify(result)

@app.route('/api/kamera-status')
@login_required
def kamera_status():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, CONCAT('Kamera ', id) as name, status FROM kamera")
    cameras = cur.fetchall()
    cur.close()
    return jsonify(cameras)

# ─── DC ROUTES ───────────────────────────────────────────────────────────────

def dc_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'datacenter':
            flash('Anda tidak memiliki akses ke halaman Data Center.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/dc/dashboard')
@dc_required
def dc_dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) as total FROM laporan_keamanan")
    laporan_masuk = cur.fetchone()['total']
    cur.close()
    
    return render_template('pusat_keamanan/dashboard.html', laporan_masuk=laporan_masuk)

@app.route('/dc/laporan_keamanan')
@dc_required
def dc_laporan_keamanan():
    tanggal = request.args.get('tanggal', '')
    cur = mysql.connection.cursor()
    
    query = '''
        SELECT d.*, u.alamat as user_alamat, u.lintang as user_lat, u.bujur as user_lng, d.nama_toko as user_nama_toko
        FROM laporan_keamanan d
        LEFT JOIN petugas_minimarket u ON d.id_petugas = u.id
    '''
    params = ()
    if tanggal:
        query += " WHERE DATE(d.waktu) = %s"
        params = (tanggal,)
    query += " ORDER BY d.waktu DESC"
    
    cur.execute(query, params)
    laporan_list = cur.fetchall()
    cur.close()
    
    return render_template('pusat_keamanan/laporan_keamanan.html', laporan_list=laporan_list, tanggal=tanggal)


@app.route('/dc/notifikasi')
@dc_required
def dc_notifikasi():
    tanggal = request.args.get('tanggal', '')
    cur = mysql.connection.cursor()
    
    query = '''
        SELECT np.id, np.id_laporan, np.waktu, np.bukti, np.sudah_dibaca AS is_read,
               lk.jenis_benda, lk.bukti as det_bukti, CONCAT('Kamera ', lk.id_kamera) as camera_name
        FROM notifikasi_pusat np
        LEFT JOIN laporan_keamanan lk ON np.id_laporan = lk.id
    '''
    params = ()
    if tanggal:
        query += " WHERE DATE(np.waktu) = %s"
        params = (tanggal,)
    query += " ORDER BY np.waktu DESC"
    
    cur.execute(query, params)
    notif_list = cur.fetchall()
    
    # Mark as read
    cur.execute("UPDATE notifikasi_pusat SET sudah_dibaca = TRUE WHERE sudah_dibaca = FALSE")
    mysql.connection.commit()
    
    cur.close()
    
    return render_template('pusat_keamanan/notifikasi.html', notif_list=notif_list, tanggal=tanggal)

@app.route('/dc/notifikasi/hapus/<int:notif_id>', methods=['POST'])
@dc_required
def dc_hapus_notifikasi(notif_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM notifikasi_pusat WHERE id = %s", (notif_id,))
    mysql.connection.commit()
    cur.close()
    flash('Notifikasi berhasil dihapus.', 'success')
    return redirect(url_for('dc_notifikasi'))

@app.route('/dc/laporan/hapus/<int:deteksi_id>', methods=['POST'])
@dc_required
def dc_hapus_laporan(deteksi_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM laporan_keamanan WHERE id = %s", (deteksi_id,))
    mysql.connection.commit()
    cur.close()
    flash('Data laporan berhasil dihapus.', 'success')
    return redirect(request.referrer or url_for('dc_laporan_keamanan'))

@app.route('/dc/laporan/hapus-semua', methods=['POST'])
@dc_required
def dc_hapus_semua_laporan():
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM notifikasi_pusat")
    cur.execute("DELETE FROM laporan_keamanan")
    mysql.connection.commit()
    cur.close()
    flash('Semua riwayat laporan keamanan berhasil dibersihkan.', 'success')
    return redirect(request.referrer or url_for('dc_laporan_keamanan'))

@app.route('/dc/notifikasi/hapus-semua', methods=['POST'])
@dc_required
def dc_hapus_semua_notifikasi():
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM notifikasi_pusat")
    mysql.connection.commit()
    cur.close()
    flash('Semua riwayat notifikasi berhasil dibersihkan.', 'success')
    return redirect(url_for('dc_notifikasi'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)

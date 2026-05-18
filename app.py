from flask import Flask, render_template, request, redirect, session, flash, make_response
from functools import wraps
import psycopg2
import os
import random
import json
import urllib.request
from datetime import date, datetime, timedelta
import threading

# ── Configuración de correo via SendGrid ─────────────────────────────────────
# Render Free bloquea SMTP (puertos 465/587).
# SendGrid usa HTTPS (puerto 443) que Render sí permite.
# Crea cuenta gratuita en sendgrid.com y agrega SENDGRID_KEY en Render.
SENDGRID_KEY = os.getenv("SENDGRID_KEY", "")
MAIL_USER    = os.getenv("MAIL_USER", "mediclover19@gmail.com")

def enviar_correo(destinatario, asunto, cuerpo_html):
    """Envía correo via SendGrid HTTP API (funciona en Render Free)."""
    if not SENDGRID_KEY:
        print("⚠️  SENDGRID_KEY no configurado — correo omitido")
        return False
    try:
        payload = json.dumps({
            "personalizations": [{"to": [{"email": destinatario}]}],
            "from": {"email": MAIL_USER, "name": "MediClover"},
            "subject": asunto,
            "content": [{"type": "text/html", "value": cuerpo_html}]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=payload,
            headers={
                "Authorization": f"Bearer {SENDGRID_KEY}",
                "Content-Type":  "application/json",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 202:
                print(f"✅ Correo enviado a {destinatario}")
                return True
            print(f"⚠️  SendGrid status {resp.status}")
            return False
    except Exception as e:
        print(f"⚠️  Error al enviar correo: {e}")
        return False


def enviar_correo_async(destinatario, asunto, cuerpo_html):
    """Envía el correo en un hilo de fondo — no bloquea la respuesta HTTP."""
    threading.Thread(
        target=enviar_correo,
        args=(destinatario, asunto, cuerpo_html),
        daemon=True
    ).start()



def enviar_confirmacion_cita(correo_paciente, nombre_paciente, fecha, hora, descripcion):
    """
    Envía un correo HTML de confirmación al paciente tras reservar una cita.
    Llamar después de hacer el INSERT en la BD.
    """
    # Formatear hora para mostrar
    if hasattr(hora, 'strftime'):
        hora_str = hora.strftime('%H:%M')
    else:
        hora_str = str(hora)[:5]

    # Formatear fecha
    if hasattr(fecha, 'strftime'):
        fecha_str = fecha.strftime('%A %d de %B de %Y')
        # Capitalizar primera letra
        fecha_str = fecha_str.capitalize()
    else:
        fecha_str = str(fecha)

    # Hora de fin (35 minutos después)
    try:
        hora_dt  = datetime.strptime(hora_str, '%H:%M')
        hora_fin = (hora_dt + timedelta(minutes=35)).strftime('%H:%M')
    except Exception:
        hora_fin = '—'

    cuerpo = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Confirmación de cita — MediClover</title>
    </head>
    <body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#f4f7f5;">

      <div style="max-width:580px;margin:32px auto;background:#ffffff;border-radius:16px;
                  overflow:hidden;box-shadow:0 4px 24px rgba(11,31,58,.1);">

        <!-- Header verde -->
        <div style="background:linear-gradient(135deg,#0b1f3a 0%,#162f55 100%);
                    padding:36px 40px;text-align:center;position:relative;">
          <div style="display:inline-flex;align-items:center;justify-content:center;
                      width:64px;height:64px;background:rgba(10,124,92,.25);
                      border:1px solid rgba(10,124,92,.4);border-radius:16px;
                      margin-bottom:16px;">
            <span style="font-size:28px;">📅</span>
          </div>
          <h1 style="margin:0 0 6px;color:#ffffff;font-size:22px;font-weight:700;
                     font-family:Georgia,serif;">¡Cita confirmada!</h1>
          <p style="margin:0;color:rgba(255,255,255,0.6);font-size:14px;">
            Tu reserva ha sido registrada exitosamente
          </p>
        </div>

        <!-- Saludo -->
        <div style="padding:32px 40px 0;">
          <p style="margin:0 0 20px;color:#334155;font-size:15px;line-height:1.7;">
            Hola <strong style="color:#0b1f3a;">{nombre_paciente}</strong>, 👋<br>
            Tu cita médica ha sido <strong style="color:#16a34a;">confirmada con éxito</strong>.
            Aquí tienes todos los detalles:
          </p>
        </div>

        <!-- Tarjeta de detalles -->
        <div style="margin:0 40px;background:#f0fdf4;border:1px solid #bbf7d0;
                    border-radius:12px;overflow:hidden;">

          <!-- Fila: Doctor -->
          <div style="display:flex;align-items:center;gap:12px;
                      padding:14px 20px;border-bottom:1px solid #dcfce7;">
            <div style="width:36px;height:36px;background:#dcfce7;border-radius:8px;
                        display:flex;align-items:center;justify-content:center;
                        font-size:16px;flex-shrink:0;">👨‍⚕️</div>
            <div>
              <div style="font-size:11px;color:#6b7280;text-transform:uppercase;
                          letter-spacing:.06em;font-weight:700;">Doctor</div>
              <div style="font-size:14px;color:#0b1f3a;font-weight:600;margin-top:1px;">
                Dr. Luis Suárez · Médico General
              </div>
            </div>
          </div>

          <!-- Fila: Fecha -->
          <div style="display:flex;align-items:center;gap:12px;
                      padding:14px 20px;border-bottom:1px solid #dcfce7;">
            <div style="width:36px;height:36px;background:#dcfce7;border-radius:8px;
                        display:flex;align-items:center;justify-content:center;
                        font-size:16px;flex-shrink:0;">📆</div>
            <div>
              <div style="font-size:11px;color:#6b7280;text-transform:uppercase;
                          letter-spacing:.06em;font-weight:700;">Fecha</div>
              <div style="font-size:14px;color:#0b1f3a;font-weight:600;margin-top:1px;">
                {fecha_str}
              </div>
            </div>
          </div>

          <!-- Fila: Hora -->
          <div style="display:flex;align-items:center;gap:12px;
                      padding:14px 20px;border-bottom:1px solid #dcfce7;">
            <div style="width:36px;height:36px;background:#dcfce7;border-radius:8px;
                        display:flex;align-items:center;justify-content:center;
                        font-size:16px;flex-shrink:0;">🕐</div>
            <div>
              <div style="font-size:11px;color:#6b7280;text-transform:uppercase;
                          letter-spacing:.06em;font-weight:700;">Hora</div>
              <div style="font-size:14px;color:#0b1f3a;font-weight:600;margin-top:1px;">
                {hora_str} – {hora_fin}
                <span style="font-size:12px;color:#6b7280;font-weight:400;">(35 minutos)</span>
              </div>
            </div>
          </div>

          <!-- Fila: Motivo -->
          <div style="display:flex;align-items:flex-start;gap:12px;padding:14px 20px;">
            <div style="width:36px;height:36px;background:#dcfce7;border-radius:8px;
                        display:flex;align-items:center;justify-content:center;
                        font-size:16px;flex-shrink:0;margin-top:2px;">💬</div>
            <div>
              <div style="font-size:11px;color:#6b7280;text-transform:uppercase;
                          letter-spacing:.06em;font-weight:700;">Motivo de consulta</div>
              <div style="font-size:14px;color:#0b1f3a;margin-top:1px;line-height:1.6;">
                {descripcion}
              </div>
            </div>
          </div>

        </div>

        <!-- Recordatorio -->
        <div style="margin:20px 40px;background:#fefce8;border:1px solid #fde68a;
                    border-radius:10px;padding:14px 18px;display:flex;
                    align-items:flex-start;gap:10px;">
          <span style="font-size:18px;flex-shrink:0;margin-top:1px;">⚠️</span>
          <div style="font-size:13px;color:#92400e;line-height:1.65;">
            <strong>Recuerda:</strong> Si necesitas cancelar tu cita, puedes hacerlo
            desde tu panel en MediClover con al menos unas horas de anticipación.
          </div>
        </div>

        <!-- CTA -->
        <div style="padding:20px 40px 36px;text-align:center;">
          <a href="https://mediclover.onrender.com/panel_paciente"
             style="display:inline-block;background:#0a7c5c;color:#ffffff;
                    text-decoration:none;padding:13px 32px;border-radius:8px;
                    font-weight:700;font-size:15px;
                    box-shadow:0 4px 14px rgba(10,124,92,.35);">
            Ver mis citas →
          </a>
          <p style="margin:16px 0 0;font-size:12px;color:#94a3b8;">
            ¿Problemas con el botón? Visita
            <a href="https://mediclover.onrender.com" style="color:#0a7c5c;">
              mediclover.onrender.com
            </a>
          </p>
        </div>

        <!-- Footer -->
        <div style="background:#f4f7f5;border-top:1px solid #e2e8f0;
                    padding:18px 40px;text-align:center;">
          <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.6;">
            <strong style="color:#64748b;">MediClover</strong> — Sistema de Gestión de Citas Médicas<br>
            Este correo fue enviado automáticamente. Por favor no respondas a este mensaje.
          </p>
        </div>

      </div>
    </body>
    </html>
    """

    asunto = f"✅ Cita confirmada — {hora_str} del {fecha_str} · MediClover"
    # Usar async para no bloquear el worker de Gunicorn
    enviar_correo_async(correo_paciente, asunto, cuerpo)


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(32))

DURACION_CITA = 35  # minutos

# ── Horario del Dr. Luis Suárez: Lunes a Domingo 7:00 - 19:00 ──
HORA_APERTURA = "07:00"   # primera cita posible
HORA_CIERRE   = "19:00"   # última cita posible (la cita terminaría a las 19:35 máx)

# ── Constantes de rol (números, no strings — más difícil de manipular)
ROL_ADMIN    = 1
ROL_DOCTOR   = 2
ROL_PACIENTE = 3

# ── Admins desde variable de entorno en Render
# Formato: "usuario:password,usuario2:password2"
# CAMBIA LAS CREDENCIALES EN Render → Environment → ADMIN_CREDENTIALS
_raw = os.getenv("ADMIN_CREDENTIALS", "Admin_Mediclover:MedicloverLuis56_19")
ADMINS = {}
for par in _raw.split(","):
    par = par.strip()
    if ":" in par:
        u, p = par.split(":", 1)
        ADMINS[u.strip()] = p.strip()

DATABASE_URL = os.getenv("DATABASE_URL")
conn = None

def get_conn():
    """
    Retorna la conexión global, reconectando si está cerrada o rota.
    Usa autocommit=False (psycopg2 default). El ping usa connection.closed
    en lugar de abrir un cursor extra que puede dejar la BD en estado sucio.
    """
    global conn
    try:
        # connection.closed == 0 significa que está abierta
        if conn and conn.closed == 0:
            return conn
    except Exception:
        pass
    # Reconectar
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        print("✅ (Re)conectado a PostgreSQL")
        return conn
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return None


def get_cursor():
    """
    Retorna (conexion, cursor) de la misma instancia.
    Siempre usar: _db, cursor = get_cursor()
    Siempre cerrar con: cursor.close()
    Siempre confirmar con: _db.commit()
    """
    c = get_conn()
    return c, c.cursor()


# ===============================
# CREAR TABLAS SI NO EXISTEN
# ===============================
def init_db():
    """
    Crea las tablas necesarias en Supabase.
    Usa una conexión PROPIA (no la global) para no interferir
    con el hilo principal mientras Gunicorn arranca.
    """
    if not DATABASE_URL:
        return
    try:
        c = psycopg2.connect(DATABASE_URL, sslmode="require")
        cursor = c.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctor (
                id_doctor    SERIAL PRIMARY KEY,
                nombre       VARCHAR(100) NOT NULL,
                apellido     VARCHAR(100) NOT NULL,
                correo       VARCHAR(150),
                password     VARCHAR(255) NOT NULL,
                especialidad VARCHAR(150) DEFAULT 'Médico General'
            )
        """)
        # Ampliar password si ya existe con VARCHAR(100)
        cursor.execute("""
            ALTER TABLE doctor
            ALTER COLUMN password TYPE VARCHAR(255)
        """)
        # Agregar campo password a paciente (para nuevos registros con contraseña)
        cursor.execute("""
            ALTER TABLE paciente
            ADD COLUMN IF NOT EXISTS password VARCHAR(255)
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS slot (
                id_slot    SERIAL PRIMARY KEY,
                id_doctor  INTEGER REFERENCES doctor(id_doctor) ON DELETE CASCADE,
                fecha      DATE NOT NULL,
                hora       TIME NOT NULL,
                disponible BOOLEAN DEFAULT TRUE
            )
        """)
        cursor.execute("ALTER TABLE cita ADD COLUMN IF NOT EXISTS id_doctor INTEGER REFERENCES doctor(id_doctor)")
        cursor.execute("ALTER TABLE cita ADD COLUMN IF NOT EXISTS id_slot   INTEGER REFERENCES slot(id_slot)")
        cursor.execute("ALTER TABLE cita ALTER COLUMN fecha DROP NOT NULL")
        cursor.execute("ALTER TABLE cita ALTER COLUMN hora  DROP NOT NULL")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historial_clinico (
                id_historial   SERIAL PRIMARY KEY,
                id_paciente    INTEGER REFERENCES paciente(id_paciente) ON DELETE CASCADE,
                id_doctor      INTEGER REFERENCES doctor(id_doctor),
                id_cita        INTEGER REFERENCES cita(id_cita),
                fecha_registro TIMESTAMPTZ DEFAULT NOW(),
                diagnostico    TEXT NOT NULL,
                tratamiento    TEXT,
                observaciones  TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS receta (
                id_receta     SERIAL PRIMARY KEY,
                id_paciente   INTEGER REFERENCES paciente(id_paciente) ON DELETE CASCADE,
                id_doctor     INTEGER REFERENCES doctor(id_doctor),
                id_cita       INTEGER REFERENCES cita(id_cita),
                fecha_emision TIMESTAMPTZ DEFAULT NOW(),
                medicamentos  TEXT NOT NULL,
                indicaciones  TEXT,
                duracion_dias INTEGER DEFAULT 7
            )
        """)
        # Tabla de notificaciones internas para el paciente
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notificacion (
                id_notif     SERIAL PRIMARY KEY,
                id_paciente  INTEGER REFERENCES paciente(id_paciente) ON DELETE CASCADE,
                tipo         VARCHAR(30) NOT NULL,
                mensaje      TEXT NOT NULL,
                leida        BOOLEAN DEFAULT FALSE,
                fecha        TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        c.commit()
        cursor.close()
        c.close()
        print("✅ BD inicializada")
    except Exception as e:
        print(f"⚠️  init_db error: {e}")


# ── Iniciar BD en hilo de fondo para no bloquear el arranque de Gunicorn ──
threading.Thread(target=init_db, daemon=True).start()


def _migrar_password_doctor():
    """
    Al arrancar, verifica si la contraseña del doctor está en texto plano.
    Si es así, la convierte a hash bcrypt automáticamente.
    Esto corre una sola vez por deploy y no interrumpe el servicio.
    """
    import time as _t
    _t.sleep(5)  # esperar a que init_db termine
    try:
        from werkzeug.security import generate_password_hash
        c = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = c.cursor()
        cur.execute("SELECT id_doctor, password FROM doctor LIMIT 1")
        doc = cur.fetchone()
        if doc:
            pwd = doc[1]
            # Los hashes de werkzeug empiezan con "pbkdf2:" o "scrypt:"
            if not (pwd.startswith("pbkdf2:") or pwd.startswith("scrypt:")):
                hashed = generate_password_hash(pwd)
                cur.execute("UPDATE doctor SET password=%s WHERE id_doctor=%s",
                            (hashed, doc[0]))
                c.commit()
                print("✅ Contraseña del doctor migrada a hash seguro")
        cur.close()
        c.close()
    except Exception as e:
        print(f"⚠️  _migrar_password_doctor: {e}")

threading.Thread(target=_migrar_password_doctor, daemon=True).start()


# ===============================
# HELPERS
# ===============================

# Rate limiting simple en memoria: { ip: {"intentos": n, "bloqueado_hasta": datetime} }
_login_intentos = {}

def _check_rate_limit(ip):
    """Retorna True si la IP está bloqueada."""
    from datetime import datetime as _dt
    entrada = _login_intentos.get(ip)
    if not entrada:
        return False
    if entrada.get("bloqueado_hasta") and _dt.now() < entrada["bloqueado_hasta"]:
        return True
    return False

def _registrar_fallo(ip):
    """Registra un intento fallido. Bloquea 15 min tras 5 fallos."""
    from datetime import datetime as _dt
    entrada = _login_intentos.get(ip, {"intentos": 0, "bloqueado_hasta": None})
    entrada["intentos"] += 1
    if entrada["intentos"] >= 5:
        entrada["bloqueado_hasta"] = _dt.now() + timedelta(minutes=15)
        entrada["intentos"] = 0
        print(f"⚠️  IP {ip} bloqueada por 15 min (5 intentos fallidos)")
    _login_intentos[ip] = entrada

def _limpiar_fallo(ip):
    """Login exitoso — limpiar contador."""
    _login_intentos.pop(ip, None)

def get_cursor():
    """Helper que retorna (conexión, cursor) siempre de la misma conexión."""
    c = get_conn()
    return c, c.cursor()

def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            rol_sesion = session.get("rol")
            # Verificación doble: clave específica + número de rol
            # Si falla cualquiera, limpia la sesión y redirige
            if role == "admin":
                if session.get("usuario") not in ADMINS or rol_sesion != ROL_ADMIN:
                    session.clear()
                    return redirect("/login")
            elif role == "doctor":
                if not session.get("doctor_id") or rol_sesion != ROL_DOCTOR:
                    session.clear()
                    return redirect("/login_doctor")
            elif role == "paciente":
                if not session.get("paciente_id") or rol_sesion != ROL_PACIENTE:
                    session.clear()
                    return redirect("/login_paciente")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def slot_solapado(id_doctor, fecha, hora_str, excluir_id=None):
    """True si la hora choca con un slot existente del doctor (±35 min)."""
    c = get_conn()
    cursor = c.cursor()
    q = "SELECT hora FROM slot WHERE id_doctor=%s AND fecha=%s"
    params = [id_doctor, fecha]
    if excluir_id:
        q += " AND id_slot != %s"
        params.append(excluir_id)
    cursor.execute(q, params)
    rows = cursor.fetchall()
    cursor.close()
    nueva = datetime.strptime(hora_str, "%H:%M")
    for (h,) in rows:
        existente = datetime.strptime(str(h)[:5], "%H:%M")
        if abs((nueva - existente).total_seconds()) / 60 < DURACION_CITA:
            return True
    return False


def slot_solapado_en_lista(hora_nueva_dt, horas_pendientes):
    """Verifica solapamiento contra una lista de horas ya planeadas (datetime)."""
    for h in horas_pendientes:
        if abs((hora_nueva_dt - h).total_seconds()) / 60 < DURACION_CITA:
            return True
    return False


# ================================================================
# HOME
# ================================================================
@app.route("/")
def home():
    return render_template("home.html")


# ================================================================
# ADMIN
# ================================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr
        if _check_rate_limit(ip):
            return render_template("login.html",
                error="Demasiados intentos fallidos. Espera 15 minutos.")
        usuario  = request.form.get("usuario", "").strip()
        password = request.form.get("password", "").strip()
        if usuario in ADMINS and ADMINS[usuario] == password:
            _limpiar_fallo(ip)
            session.clear()
            session["usuario"]      = usuario
            session["admin_nombre"] = usuario.capitalize()
            session["rol"]          = ROL_ADMIN   # número 1
            return redirect("/admin")
        _registrar_fallo(ip)
        return render_template("login.html", error="Credenciales incorrectas")
    return render_template("login.html")


@app.route("/admin")
@login_required(role="admin")
def admin():
    _db, cursor = get_cursor()
    cursor.execute("SELECT COUNT(*) FROM paciente")
    total_pacientes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cita WHERE estado='pendiente'")
    citas_pendientes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cita")
    total_citas = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM cita c JOIN slot s ON c.id_slot=s.id_slot
        WHERE s.fecha=(NOW() AT TIME ZONE 'America/Guayaquil')::DATE
    """)
    citas_hoy = cursor.fetchone()[0]

    cursor.execute("""
        SELECT c.id_cita, p.nombre, p.apellido, s.fecha, s.hora, c.estado
        FROM cita c
        JOIN paciente p ON c.id_paciente = p.id_paciente
        LEFT JOIN slot s ON c.id_slot = s.id_slot
        ORDER BY s.fecha DESC, s.hora DESC
        LIMIT 8
    """)
    citas_recientes = cursor.fetchall()
    cursor.close()

    return render_template("index.html",
        total_pacientes=total_pacientes,
        citas_pendientes=citas_pendientes,
        citas_hoy=citas_hoy,
        total_citas=total_citas,
        citas_recientes=citas_recientes
    )


@app.route("/pacientes")
@login_required(role="admin")
def pacientes():
    _db, cursor = get_cursor()
    cursor.execute("SELECT id_paciente,nombre,apellido,correo,telefono,cedula FROM paciente")
    lista = cursor.fetchall()
    cursor.close()
    return render_template("pacientes.html", pacientes=lista)


@app.route("/editar_paciente/<int:id>", methods=["GET", "POST"])
@login_required(role="admin")
def editar_paciente(id):
    _db, cursor = get_cursor()
    if request.method == "POST":
        cursor.execute("""
            UPDATE paciente SET nombre=%s,apellido=%s,correo=%s,telefono=%s,cedula=%s
            WHERE id_paciente=%s
        """, (request.form["nombre"], request.form["apellido"], request.form["correo"],
              request.form["telefono"], request.form["cedula"], id))
        _db.commit()
        cursor.close()
        return redirect("/pacientes")
    cursor.execute("SELECT nombre,apellido,correo,telefono,cedula FROM paciente WHERE id_paciente=%s", (id,))
    paciente = cursor.fetchone()
    cursor.close()
    return render_template("editar_paciente.html", paciente=paciente, origen="admin")


@app.route("/doctor/editar_paciente/<int:id>", methods=["GET", "POST"])
@login_required(role="doctor")
def doctor_editar_paciente(id):
    """El doctor puede corregir los datos básicos de un paciente desde su panel."""
    _db, cursor = get_cursor()
    if request.method == "POST":
        nombre    = request.form.get("nombre", "").strip()
        apellido  = request.form.get("apellido", "").strip()
        telefono  = request.form.get("telefono", "").strip()
        # El doctor puede editar nombre, apellido y teléfono
        # No modifica correo ni cédula (esos son identificadores únicos)
        if not nombre or not apellido:
            cursor.close()
            return redirect(request.referrer or "/doctor/historial")
        cursor.execute("""
            UPDATE paciente SET nombre=%s, apellido=%s, telefono=%s
            WHERE id_paciente=%s
        """, (nombre, apellido, telefono, id))
        _db.commit()
        cursor.close()
        return redirect(f"/doctor/historial_clinico/{id}")
    cursor.execute("""
        SELECT id_paciente, nombre, apellido, correo, telefono, cedula
        FROM paciente WHERE id_paciente=%s
    """, (id,))
    paciente = cursor.fetchone()
    cursor.close()
    if not paciente:
        return redirect("/doctor/historial")
    return render_template("editar_paciente.html", paciente=paciente, origen="doctor")


@app.route("/eliminar_paciente/<int:id>", methods=["POST"])
@login_required(role="admin")
def eliminar_paciente(id):
    _db, cursor = get_cursor()
    cursor.execute("DELETE FROM historial_clinico WHERE id_paciente=%s", (id,))
    cursor.execute("DELETE FROM receta           WHERE id_paciente=%s", (id,))
    cursor.execute("DELETE FROM cita             WHERE id_paciente=%s", (id,))
    cursor.execute("DELETE FROM paciente         WHERE id_paciente=%s", (id,))
    _db.commit()
    cursor.close()
    return redirect("/pacientes")


@app.route("/citas")
@login_required(role="admin")
def citas():
    _db, cursor = get_cursor()
    cursor.execute("""
        SELECT c.id_cita, p.nombre, p.apellido, s.fecha, s.hora,
               c.estado, c.descripcion, d.nombre, d.apellido
        FROM cita c
        JOIN  paciente p ON c.id_paciente = p.id_paciente
        LEFT JOIN slot   s ON c.id_slot   = s.id_slot
        LEFT JOIN doctor d ON c.id_doctor = d.id_doctor
        ORDER BY s.fecha DESC, s.hora DESC
    """)
    lista = cursor.fetchall()
    cursor.close()
    return render_template("citas.html", citas=lista)


@app.route("/completar_cita/<int:id>", methods=["POST"])
@login_required(role="admin")
def completar_cita(id):
    _db, cursor = get_cursor()
    cursor.execute("UPDATE cita SET estado='completada' WHERE id_cita=%s", (id,))
    _db.commit()
    cursor.close()
    return redirect("/citas")


@app.route("/cancelar_cita/<int:id>", methods=["POST"])
@login_required(role="admin")
def cancelar_cita(id):
    _db, cursor = get_cursor()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s", (id,))
    _db.commit()
    cursor.close()
    return redirect("/citas")


@app.route("/admin/hashear_doctor", methods=["POST"])
@login_required(role="admin")
def hashear_password_doctor():
    """
    Migra la contraseña del doctor de texto plano a hash seguro.
    Llamar una sola vez desde el panel de administración.
    """
    from werkzeug.security import generate_password_hash, check_password_hash
    _db, cursor = get_cursor()
    cursor.execute("SELECT id_doctor, password FROM doctor LIMIT 1")
    doc = cursor.fetchone()
    if doc:
        pwd = doc[1]
        # Solo hashear si todavía es texto plano (los hash empiezan con pbkdf2: o scrypt:)
        if not (pwd.startswith("pbkdf2:") or pwd.startswith("scrypt:")):
            hashed = generate_password_hash(pwd)
            cursor.execute("UPDATE doctor SET password=%s WHERE id_doctor=%s",
                           (hashed, doc[0]))
            _db.commit()
            msg = "✅ Contraseña del doctor migrada a hash seguro correctamente."
        else:
            msg = "ℹ️  La contraseña ya está en formato hash. No se hizo ningún cambio."
    else:
        msg = "⚠️  No se encontró ningún doctor en la base de datos."
    cursor.close()
    session["admin_msg"] = msg
    return redirect("/admin")


# ================================================================
# DOCTOR
# ================================================================
@app.route("/login_doctor", methods=["GET", "POST"])
def login_doctor():
    if not get_conn():
        return "Error BD"
    if request.method == "POST":
        ip = request.remote_addr
        if _check_rate_limit(ip):
            return render_template("login_doctor.html",
                error="Demasiados intentos fallidos. Espera 15 minutos.")
        _db, cursor = get_cursor()
        cursor.execute(
            "SELECT id_doctor, nombre, password FROM doctor WHERE usuario=%s",
            (request.form.get("usuario","").strip(),)
        )
        doc = cursor.fetchone()
        cursor.close()

        # Soporte dual: werkzeug hash O texto plano (migración gradual)
        password_ok = False
        if doc:
            stored = doc[2]
            try:
                from werkzeug.security import check_password_hash
                password_ok = check_password_hash(stored, request.form.get("password",""))
            except Exception:
                pass
            if not password_ok:
                password_ok = (stored == request.form.get("password",""))

        if doc and password_ok:
            _limpiar_fallo(ip)
            session.clear()
            session["doctor_id"]     = doc[0]
            session["doctor_nombre"] = doc[1]
            session["rol"]           = ROL_DOCTOR   # número 2
            return redirect("/doctor/panel")

        _registrar_fallo(ip)
        return render_template("login_doctor.html",
            error="Usuario o contraseña incorrectos")
    return render_template("login_doctor.html")


@app.route("/doctor/panel")
@login_required(role="doctor")
def doctor_panel():
    _db, cursor = get_cursor()
    cursor.execute("""
        SELECT c.id_cita, p.nombre, p.apellido, p.cedula,
               s.fecha, s.hora, c.estado, c.descripcion
        FROM cita c
        JOIN paciente p ON c.id_paciente = p.id_paciente
        JOIN slot     s ON c.id_slot     = s.id_slot
        WHERE c.id_doctor=%s AND c.estado='pendiente'
        ORDER BY s.fecha, s.hora
    """, (session["doctor_id"],))
    citas = cursor.fetchall()

    cursor.execute("""
        SELECT id_slot, fecha, hora, disponible FROM slot
        WHERE id_doctor=%s
          AND (
            fecha > (NOW() AT TIME ZONE 'America/Guayaquil')::DATE
            OR (
              fecha = (NOW() AT TIME ZONE 'America/Guayaquil')::DATE
              AND hora >= (NOW() AT TIME ZONE 'America/Guayaquil')::TIME
            )
          )
        ORDER BY fecha, hora
    """, (session["doctor_id"],))
    slots = cursor.fetchall()
    cursor.close()

    # Limpiar mensaje de slots creados ANTES de renderizar
    # (esto evita el bug de session.pop() en template)
    slots_resultado = session.pop("slots_resultado", None)

    return render_template("doctor_panel.html",
                           citas=citas,
                           slots=slots,
                           hoy=date.today(),
                           slots_resultado=slots_resultado)


def _crear_notificacion(id_paciente, tipo, mensaje):
    """Crea una notificación interna para el paciente. No bloquea si falla."""
    try:
        c = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = c.cursor()
        cur.execute("""
            INSERT INTO notificacion (id_paciente, tipo, mensaje)
            VALUES (%s, %s, %s)
        """, (id_paciente, tipo, mensaje))
        c.commit()
        cur.close()
        c.close()
    except Exception as e:
        print(f"⚠️  notificacion: {e}")


@app.route("/doctor/completar/<int:id>", methods=["POST"])
@login_required(role="doctor")
def doctor_completar(id):
    _db, cursor = get_cursor()
    # Obtener datos de la cita para la notificación
    cursor.execute("""
        SELECT c.id_paciente, s.fecha, s.hora
        FROM cita c JOIN slot s ON c.id_slot = s.id_slot
        WHERE c.id_cita=%s
    """, (id,))
    cita = cursor.fetchone()
    cursor.execute("UPDATE cita SET estado='completada' WHERE id_cita=%s AND id_doctor=%s",
                   (id, session["doctor_id"]))
    _db.commit()
    cursor.close()
    if cita:
        fecha_str = cita[1].strftime('%d/%m/%Y') if hasattr(cita[1], 'strftime') else str(cita[1])
        hora_str  = cita[2].strftime('%H:%M')    if hasattr(cita[2], 'strftime') else str(cita[2])
        threading.Thread(
            target=_crear_notificacion,
            args=(cita[0], "completada",
                  f"✅ Tu cita del {fecha_str} a las {hora_str} fue completada por el Dr. Luis Suárez."),
            daemon=True
        ).start()
    return redirect("/doctor/panel")


@app.route("/doctor/cancelar/<int:id>", methods=["POST"])
@login_required(role="doctor")
def doctor_cancelar(id):
    _db, cursor = get_cursor()
    cursor.execute("""
        SELECT c.id_paciente, s.fecha, s.hora
        FROM cita c JOIN slot s ON c.id_slot = s.id_slot
        WHERE c.id_cita=%s
    """, (id,))
    cita = cursor.fetchone()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s AND id_doctor=%s",
                   (id, session["doctor_id"]))
    _db.commit()
    cursor.close()
    if cita:
        fecha_str = cita[1].strftime('%d/%m/%Y') if hasattr(cita[1], 'strftime') else str(cita[1])
        hora_str  = cita[2].strftime('%H:%M')    if hasattr(cita[2], 'strftime') else str(cita[2])
        threading.Thread(
            target=_crear_notificacion,
            args=(cita[0], "cancelada",
                  f"❌ Tu cita del {fecha_str} a las {hora_str} fue cancelada por el Dr. Luis Suárez. Puedes reservar un nuevo horario."),
            daemon=True
        ).start()
    return redirect("/doctor/panel")


@app.route("/doctor/historial", methods=["GET", "POST"])
@login_required(role="doctor")
def doctor_historial():
    paciente  = None
    historial = []
    error     = None
    resultados_multiples = []  # cuando la búsqueda devuelve más de un paciente

    if request.method == "POST":
        termino = request.form.get("termino", "").strip()

        if not termino:
            error = "Ingresa un nombre, apellido o cédula para buscar"
        else:
            _db, cursor = get_cursor()

            # Buscar por cédula exacta, o por nombre/apellido con ILIKE
            cursor.execute("""
                SELECT id_paciente, nombre, apellido, correo, telefono, cedula
                FROM paciente
                WHERE cedula = %s
                   OR LOWER(nombre)   LIKE LOWER(%s)
                   OR LOWER(apellido) LIKE LOWER(%s)
                   OR LOWER(nombre || ' ' || apellido) LIKE LOWER(%s)
                ORDER BY apellido, nombre
                LIMIT 20
            """, (termino, f"%{termino}%", f"%{termino}%", f"%{termino}%"))

            filas = cursor.fetchall()

            if not filas:
                error = f"No se encontró ningún paciente con \"{termino}\""
            elif len(filas) == 1:
                # Resultado único → mostrar directamente
                paciente = filas[0]
                cursor.execute("""
                    SELECT s.fecha, s.hora, c.estado, c.descripcion,
                           d.nombre, d.apellido
                    FROM cita c
                    JOIN slot s        ON c.id_slot   = s.id_slot
                    LEFT JOIN doctor d ON c.id_doctor = d.id_doctor
                    WHERE c.id_paciente = %s
                    ORDER BY s.fecha DESC, s.hora DESC
                """, (paciente[0],))
                historial = cursor.fetchall()
            else:
                # Múltiples resultados → mostrar lista para elegir
                resultados_multiples = filas

            cursor.close()

    return render_template("doctor_historial.html",
                           paciente=paciente,
                           historial=historial,
                           error=error,
                           resultados_multiples=resultados_multiples)


@app.route("/doctor/historial/paciente/<int:id_paciente>")
@login_required(role="doctor")
def doctor_historial_paciente(id_paciente):
    """Carga el historial de un paciente específico desde la lista de resultados."""
    _db, cursor = get_cursor()
    cursor.execute("""
        SELECT id_paciente, nombre, apellido, correo, telefono, cedula
        FROM paciente WHERE id_paciente = %s
    """, (id_paciente,))
    paciente = cursor.fetchone()

    historial = []
    if paciente:
        cursor.execute("""
            SELECT s.fecha, s.hora, c.estado, c.descripcion,
                   d.nombre, d.apellido
            FROM cita c
            JOIN slot s        ON c.id_slot   = s.id_slot
            LEFT JOIN doctor d ON c.id_doctor = d.id_doctor
            WHERE c.id_paciente = %s
            ORDER BY s.fecha DESC, s.hora DESC
        """, (paciente[0],))
        historial = cursor.fetchall()

    cursor.close()
    return render_template("doctor_historial.html",
                           paciente=paciente,
                           historial=historial,
                           error=None,
                           resultados_multiples=[])


# ================================================================
# SLOTS — Creación masiva automática cada 35 minutos
# ================================================================
@app.route("/doctor/slots/crear", methods=["POST"])
@login_required(role="doctor")
def crear_slot():
    fecha      = request.form.get("fecha", "").strip()
    emergencia = request.form.get("emergencia") == "on"
    # En modo emergencia se usa un input de texto libre
    if emergencia:
        hora = request.form.get("hora_emerg", "").strip()
    else:
        hora = request.form.get("hora", "").strip()
    cantidad   = request.form.get("cantidad", "1").strip()

    if not fecha or not hora:
        return redirect("/doctor/panel")
    if fecha < str(date.today()):
        return redirect("/doctor/panel")

    hora_dt     = datetime.strptime(hora, "%H:%M")
    apertura_dt = datetime.strptime(HORA_APERTURA, "%H:%M")
    cierre_dt   = datetime.strptime(HORA_CIERRE,   "%H:%M")

    # Solo validar horario si NO es emergencia
    if not emergencia and (hora_dt < apertura_dt or hora_dt >= cierre_dt):
        session["slots_resultado"] = {
            "creados": 0, "omitidos": 0,
            "error": f"Horario fuera de rango. El consultorio atiende de {HORA_APERTURA} a {HORA_CIERRE}. "
                     f"Activa 'Horario de emergencia' para crear slots fuera de ese rango."
        }
        return redirect("/doctor/panel")

    try:
        cantidad = int(cantidad)
        if cantidad < 1:
            cantidad = 1
    except ValueError:
        cantidad = 1

    hora_actual_dt   = hora_dt
    creados          = 0
    omitidos         = 0
    horas_pendientes = []

    _db, cursor = get_cursor()

    for i in range(cantidad):
        hora_str = hora_actual_dt.strftime("%H:%M")

        # En modo normal no crear slots más allá del cierre
        if not emergencia and hora_actual_dt >= cierre_dt:
            omitidos += (cantidad - i)
            break

        solapaBD    = slot_solapado(session["doctor_id"], fecha, hora_str)
        solapaTanda = slot_solapado_en_lista(hora_actual_dt, horas_pendientes)

        if not solapaBD and not solapaTanda:
            cursor.execute(
                "INSERT INTO slot(id_doctor, fecha, hora) VALUES(%s, %s, %s)",
                (session["doctor_id"], fecha, hora_str)
            )
            horas_pendientes.append(hora_actual_dt)
            creados += 1
        else:
            omitidos += 1

        hora_actual_dt += timedelta(minutes=DURACION_CITA)

    _db.commit()
    cursor.close()

    session["slots_resultado"] = {
        "creados":  creados,
        "omitidos": omitidos,
        "emergencia": emergencia
    }

    return redirect("/doctor/panel")


@app.route("/doctor/slots/eliminar/<int:id>", methods=["POST"])
@login_required(role="doctor")
def eliminar_slot(id):
    _db, cursor = get_cursor()
    try:
        cursor.execute(
            "SELECT id_cita FROM cita WHERE id_slot=%s AND estado='pendiente'",
            (id,)
        )
        ocupado = cursor.fetchone()
        if not ocupado:
            cursor.execute(
                "DELETE FROM slot WHERE id_slot=%s AND id_doctor=%s",
                (id, session["doctor_id"])
            )
            _db.commit()
        else:
            # Slot reservado — no eliminar, pero hacer rollback limpio
            _db.rollback()
    except Exception as e:
        _db.rollback()
        print(f"⚠️  Error eliminando slot: {e}")
    finally:
        cursor.close()
    return redirect("/doctor/panel")


# ================================================================
# PACIENTE
# ================================================================
# ================================================================
# PACIENTE
# ================================================================
@app.route("/login_paciente", methods=["GET", "POST"])
def login_paciente():
    if not get_conn():
        return "Error BD"
    if request.method == "POST":
        from werkzeug.security import check_password_hash
        correo   = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")

        _db, cursor = get_cursor()
        cursor.execute(
            "SELECT id_paciente, nombre, password FROM paciente WHERE correo=%s",
            (correo,)
        )
        user = cursor.fetchone()
        cursor.close()

        if not user:
            return render_template("login_paciente.html",
                error="Correo no registrado. ¿Quieres crear una cuenta?")

        # Soporte dual: hash werkzeug O texto plano (pacientes existentes sin hash)
        pwd_ok = False
        stored = user[2]
        if stored:
            try:
                pwd_ok = check_password_hash(stored, password)
            except Exception:
                pass
            if not pwd_ok:
                pwd_ok = (stored == password)

        if not pwd_ok:
            return render_template("login_paciente.html",
                error="Contraseña incorrecta.")

        session.clear()
        session["paciente_id"]     = user[0]
        session["paciente_nombre"] = user[1]
        session["rol"]             = ROL_PACIENTE
        return redirect("/panel_paciente")

    return render_template("login_paciente.html")


@app.route("/registro_paciente", methods=["GET", "POST"])
def registro_paciente():
    if not get_conn():
        return "Error BD"
    if request.method == "POST":
        from werkzeug.security import generate_password_hash
        nombre   = request.form.get("nombre", "").strip()
        apellido = request.form.get("apellido", "").strip()
        correo   = request.form.get("correo", "").strip().lower()
        telefono = request.form.get("telefono", "").strip()
        cedula   = request.form.get("cedula", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        if len(nombre) < 3 or not nombre.replace(" ", "").isalpha():
            return render_template("registro_paciente.html", mensaje="Nombre inválido", tipo="error")
        if len(apellido) < 3 or not apellido.replace(" ", "").isalpha():
            return render_template("registro_paciente.html", mensaje="Apellido inválido", tipo="error")
        if "@" not in correo:
            return render_template("registro_paciente.html", mensaje="Correo inválido", tipo="error")
        if not telefono.isdigit():
            return render_template("registro_paciente.html", mensaje="Teléfono inválido (solo números)", tipo="error")
        if not cedula.isdigit() or len(cedula) != 10:
            return render_template("registro_paciente.html", mensaje="Cédula inválida (10 dígitos)", tipo="error")
        if len(password) < 6:
            return render_template("registro_paciente.html", mensaje="La contraseña debe tener mínimo 6 caracteres", tipo="error")
        if password != confirm:
            return render_template("registro_paciente.html", mensaje="Las contraseñas no coinciden", tipo="error")

        _db, cursor = get_cursor()
        cursor.execute("SELECT id_paciente FROM paciente WHERE correo=%s OR cedula=%s", (correo, cedula))
        if cursor.fetchone():
            cursor.close()
            return render_template("registro_paciente.html", mensaje="Correo o cédula ya registrados", tipo="error")

        pwd_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO paciente(nombre, apellido, correo, telefono, cedula, password)
            VALUES(%s, %s, %s, %s, %s, %s)
        """, (nombre, apellido, correo, telefono, cedula, pwd_hash))
        _db.commit()
        cursor.close()
        return render_template("registro_paciente.html",
            mensaje="¡Cuenta creada! Ya puedes iniciar sesión.", tipo="success")
    return render_template("registro_paciente.html")


@app.route("/panel_paciente")
@login_required(role="paciente")
def panel_paciente():
    _db, cursor = get_cursor()
    cursor.execute("""
        SELECT c.id_cita, s.fecha, s.hora, c.estado, c.descripcion,
               d.nombre, d.apellido, d.especialidad
        FROM cita c
        JOIN slot s        ON c.id_slot   = s.id_slot
        LEFT JOIN doctor d ON c.id_doctor = d.id_doctor
        WHERE c.id_paciente=%s
        ORDER BY s.fecha ASC, s.hora ASC
    """, (session["paciente_id"],))
    citas = cursor.fetchall()

    # Notificaciones no leídas
    try:
        cursor.execute("""
            SELECT id_notif, tipo, mensaje, fecha
            FROM notificacion
            WHERE id_paciente=%s AND leida=FALSE
            ORDER BY fecha DESC
        """, (session["paciente_id"],))
        notificaciones = cursor.fetchall()
    except Exception:
        notificaciones = []
    cursor.close()

    # Calcular conteos en Python — más seguro que en Jinja2 con tuplas
    n_pend = sum(1 for c in citas if c[3] == 'pendiente')
    n_comp = sum(1 for c in citas if c[3] == 'completada')
    n_canc = sum(1 for c in citas if c[3] == 'cancelada')
    proxima = next((c for c in citas if c[3] == 'pendiente'), None)

    return render_template("panel_paciente.html",
                           citas=citas,
                           notificaciones=notificaciones,
                           n_pend=n_pend, n_comp=n_comp,
                           n_canc=n_canc, proxima=proxima)


@app.route("/leer_notificacion/<int:id_notif>", methods=["POST"])
@login_required(role="paciente")
def leer_notificacion(id_notif):
    """Marca una notificación como leída."""
    _db, cursor = get_cursor()
    cursor.execute("""
        UPDATE notificacion SET leida=TRUE
        WHERE id_notif=%s AND id_paciente=%s
    """, (id_notif, session["paciente_id"]))
    _db.commit()
    cursor.close()
    return redirect("/panel_paciente")


@app.route("/leer_todas_notificaciones", methods=["POST"])
@login_required(role="paciente")
def leer_todas_notificaciones():
    """Marca todas las notificaciones del paciente como leídas."""
    _db, cursor = get_cursor()
    cursor.execute("""
        UPDATE notificacion SET leida=TRUE
        WHERE id_paciente=%s AND leida=FALSE
    """, (session["paciente_id"],))
    _db.commit()
    cursor.close()
    return redirect("/panel_paciente")


@app.route("/cancelar_cita_paciente/<int:id>", methods=["POST"])
@login_required(role="paciente")
def cancelar_cita_paciente(id):
    _db, cursor = get_cursor()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s AND id_paciente=%s",
                   (id, session["paciente_id"]))
    _db.commit()
    cursor.close()
    return redirect("/panel_paciente")


@app.route("/reservar", methods=["GET", "POST"])
@login_required(role="paciente")
def reservar():

    def get_slots():
        """
        Devuelve slots disponibles futuros.
        IMPORTANTE: Supabase usa UTC. Ecuador = UTC-5.
        Comparamos contra NOW() AT TIME ZONE 'America/Guayaquil'
        para que los slots de hoy se filtren con la hora real de Quito,
        no con la hora UTC de la BD.
        """
        _, cursor2 = get_cursor()
        cursor2.execute("""
            SELECT id_slot, fecha, hora
            FROM slot
            WHERE disponible = TRUE
              AND (
                fecha > (NOW() AT TIME ZONE 'America/Guayaquil')::DATE
                OR (
                  fecha = (NOW() AT TIME ZONE 'America/Guayaquil')::DATE
                  AND hora > (NOW() AT TIME ZONE 'America/Guayaquil')::TIME
                )
              )
            ORDER BY fecha, hora
        """)
        result = cursor2.fetchall()
        cursor2.close()
        return result

    if request.method == "POST":
        id_slot     = request.form.get("id_slot")
        descripcion = request.form.get("descripcion", "").strip()

        if not id_slot:
            return render_template("reservar.html",
                slots=get_slots(), mensaje="Selecciona un horario disponible", tipo="error")

        if len(descripcion) < 5:
            return render_template("reservar.html",
                slots=get_slots(), mensaje="Describe el motivo (mínimo 5 caracteres)", tipo="error")

        _db, cursor = get_cursor()
        cursor.execute("SELECT id_slot, id_doctor FROM slot WHERE id_slot=%s AND disponible=TRUE", (id_slot,))
        slot = cursor.fetchone()

        if not slot:
            cursor.close()
            return render_template("reservar.html",
                slots=get_slots(), mensaje="Ese horario ya no está disponible", tipo="error")

        # Verificar que el paciente no tenga ya una cita pendiente
        cursor.execute("""
            SELECT c.id_cita, s.fecha, s.hora
            FROM cita c
            JOIN slot s ON c.id_slot = s.id_slot
            WHERE c.id_paciente = %s AND c.estado = 'pendiente'
            ORDER BY s.fecha, s.hora
            LIMIT 1
        """, (session["paciente_id"],))
        cita_existente = cursor.fetchone()
        if cita_existente:
            cursor.close()
            from datetime import date as _date
            fecha_ex = cita_existente[1]
            hora_ex  = cita_existente[2].strftime('%H:%M') if hasattr(cita_existente[2], 'strftime') else str(cita_existente[2])[:5]
            return render_template("reservar.html",
                slots=get_slots(),
                mensaje=f"Ya tienes una cita pendiente para el {fecha_ex} a las {hora_ex}. Cancélala primero si deseas reagendar.",
                tipo="error")

        # Marcar slot como no disponible y crear cita
        cursor.execute("UPDATE slot SET disponible=FALSE WHERE id_slot=%s", (slot[0],))
        cursor.execute("""
            INSERT INTO cita(id_paciente, id_doctor, id_slot, estado, descripcion)
            VALUES(%s, %s, %s, 'pendiente', %s)
        """, (session["paciente_id"], slot[1], slot[0], descripcion))
        _db.commit()

        # Datos para el correo de confirmación
        try:
            cursor.execute("""
                SELECT p.correo, p.nombre, p.apellido, s.fecha, s.hora
                FROM paciente p, slot s
                WHERE p.id_paciente = %s AND s.id_slot = %s
            """, (session["paciente_id"], slot[0]))
            datos_correo = cursor.fetchone()
            if datos_correo:
                correo_pac, nombre_pac, apellido_pac, fecha_cita, hora_cita = datos_correo
                enviar_confirmacion_cita(
                    correo_paciente=correo_pac,
                    nombre_paciente=f"{nombre_pac} {apellido_pac}",
                    fecha=fecha_cita, hora=hora_cita, descripcion=descripcion
                )
        except Exception as e:
            print(f"⚠️  Error enviando confirmación: {e}")

        cursor.close()
        return render_template("reservar.html",
            slots=[], mensaje="¡Cita reservada con éxito!", tipo="success")

    # GET
    return render_template("reservar.html", slots=get_slots())


# ================================================================
# LOGOUT
# ================================================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ================================================================
# RECUPERAR CONTRASEÑA — DOCTOR
# ================================================================
@app.route("/doctor/recuperar", methods=["GET", "POST"])
def doctor_recuperar():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        _db, cursor = get_cursor()
        cursor.execute("SELECT id_doctor FROM doctor WHERE correo=%s", (correo,))
        doc = cursor.fetchone()
        cursor.close()

        if not doc:
            return render_template("doctor_recuperar.html",
                error="No hay ningún doctor registrado con ese correo.")

        codigo = str(random.randint(100000, 999999))
        session["reset_codigo"] = codigo
        session["reset_correo"] = correo
        session["reset_expira"] = (datetime.now() + timedelta(minutes=15)).isoformat()

        cuerpo = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:2rem;
                    border:1px solid #e8f5ee;border-radius:16px">
          <h2 style="color:#1a6b4a">🔑 Código de verificación</h2>
          <p>Hola, recibiste este correo porque solicitaste restablecer la contraseña
             de tu cuenta en <strong>MediClover</strong>.</p>
          <div style="font-size:2.5rem;font-weight:bold;letter-spacing:.8rem;
                      text-align:center;background:#f0faf5;padding:1rem;
                      border-radius:12px;color:#1a6b4a;margin:1.5rem 0">
            {codigo}
          </div>
          <p style="color:#666;font-size:.875rem">
            Este código expira en <strong>15 minutos</strong>.<br>
            Si no solicitaste este cambio, ignora este correo.
          </p>
          <hr style="border-color:#e8f5ee">
          <p style="color:#aaa;font-size:.75rem">MediClover — Sistema de Gestión Médica</p>
        </div>
        """

        enviado = True
        enviar_correo_async(correo, "MediClover — Código para restablecer contraseña", cuerpo)
        # Redirigir inmediatamente, el correo se envía en background
        if enviado:
            return render_template("doctor_verificar_codigo.html", correo=correo)
        else:
            return render_template("doctor_recuperar.html",
                error="Error al enviar el correo. Verifica la configuración SMTP.")

    return render_template("doctor_recuperar.html")


@app.route("/doctor/verificar_codigo", methods=["POST"])
def doctor_verificar_codigo():
    correo           = request.form.get("correo", "").strip().lower()
    codigo_ingresado = request.form.get("codigo", "").strip()
    nueva_password   = request.form.get("nueva_password", "")
    confirmar        = request.form.get("confirmar_password", "")

    def volver(err):
        return render_template("doctor_verificar_codigo.html", correo=correo, error=err)

    if session.get("reset_correo") != correo:
        return volver("Sesión inválida. Solicita un nuevo código.")

    expira = session.get("reset_expira")
    if not expira or datetime.now() > datetime.fromisoformat(expira):
        session.pop("reset_codigo", None)
        session.pop("reset_correo", None)
        session.pop("reset_expira", None)
        return volver("El código expiró. Solicita uno nuevo.")

    if session.get("reset_codigo") != codigo_ingresado:
        return volver("Código incorrecto. Inténtalo de nuevo.")

    if len(nueva_password) < 6:
        return volver("La contraseña debe tener al menos 6 caracteres.")

    if nueva_password != confirmar:
        return volver("Las contraseñas no coinciden.")

    _db, cursor = get_cursor()
    cursor.execute("UPDATE doctor SET password=%s WHERE correo=%s", (nueva_password, correo))
    _db.commit()
    cursor.close()

    session.pop("reset_codigo", None)
    session.pop("reset_correo", None)
    session.pop("reset_expira", None)

    return render_template("login_doctor.html",
        mensaje="¡Contraseña restablecida con éxito! Ya puedes iniciar sesión.",
        tipo="success")


# ================================================================
# HISTORIAL CLÍNICO
# ================================================================

@app.route("/doctor/historial_clinico/<int:id_paciente>", methods=["GET", "POST"])
@login_required(role="doctor")
def historial_clinico(id_paciente):
    """El doctor ve y agrega entradas al historial clínico de un paciente."""
    _db, cursor = get_cursor()

    # Datos del paciente
    cursor.execute("""
        SELECT id_paciente, nombre, apellido, correo, telefono, cedula
        FROM paciente WHERE id_paciente=%s
    """, (id_paciente,))
    paciente = cursor.fetchone()
    if not paciente:
        cursor.close()
        return redirect("/doctor/historial")

    if request.method == "POST":
        id_cita       = request.form.get("id_cita") or None
        diagnostico   = request.form.get("diagnostico", "").strip()
        tratamiento   = request.form.get("tratamiento", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        if diagnostico:
            cursor.execute("""
                INSERT INTO historial_clinico
                    (id_paciente, id_doctor, id_cita, diagnostico, tratamiento, observaciones)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (id_paciente, session["doctor_id"],
                  id_cita or None, diagnostico, tratamiento or None, observaciones or None))
            _db.commit()

    # Historial del paciente
    cursor.execute("""
        SELECT h.id_historial, h.fecha_registro, h.diagnostico,
               h.tratamiento, h.observaciones, h.id_cita,
               s.fecha AS fecha_cita, s.hora AS hora_cita
        FROM historial_clinico h
        LEFT JOIN cita c ON h.id_cita = c.id_cita
        LEFT JOIN slot s ON c.id_slot = s.id_slot
        WHERE h.id_paciente = %s
        ORDER BY h.fecha_registro DESC
    """, (id_paciente,))
    historial = cursor.fetchall()

    # Citas completadas del paciente (para asociar al historial)
    cursor.execute("""
        SELECT c.id_cita, s.fecha, s.hora
        FROM cita c
        JOIN slot s ON c.id_slot = s.id_slot
        WHERE c.id_paciente = %s AND c.id_doctor = %s AND c.estado = 'completada'
        ORDER BY s.fecha DESC
    """, (id_paciente, session["doctor_id"]))
    citas_completadas = cursor.fetchall()

    cursor.close()
    return render_template("historial_clinico.html",
                           paciente=paciente,
                           historial=historial,
                           citas_completadas=citas_completadas)


@app.route("/doctor/historial_clinico/<int:id_historial>/eliminar")
@login_required(role="doctor")
def eliminar_entrada_historial(id_historial):
    _db, cursor = get_cursor()
    cursor.execute("DELETE FROM historial_clinico WHERE id_historial=%s AND id_doctor=%s",
                   (id_historial, session["doctor_id"]))
    _db.commit()
    cursor.close()
    return redirect(request.referrer or "/doctor/historial")


@app.route("/doctor/historial_clinico/<int:id_historial>/editar", methods=["GET", "POST"])
@login_required(role="doctor")
def editar_entrada_historial(id_historial):
    """El doctor puede corregir una entrada de historial clínico que registró él mismo."""
    _db, cursor = get_cursor()
    if request.method == "POST":
        diagnostico   = request.form.get("diagnostico", "").strip()
        tratamiento   = request.form.get("tratamiento", "").strip()
        observaciones = request.form.get("observaciones", "").strip()
        if not diagnostico or not tratamiento:
            cursor.close()
            return redirect(request.referrer or "/doctor/historial")
        cursor.execute("""
            UPDATE historial_clinico
            SET diagnostico=%s, tratamiento=%s, observaciones=%s
            WHERE id_historial=%s AND id_doctor=%s
        """, (diagnostico, tratamiento, observaciones, id_historial, session["doctor_id"]))
        _db.commit()
        # Obtener el id_paciente para redirigir al historial correcto
        cursor.execute("SELECT id_paciente FROM historial_clinico WHERE id_historial=%s",
                       (id_historial,))
        row = cursor.fetchone()
        cursor.close()
        if row:
            return redirect(f"/doctor/historial_clinico/{row[0]}")
        return redirect("/doctor/historial")

    # GET → cargar la entrada actual
    cursor.execute("""
        SELECT id_historial, id_paciente, diagnostico, tratamiento, observaciones
        FROM historial_clinico
        WHERE id_historial=%s AND id_doctor=%s
    """, (id_historial, session["doctor_id"]))
    entrada = cursor.fetchone()
    cursor.close()
    if not entrada:
        return redirect("/doctor/historial")
    return render_template("editar_historial.html", entrada=entrada)


# ── Panel del paciente: ver su propio historial clínico ──────────
@app.route("/mi_historial")
@login_required(role="paciente")
def mi_historial():
    _db, cursor = get_cursor()
    cursor.execute("""
        SELECT h.fecha_registro, h.diagnostico, h.tratamiento,
               h.observaciones, s.fecha AS fecha_cita, s.hora AS hora_cita,
               d.nombre, d.apellido
        FROM historial_clinico h
        LEFT JOIN cita c   ON h.id_cita   = c.id_cita
        LEFT JOIN slot s   ON c.id_slot   = s.id_slot
        LEFT JOIN doctor d ON h.id_doctor = d.id_doctor
        WHERE h.id_paciente = %s
        ORDER BY h.fecha_registro DESC
    """, (session["paciente_id"],))
    historial = cursor.fetchall()
    cursor.close()
    return render_template("mi_historial.html", historial=historial)


# ================================================================
# RECETAS DIGITALES
# ================================================================

@app.route("/doctor/receta/nueva/<int:id_paciente>", methods=["GET", "POST"])
@login_required(role="doctor")
def nueva_receta(id_paciente):
    """El doctor emite una receta digital para un paciente."""
    _db, cursor = get_cursor()

    cursor.execute("""
        SELECT id_paciente, nombre, apellido, correo, cedula
        FROM paciente WHERE id_paciente=%s
    """, (id_paciente,))
    paciente = cursor.fetchone()
    if not paciente:
        cursor.close()
        return redirect("/doctor/historial")

    if request.method == "POST":
        id_cita       = request.form.get("id_cita") or None
        medicamentos  = request.form.get("medicamentos", "").strip()
        indicaciones  = request.form.get("indicaciones", "").strip()
        duracion_dias = request.form.get("duracion_dias", "7").strip()

        if medicamentos:
            try:
                duracion_dias = int(duracion_dias)
            except ValueError:
                duracion_dias = 7

            cursor.execute("""
                INSERT INTO receta
                    (id_paciente, id_doctor, id_cita, medicamentos, indicaciones, duracion_dias)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (id_paciente, session["doctor_id"],
                  id_cita or None, medicamentos,
                  indicaciones or None, duracion_dias))
            _db.commit()
            cursor.close()
            return redirect(f"/doctor/recetas/{id_paciente}")

    # Citas completadas para asociar
    cursor.execute("""
        SELECT c.id_cita, s.fecha, s.hora
        FROM cita c
        JOIN slot s ON c.id_slot = s.id_slot
        WHERE c.id_paciente = %s AND c.id_doctor = %s AND c.estado = 'completada'
        ORDER BY s.fecha DESC
    """, (id_paciente, session["doctor_id"]))
    citas_completadas = cursor.fetchall()
    cursor.close()
    return render_template("nueva_receta.html",
                           paciente=paciente,
                           citas_completadas=citas_completadas)


@app.route("/doctor/recetas/<int:id_paciente>")
@login_required(role="doctor")
def ver_recetas_doctor(id_paciente):
    _db, cursor = get_cursor()
    cursor.execute("""
        SELECT id_paciente, nombre, apellido, correo, cedula
        FROM paciente WHERE id_paciente=%s
    """, (id_paciente,))
    paciente = cursor.fetchone()

    cursor.execute("""
        SELECT r.id_receta, r.fecha_emision, r.medicamentos,
               r.indicaciones, r.duracion_dias,
               s.fecha AS fecha_cita, s.hora AS hora_cita
        FROM receta r
        LEFT JOIN cita c ON r.id_cita = c.id_cita
        LEFT JOIN slot s ON c.id_slot = s.id_slot
        WHERE r.id_paciente = %s AND r.id_doctor = %s
        ORDER BY r.fecha_emision DESC
    """, (id_paciente, session["doctor_id"]))
    recetas = cursor.fetchall()
    cursor.close()
    return render_template("ver_recetas_doctor.html",
                           paciente=paciente, recetas=recetas)


@app.route("/doctor/receta/<int:id_receta>/editar", methods=["GET", "POST"])
@login_required(role="doctor")
def editar_receta(id_receta):
    """El doctor puede corregir una receta que emitió él mismo."""
    _db, cursor = get_cursor()
    if request.method == "POST":
        medicamentos  = request.form.get("medicamentos", "").strip()
        indicaciones  = request.form.get("indicaciones", "").strip()
        duracion_dias = request.form.get("duracion_dias", "7").strip()
        if not medicamentos:
            cursor.close()
            return redirect(request.referrer or "/doctor/historial")
        cursor.execute("""
            UPDATE receta
            SET medicamentos=%s, indicaciones=%s, duracion_dias=%s
            WHERE id_receta=%s AND id_doctor=%s
        """, (medicamentos, indicaciones, duracion_dias or 7, id_receta, session["doctor_id"]))
        _db.commit()
        # Redirigir al historial del paciente
        cursor.execute("SELECT id_paciente FROM receta WHERE id_receta=%s", (id_receta,))
        row = cursor.fetchone()
        cursor.close()
        if row:
            return redirect(f"/doctor/recetas/{row[0]}")
        return redirect("/doctor/historial")

    # GET → cargar receta
    cursor.execute("""
        SELECT id_receta, id_paciente, medicamentos, indicaciones, duracion_dias
        FROM receta
        WHERE id_receta=%s AND id_doctor=%s
    """, (id_receta, session["doctor_id"]))
    receta = cursor.fetchone()
    cursor.close()
    if not receta:
        return redirect("/doctor/historial")
    return render_template("editar_receta.html", receta=receta)


# ── Paciente: ver sus propias recetas ────────────────────────────
@app.route("/mis_recetas")
@login_required(role="paciente")
def mis_recetas():
    _db, cursor = get_cursor()
    cursor.execute("""
        SELECT r.id_receta, r.fecha_emision, r.medicamentos,
               r.indicaciones, r.duracion_dias,
               s.fecha AS fecha_cita, s.hora AS hora_cita,
               d.nombre, d.apellido
        FROM receta r
        LEFT JOIN cita c   ON r.id_cita   = c.id_cita
        LEFT JOIN slot s   ON c.id_slot   = s.id_slot
        LEFT JOIN doctor d ON r.id_doctor = d.id_doctor
        WHERE r.id_paciente = %s
        ORDER BY r.fecha_emision DESC
    """, (session["paciente_id"],))
    recetas = cursor.fetchall()
    cursor.close()
    return render_template("mis_recetas.html", recetas=recetas)


# ================================================================
# EDITAR PERFIL PACIENTE
# ================================================================
@app.route("/editar_perfil", methods=["GET", "POST"])
@login_required(role="paciente")
def editar_perfil():
    _db, cursor = get_cursor()
    if request.method == "POST":
        nombre   = request.form.get("nombre","").strip()
        apellido = request.form.get("apellido","").strip()
        correo   = request.form.get("correo","").strip().lower()
        telefono = request.form.get("telefono","").strip()
        error    = None
        if len(nombre) < 2:
            error = "El nombre es muy corto"
        elif len(apellido) < 2:
            error = "El apellido es muy corto"
        elif "@" not in correo or "." not in correo:
            error = "Escribe un correo válido"
        elif telefono and not telefono.isdigit():
            error = "El teléfono solo debe tener números"
        else:
            # Verificar que el correo no esté usado por otro paciente
            cursor.execute(
                "SELECT id_paciente FROM paciente WHERE correo=%s AND id_paciente!=%s",
                (correo, session["paciente_id"])
            )
            if cursor.fetchone():
                error = "Ese correo ya está registrado por otro paciente"

        if error:
            cursor.execute("SELECT nombre,apellido,correo,telefono,cedula FROM paciente WHERE id_paciente=%s",
                           (session["paciente_id"],))
            p = cursor.fetchone()
            cursor.close()
            return render_template("editar_perfil.html", paciente=p, error=error)

        cursor.execute("""
            UPDATE paciente SET nombre=%s, apellido=%s, correo=%s, telefono=%s
            WHERE id_paciente=%s
        """, (nombre, apellido, correo, telefono or None, session["paciente_id"]))
        _db.commit()
        session["paciente_nombre"] = nombre
        cursor.close()
        return redirect("/panel_paciente")

    cursor.execute("SELECT nombre,apellido,correo,telefono,cedula FROM paciente WHERE id_paciente=%s",
                   (session["paciente_id"],))
    paciente = cursor.fetchone()
    cursor.close()
    return render_template("editar_perfil.html", paciente=paciente)


# ================================================================
# RECUPERAR CONTRASEÑA — PACIENTE
# (El paciente no tiene contraseña, pero sí puede "recuperar acceso"
#  si olvidó qué correo usó — el admin lo ayuda. Esta ruta es informativa.)
# En su lugar implementamos OTP real para login de paciente.
# ================================================================

# ================================================================
# ESTADÍSTICAS DEL DASHBOARD (JSON para gráficas)
# ================================================================
@app.route("/admin/stats")
@login_required(role="admin")
def admin_stats():
    """Devuelve JSON con citas por mes para las gráficas del dashboard."""
    _db, cursor = get_cursor()
    # Citas por mes (últimos 6 meses)
    cursor.execute("""
        SELECT
            TO_CHAR(s.fecha, 'Mon YYYY') AS mes,
            DATE_TRUNC('month', s.fecha) AS mes_orden,
            COUNT(*) AS total,
            SUM(CASE WHEN c.estado='completada' THEN 1 ELSE 0 END) AS completadas,
            SUM(CASE WHEN c.estado='cancelada'  THEN 1 ELSE 0 END) AS canceladas,
            SUM(CASE WHEN c.estado='pendiente'  THEN 1 ELSE 0 END) AS pendientes
        FROM cita c
        JOIN slot s ON c.id_slot = s.id_slot
        WHERE s.fecha >= (NOW() AT TIME ZONE 'America/Guayaquil')::DATE - INTERVAL '6 months'
        GROUP BY mes, mes_orden
        ORDER BY mes_orden
    """)
    filas = cursor.fetchall()
    cursor.close()
    data = {
        "labels":     [f[0] for f in filas],
        "total":      [f[2] for f in filas],
        "completadas":[f[3] for f in filas],
        "canceladas": [f[4] for f in filas],
        "pendientes": [f[5] for f in filas],
    }
    return make_response(json.dumps(data), 200, {"Content-Type": "application/json"})


# ================================================================
# EXPORTAR HISTORIAL A PDF (HTML → PDF con CSS)
# ================================================================
@app.route("/mi_historial/pdf")
@login_required(role="paciente")
def mi_historial_pdf():
    """Genera un PDF del historial clínico del paciente."""
    _db, cursor = get_cursor()
    # Datos del paciente
    cursor.execute("""
        SELECT nombre, apellido, cedula, correo, telefono
        FROM paciente WHERE id_paciente=%s
    """, (session["paciente_id"],))
    paciente = cursor.fetchone()

    # Historial completo
    cursor.execute("""
        SELECT h.fecha_registro, h.diagnostico, h.tratamiento,
               h.observaciones, s.fecha, s.hora, d.nombre, d.apellido
        FROM historial_clinico h
        LEFT JOIN cita c   ON h.id_cita   = c.id_cita
        LEFT JOIN slot s   ON c.id_slot   = s.id_slot
        LEFT JOIN doctor d ON h.id_doctor = d.id_doctor
        WHERE h.id_paciente = %s
        ORDER BY h.fecha_registro DESC
    """, (session["paciente_id"],))
    historial = cursor.fetchall()

    # Recetas
    cursor.execute("""
        SELECT r.fecha_emision, r.medicamentos, r.indicaciones,
               r.duracion_dias, d.nombre, d.apellido
        FROM receta r
        LEFT JOIN doctor d ON r.id_doctor = d.id_doctor
        WHERE r.id_paciente = %s
        ORDER BY r.fecha_emision DESC
    """, (session["paciente_id"],))
    recetas = cursor.fetchall()
    cursor.close()

    ahora = datetime.now().strftime('%d/%m/%Y %H:%M')

    # Construir HTML del PDF
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family: Arial, sans-serif; font-size: 12px; color: #222; background: #fff; padding: 2cm; }}
  .header {{ display:flex; justify-content:space-between; align-items:flex-start; border-bottom: 3px solid #0a7c5c; padding-bottom: 1.2rem; margin-bottom: 1.5rem; }}
  .header-brand {{ font-size: 22px; font-weight: 700; color: #0b1f3a; }}
  .header-brand span {{ color: #0a7c5c; }}
  .header-meta {{ text-align:right; font-size:11px; color:#666; }}
  .section-title {{ font-size:13px; font-weight:700; color:#0a7c5c; text-transform:uppercase; letter-spacing:.06em; border-bottom:1px solid #e2e8f0; padding-bottom:.35rem; margin: 1.5rem 0 .85rem; }}
  .pac-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:.4rem .75rem; margin-bottom:1rem; }}
  .pac-row {{ font-size:11.5px; }}
  .pac-row strong {{ color:#0b1f3a; }}
  .entry {{ border:1px solid #e2e8f0; border-radius:6px; padding:.85rem 1rem; margin-bottom:.75rem; page-break-inside:avoid; }}
  .entry-diag {{ font-size:13px; font-weight:700; color:#0b1f3a; margin-bottom:.3rem; }}
  .entry-meta {{ font-size:10.5px; color:#888; margin-bottom:.6rem; }}
  .entry-label {{ font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:#aaa; margin:.5rem 0 .2rem; }}
  .entry-val {{ font-size:11.5px; color:#444; line-height:1.55; }}
  .receta-entry {{ border:1px solid #e2e8f0; border-radius:6px; padding:.85rem 1rem; margin-bottom:.75rem; page-break-inside:avoid; }}
  .receta-header {{ display:flex; justify-content:space-between; margin-bottom:.5rem; }}
  .receta-rx {{ font-size:22px; font-weight:700; color:#e2e8f0; }}
  .footer {{ margin-top:2rem; border-top:1px solid #e2e8f0; padding-top:.75rem; font-size:10px; color:#aaa; text-align:center; }}
  .empty {{ color:#aaa; font-style:italic; font-size:11px; }}
</style>
</head>
<body>

<div class="header">
  <div>
    <div class="header-brand">Medi<span>Clover</span></div>
    <div style="font-size:11px;color:#888;margin-top:.2rem;">Sistema de Gestión de Citas Médicas</div>
  </div>
  <div class="header-meta">
    <div><strong>Historial Clínico Personal</strong></div>
    <div>Generado el {ahora}</div>
    <div>Quito, Ecuador</div>
  </div>
</div>

<div class="section-title">Datos del paciente</div>
<div class="pac-grid">
  <div class="pac-row"><strong>Nombre:</strong> {paciente[0]} {paciente[1]}</div>
  <div class="pac-row"><strong>Cédula:</strong> {paciente[2]}</div>
  <div class="pac-row"><strong>Correo:</strong> {paciente[3]}</div>
  <div class="pac-row"><strong>Teléfono:</strong> {paciente[4] or '—'}</div>
</div>
<div class="pac-row"><strong>Doctor tratante:</strong> Dr. Luis Suárez — Médico General</div>

<div class="section-title">Historial clínico ({len(historial)} entrada(s))</div>
"""

    if historial:
        for h in historial:
            fecha_reg  = h[0].strftime('%d/%m/%Y %H:%M') if h[0] else '—'
            diagnostico = h[1] or '—'
            tratamiento = h[2] or ''
            observaciones = h[3] or ''
            fecha_cita = str(h[4]) if h[4] else ''
            hora_cita  = h[5].strftime('%H:%M') if h[5] else ''
            dr_nombre  = f"Dr. {h[6]} {h[7]}" if h[6] else 'Dr. Luis Suárez'
            cita_txt   = f"Cita del {fecha_cita} {hora_cita}" if fecha_cita else ''

            html += f"""
<div class="entry">
  <div class="entry-diag">{diagnostico}</div>
  <div class="entry-meta">{fecha_reg} &nbsp;·&nbsp; {dr_nombre}"""
            if cita_txt:
                html += f" &nbsp;·&nbsp; {cita_txt}"
            html += "</div>"
            if tratamiento:
                html += f'<div class="entry-label">Tratamiento</div><div class="entry-val">{tratamiento}</div>'
            if observaciones:
                html += f'<div class="entry-label">Observaciones</div><div class="entry-val">{observaciones}</div>'
            html += "</div>"
    else:
        html += '<p class="empty">Sin entradas en el historial clínico.</p>'

    html += f'<div class="section-title">Recetas digitales ({len(recetas)} receta(s))</div>'

    if recetas:
        for r in recetas:
            fecha_em   = r[0].strftime('%d/%m/%Y') if r[0] else '—'
            medicamentos = r[1] or '—'
            indicaciones = r[2] or ''
            duracion   = r[3] or 7
            dr_nombre  = f"Dr. {r[4]} {r[5]}" if r[4] else 'Dr. Luis Suárez'
            html += f"""
<div class="receta-entry">
  <div class="receta-header">
    <div>
      <div style="font-weight:700;color:#0b1f3a;font-size:12px;">Receta del {fecha_em}</div>
      <div style="font-size:10.5px;color:#888;">{dr_nombre} &nbsp;·&nbsp; Duración: {duracion} días</div>
    </div>
    <div class="receta-rx">Rx</div>
  </div>
  <div class="entry-label">Medicamentos</div>
  <div class="entry-val" style="white-space:pre-wrap;">{medicamentos}</div>"""
            if indicaciones:
                html += f'<div class="entry-label">Indicaciones</div><div class="entry-val">{indicaciones}</div>'
            html += "</div>"
    else:
        html += '<p class="empty">Sin recetas emitidas.</p>'

    html += f"""
<div class="footer">
  MediClover — Sistema de Gestión de Citas Médicas · Quito, Ecuador · © 2026<br>
  Este documento es un resumen del historial registrado en el sistema. Generado el {ahora}.
</div>
</body></html>"""

    # Intentar usar weasyprint si está disponible
    try:
        from weasyprint import HTML as WH
        pdf_bytes = WH(string=html).write_pdf()
        response = make_response(pdf_bytes)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="historial_{paciente[2]}.pdf"'
        return response
    except ImportError:
        # weasyprint no está instalado — devolver HTML para imprimir
        response = make_response(html + """
        <script>
          document.addEventListener('DOMContentLoaded', function() {
            window.print();
          });
        </script>""")
        response.headers["Content-Type"] = "text/html; charset=utf-8"
        return response


# ================================================================
# BLOQUEAR FECHAS — DOCTOR
# ================================================================
@app.route("/doctor/bloquear", methods=["GET", "POST"])
@login_required(role="doctor")
def doctor_bloquear():
    _db, cursor = get_cursor()

    if request.method == "POST":
        accion     = request.form.get("accion")
        fecha_ini  = request.form.get("fecha_inicio", "").strip()
        fecha_fin  = request.form.get("fecha_fin", "").strip()
        motivo     = request.form.get("motivo", "Vacaciones").strip()
        bloqueo_id = request.form.get("bloqueo_id")

        if accion == "crear" and fecha_ini and fecha_fin:
            # Verificar que no haya citas pendientes en esas fechas
            cursor.execute("""
                SELECT COUNT(*) FROM cita c
                JOIN slot s ON c.id_slot = s.id_slot
                WHERE c.id_doctor = %s
                  AND s.fecha BETWEEN %s AND %s
                  AND c.estado = 'pendiente'
            """, (session["doctor_id"], fecha_ini, fecha_fin))
            citas_afectadas = cursor.fetchone()[0]

            if citas_afectadas > 0:
                # Hay citas — advertir pero no bloquear
                cursor.execute("""
                    INSERT INTO bloqueo_fecha (id_doctor, fecha_inicio, fecha_fin, motivo)
                    VALUES (%s, %s, %s, %s)
                """, (session["doctor_id"], fecha_ini, fecha_fin, motivo))
                _db.commit()
                session["bloqueo_msg"] = f"Bloqueo creado. Atención: hay {citas_afectadas} cita(s) pendiente(s) en ese período que debes revisar manualmente."
            else:
                cursor.execute("""
                    INSERT INTO bloqueo_fecha (id_doctor, fecha_inicio, fecha_fin, motivo)
                    VALUES (%s, %s, %s, %s)
                """, (session["doctor_id"], fecha_ini, fecha_fin, motivo))
                # Eliminar slots disponibles en ese rango
                cursor.execute("""
                    DELETE FROM slot
                    WHERE id_doctor = %s
                      AND fecha BETWEEN %s AND %s
                      AND disponible = TRUE
                """, (session["doctor_id"], fecha_ini, fecha_fin))
                _db.commit()
                session["bloqueo_msg"] = f"Fechas bloqueadas del {fecha_ini} al {fecha_fin}."

        elif accion == "eliminar" and bloqueo_id:
            cursor.execute("DELETE FROM bloqueo_fecha WHERE id_bloqueo=%s AND id_doctor=%s",
                           (bloqueo_id, session["doctor_id"]))
            _db.commit()

        cursor.close()
        return redirect("/doctor/bloquear")

    # GET — mostrar bloqueos
    cursor.execute("""
        SELECT id_bloqueo, fecha_inicio, fecha_fin, motivo, created_at
        FROM bloqueo_fecha
        WHERE id_doctor = %s
          AND fecha_fin >= (NOW() AT TIME ZONE 'America/Guayaquil')::DATE
        ORDER BY fecha_inicio
    """, (session["doctor_id"],))
    bloqueos = cursor.fetchall()
    cursor.close()

    mensaje = session.pop("bloqueo_msg", None)
    return render_template("doctor_bloquear.html",
                           bloqueos=bloqueos, hoy=date.today(), mensaje=mensaje)


# ================================================================
# INIT tabla bloqueo_fecha al arranque (en hilo)
# ================================================================
def _crear_tabla_bloqueo():
    try:
        c = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = c.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bloqueo_fecha (
                id_bloqueo   SERIAL PRIMARY KEY,
                id_doctor    INTEGER REFERENCES doctor(id_doctor) ON DELETE CASCADE,
                fecha_inicio DATE NOT NULL,
                fecha_fin    DATE NOT NULL,
                motivo       VARCHAR(200) DEFAULT 'Vacaciones',
                created_at   TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        c.commit()
        cur.close()
        c.close()
    except Exception as e:
        print(f"⚠️  _crear_tabla_bloqueo: {e}")

threading.Thread(target=_crear_tabla_bloqueo, daemon=True).start()


# ================================================================
# FILTRO DE CITAS EN PANEL PACIENTE (AJAX)
# ================================================================
@app.route("/api/mis_citas")
@login_required(role="paciente")
def api_mis_citas():
    """Devuelve citas del paciente filtradas por estado. Usado por JS del panel."""
    estado = request.args.get("estado", "todas")
    _db, cursor = get_cursor()
    if estado == "todas":
        cursor.execute("""
            SELECT c.id_cita, s.fecha, s.hora, c.estado, c.descripcion
            FROM cita c
            JOIN slot s ON c.id_slot = s.id_slot
            WHERE c.id_paciente = %s
            ORDER BY s.fecha DESC, s.hora DESC
        """, (session["paciente_id"],))
    else:
        cursor.execute("""
            SELECT c.id_cita, s.fecha, s.hora, c.estado, c.descripcion
            FROM cita c
            JOIN slot s ON c.id_slot = s.id_slot
            WHERE c.id_paciente = %s AND c.estado = %s
            ORDER BY s.fecha DESC, s.hora DESC
        """, (session["paciente_id"], estado))
    filas = cursor.fetchall()
    cursor.close()
    data = [{
        "id": f[0],
        "fecha": str(f[1]),
        "hora":  f[2].strftime('%H:%M') if f[2] else '—',
        "estado": f[3],
        "descripcion": f[4] or ''
    } for f in filas]
    return make_response(json.dumps(data), 200, {"Content-Type": "application/json"})


if __name__ == "__main__":
    app.run(debug=True)


# ================================================================
# PÁGINAS DE ERROR PERSONALIZADAS
# ================================================================

@app.errorhandler(404)
def error_404(e):
    return render_template("error.html",
        codigo=404,
        titulo="Página no encontrada",
        mensaje="La página que buscas no existe o fue movida.",
        icono="bi-compass"
    ), 404

@app.errorhandler(403)
def error_403(e):
    return render_template("error.html",
        codigo=403,
        titulo="Acceso denegado",
        mensaje="No tienes permiso para ver esta página.",
        icono="bi-shield-x"
    ), 403

@app.errorhandler(500)
def error_500(e):
    return render_template("error.html",
        codigo=500,
        titulo="Error del servidor",
        mensaje="Algo salió mal. Ya estamos trabajando en solucionarlo.",
        icono="bi-exclamation-triangle"
    ), 500


# ================================================================
# RECORDATORIO AUTOMÁTICO DE CITAS (24 horas antes)
# ================================================================

def enviar_recordatorios():
    """
    Busca citas para mañana y manda un correo de recordatorio a cada paciente.
    Se ejecuta en un hilo de fondo al arrancar el servidor.
    Se repite cada 12 horas para no perder recordatorios si el servidor reinicia.
    """
    import time as _time

    while True:
        try:
            c = psycopg2.connect(DATABASE_URL, sslmode="require")
            cur = c.cursor()

            # Citas pendientes para mañana en hora de Quito
            cur.execute("""
                SELECT
                    p.correo, p.nombre, p.apellido,
                    s.fecha, s.hora,
                    c.descripcion
                FROM cita c
                JOIN paciente p ON c.id_paciente = p.id_paciente
                JOIN slot     s ON c.id_slot     = s.id_slot
                WHERE c.estado = 'pendiente'
                  AND s.fecha = (NOW() AT TIME ZONE 'America/Guayaquil')::DATE + INTERVAL '1 day'
                ORDER BY s.hora
            """)
            citas = cur.fetchall()
            cur.close()
            c.close()

            for cita in citas:
                correo, nombre, apellido, fecha, hora, descripcion = cita
                hora_str = hora.strftime('%H:%M') if hasattr(hora, 'strftime') else str(hora)[:5]

                try:
                    fecha_dt   = fecha if hasattr(fecha, 'strftime') else fecha
                    fecha_str  = fecha_dt.strftime('%A %d de %B de %Y').capitalize()
                except Exception:
                    fecha_str  = str(fecha)

                cuerpo = f"""
                <!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"></head>
                <body style="font-family:Arial,sans-serif;background:#f4f6f9;padding:2rem;margin:0;">
                <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.08);">
                  <div style="background:linear-gradient(135deg,#0b1f3a,#162f55);padding:2rem;text-align:center;">
                    <div style="font-size:2rem;margin-bottom:.5rem;">⏰</div>
                    <h2 style="margin:0;color:#fff;font-size:1.2rem;">Recordatorio de cita</h2>
                    <p style="margin:.4rem 0 0;color:rgba(255,255,255,.55);font-size:.85rem;">MediClover · Dr. Luis Suárez</p>
                  </div>
                  <div style="padding:2rem;">
                    <p style="color:#334155;font-size:.95rem;margin:0 0 1.5rem;">
                      Hola <strong>{nombre} {apellido}</strong>, te recordamos que tienes una cita
                      <strong style="color:#0a7c5c;">mañana</strong>.
                    </p>
                    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:1.25rem;">
                      <div style="margin-bottom:.75rem;font-size:.875rem;color:#374151;">
                        <strong>📆 Fecha:</strong> {fecha_str}
                      </div>
                      <div style="margin-bottom:.75rem;font-size:.875rem;color:#374151;">
                        <strong>🕐 Hora:</strong> {hora_str}
                      </div>
                      <div style="font-size:.875rem;color:#374151;">
                        <strong>👨‍⚕️ Doctor:</strong> Dr. Luis Suárez — Médico General
                      </div>
                    </div>
                    <p style="color:#6b7280;font-size:.8rem;margin:1.25rem 0 0;line-height:1.6;">
                      Si necesitas cancelar tu cita, hazlo desde tu panel en MediClover
                      con suficiente tiempo de anticipación.
                    </p>
                    <div style="text-align:center;margin-top:1.5rem;">
                      <a href="https://mediclover.onrender.com/panel_paciente"
                         style="background:#0a7c5c;color:#fff;padding:.75rem 1.75rem;
                                border-radius:6px;text-decoration:none;font-weight:700;font-size:.9rem;">
                        Ver mi panel
                      </a>
                    </div>
                  </div>
                  <div style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:1rem 2rem;text-align:center;">
                    <p style="margin:0;font-size:.75rem;color:#94a3b8;">
                      MediClover · Sistema de Gestión de Citas Médicas · Quito, Ecuador
                    </p>
                  </div>
                </div>
                </body></html>
                """
                asunto = f"⏰ Recordatorio: tienes cita mañana {hora_str} — MediClover"
                enviar_correo_async(correo, asunto, cuerpo)

            if citas:
                print(f"✅ Recordatorios enviados: {len(citas)} paciente(s)")

        except Exception as e:
            print(f"⚠️  Error en recordatorios: {e}")

        # Esperar 12 horas antes de volver a revisar
        _time.sleep(12 * 60 * 60)


# Iniciar el hilo de recordatorios si hay configuración de correo
if SENDGRID_KEY:
    threading.Thread(target=enviar_recordatorios, daemon=True).start()
    print("✅ Recordatorios automáticos activados")

from flask import Flask, render_template, request, redirect, session, flash
from functools import wraps
import psycopg2
import os
import random
import smtplib
from email.mime.text import MIMEText
from datetime import date, datetime, timedelta
import threading

# ── Configuración Gmail SMTP ──────────────────────────────────────────────────
MAIL_USER = os.getenv("MAIL_USER", "")
MAIL_PASS = os.getenv("MAIL_PASS", "")

def enviar_correo(destinatario, asunto, cuerpo_html):
    if not MAIL_USER or not MAIL_PASS:
        print("MAIL_USER o MAIL_PASS no configurados")
        return False
    try:
        msg = MIMEText(cuerpo_html, "html", "utf-8")
        msg["Subject"] = asunto
        msg["From"]    = f"MediClover <{MAIL_USER}>"
        msg["To"]      = destinatario
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(MAIL_USER, MAIL_PASS)
            smtp.sendmail(MAIL_USER, destinatario, msg.as_string())
        return True
    except Exception as e:
        print("Error al enviar correo:", e)
        return False


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
    return enviar_correo(correo_paciente, asunto, cuerpo)


app = Flask(__name__)
app.secret_key = "Mediclover_19"

DURACION_CITA = 35  # minutos

# ── Admins por variable de entorno (formato: "usuario:pass,usuario2:pass2")
# Configura en Render → Environment → ADMIN_CREDENTIALS
# Ejemplo: "admin:1234,mathias:pass123,jair:pass456,jose:pass789"
_raw = os.getenv("ADMIN_CREDENTIALS", "admin:1234")
ADMINS = {}
for par in _raw.split(","):
    par = par.strip()
    if ":" in par:
        u, p = par.split(":", 1)
        ADMINS[u.strip()] = p.strip()
# ADMINS queda como dict: {"admin":"1234","mathias":"pass123", ...}

DATABASE_URL = os.getenv("DATABASE_URL")
conn = None

def get_conn():
    """
    Devuelve la conexión global, reconectando automáticamente si está caída.
    Esto soluciona los Internal Server Error en Render (free tier duerme la BD).
    """
    global conn
    try:
        if conn:
            conn.cursor().execute("SELECT 1")
            return conn
    except Exception:
        conn = None

    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            print("✅ (Re)conectado a PostgreSQL")
            return conn
        else:
            print("❌ No hay DATABASE_URL")
            return None
    except Exception as e:
        print("❌ Error de conexión:", e)
        return None


# ===============================
# CREAR TABLAS SI NO EXISTEN
# ===============================
def init_db():
    c = get_conn()
    if not c:
        return
    try:
        cursor = c.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctor (
                id_doctor    SERIAL PRIMARY KEY,
                nombre       VARCHAR(100) NOT NULL,
                apellido     VARCHAR(100) NOT NULL,
                correo       VARCHAR(150),
                password     VARCHAR(100) NOT NULL,
                especialidad VARCHAR(150) DEFAULT 'Médico General'
            )
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
        c.commit()
        cursor.close()
        print("✅ BD inicializada")
    except Exception as e:
        print(f"⚠️  init_db error: {e}")


# ── Iniciar BD en hilo de fondo para no bloquear el arranque de Gunicorn ──
# Render requiere que el puerto HTTP esté disponible en <60s.
# Conectar a Supabase puede tardar varios segundos en cold start.
threading.Thread(target=init_db, daemon=True).start()


# ===============================
# HELPERS
# ===============================

def get_cursor():
    """Helper que retorna (conexión, cursor) siempre de la misma conexión."""
    c = get_conn()
    return c, c.cursor()

def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if role == "admin"    and session.get("usuario") not in ADMINS:
                return redirect("/login")
            if role == "paciente" and "paciente_id" not in session:
                return redirect("/login_paciente")
            if role == "doctor"   and "doctor_id" not in session:
                return redirect("/login_doctor")
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
        usuario  = request.form.get("usuario", "").strip()
        password = request.form.get("password", "").strip()
        # Verificar contra el diccionario de admins (cargado desde variable de entorno)
        if usuario in ADMINS and ADMINS[usuario] == password:
            session.clear()
            session["usuario"]       = usuario
            session["admin_nombre"]  = usuario.capitalize()
            return redirect("/admin")
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
    cursor.execute("""
        SELECT COUNT(*) FROM cita c JOIN slot s ON c.id_slot=s.id_slot
        WHERE s.fecha=CURRENT_DATE
    """)
    citas_hoy = cursor.fetchone()[0]
    cursor.close()
    return render_template("index.html",
        total_pacientes=total_pacientes,
        citas_pendientes=citas_pendientes,
        citas_hoy=citas_hoy
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
    return render_template("editar_paciente.html", paciente=paciente)


@app.route("/eliminar_paciente/<int:id>")
@login_required(role="admin")
def eliminar_paciente(id):
    _db, cursor = get_cursor()
    cursor.execute("DELETE FROM cita     WHERE id_paciente=%s", (id,))
    cursor.execute("DELETE FROM paciente WHERE id_paciente=%s", (id,))
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
        ORDER BY s.fecha, s.hora
    """)
    lista = cursor.fetchall()
    cursor.close()
    return render_template("citas.html", citas=lista)


@app.route("/completar_cita/<int:id>")
@login_required(role="admin")
def completar_cita(id):
    _db, cursor = get_cursor()
    cursor.execute("UPDATE cita SET estado='completada' WHERE id_cita=%s", (id,))
    _db.commit()
    cursor.close()
    return redirect("/citas")


@app.route("/cancelar_cita/<int:id>")
@login_required(role="admin")
def cancelar_cita(id):
    _db, cursor = get_cursor()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s", (id,))
    _db.commit()
    cursor.close()
    return redirect("/citas")


# Admin — doctores
@app.route("/admin/doctores")
@login_required(role="admin")
def admin_doctores():
    _db, cursor = get_cursor()
    cursor.execute("SELECT id_doctor,nombre,apellido,correo,especialidad FROM doctor")
    lista = cursor.fetchall()
    cursor.close()
    return render_template("admin_doctores.html", doctores=lista)


@app.route("/admin/crear_doctor", methods=["GET", "POST"])
@login_required(role="admin")
def crear_doctor():
    if request.method == "POST":
        _db, cursor = get_cursor()
        cursor.execute("SELECT id_doctor FROM doctor WHERE usuario=%s", (request.form["usuario"],))
        if cursor.fetchone():
            cursor.close()
            return render_template("crear_doctor.html", error="Ese usuario ya existe")
        correo_doc = request.form.get("correo", "").strip().lower()
        cursor.execute("""
            INSERT INTO doctor(nombre, apellido, usuario, password, especialidad, correo)
            VALUES(%s, %s, %s, %s, %s, %s)
        """, (request.form["nombre"], request.form["apellido"], request.form["usuario"],
              request.form["password"], request.form["especialidad"], correo_doc or None))
        _db.commit()
        cursor.close()
        return redirect("/admin/doctores")
    return render_template("crear_doctor.html")


@app.route("/admin/eliminar_doctor/<int:id>")
@login_required(role="admin")
def eliminar_doctor(id):
    _db, cursor = get_cursor()
    cursor.execute("UPDATE cita SET id_doctor=NULL WHERE id_doctor=%s", (id,))
    cursor.execute("DELETE FROM slot   WHERE id_doctor=%s", (id,))
    cursor.execute("DELETE FROM doctor WHERE id_doctor=%s", (id,))
    _db.commit()
    cursor.close()
    return redirect("/admin/doctores")


# ================================================================
# DOCTOR
# ================================================================
@app.route("/login_doctor", methods=["GET", "POST"])
def login_doctor():
    if not get_conn():
        return "Error BD"
    if request.method == "POST":
        _db, cursor = get_cursor()
        cursor.execute("SELECT id_doctor,nombre FROM doctor WHERE usuario=%s AND password=%s",
                       (request.form["usuario"], request.form["password"]))
        doc = cursor.fetchone()
        cursor.close()
        if doc:
            session.clear()
            session["doctor_id"]     = doc[0]
            session["doctor_nombre"] = doc[1]
            return redirect("/doctor/panel")
        return render_template("login_doctor.html", error="Usuario o contraseña incorrectos")
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


@app.route("/doctor/completar/<int:id>")
@login_required(role="doctor")
def doctor_completar(id):
    _db, cursor = get_cursor()
    cursor.execute("UPDATE cita SET estado='completada' WHERE id_cita=%s AND id_doctor=%s",
                   (id, session["doctor_id"]))
    _db.commit()
    cursor.close()
    return redirect("/doctor/panel")


@app.route("/doctor/cancelar/<int:id>")
@login_required(role="doctor")
def doctor_cancelar(id):
    _db, cursor = get_cursor()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s AND id_doctor=%s",
                   (id, session["doctor_id"]))
    _db.commit()
    cursor.close()
    return redirect("/doctor/panel")


@app.route("/doctor/historial", methods=["GET", "POST"])
@login_required(role="doctor")
def doctor_historial():
    paciente = None
    historial = []
    error = None
    if request.method == "POST":
        cedula = request.form.get("cedula", "").strip()
        if not cedula.isdigit() or len(cedula) != 10:
            error = "Ingresa una cédula válida de 10 dígitos"
        else:
            _db, cursor = get_cursor()
            cursor.execute("""
                SELECT id_paciente,nombre,apellido,correo,telefono,cedula
                FROM paciente WHERE cedula=%s
            """, (cedula,))
            paciente = cursor.fetchone()
            if paciente:
                cursor.execute("""
                    SELECT s.fecha, s.hora, c.estado, c.descripcion,
                           d.nombre, d.apellido
                    FROM cita c
                    JOIN slot s        ON c.id_slot   = s.id_slot
                    LEFT JOIN doctor d ON c.id_doctor = d.id_doctor
                    WHERE c.id_paciente=%s
                    ORDER BY s.fecha DESC, s.hora DESC
                """, (paciente[0],))
                historial = cursor.fetchall()
            else:
                error = "No se encontró paciente con esa cédula"
            cursor.close()
    return render_template("doctor_historial.html",
                           paciente=paciente, historial=historial, error=error)


# ================================================================
# SLOTS — Creación masiva automática cada 35 minutos
# ================================================================
@app.route("/doctor/slots/crear", methods=["POST"])
@login_required(role="doctor")
def crear_slot():
    fecha    = request.form.get("fecha", "").strip()
    hora     = request.form.get("hora",  "").strip()
    cantidad = request.form.get("cantidad", "1").strip()

    if not fecha or not hora:
        return redirect("/doctor/panel")
    if fecha < str(date.today()):
        return redirect("/doctor/panel")

    try:
        cantidad = int(cantidad)
        if cantidad < 1:
            cantidad = 1
    except ValueError:
        cantidad = 1

    hora_actual_dt   = datetime.strptime(hora, "%H:%M")
    creados          = 0
    omitidos         = 0
    horas_pendientes = []

    _db, cursor = get_cursor()

    for i in range(cantidad):
        hora_str    = hora_actual_dt.strftime("%H:%M")
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

    # Guardar en sesión — se limpia en doctor_panel() antes de renderizar
    session["slots_resultado"] = {
        "creados":  creados,
        "omitidos": omitidos
    }

    return redirect("/doctor/panel")


@app.route("/doctor/slots/eliminar/<int:id>")
@login_required(role="doctor")
def eliminar_slot(id):
    _db, cursor = get_cursor()
    cursor.execute("SELECT id_cita FROM cita WHERE id_slot=%s AND estado='pendiente'", (id,))
    if not cursor.fetchone():
        cursor.execute("DELETE FROM slot WHERE id_slot=%s AND id_doctor=%s",
                       (id, session["doctor_id"]))
        _db.commit()
    cursor.close()
    return redirect("/doctor/panel")


# ================================================================
# PACIENTE
# ================================================================
@app.route("/login_paciente", methods=["GET", "POST"])
def login_paciente():
    if not get_conn():
        return "Error BD"
    if request.method == "POST":
        _db, cursor = get_cursor()
        cursor.execute("SELECT id_paciente,nombre FROM paciente WHERE correo=%s",
                       (request.form["correo"],))
        user = cursor.fetchone()
        cursor.close()
        if user:
            session.clear()
            session["paciente_id"]     = user[0]
            session["paciente_nombre"] = user[1]
            return redirect("/panel_paciente")
        return render_template("login_paciente.html", error="Correo no registrado")
    return render_template("login_paciente.html")


@app.route("/registro_paciente", methods=["GET", "POST"])
def registro_paciente():
    if not get_conn():
        return "Error BD"
    if request.method == "POST":
        nombre   = request.form["nombre"]
        apellido = request.form["apellido"]
        correo   = request.form["correo"]
        telefono = request.form["telefono"]
        cedula   = request.form["cedula"]

        if len(nombre) < 3 or not nombre.replace(" ", "").isalpha():
            return render_template("registro_paciente.html", mensaje="Nombre inválido", tipo="error")
        if len(apellido) < 3 or not apellido.replace(" ", "").isalpha():
            return render_template("registro_paciente.html", mensaje="Apellido inválido", tipo="error")
        if "@" not in correo:
            return render_template("registro_paciente.html", mensaje="Correo inválido", tipo="error")
        if not telefono.isdigit():
            return render_template("registro_paciente.html", mensaje="Teléfono inválido", tipo="error")
        if not cedula.isdigit() or len(cedula) != 10:
            return render_template("registro_paciente.html", mensaje="Cédula inválida (10 dígitos)", tipo="error")

        _db, cursor = get_cursor()
        cursor.execute("SELECT * FROM paciente WHERE correo=%s OR cedula=%s", (correo, cedula))
        if cursor.fetchone():
            cursor.close()
            return render_template("registro_paciente.html", mensaje="Correo o cédula ya registrados", tipo="error")
        cursor.execute("""
            INSERT INTO paciente(nombre,apellido,correo,telefono,cedula)
            VALUES(%s,%s,%s,%s,%s)
        """, (nombre, apellido, correo, telefono, cedula))
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
        ORDER BY s.fecha DESC, s.hora DESC
    """, (session["paciente_id"],))
    citas = cursor.fetchall()
    cursor.close()
    return render_template("panel_paciente.html", citas=citas)


@app.route("/cancelar_cita_paciente/<int:id>")
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

        enviado = enviar_correo(correo, "MediClover — Código para restablecer contraseña", cuerpo)
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


if __name__ == "__main__":
    app.run(debug=True)


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

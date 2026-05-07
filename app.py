from flask import Flask, render_template, request, redirect, session, flash
from functools import wraps
import psycopg2
import os
import random
import smtplib
from email.mime.text import MIMEText
from datetime import date, datetime, timedelta

# ── Configuración Gmail SMTP ──────────────────────────────────────────────────
# Variables de entorno en Render: MAIL_USER y MAIL_PASS
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

app = Flask(__name__)
app.secret_key = "Mediclover_19"

ADMIN_USER = "admin"
ADMIN_PASS = "1234"
DURACION_CITA = 35  # minutos

DATABASE_URL = os.getenv("DATABASE_URL")
conn = None

try:
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        print("✅ Conectado a PostgreSQL")
    else:
        print("❌ No hay DATABASE_URL")
except Exception as e:
    print("❌ Error de conexión:", e)


# ===============================
# CREAR TABLAS SI NO EXISTEN
# ===============================
def init_db():
    if not conn:
        return
    cursor = conn.cursor()
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
    # NOTA: la columna 'usuario' fue agregada manualmente en Supabase SQL Editor
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
    conn.commit()
    cursor.close()
    print("✅ BD inicializada")

init_db()


# ===============================
# HELPERS
# ===============================
def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if role == "admin"    and session.get("usuario") != ADMIN_USER:
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
    cursor = conn.cursor()
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
        if request.form["usuario"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session.clear()
            session["usuario"] = ADMIN_USER
            return redirect("/admin")
        return render_template("login.html", error="Credenciales incorrectas")
    return render_template("login.html")


@app.route("/admin")
@login_required(role="admin")
def admin():
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM paciente")
    total_pacientes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM cita WHERE estado='pendiente'")
    citas_pendientes = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM cita c JOIN slot s ON c.id_slot=s.id_slot
        WHERE s.fecha=CURRENT_DATE
    """)
    citas_hoy = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM doctor")
    total_doctores = cursor.fetchone()[0]
    cursor.close()
    return render_template("index.html",
        total_pacientes=total_pacientes,
        citas_pendientes=citas_pendientes,
        citas_hoy=citas_hoy,
        total_doctores=total_doctores
    )


@app.route("/pacientes")
@login_required(role="admin")
def pacientes():
    cursor = conn.cursor()
    cursor.execute("SELECT id_paciente,nombre,apellido,correo,telefono,cedula FROM paciente")
    lista = cursor.fetchall()
    cursor.close()
    return render_template("pacientes.html", pacientes=lista)


@app.route("/editar_paciente/<int:id>", methods=["GET", "POST"])
@login_required(role="admin")
def editar_paciente(id):
    cursor = conn.cursor()
    if request.method == "POST":
        cursor.execute("""
            UPDATE paciente SET nombre=%s,apellido=%s,correo=%s,telefono=%s,cedula=%s
            WHERE id_paciente=%s
        """, (request.form["nombre"], request.form["apellido"], request.form["correo"],
              request.form["telefono"], request.form["cedula"], id))
        conn.commit()
        cursor.close()
        return redirect("/pacientes")
    cursor.execute("SELECT nombre,apellido,correo,telefono,cedula FROM paciente WHERE id_paciente=%s", (id,))
    paciente = cursor.fetchone()
    cursor.close()
    return render_template("editar_paciente.html", paciente=paciente)


@app.route("/eliminar_paciente/<int:id>")
@login_required(role="admin")
def eliminar_paciente(id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cita     WHERE id_paciente=%s", (id,))
    cursor.execute("DELETE FROM paciente WHERE id_paciente=%s", (id,))
    conn.commit()
    cursor.close()
    return redirect("/pacientes")


@app.route("/citas")
@login_required(role="admin")
def citas():
    cursor = conn.cursor()
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
    cursor = conn.cursor()
    cursor.execute("UPDATE cita SET estado='completada' WHERE id_cita=%s", (id,))
    conn.commit()
    cursor.close()
    return redirect("/citas")


@app.route("/cancelar_cita/<int:id>")
@login_required(role="admin")
def cancelar_cita(id):
    cursor = conn.cursor()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s", (id,))
    conn.commit()
    cursor.close()
    return redirect("/citas")


# Admin — doctores
@app.route("/admin/doctores")
@login_required(role="admin")
def admin_doctores():
    cursor = conn.cursor()
    cursor.execute("SELECT id_doctor,nombre,apellido,correo,especialidad FROM doctor")
    lista = cursor.fetchall()
    cursor.close()
    return render_template("admin_doctores.html", doctores=lista)


@app.route("/admin/crear_doctor", methods=["GET", "POST"])
@login_required(role="admin")
def crear_doctor():
    if request.method == "POST":
        cursor = conn.cursor()
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
        conn.commit()
        cursor.close()
        return redirect("/admin/doctores")
    return render_template("crear_doctor.html")


@app.route("/admin/eliminar_doctor/<int:id>")
@login_required(role="admin")
def eliminar_doctor(id):
    cursor = conn.cursor()
    cursor.execute("UPDATE cita SET id_doctor=NULL WHERE id_doctor=%s", (id,))
    cursor.execute("DELETE FROM slot   WHERE id_doctor=%s", (id,))
    cursor.execute("DELETE FROM doctor WHERE id_doctor=%s", (id,))
    conn.commit()
    cursor.close()
    return redirect("/admin/doctores")


# ================================================================
# DOCTOR
# ================================================================
@app.route("/login_doctor", methods=["GET", "POST"])
def login_doctor():
    if not conn:
        return "Error BD"
    if request.method == "POST":
        cursor = conn.cursor()
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
    cursor = conn.cursor()
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
        WHERE id_doctor=%s AND fecha >= CURRENT_DATE
        ORDER BY fecha, hora
    """, (session["doctor_id"],))
    slots = cursor.fetchall()
    cursor.close()
    return render_template("doctor_panel.html", citas=citas, slots=slots, hoy=date.today())


@app.route("/doctor/completar/<int:id>")
@login_required(role="doctor")
def doctor_completar(id):
    cursor = conn.cursor()
    cursor.execute("UPDATE cita SET estado='completada' WHERE id_cita=%s AND id_doctor=%s",
                   (id, session["doctor_id"]))
    conn.commit()
    cursor.close()
    return redirect("/doctor/panel")


@app.route("/doctor/cancelar/<int:id>")
@login_required(role="doctor")
def doctor_cancelar(id):
    cursor = conn.cursor()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s AND id_doctor=%s",
                   (id, session["doctor_id"]))
    conn.commit()
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
            cursor = conn.cursor()
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
    fecha      = request.form.get("fecha", "").strip()
    hora       = request.form.get("hora",  "").strip()
    cantidad   = request.form.get("cantidad", "1").strip()

    # --- Validaciones básicas ---
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

    # --- Generar slots cada 35 min, saltando los que se solapan ---
    hora_actual_dt = datetime.strptime(hora, "%H:%M")
    creados        = 0
    omitidos       = 0
    # Guardamos las horas que vamos a insertar en esta misma tanda
    # para validar solapamiento entre ellas también
    horas_pendientes = []

    cursor = conn.cursor()

    for i in range(cantidad):
        hora_str = hora_actual_dt.strftime("%H:%M")

        # Verificar contra BD y contra los de esta misma tanda
        solapaBD     = slot_solapado(session["doctor_id"], fecha, hora_str)
        solapaTanda  = slot_solapado_en_lista(hora_actual_dt, horas_pendientes)

        if not solapaBD and not solapaTanda:
            cursor.execute(
                "INSERT INTO slot(id_doctor, fecha, hora) VALUES(%s, %s, %s)",
                (session["doctor_id"], fecha, hora_str)
            )
            horas_pendientes.append(hora_actual_dt)
            creados += 1
        else:
            omitidos += 1

        # Avanzar 35 minutos para el siguiente slot
        hora_actual_dt += timedelta(minutes=DURACION_CITA)

    conn.commit()
    cursor.close()

    # Guardar resumen en sesión para mostrarlo en el panel
    session["slots_resultado"] = {
        "creados":  creados,
        "omitidos": omitidos
    }

    return redirect("/doctor/panel")


@app.route("/doctor/slots/eliminar/<int:id>")
@login_required(role="doctor")
def eliminar_slot(id):
    cursor = conn.cursor()
    cursor.execute("SELECT id_cita FROM cita WHERE id_slot=%s AND estado='pendiente'", (id,))
    if not cursor.fetchone():
        cursor.execute("DELETE FROM slot WHERE id_slot=%s AND id_doctor=%s",
                       (id, session["doctor_id"]))
        conn.commit()
    cursor.close()
    return redirect("/doctor/panel")


# ================================================================
# PACIENTE
# ================================================================
@app.route("/login_paciente", methods=["GET", "POST"])
def login_paciente():
    if not conn:
        return "Error BD"
    if request.method == "POST":
        cursor = conn.cursor()
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
    if not conn:
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

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM paciente WHERE correo=%s OR cedula=%s", (correo, cedula))
        if cursor.fetchone():
            cursor.close()
            return render_template("registro_paciente.html", mensaje="Correo o cédula ya registrados", tipo="error")
        cursor.execute("""
            INSERT INTO paciente(nombre,apellido,correo,telefono,cedula)
            VALUES(%s,%s,%s,%s,%s)
        """, (nombre, apellido, correo, telefono, cedula))
        conn.commit()
        cursor.close()
        return render_template("registro_paciente.html",
            mensaje="¡Cuenta creada! Ya puedes iniciar sesión.", tipo="success")
    return render_template("registro_paciente.html")


@app.route("/panel_paciente")
@login_required(role="paciente")
def panel_paciente():
    cursor = conn.cursor()
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
    cursor = conn.cursor()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s AND id_paciente=%s",
                   (id, session["paciente_id"]))
    conn.commit()
    cursor.close()
    return redirect("/panel_paciente")


@app.route("/reservar", methods=["GET", "POST"])
@login_required(role="paciente")
def reservar():
    cursor = conn.cursor()
    if request.method == "POST":
        id_slot     = request.form.get("id_slot")
        descripcion = request.form.get("descripcion", "").strip()

        def reload(msg, tipo):
            cursor2 = conn.cursor()
            cursor2.execute("""
                SELECT s.id_slot, s.fecha, s.hora,
                       d.nombre, d.apellido, d.especialidad
                FROM slot s
                JOIN doctor d ON s.id_doctor = d.id_doctor
                WHERE s.disponible=TRUE AND s.fecha >= CURRENT_DATE
                ORDER BY s.fecha, s.hora
            """)
            slots = cursor2.fetchall()
            cursor2.close()
            return render_template("reservar.html", slots=slots, mensaje=msg, tipo=tipo)

        if not id_slot:
            return reload("Selecciona un horario disponible", "error")
        if len(descripcion) < 5:
            return reload("Describe el motivo (mínimo 5 caracteres)", "error")

        cursor.execute("SELECT id_slot, id_doctor FROM slot WHERE id_slot=%s AND disponible=TRUE", (id_slot,))
        slot = cursor.fetchone()
        if not slot:
            cursor.close()
            return reload("Ese horario ya no está disponible", "error")

        cursor.execute("UPDATE slot SET disponible=FALSE WHERE id_slot=%s", (slot[0],))
        cursor.execute("""
            INSERT INTO cita(id_paciente, id_doctor, id_slot, estado, descripcion)
            VALUES(%s, %s, %s, 'pendiente', %s)
        """, (session["paciente_id"], slot[1], slot[0], descripcion))
        conn.commit()
        cursor.close()
        return render_template("reservar.html", slots=[], mensaje="¡Cita reservada con éxito!", tipo="success")

    cursor.execute("""
        SELECT s.id_slot, s.fecha, s.hora,
               d.nombre, d.apellido, d.especialidad
        FROM slot s
        JOIN doctor d ON s.id_doctor = d.id_doctor
        WHERE s.disponible=TRUE AND s.fecha >= CURRENT_DATE
        ORDER BY s.fecha, s.hora
    """)
    slots = cursor.fetchall()
    cursor.close()
    return render_template("reservar.html", slots=slots)


# ================================================================
# LOGOUT
# ================================================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)


# ================================================================
# RECUPERAR CONTRASEÑA — DOCTOR
# ================================================================
@app.route("/doctor/recuperar", methods=["GET", "POST"])
def doctor_recuperar():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        cursor = conn.cursor()
        cursor.execute("SELECT id_doctor FROM doctor WHERE correo=%s", (correo,))
        doc = cursor.fetchone()
        cursor.close()

        if not doc:
            return render_template("doctor_recuperar.html",
                error="No hay ningún doctor registrado con ese correo.")

        # Generar código de 6 dígitos y guardarlo en sesión con expiración
        codigo = str(random.randint(100000, 999999))
        session["reset_codigo"]  = codigo
        session["reset_correo"]  = correo
        session["reset_expira"]  = (datetime.now() + timedelta(minutes=15)).isoformat()

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
    correo            = request.form.get("correo", "").strip().lower()
    codigo_ingresado  = request.form.get("codigo", "").strip()
    nueva_password    = request.form.get("nueva_password", "")
    confirmar         = request.form.get("confirmar_password", "")

    def volver(err):
        return render_template("doctor_verificar_codigo.html", correo=correo, error=err)

    # Validaciones
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

    # Actualizar contraseña
    cursor = conn.cursor()
    cursor.execute("UPDATE doctor SET password=%s WHERE correo=%s", (nueva_password, correo))
    conn.commit()
    cursor.close()

    # Limpiar sesión de reset
    session.pop("reset_codigo", None)
    session.pop("reset_correo", None)
    session.pop("reset_expira", None)

    return render_template("login_doctor.html",
        mensaje="¡Contraseña restablecida con éxito! Ya puedes iniciar sesión.",
        tipo="success")

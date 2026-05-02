from flask import Flask, render_template, request, redirect, session
from functools import wraps
import psycopg2
import os
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "Mediclover_19"

ADMIN_USER = "Luis54"
ADMIN_PASS = "L2008S"
DURACION_CITA = 35  # minutos

DATABASE_URL = os.getenv("DATABASE_URL")
conn = None

def get_conn():
    global conn
    try:
        if conn is None or conn.closed != 0:
            raise Exception("reconectar")
        conn.cursor().execute("SELECT 1")
    except Exception:
        try:
            conn = psycopg2.connect(DATABASE_URL, sslmode="require", connect_timeout=10)
            print("✅ Conectado a PostgreSQL")
        except Exception as e:
            print("❌ Error de conexión:", e)
            conn = None
    return conn


# ===============================
# CREAR TABLAS SI NO EXISTEN
# ===============================
def init_db(): 
    c = get_conn()
    if not c:
        return
    cursor = c.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctor (
            id_doctor    SERIAL PRIMARY KEY,
            nombre       VARCHAR(100) NOT NULL,
            apellido     VARCHAR(100) NOT NULL,
            correo       VARCHAR(150) UNIQUE NOT NULL,
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
    c.commit()
    cursor.close()
    print("✅ BD inicializada")

init_db() # init_db()  ← comentada, las tablas ya existen en Supabase


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
    cursor = get_conn().cursor()
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
    cursor = get_conn().cursor()
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
    cedula_busqueda = request.args.get("cedula", "").strip()
    cursor = get_conn().cursor()
    if cedula_busqueda:
        cursor.execute(
            "SELECT id_paciente,nombre,apellido,correo,telefono,cedula FROM paciente WHERE cedula=%s",
            (cedula_busqueda,)
        )
    else:
        cursor.execute("SELECT id_paciente,nombre,apellido,correo,telefono,cedula FROM paciente")
    lista = cursor.fetchall()
    cursor.close()
    return render_template("pacientes.html", pacientes=lista, cedula_busqueda=cedula_busqueda)


@app.route("/editar_paciente/<int:id>", methods=["GET", "POST"])
@login_required(role="admin")
def editar_paciente(id):
    cursor = get_conn().cursor()
    if request.method == "POST":
        cursor.execute("""
            UPDATE paciente SET nombre=%s,apellido=%s,correo=%s,telefono=%s,cedula=%s
            WHERE id_paciente=%s
        """, (request.form["nombre"], request.form["apellido"], request.form["correo"],
              request.form["telefono"], request.form["cedula"], id))
        get_conn().commit()
        cursor.close()
        return redirect("/pacientes")
    cursor.execute("SELECT nombre,apellido,correo,telefono,cedula FROM paciente WHERE id_paciente=%s", (id,))
    paciente = cursor.fetchone()
    cursor.close()
    return render_template("editar_paciente.html", paciente=paciente)


@app.route("/eliminar_paciente/<int:id>")
@login_required(role="admin")
def eliminar_paciente(id):
    c = get_conn()
    cursor = c.cursor()
    cursor.execute("DELETE FROM cita     WHERE id_paciente=%s", (id,))
    cursor.execute("DELETE FROM paciente WHERE id_paciente=%s", (id,))
    c.commit()
    cursor.close()
    return redirect("/pacientes")


@app.route("/citas")
@login_required(role="admin")
def citas():
    cursor = get_conn().cursor()
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
    c = get_conn()
    cursor = c.cursor()
    cursor.execute("UPDATE cita SET estado='completada' WHERE id_cita=%s", (id,))
    c.commit()
    cursor.close()
    return redirect("/citas")


@app.route("/cancelar_cita/<int:id>")
@login_required(role="admin")
def cancelar_cita(id):
    c = get_conn()
    cursor = c.cursor()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s", (id,))
    c.commit()
    cursor.close()
    return redirect("/citas")


# Admin — doctores
@app.route("/admin/doctores")
@login_required(role="admin")
def admin_doctores():
    cursor = get_conn().cursor()
    cursor.execute("SELECT id_doctor,nombre,apellido,correo,especialidad FROM doctor")
    lista = cursor.fetchall()
    cursor.close()
    return render_template("admin_doctores.html", doctores=lista)


@app.route("/admin/crear_doctor", methods=["GET", "POST"])
@login_required(role="admin")
def crear_doctor():
    if request.method == "POST":
        c = get_conn()
        cursor = c.cursor()
        cursor.execute("SELECT id_doctor FROM doctor WHERE correo=%s", (request.form["correo"],))
        if cursor.fetchone():
            cursor.close()
            return render_template("crear_doctor.html", error="Correo ya registrado")
        cursor.execute("""
            INSERT INTO doctor(nombre,apellido,correo,password,especialidad)
            VALUES(%s,%s,%s,%s,%s)
        """, (request.form["nombre"], request.form["apellido"], request.form["correo"],
              request.form["password"], request.form["especialidad"]))
        c.commit()
        cursor.close()
        return redirect("/admin/doctores")
    return render_template("crear_doctor.html")


@app.route("/admin/eliminar_doctor/<int:id>")
@login_required(role="admin")
def eliminar_doctor(id):
    c = get_conn()
    cursor = c.cursor()
    cursor.execute("UPDATE cita SET id_doctor=NULL WHERE id_doctor=%s", (id,))
    cursor.execute("DELETE FROM slot   WHERE id_doctor=%s", (id,))
    cursor.execute("DELETE FROM doctor WHERE id_doctor=%s", (id,))
    c.commit()
    cursor.close()
    return redirect("/admin/doctores")


# ================================================================
# DOCTOR
# ================================================================
@app.route("/login_doctor", methods=["GET", "POST"])
def login_doctor():
    if request.method == "POST":
        cursor = get_conn().cursor()
        cursor.execute("SELECT id_doctor,nombre FROM doctor WHERE correo=%s AND password=%s",
                       (request.form["correo"], request.form["password"]))
        doc = cursor.fetchone()
        cursor.close()
        if doc:
            session.clear()
            session["doctor_id"]     = doc[0]
            session["doctor_nombre"] = doc[1]
            return redirect("/doctor/panel")
        return render_template("login_doctor.html", error="Credenciales incorrectas")
    return render_template("login_doctor.html")


@app.route("/doctor/panel")
@login_required(role="doctor")
def doctor_panel():
    cursor = get_conn().cursor()
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
    c = get_conn()
    cursor = c.cursor()
    cursor.execute("UPDATE cita SET estado='completada' WHERE id_cita=%s AND id_doctor=%s",
                   (id, session["doctor_id"]))
    c.commit()
    cursor.close()
    return redirect("/doctor/panel")


@app.route("/doctor/cancelar/<int:id>")
@login_required(role="doctor")
def doctor_cancelar(id):
    c = get_conn()
    cursor = c.cursor()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s AND id_doctor=%s",
                   (id, session["doctor_id"]))
    c.commit()
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
            cursor = get_conn().cursor()
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


@app.route("/doctor/slots/crear", methods=["POST"])
@login_required(role="doctor")
def crear_slot():
    fecha = request.form["fecha"]
    hora  = request.form["hora"]
    if fecha < str(date.today()):
        return redirect("/doctor/panel")
    if not slot_solapado(session["doctor_id"], fecha, hora):
        c = get_conn()
        cursor = c.cursor()
        cursor.execute("INSERT INTO slot(id_doctor,fecha,hora) VALUES(%s,%s,%s)",
                       (session["doctor_id"], fecha, hora))
        c.commit()
        cursor.close()
    return redirect("/doctor/panel")


@app.route("/doctor/slots/eliminar/<int:id>")
@login_required(role="doctor")
def eliminar_slot(id):
    c = get_conn()
    cursor = c.cursor()
    cursor.execute("SELECT id_cita FROM cita WHERE id_slot=%s AND estado='pendiente'", (id,))
    if not cursor.fetchone():
        cursor.execute("DELETE FROM slot WHERE id_slot=%s AND id_doctor=%s",
                       (id, session["doctor_id"]))
        c.commit()
    cursor.close()
    return redirect("/doctor/panel")


# ================================================================
# PACIENTE
# ================================================================
@app.route("/login_paciente", methods=["GET", "POST"])
def login_paciente():
    if request.method == "POST":
        cursor = get_conn().cursor()
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
    if request.method == "POST":
        nombre   = request.form["nombre"]
        apellido = request.form["apellido"]
        correo   = request.form["correo"]
        telefono = request.form["telefono"]
        cedula   = request.form["cedula"]

        if len(nombre) < 3 or not nombre.replace(" ","").isalpha():
            return render_template("registro_paciente.html", mensaje="Nombre inválido", tipo="error")
        if len(apellido) < 3 or not apellido.replace(" ","").isalpha():
            return render_template("registro_paciente.html", mensaje="Apellido inválido", tipo="error")
        if "@" not in correo:
            return render_template("registro_paciente.html", mensaje="Correo inválido", tipo="error")
        if not telefono.isdigit():
            return render_template("registro_paciente.html", mensaje="Teléfono inválido", tipo="error")
        if not cedula.isdigit() or len(cedula) != 10:
            return render_template("registro_paciente.html", mensaje="Cédula inválida (10 dígitos)", tipo="error")

        c = get_conn()
        cursor = c.cursor()
        cursor.execute("SELECT * FROM paciente WHERE correo=%s OR cedula=%s", (correo, cedula))
        if cursor.fetchone():
            cursor.close()
            return render_template("registro_paciente.html", mensaje="Correo o cédula ya registrados", tipo="error")
        cursor.execute("""
            INSERT INTO paciente(nombre,apellido,correo,telefono,cedula)
            VALUES(%s,%s,%s,%s,%s)
        """, (nombre, apellido, correo, telefono, cedula))
        c.commit()
        cursor.close()
        return render_template("registro_paciente.html",
            mensaje="¡Cuenta creada! Ya puedes iniciar sesión.", tipo="success")
    return render_template("registro_paciente.html")


@app.route("/panel_paciente")
@login_required(role="paciente")
def panel_paciente():
    cursor = get_conn().cursor()
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
    c = get_conn()
    cursor = c.cursor()
    cursor.execute("UPDATE slot SET disponible=TRUE WHERE id_slot=(SELECT id_slot FROM cita WHERE id_cita=%s)", (id,))
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s AND id_paciente=%s",
                   (id, session["paciente_id"]))
    c.commit()
    cursor.close()
    return redirect("/panel_paciente")


@app.route("/reservar", methods=["GET", "POST"])
@login_required(role="paciente")
def reservar():
    c = get_conn()
    cursor = c.cursor()
    if request.method == "POST":
        id_slot     = request.form.get("id_slot")
        descripcion = request.form.get("descripcion", "").strip()

        def reload(msg, tipo):
            cursor2 = get_conn().cursor()
            cursor2.execute("""
                SELECT s.id_slot,s.fecha,s.hora,d.nombre,d.apellido,d.especialidad
                FROM slot s JOIN doctor d ON s.id_doctor=d.id_doctor
                WHERE s.disponible=TRUE AND s.fecha>=CURRENT_DATE
                ORDER BY s.fecha,s.hora
            """)
            slots = cursor2.fetchall()
            cursor2.close()
            return render_template("reservar.html", slots=slots, mensaje=msg, tipo=tipo)

        if not id_slot:
            return reload("Selecciona un horario disponible", "error")
        if len(descripcion) < 5:
            return reload("Describe el motivo (mínimo 5 caracteres)", "error")

        cursor.execute("SELECT id_slot,id_doctor FROM slot WHERE id_slot=%s AND disponible=TRUE", (id_slot,))
        slot = cursor.fetchone()
        if not slot:
            cursor.close()
            return reload("Ese horario ya no está disponible", "error")

        cursor.execute("UPDATE slot SET disponible=FALSE WHERE id_slot=%s", (slot[0],))
        cursor.execute("""
            INSERT INTO cita(id_paciente,id_doctor,id_slot,estado,descripcion)
            VALUES(%s,%s,%s,'pendiente',%s)
        """, (session["paciente_id"], slot[1], slot[0], descripcion))
        c.commit()
        cursor.close()
        return render_template("reservar.html", slots=[], mensaje="¡Cita reservada con éxito!", tipo="success")

    cursor.execute("""
        SELECT s.id_slot,s.fecha,s.hora,d.nombre,d.apellido,d.especialidad
        FROM slot s JOIN doctor d ON s.id_doctor=d.id_doctor
        WHERE s.disponible=TRUE AND s.fecha>=CURRENT_DATE
        ORDER BY s.fecha,s.hora
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
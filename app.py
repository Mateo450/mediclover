from flask import Flask, render_template, request, redirect, session
from functools import wraps
import psycopg2
import os
from datetime import date

app = Flask(__name__)
app.secret_key = "Mediclover_19"

ADMIN_USER = "admin"
ADMIN_PASS = "1234"

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
# LOGIN REQUIRED
# ===============================
def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            if role == "admin":
                if session.get("usuario") != ADMIN_USER:
                    return redirect("/login")

            if role == "paciente":
                if "paciente_id" not in session:
                    return redirect("/login_paciente")

            return func(*args, **kwargs)
        return wrapper
    return decorator

# ===============================
# HOME
# ===============================
@app.route("/")
def home():
    return render_template("home.html")

# ===============================
# LOGIN ADMIN
# ===============================
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form["usuario"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session.clear()
            session["usuario"] = ADMIN_USER
            return redirect("/admin")
        else:
            return render_template("login.html", error="Credenciales incorrectas")

    return render_template("login.html")

# ===============================
# LOGIN PACIENTE
# ===============================
@app.route("/login_paciente", methods=["GET","POST"])
def login_paciente():

    if not conn:
        return "Error BD"

    if request.method == "POST":
        cursor = conn.cursor()
        cursor.execute("SELECT id_paciente, nombre FROM paciente WHERE correo=%s",
                       (request.form["correo"],))
        user = cursor.fetchone()
        cursor.close()

        if user:
            session.clear()
            session["paciente_id"] = user[0]
            session["paciente_nombre"] = user[1]
            return redirect("/panel_paciente")
        else:
            return render_template("login_paciente.html", error="Correo no registrado")

    return render_template("login_paciente.html")

# ===============================
# REGISTRO PACIENTE (CON CÉDULA)
# ===============================
@app.route("/registro_paciente", methods=["GET","POST"])
def registro_paciente():

    if not conn:
        return "Error BD"

    if request.method == "POST":
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        correo = request.form["correo"]
        telefono = request.form["telefono"]
        cedula = request.form["cedula"]

        # VALIDACIONES
        if len(nombre) < 3 or not nombre.replace(" ", "").isalpha():
            return render_template("registro_paciente.html", mensaje="Nombre inválido", tipo="error")

        if len(apellido) < 3 or not apellido.replace(" ", "").isalpha():
            return render_template("registro_paciente.html", mensaje="Apellido inválido", tipo="error")

        if "@" not in correo:
            return render_template("registro_paciente.html", mensaje="Correo inválido", tipo="error")

        if not telefono.isdigit():
            return render_template("registro_paciente.html", mensaje="Teléfono inválido", tipo="error")

        if not cedula.isdigit() or len(cedula) != 10:
            return render_template("registro_paciente.html", mensaje="Cédula inválida", tipo="error")

        cursor = conn.cursor()

        cursor.execute("SELECT * FROM paciente WHERE correo=%s OR cedula=%s",(correo, cedula))
        if cursor.fetchone():
            cursor.close()
            return render_template("registro_paciente.html", mensaje="Usuario ya existe", tipo="error")

        cursor.execute("""
        INSERT INTO paciente(nombre,apellido,correo,telefono,cedula)
        VALUES(%s,%s,%s,%s,%s)
        """,(nombre,apellido,correo,telefono,cedula))

        conn.commit()
        cursor.close()

        return render_template("registro_paciente.html", mensaje="Cuenta creada correctamente", tipo="success")

    return render_template("registro_paciente.html")

# ===============================
# PANEL PACIENTE
# ===============================
@app.route("/panel_paciente")
@login_required(role="paciente")
def panel_paciente():

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id_cita, fecha, hora, estado, descripcion
        FROM cita
        WHERE id_paciente=%s
        ORDER BY fecha, hora
    """,(session["paciente_id"],))

    citas = cursor.fetchall()
    cursor.close()

    return render_template("panel_paciente.html", citas=citas)

# ===============================
# CANCELAR CITA PACIENTE
# ===============================
@app.route("/cancelar_cita_paciente/<int:id>")
@login_required(role="paciente")
def cancelar_cita_paciente(id):

    cursor = conn.cursor()
    cursor.execute("""
    UPDATE cita
    SET estado='cancelada'
    WHERE id_cita=%s AND id_paciente=%s
    """,(id, session["paciente_id"]))

    conn.commit()
    cursor.close()

    return redirect("/panel_paciente")

# ===============================
# ADMIN DASHBOARD (FIX)
# ===============================
@app.route("/admin")
@login_required(role="admin")
def admin():

    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM paciente")
    total_pacientes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cita WHERE estado='pendiente'")
    citas_pendientes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cita WHERE fecha = CURRENT_DATE")
    citas_hoy = cursor.fetchone()[0]

    cursor.close()

    return render_template("index.html",
        total_pacientes=total_pacientes,
        citas_pendientes=citas_pendientes,
        citas_hoy=citas_hoy
    )

# ===============================
# PACIENTES ADMIN (FIX ERROR)
# ===============================
@app.route("/pacientes")
@login_required(role="admin")
def pacientes():

    cursor = conn.cursor()
    cursor.execute("""
    SELECT id_paciente,nombre,apellido,correo,telefono,cedula
    FROM paciente
    """)
    pacientes = cursor.fetchall()
    cursor.close()

    return render_template("pacientes.html", pacientes=pacientes)

# ===============================
# CITAS ADMIN
# ===============================
@app.route("/citas")
@login_required(role="admin")
def citas():

    cursor = conn.cursor()
    cursor.execute("""
    SELECT c.id_cita,p.nombre,p.apellido,c.fecha,c.hora,c.estado,c.descripcion
    FROM cita c
    JOIN paciente p ON c.id_paciente = p.id_paciente
    ORDER BY c.fecha,c.hora
    """)
    citas = cursor.fetchall()
    cursor.close()

    return render_template("citas.html", citas=citas)

# ===============================
# LOGOUT
# ===============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ===============================
# RESERVAR (VALIDADO)
# ===============================
@app.route("/reservar", methods=["GET","POST"])
@login_required(role="paciente")
def reservar():

    if request.method == "POST":
        fecha = request.form["fecha"]
        descripcion = request.form["descripcion"]

        if fecha < str(date.today()):
            return render_template("reservar.html", mensaje="Fecha inválida", tipo="error", fecha_hoy=date.today())

        if len(descripcion) < 5:
            return render_template("reservar.html", mensaje="Descripción muy corta", tipo="error", fecha_hoy=date.today())

        cursor = conn.cursor()

        cursor.execute("""
        SELECT * FROM cita
        WHERE fecha=%s AND hora=%s AND estado='pendiente'
        """,(request.form["fecha"], request.form["hora"]))

        if cursor.fetchone():
            cursor.close()
            return render_template("reservar.html", mensaje="Horario ocupado", tipo="error", fecha_hoy=date.today())

        cursor.execute("""
        INSERT INTO cita(id_paciente,fecha,hora,estado,descripcion)
        VALUES(%s,%s,%s,'pendiente',%s)
        """,(session["paciente_id"], request.form["fecha"], request.form["hora"], descripcion))

        conn.commit()
        cursor.close()

        return render_template("reservar.html", mensaje="Cita creada", tipo="success", fecha_hoy=date.today())

    return render_template("reservar.html", fecha_hoy=date.today())

if __name__ == "__main__":
    app.run(debug=True)
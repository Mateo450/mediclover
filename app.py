from flask import Flask, render_template, request, redirect, session
from functools import wraps
import psycopg2
import os

app = Flask(__name__)
app.secret_key = "Mediclover_19"

ADMIN_USER = "admin"
ADMIN_PASS = "1234"

# ===============================
# CONEXIÓN BD SEGURA
# ===============================
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

            if "usuario" not in session:
                return redirect("/login")

            if role == "admin":
                if session.get("usuario") != ADMIN_USER:
                    return redirect("/login")

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
# ADMIN
# ===============================
@app.route("/admin")
@login_required(role="admin")
def index():

    if not conn:
        return "❌ Error de conexión a la base de datos"

    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM paciente")
    total_pacientes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cita WHERE estado='pendiente'")
    citas_pendientes = cursor.fetchone()[0]

    cursor.close()

    return render_template("index.html",
        total_pacientes=total_pacientes,
        citas_pendientes=citas_pendientes
    )

# ===============================
# PACIENTES
# ===============================
@app.route("/pacientes")
@login_required(role="admin")
def pacientes():

    if not conn:
        return "❌ Error de conexión a la base de datos"

    cursor = conn.cursor()

    cursor.execute("""
    SELECT id_paciente,nombre,apellido,correo,telefono,fecha_nacimiento
    FROM paciente
    """)

    pacientes = cursor.fetchall()
    cursor.close()

    return render_template("pacientes.html", pacientes=pacientes)

# ===============================
# EDITAR PACIENTE
# ===============================
@app.route("/editar_paciente/<int:id>", methods=["GET","POST"])
@login_required(role="admin")
def editar_paciente(id):

    if not conn:
        return "❌ Error de conexión a la base de datos"

    cursor = conn.cursor()

    if request.method == "POST":
        cursor.execute("""
        UPDATE paciente
        SET nombre=%s, apellido=%s, correo=%s, telefono=%s, fecha_nacimiento=%s
        WHERE id_paciente=%s
        """,(
            request.form["nombre"],
            request.form["apellido"],
            request.form["correo"],
            request.form["telefono"],
            request.form["fecha_nacimiento"],
            id
        ))

        conn.commit()
        cursor.close()
        return redirect("/pacientes")

    cursor.execute("""
    SELECT nombre,apellido,correo,telefono,fecha_nacimiento
    FROM paciente
    WHERE id_paciente=%s
    """,(id,))

    paciente = cursor.fetchone()
    cursor.close()

    return render_template("editar_paciente.html", paciente=paciente)

# ===============================
# ELIMINAR PACIENTE
# ===============================
@app.route("/eliminar_paciente/<int:id>")
@login_required(role="admin")
def eliminar_paciente(id):

    if not conn:
        return "❌ Error de conexión a la base de datos"

    cursor = conn.cursor()

    cursor.execute("DELETE FROM cita WHERE id_paciente=%s",(id,))
    cursor.execute("DELETE FROM paciente WHERE id_paciente=%s",(id,))

    conn.commit()
    cursor.close()

    return redirect("/pacientes")

# ===============================
# CITAS
# ===============================
@app.route("/citas")
@login_required(role="admin")
def citas():

    if not conn:
        return "❌ Error de conexión a la base de datos"

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
# ACCIONES CITAS
# ===============================
@app.route("/completar_cita/<int:id>")
@login_required(role="admin")
def completar_cita(id):

    if not conn:
        return "❌ Error de conexión a la base de datos"

    cursor = conn.cursor()
    cursor.execute("UPDATE cita SET estado='completada' WHERE id_cita=%s",(id,))
    conn.commit()
    cursor.close()

    return redirect("/citas")

@app.route("/cancelar_cita/<int:id>")
@login_required(role="admin")
def cancelar_cita(id):

    if not conn:
        return "❌ Error de conexión a la base de datos"

    cursor = conn.cursor()
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s",(id,))
    conn.commit()
    cursor.close()

    return redirect("/citas")

# ===============================
# LOGIN
# ===============================
@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":
        if request.form["usuario"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["usuario"] = ADMIN_USER
            return redirect("/admin")
        else:
            return render_template("login.html", error="Credenciales incorrectas")

    return render_template("login.html")

# ===============================
# LOGOUT
# ===============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)
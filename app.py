from flask import Flask, render_template, request, redirect, session
from functools import wraps
import psycopg2
import os

app = Flask(__name__)
app.secret_key = "Mediclover_19"

ADMIN_USER = "admin"
ADMIN_PASS = "1234"

DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode="require")


# ===============================
# LOGIN REQUIRED
# ===============================
def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            if "usuario" not in session and "paciente_id" not in session:
                return redirect("/login")

            if role == "admin":
                if session.get("usuario") != ADMIN_USER:
                    return redirect("/login")

            if role == "paciente":
                if session.get("role") != "paciente":
                    return redirect("/login_paciente")

            return func(*args, **kwargs)
        return wrapper
    return decorator


# ===============================
# HOME (PÁGINA PÚBLICA)
# ===============================
@app.route("/")
def home():
    return render_template("home.html")


# ===============================
# DASHBOARD ADMIN
# ===============================
@app.route("/admin")
@login_required(role="admin")
def index():

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

    cursor = conn.cursor()

    cursor.execute("""
    SELECT id_paciente,nombre,apellido,correo,telefono,fecha_nacimiento
    FROM paciente
    """)

    pacientes = cursor.fetchall()
    cursor.close()

    return render_template("pacientes.html", pacientes=pacientes)


# ===============================
# CITAS
# ===============================
@app.route("/citas")
@login_required(role="admin")
def citas():

    cursor = conn.cursor()
    fecha = request.args.get("fecha")

    if fecha and fecha < "2026-01-01":
        fecha = None

    if fecha:
        cursor.execute("""
        SELECT c.id_cita,p.nombre,p.apellido,c.fecha,c.hora,c.estado,c.descripcion
        FROM cita c
        JOIN paciente p ON c.id_paciente = p.id_paciente
        WHERE c.fecha=%s
        ORDER BY c.fecha,c.hora
        """,(fecha,))
    else:
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
# ACCIONES DE CITAS
# ===============================
@app.route("/completar_cita/<int:id>")
@login_required(role="admin")
def completar_cita(id):

    cursor = conn.cursor()
    cursor.execute("UPDATE cita SET estado='completada' WHERE id_cita=%s",(id,))
    conn.commit()
    cursor.close()

    return redirect("/citas")


@app.route("/cancelar_cita/<int:id>")
@login_required(role="admin")
def cancelar_cita(id):

    cursor = conn.cursor()
    cursor.execute("UPDATE cita SET estado='cancelada' WHERE id_cita=%s",(id,))
    conn.commit()
    cursor.close()

    return redirect("/citas")


# ===============================
# LOGIN ADMIN
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
# LOGIN PACIENTE
# ===============================
@app.route("/login_paciente", methods=["GET","POST"])
def login_paciente():

    if request.method == "POST":

        correo = request.form.get("correo")

        cursor = conn.cursor()
        cursor.execute("""
        SELECT id_paciente,nombre,apellido
        FROM paciente
        WHERE correo=%s
        """,(correo,))

        paciente = cursor.fetchone()
        cursor.close()

        if not paciente:
            return render_template("login_paciente.html", error="Correo no registrado")

        session.clear()
        session["paciente_id"] = paciente[0]
        session["paciente_nombre"] = paciente[1]
        session["paciente_apellido"] = paciente[2]
        session["role"] = "paciente"

        return redirect("/panel_paciente")

    return render_template("login_paciente.html")

# ===============================
# REGISTRO PACIENTE
# ===============================
@app.route("/registro_paciente", methods=["GET","POST"])
def registro_paciente():

    if request.method == "POST":

        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        correo = request.form["correo"]
        telefono = request.form["telefono"]

        cursor = conn.cursor()

        try:
            cursor.execute("""
            INSERT INTO paciente(nombre,apellido,correo,telefono)
            VALUES(%s,%s,%s,%s)
            """,(nombre,apellido,correo,telefono))

            conn.commit()

        except:
            conn.rollback()
            return render_template("registro_paciente.html", error="Correo ya registrado")

        cursor.close()
        return redirect("/login_paciente")

    return render_template("registro_paciente.html")

# ===============================
# PANEL PACIENTE
# ===============================
@app.route("/panel_paciente")
@login_required(role="paciente")
def panel_paciente():

    cursor = conn.cursor()

    cursor.execute("""
    SELECT id_cita,fecha,hora,estado,descripcion
    FROM cita
    WHERE id_paciente=%s
    ORDER BY fecha,hora
    """,(session["paciente_id"],))

    citas = cursor.fetchall()
    cursor.close()

    return render_template("panel_paciente.html", citas=citas)


# ===============================
# RESERVAR
# ===============================
@app.route("/reservar", methods=["GET","POST"])
@login_required(role="paciente")
def reservar():

    mensaje=None
    tipo=None

    if request.method=="POST":

        cursor = conn.cursor()

        cursor.execute("""
        SELECT 1 FROM cita
        WHERE fecha=%s AND hora=%s AND id_paciente=%s
        """,(request.form["fecha"],request.form["hora"],session["paciente_id"]))

        if cursor.fetchone():
            mensaje="Ya tienes una cita en ese horario"
            tipo="error"
        else:
            cursor.execute("""
            INSERT INTO cita(id_paciente,fecha,hora,estado,descripcion)
            VALUES(%s,%s,%s,'pendiente',%s)
            """,(session["paciente_id"],
                request.form["fecha"],
                request.form["hora"],
                request.form["descripcion"]))

            conn.commit()
            mensaje="Cita reservada"
            tipo="success"

        cursor.close()

    return render_template("reservar.html",mensaje=mensaje,tipo=tipo)


# ===============================
# LOGOUT
# ===============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)
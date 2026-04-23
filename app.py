from flask import Flask, render_template, request, redirect, session
from functools import wraps
import psycopg2
import os

app = Flask(__name__)
app.secret_key = "Mediclover_19"

ADMIN_USER = "admin"
ADMIN_PASS = "1234"

# ===============================
# CONEXIÓN BD
# ===============================
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL, sslmode="require")

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
# REGISTRO PACIENTE
# ===============================
@app.route("/registro_paciente", methods=["GET","POST"])
def registro_paciente():

    if request.method == "POST":
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM paciente WHERE correo=%s",
                       (request.form["correo"],))

        if cursor.fetchone():
            cursor.close()
            return render_template("registro_paciente.html",
                                   mensaje="Correo ya registrado",
                                   tipo="error")

        cursor.execute("""
        INSERT INTO paciente(nombre,apellido,correo,telefono)
        VALUES(%s,%s,%s,%s)
        """,(
            request.form["nombre"],
            request.form["apellido"],
            request.form["correo"],
            request.form["telefono"]
        ))

        conn.commit()
        cursor.close()

        return render_template("registro_paciente.html",
                               mensaje="Cuenta creada correctamente",
                               tipo="success")

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
# RESERVAR CITA
# ===============================
@app.route("/reservar", methods=["GET","POST"])
@login_required(role="paciente")
def reservar():

    if request.method == "POST":
        cursor = conn.cursor()

        # evitar doble reserva
        cursor.execute("""
        SELECT * FROM cita
        WHERE fecha=%s AND hora=%s AND estado='pendiente'
        """,(request.form["fecha"], request.form["hora"]))

        if cursor.fetchone():
            cursor.close()
            return render_template("reservar.html",
                                   mensaje="Horario ocupado",
                                   tipo="error")

        cursor.execute("""
        INSERT INTO cita(id_paciente,fecha,hora,estado,descripcion)
        VALUES(%s,%s,%s,'pendiente',%s)
        """,(
            session["paciente_id"],
            request.form["fecha"],
            request.form["hora"],
            request.form["descripcion"]
        ))

        conn.commit()
        cursor.close()

        return render_template("reservar.html",
                               mensaje="Cita reservada correctamente",
                               tipo="success")

    return render_template("reservar.html")

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
    WHERE id_cita=%s AND estado='pendiente'
    """,(id,))
    conn.commit()
    cursor.close()

    return redirect("/panel_paciente")

# ===============================
# ADMIN
# ===============================
@app.route("/admin")
@login_required(role="admin")
def admin():

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
# LOGOUT
# ===============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")
    
if __name__ == "__main__":
    app.run(debug=True)
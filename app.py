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


@app.route("/")
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


# 🔥 NUEVAS RUTAS
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


@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":
        if request.form["usuario"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["usuario"] = ADMIN_USER
            return redirect("/")
        else:
            return render_template("login.html", error="Error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)
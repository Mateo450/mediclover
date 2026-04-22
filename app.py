# ===============================
# 1. IMPORTS
# ===============================
from flask import Flask, render_template, request, redirect, session
from functools import wraps
import psycopg2
import os

# ===============================
# 2. CONFIGURACIÓN
# ===============================
app = Flask(__name__)
app.secret_key = "Mediclover_19"

ADMIN_USER = "admin"
ADMIN_PASS = "1234"

# ===============================
# 3. CONEXIÓN BD
# ===============================
DATABASE_URL = os.getenv("DATABASE_URL")

conn = None
try:
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        print("✅ Conectado a PostgreSQL")
    else:
        print("❌ No existe DATABASE_URL")
except Exception as e:
    print("❌ Error:", e)

# ===============================
# 4. SEGURIDAD
# ===============================
def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):

            if "usuario" not in session and "paciente_id" not in session:
                return redirect("/login")

            if role == "admin" and session.get("usuario") != ADMIN_USER:
                return redirect("/login")

            if role == "paciente" and session.get("role") != "paciente":
                return redirect("/login_paciente")

            return func(*args, **kwargs)
        return wrapper
    return decorator

# ===============================
# 5. DASHBOARD ADMIN
# ===============================
@app.route("/")
@login_required(role="admin")
def index():

    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM paciente")
    total_pacientes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cita WHERE fecha = CURRENT_DATE")
    citas_hoy = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cita WHERE estado='pendiente'")
    citas_pendientes = cursor.fetchone()[0]

    cursor.close()

    return render_template("index.html",
        total_pacientes=total_pacientes,
        citas_hoy=citas_hoy,
        citas_pendientes=citas_pendientes
    )

# ===============================
# 6. REGISTRO PACIENTE
# ===============================
@app.route("/registro", methods=["GET","POST"])
@login_required(role="admin")
def registro():

    if request.method == "POST":

        cursor = conn.cursor()

        try:
            cursor.execute("""
            INSERT INTO paciente(nombre,apellido,correo,telefono,fecha_nacimiento)
            VALUES(%s,%s,%s,%s,%s)
            """,(
                request.form["nombre"],
                request.form["apellido"],
                request.form["correo"],
                request.form["telefono"],
                request.form["fecha_nacimiento"]
            ))

            conn.commit()
        except Exception as e:
            conn.rollback()
            return f"Error: {e}"

        cursor.close()
        return redirect("/pacientes")

    return render_template("registro.html")

# ===============================
# 7. LISTAR PACIENTES
# ===============================
@app.route("/pacientes")
@login_required(role="admin")
def pacientes():

    cursor = conn.cursor()
    buscar = request.args.get("buscar")

    if buscar:
        cursor.execute("""
        SELECT id_paciente,nombre,apellido,correo,telefono,fecha_nacimiento
        FROM paciente
        WHERE nombre ILIKE %s OR apellido ILIKE %s
        """,(f"%{buscar}%",f"%{buscar}%"))
    else:
        cursor.execute("""
        SELECT id_paciente,nombre,apellido,correo,telefono,fecha_nacimiento
        FROM paciente
        """)

    pacientes = cursor.fetchall()
    cursor.close()

    return render_template("pacientes.html",pacientes=pacientes)

# ===============================
# 8. ELIMINAR PACIENTE
# ===============================
@app.route("/eliminar_paciente/<int:id>")
@login_required(role="admin")
def eliminar_paciente(id):

    cursor = conn.cursor()

    cursor.execute("DELETE FROM cita WHERE id_paciente=%s",(id,))
    cursor.execute("DELETE FROM paciente WHERE id_paciente=%s",(id,))

    conn.commit()
    cursor.close()

    return redirect("/pacientes")

# ===============================
# 9. EDITAR PACIENTE
# ===============================
@app.route("/editar_paciente/<int:id>", methods=["GET","POST"])
@login_required(role="admin")
def editar_paciente(id):

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
    FROM paciente WHERE id_paciente=%s
    """,(id,))

    paciente = cursor.fetchone()
    cursor.close()

    return render_template("editar_paciente.html",paciente=paciente)

# ===============================
# 10. CITAS ADMIN
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

    cursor.execute("""
    SELECT p.nombre,p.apellido,c.hora,c.estado
    FROM cita c
    JOIN paciente p ON c.id_paciente = p.id_paciente
    WHERE c.fecha=CURRENT_DATE
    ORDER BY c.hora
    """)
    citas_hoy = cursor.fetchall()

    cursor.close()

    return render_template("citas.html",citas=citas,citas_hoy=citas_hoy)

# ===============================
# 11. EDITAR CITA
# ===============================
@app.route("/editar_cita/<int:id>", methods=["GET","POST"])
@login_required(role="admin")
def editar_cita(id):

    cursor = conn.cursor()

    if request.method == "POST":

        cursor.execute("""
        UPDATE cita
        SET fecha=%s, hora=%s, estado=%s, descripcion=%s
        WHERE id_cita=%s
        """,(
            request.form["fecha"],
            request.form["hora"],
            request.form["estado"],
            request.form["descripcion"],
            id
        ))

        conn.commit()
        cursor.close()
        return redirect("/citas")

    cursor.execute("""
    SELECT id_cita,id_paciente,fecha,hora,descripcion,estado
    FROM cita WHERE id_cita=%s
    """,(id,))

    cita = cursor.fetchone()
    cursor.close()

    return render_template("editar_cita.html",cita=cita)

# ===============================
# 12. LOGIN PACIENTE
# ===============================
@app.route("/login_paciente", methods=["GET","POST"])
def login_paciente():

    if request.method == "POST":

        cursor = conn.cursor()

        cursor.execute("""
        SELECT id_paciente,nombre,apellido
        FROM paciente WHERE correo=%s
        """,(request.form["correo"],))

        paciente = cursor.fetchone()
        cursor.close()

        if not paciente:
            return render_template("login_paciente.html",error="Correo no registrado")

        session.clear()
        session["paciente_id"] = paciente[0]
        session["paciente_nombre"] = paciente[1]
        session["paciente_apellido"] = paciente[2]
        session["role"] = "paciente"

        return redirect("/panel_paciente")

    return render_template("login_paciente.html")

# ===============================
# 13. PANEL PACIENTE (FIX CLAVE)
# ===============================
@app.route("/panel_paciente")
@login_required(role="paciente")
def panel_paciente():

    cursor = conn.cursor()

    cursor.execute("""
    SELECT id_cita, fecha, hora, estado, descripcion
    FROM cita
    WHERE id_paciente=%s
    ORDER BY fecha,hora
    """,(session["paciente_id"],))

    citas = cursor.fetchall()
    cursor.close()

    return render_template("panel_paciente.html",citas=citas)

# ===============================
# 14. RESERVAR
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
# 15. CANCELAR CITA PACIENTE
# ===============================
@app.route("/cancelar_cita_paciente/<int:id>")
@login_required(role="paciente")
def cancelar_cita_paciente(id):

    cursor = conn.cursor()

    cursor.execute("""
    UPDATE cita 
    SET estado='cancelada'
    WHERE id_cita=%s AND id_paciente=%s
    """, (id, session["paciente_id"]))

    conn.commit()
    cursor.close()

    return redirect("/panel_paciente")

# ===============================
# 16. LOGIN ADMIN
# ===============================
@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        if request.form["usuario"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["usuario"] = ADMIN_USER
            return redirect("/")
        else:
            return render_template("login.html",error="Credenciales incorrectas")

    return render_template("login.html")

# ===============================
# 17. LOGOUT
# ===============================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ===============================
# 18. CREAR TABLAS
# ===============================
def crear_tablas():

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS paciente(
    id_paciente SERIAL PRIMARY KEY,
    nombre VARCHAR(50),
    apellido VARCHAR(50),
    correo VARCHAR(100) UNIQUE,
    telefono VARCHAR(20),
    fecha_nacimiento DATE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cita(
    id_cita SERIAL PRIMARY KEY,
    id_paciente INT REFERENCES paciente(id_paciente),
    fecha DATE,
    hora TIME,
    estado VARCHAR(20) DEFAULT 'pendiente',
    descripcion TEXT
    )
    """)

    conn.commit()
    cursor.close()

# ===============================
# 19. EJECUCIÓN
# ===============================
if __name__ == "__main__":

    if conn:
        crear_tablas()

    app.run(debug=True)
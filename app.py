from flask import Flask, render_template, request, redirect, session
import psycopg2
from datetime import date

app = Flask(__name__)
app.secret_key = "Mediclover_19"

# ===============================
# CONFIGURACIÓN LOGIN
# ===============================

ADMIN_USER = "admin"
ADMIN_PASS = "1234"

# ===============================
# CONEXIÓN POSTGRESQL
# ===============================
import os

DATABASE_URL = os.getenv("DATABASE_URL")

conn = None
try:
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        print("Conexión exitosa a PostgreSQL")
    else:
        print("No existe DATABASE_URL")
except Exception as e:
    print("Error conectando:", e)

# ===============================
# INICIO / DASHBOARD
# ===============================

@app.route("/")
def index():

    if "usuario" not in session:
        return redirect("/login")

    if conn is None:
        return "Error de conexión con la base de datos"

    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM paciente")
    total_pacientes = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*) FROM cita
    WHERE fecha = CURRENT_DATE
    """)
    citas_hoy = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*) FROM cita
    WHERE estado='pendiente'
    """)
    citas_pendientes = cursor.fetchone()[0]

    cursor.close()

    return render_template(
        "index.html",
        total_pacientes=total_pacientes,
        citas_hoy=citas_hoy,
        citas_pendientes=citas_pendientes
    )


# ===============================
# REGISTRAR PACIENTE
# ===============================

@app.route("/registro", methods=["GET","POST"])
def registro():

    if request.method == "POST":

        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        correo = request.form["correo"]
        telefono = request.form["telefono"]
        fecha_nacimiento = request.form["fecha_nacimiento"]

        try:

            cursor = conn.cursor()

            cursor.execute("""
            INSERT INTO paciente(nombre,apellido,correo,telefono,fecha_nacimiento)
            VALUES(%s,%s,%s,%s,%s)
            """,(nombre,apellido,correo,telefono,fecha_nacimiento))

            conn.commit()
            cursor.close()

            return render_template("registro.html",
            mensaje="Paciente registrado correctamente",
            tipo="success")

        except Exception as e:

            conn.rollback()

            return render_template("registro.html",
            mensaje=f"Error: {e}",
            tipo="error")

    return render_template("registro.html")


# ===============================
# LISTAR PACIENTES
# ===============================

@app.route("/pacientes")
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
# ELIMINAR PACIENTE
# ===============================

@app.route("/eliminar_paciente/<int:id>")
def eliminar_paciente(id):

    cursor = conn.cursor()

    try:

        cursor.execute("DELETE FROM cita WHERE id_paciente=%s",(id,))
        cursor.execute("DELETE FROM paciente WHERE id_paciente=%s",(id,))

        conn.commit()

    except Exception as e:

        conn.rollback()
        print("Error:",e)

    cursor.close()

    return redirect("/pacientes")


# ===============================
# REGISTRAR CITA
# ===============================

@app.route("/cita", methods=["GET","POST"])
def registrar_cita():

    cursor = conn.cursor()

    mensaje=None
    tipo=None

    if request.method=="POST":

        id_paciente=request.form["id_paciente"]
        fecha=request.form["fecha"]
        hora=request.form["hora"]
        descripcion=request.form["descripcion"]

        try:

            cursor.execute("""
            SELECT 1 FROM cita
            WHERE fecha=%s AND hora=%s
            """,(fecha,hora))

            existe=cursor.fetchone()

            if existe:

                mensaje="Ya existe una cita en esa fecha y hora"
                tipo="error"

            else:

                cursor.execute("""
                INSERT INTO cita(id_paciente,fecha,hora,estado,descripcion)
                VALUES(%s,%s,%s,'pendiente',%s)
                """,(id_paciente,fecha,hora,descripcion))

                conn.commit()

                mensaje="Cita registrada correctamente"
                tipo="success"

        except Exception as e:

            conn.rollback()
            mensaje=f"Error: {e}"
            tipo="error"


    cursor.execute("SELECT id_paciente,nombre,apellido FROM paciente")
    pacientes=cursor.fetchall()

    cursor.close()

    return render_template("cita.html",
    pacientes=pacientes,
    mensaje=mensaje,
    tipo=tipo)


# ===============================
# LISTAR CITAS
# ===============================

@app.route("/citas")
def citas():

    cursor = conn.cursor()

    cursor.execute("""
    SELECT c.id_cita,p.nombre,p.apellido,c.fecha,c.hora,c.estado,c.descripcion
    FROM cita c
    JOIN paciente p ON c.id_paciente = p.id_paciente
    ORDER BY c.fecha,c.hora
    """)

    citas = cursor.fetchall()

    hoy = date.today()

    cursor.execute("""
    SELECT p.nombre,p.apellido,c.hora,c.estado
    FROM cita c
    JOIN paciente p ON c.id_paciente = p.id_paciente
    WHERE c.fecha=%s
    ORDER BY c.hora
    """,(hoy,))

    citas_hoy = cursor.fetchall()

    cursor.close()

    return render_template("citas.html",citas=citas,citas_hoy=citas_hoy)


# ===============================
# COMPLETAR CITA
# ===============================

@app.route("/completar_cita/<int:id>")
def completar_cita(id):

    cursor=conn.cursor()

    cursor.execute("""
    UPDATE cita
    SET estado='completada'
    WHERE id_cita=%s
    """,(id,))

    conn.commit()
    cursor.close()

    return redirect("/citas")


# ===============================
# CANCELAR CITA
# ===============================

@app.route("/cancelar_cita/<int:id>")
def cancelar_cita(id):

    cursor=conn.cursor()

    cursor.execute("""
    UPDATE cita
    SET estado='cancelada'
    WHERE id_cita=%s
    """,(id,))

    conn.commit()
    cursor.close()

    return redirect("/citas")


# ===============================
# ELIMINAR CITA
# ===============================

@app.route("/eliminar_cita/<int:id>")
def eliminar_cita(id):

    cursor=conn.cursor()

    cursor.execute("DELETE FROM cita WHERE id_cita=%s",(id,))

    conn.commit()
    cursor.close()

    return redirect("/citas")

@app.route("/login_paciente", methods=["GET","POST"])
def login_paciente():

    if request.method == "POST":

        correo = request.form["correo"]

        cursor = conn.cursor()
        cursor.execute("SELECT id_paciente,nombre FROM paciente WHERE correo=%s",(correo,))
        paciente = cursor.fetchone()
        cursor.close()

        if paciente:
            session["paciente_id"] = paciente[0]
            session["paciente_nombre"] = paciente[1]
            return redirect("/panel_paciente")
        else:
            return render_template("login_paciente.html", error="Correo no registrado")

    return render_template("login_paciente.html")

@app.route("/panel_paciente")
def panel_paciente():

    if "paciente_id" not in session:
        return redirect("/login_paciente")

    cursor = conn.cursor()

    cursor.execute("""
    SELECT fecha,hora,estado,descripcion
    FROM cita
    WHERE id_paciente=%s
    ORDER BY fecha,hora
    """,(session["paciente_id"],))

    citas = cursor.fetchall()
    cursor.close()

    return render_template("panel_paciente.html", citas=citas)

@app.route("/reservar", methods=["GET","POST"])
def reservar():

    if "paciente_id" not in session:
        return redirect("/login_paciente")

    mensaje=None
    tipo=None

    if request.method=="POST":

        fecha=request.form["fecha"]
        hora=request.form["hora"]
        descripcion=request.form["descripcion"]

        cursor=conn.cursor()

        cursor.execute("""
        SELECT 1 FROM cita WHERE fecha=%s AND hora=%s
        """,(fecha,hora))

        if cursor.fetchone():
            mensaje="Horario ocupado"
            tipo="error"
        else:
            cursor.execute("""
            INSERT INTO cita(id_paciente,fecha,hora,estado,descripcion)
            VALUES(%s,%s,%s,'pendiente',%s)
            """,(session["paciente_id"],fecha,hora,descripcion))

            conn.commit()
            mensaje="Cita reservada"
            tipo="success"

        cursor.close()

    return render_template("reservar.html",mensaje=mensaje,tipo=tipo)


# ===============================
# LOGIN
# ===============================

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        usuario = request.form["usuario"]
        password = request.form["password"]

        if usuario == ADMIN_USER and password == ADMIN_PASS:

            session["usuario"] = usuario
            return redirect("/")

        else:

            return render_template(
                "login.html",
                error="Usuario o contraseña incorrectos"
            )

    return render_template("login.html")


# ===============================
# LOGOUT
# ===============================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ===============================
# CREAR TABLAS
# ===============================

def crear_tablas():

    cursor=conn.cursor()

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

    print("Tablas listas")


# ===============================
# EJECUCIÓN
# ===============================

if __name__ == "__main__":

    if conn:
        crear_tablas()
    else:
        print("No se pudo conectar a la base de datos")

    app.run(debug=True)
import uuid
from saos_project import app
from saos_project.db import get_db
from saos_project.user import search_user
from saos_project.const import ALLOWED_EXTENSIONS

def search_file():
    user=search_user()
    db = get_db()
    if not db:
        return None
    files=[]
    try:
        cur = db.cursor()
        cur.execute("SELECT original_filename, pathname, status FROM files WHERE user_id = %s", (user[0],))
        files = cur.fetchall()
        cur.close()
    except Exception as e:
        error_message = f"Errore durante l'operazione sul database: {e}"
        app.logger.error(error_message)
    return files

def search_files():
    db = get_db()
    if not db:
        return None
    files=[]
    try:
        cur = db.cursor()
        cur.execute("SELECT * FROM files WHERE status = 'approved'", ())
        files = cur.fetchall()
        cur.close()
    except Exception as e:
        error_message = f"Errore durante l'operazione sul database: {e}"
        app.logger.error(error_message)
    return files

def search_pending_files():
    db = get_db()
    if not db:
        return None
    files=[]
    try:
        cur = db.cursor()
        cur.execute("SELECT * FROM files WHERE status = 'pending'", ())
        files = cur.fetchall()
        cur.close()
    except Exception as e:
        error_message = f"Errore durante l'operazione sul database: {e}"
        app.logger.error(error_message)
    return files

def save_file(original_filename, file_path):
    existing_user = search_user()
    db = get_db()
    if not db:
        return None
    try:
        cur = db.cursor()
        cur.execute("INSERT INTO files (pathname, user_id, original_filename) VALUES (%s,%s,%s)", (file_path, existing_user[0], original_filename))
        db.commit()
        cur.close()
        app.logger.info(
            f"Nuovo file inserito con successo nel database")
    except Exception as e:
        error_message = f"Errore durante l'operazione sul database: {e}"
        app.logger.error(error_message)
    return None

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_safe_filename(filename):
    """Genera un nome file sicuro e unico"""
    # Prendi l'estensione originale
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    # Genera un nome file unico con UUID
    return f"{uuid.uuid4()}.{ext}"

def approve_file(file_id):
    db = get_db()
    if not db:
        return None
    try:
        cur = db.cursor()
        cur.execute(
            "UPDATE files SET status = 'approved' WHERE id = %s",
            (file_id,)
        )
        db.commit()
        cur.close()
        return True
    except Exception as e:
        db.rollback()
        print(f"Errore durante l'approvazione del file: {str(e)}")
        return False

def reject_file(file_id):
    db = get_db()
    if not db:
        return None
    try:
        cur = db.cursor()
        cur.execute(
            "UPDATE files SET status = 'rejected' WHERE id = %s",
            (file_id,)
        )
        db.commit()
        cur.close()
        return True
    except Exception as e:
        db.rollback()
        print(f"Errore durante il rifiuto del file: {str(e)}")
        return False
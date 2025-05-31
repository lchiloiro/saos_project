from logging import exception

import psycopg2
from flask import Flask, request, render_template, abort, url_for, session
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, g, redirect
from flask_oidc import OpenIDConnect
import os
import uuid
import jwt
import json
import requests

app = Flask(__name__)

# Configurazione di base di Flask e OpenIDConnect
app.config.update({
    'SECRET_KEY': 'b4e0eb2951455e8af36689fc368a1d3f2dce698a704c11f7be031cd2f9a392cf',
    'OIDC_CLIENT_SECRETS': '/app/client_secrets.json',
    'OIDC_ID_TOKEN_COOKIE_SECURE': False,
    'OIDC_USER_INFO_ENABLED': True,
    'OIDC_OPENID_REALM': 'soi3',
    'OIDC_SCOPES': ['openid', 'email', 'profile'],
    'OIDC_INTROSPECTION_AUTH_METHOD': 'client_secret_post'
})

# Configurazione database PostgreSQL
DB_CONFIG = {
    'dbname': 'postgres',
    'user': 'admin',
    'password': 'admin',
    'host': 'db',
    'port': '5432'
}

def get_db():
    if 'db' not in g:
        try:
            g.db = psycopg2.connect(**DB_CONFIG)
            app.logger.info("Connessione al database stabilita con successo")
        except Exception as e:
            app.logger.error(f"Errore di connessione al database: {e}")
            return None
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
        app.logger.info("Connessione al database chiusa")
    if e is not None:
        app.logger.error(f"Errore durante la chiusura del database: {e}")

oidc = OpenIDConnect(app)

# Configurazioni
UPLOAD_FOLDER = 'uploads'
# Limite dimensione file: 16 MB
MAX_CONTENT_LENGTH = 16 * 1024 * 1024
# Estensioni permesse
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


def get_user_info():
    try:
        # Otteniamo tutte le informazioni disponibili dall'utente
        info = oidc.user_getinfo(['preferred_username', 'email', 'given_name', 'family_name',
                                  'telefono', 'data_nascita', 'indirizzo', 'citta'])
        roles = get_user_roles()

        # Aggiungiamo log per debug
        app.logger.info(f"Info utente ottenute: {info}")
        app.logger.info(f"Ruoli ottenuti: {roles}")

        return {
            'username': info.get('preferred_username', ''),
            'email': info.get('email', ''),
            'nome': info.get('given_name', ''),
            'cognome': info.get('family_name', ''),
            'telefono': info.get('telefono', ''),
            'data_nascita': info.get('data_nascita', ''),
            'indirizzo': info.get('indirizzo', ''),
            'citta': info.get('citta', ''),
            'ruolo': roles[0] if roles else ''
        }
    except Exception as e:
        app.logger.error(f"Errore in get_user_info: {e}")
        return None

def search_user():
    info = oidc.user_getinfo(['preferred_username', 'email', 'sub'])
    sub = info.get('sub')

    if not sub:
        return None
    db = get_db()
    if not db:
        return None
    existing_user=None
    try:
        cur = db.cursor()
        # Verifica se il sub esiste già
        cur.execute("SELECT id FROM users WHERE id_keycloak = %s", (sub,))
        existing_user = cur.fetchone()
        cur.close()
    except Exception as e:
        error_message = f"Errore durante l'operazione sul database: {e}"
        app.logger.error(error_message)
    return existing_user

def get_sub_by_id(id_user):
    db = get_db()
    if not db:
        return None
    try:
        cur = db.cursor()
        cur.execute("SELECT id_keycloak FROM users WHERE id = %s", (id_user,))
        row = cur.fetchone()
        cur.close()
        if row:
            return row[0]
    except Exception as e:
        error_message = f"Errore durante l'operazione sul database: {e}"
        app.logger.error(error_message)
    return None

def insert_user():
    info = oidc.user_getinfo(['preferred_username', 'email', 'sub'])
    sub = info.get('sub')
    user = search_user()
    db = get_db()
    if not db:
        return None
    try:
        if not user:
            cur = db.cursor()
            cur.execute("INSERT INTO users (id_keycloak) VALUES (%s)", (sub,))
            db.commit()
            cur.close()
            app.logger.info(f"Nuovo utente inserito con successo nel database: {info.get('preferred_username')}")
        else:
            app.logger.info(f"Utente già presente nel database con sub: {sub}")
    except Exception as e:
        error_message = f"Errore durante l'operazione sul database: {e}"
        app.logger.error(error_message)
        db.rollback()
        return jsonify({
            'message': 'Errore durante l\'accesso al database',
            'error': error_message
        }), 500
    app.logger.info(f"Accesso protetto completato con successo per l'utente: {info.get('preferred_username')}")

    return get_user_info()

def search_file():
    user=search_user()
    db = get_db()
    if not db:
        return None
    files=[]
    try:
        cur = db.cursor()
        cur.execute("SELECT original_filename FROM files WHERE user_id = %s", (user[0],))
        files = cur.fetchall()
        cur.close()
    except Exception as e:
        error_message = f"Errore durante l'operazione sul database: {e}"
        app.logger.error(error_message)
    return files

def load_keycloak_config(path='app/client_secrets.json'):
    with open(path) as f:
        config = json.load(f)
    return config['web']

def get_admin_token():
    config = load_keycloak_config()

    token_url = config['token_uri']
    client_id = config['client_id']
    client_secret = config['client_secret']

    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }

    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        raise Exception(f"Token request failed: {response.status_code} {response.text}")

    return response.json()['access_token']


def get_user_by_sub(sub_id):
    token = get_admin_token()
    config = load_keycloak_config()

    issuer_url = config['issuer']
    admin_base = issuer_url.replace('/realms/', '/admin/realms/')
    user_url = f"{admin_base}/users/{sub_id}"

    headers = {'Authorization': f'Bearer {token}'}

    response = requests.get(user_url, headers=headers)
    if response.status_code == 200:
        user = response.json()
        app.logger.info(f"Dati utente ricevuti da Keycloak: {user}")  # Log dei dati ricevuti

        # Controlliamo anche altri possibili campi per nome e cognome
        firstName = user.get('firstName') or user.get('given_name') or user.get('givenName')
        lastName = user.get('lastName') or user.get('family_name') or user.get('familyName')

        app.logger.info(f"Nome: {firstName}, Cognome: {lastName}")  # Log dei valori estratti

        return {
            'firstName': firstName,
            'lastName': lastName
        }
    elif response.status_code == 404:
        app.logger.error(f"Utente con sub {sub_id} non trovato in Keycloak")
        return None
    else:
        app.logger.error(f"Errore nella chiamata a Keycloak: {response.status_code} {response.text}")
        raise Exception(f"User lookup failed: {response.status_code} {response.text}")

def search_files():
    db = get_db()
    if not db:
        return None
    files=[]
    try:
        cur = db.cursor()
        cur.execute("SELECT * FROM files", ())
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

# Assicurati che la cartella uploads esista
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_user_roles():
    access_token = oidc.get_access_token()
    decoded = jwt.decode(access_token, options={"verify_signature": False})
    roles = decoded.get('realm_access', {}).get('roles', [])
    # Filtra solo i ruoli permessi
    roles = [role for role in roles if role in ("Viewer", "Editor", "Admin")]
    return roles

@app.route('/')
@oidc.require_login
def home():
    files = search_file()
    info = oidc.user_getinfo(['preferred_username', 'email', 'sub'])
    roles = get_user_roles()
    session['user_roles'] = roles
    return render_template('index.html', files=files)

@app.route('/upload', methods=['POST'])
@oidc.require_login
def upload_file():
    try:
        # Verifica se la richiesta contiene un file
        if 'file' not in request.files:
            return 'Nessun file selezionato', 400

        file = request.files['file']

        # Se l'utente non seleziona un file, il browser invia
        # una parte vuota senza filename
        if file.filename == '':
            return 'Nessun file selezionato', 400

        # Verifica se il file ha un'estensione permessa
        if not allowed_file(file.filename):
            return f'Tipo di file non permesso. Estensioni consentite: {", ".join(ALLOWED_EXTENSIONS)}', 400

        if file:
            # Crea un nome file sicuro
            original_filename = secure_filename(file.filename)
            safe_filename = generate_safe_filename(original_filename)

            # Salva il file
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
            file.save(file_path)

            # Verifica che il file sia stato effettivamente salvato
            if not os.path.exists(file_path):
                return 'Errore durante il salvataggio del file', 500

            save_file(original_filename, file_path)

        return {
            'message': 'File caricato con successo',
            'original_name': original_filename,
            'saved_as': safe_filename
        }
    except Exception as e:
        print(f"Errore durante l'upload del file: {str(e)}")
        return 'Si è verificato un errore durante il caricamento del file'

# Gestione dell'errore per file troppo grandi
@app.errorhandler(413)
def too_large(e):
    return f'File troppo grande. Dimensione massima: {MAX_CONTENT_LENGTH/1024/1024}MB', 413

@app.route('/protected')
@oidc.require_login
def protected():
    insert_user()
    user_info = get_user_info()
    return render_template('user.html', user=user_info)

@app.route('/doc')
@oidc.require_login
def doc():
    files = search_files()
    files_with_users = []

    for file in files:
        id_user = file[2]
        sub = get_sub_by_id(id_user)
        user_info = get_user_by_sub(sub) if sub else None

        files_with_users.append({
            'file_info': file,
            'user': user_info
        })

    return render_template('doc.html', files=files_with_users)

@app.route('/login')
def login():
    return oidc.redirect_to_auth_server(request.args.get('next', '/'))

@app.route('/logout')
def logout():
    pass

def main():
    app.run(debug=True)
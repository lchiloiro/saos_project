from logging import exception

import psycopg2
from flask import Flask, request, render_template, abort, url_for, session
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, g, redirect
from flask_oidc import OpenIDConnect
import os
import uuid

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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
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

            return {
                'message': 'File caricato con successo',
                'original_name': original_filename,
                'saved_as': safe_filename
            }

    except Exception as e:
        # Log dell'errore (in un ambiente di produzione dovresti usare un logger appropriato)
        print(f"Errore durante l'upload del file: {str(e)}")
        return 'Si è verificato un errore durante il caricamento del file', 500

# Gestione dell'errore per file troppo grandi
@app.errorhandler(413)
def too_large(e):
    return f'File troppo grande. Dimensione massima: {MAX_CONTENT_LENGTH/1024/1024}MB', 413


# Route protetta che richiede autenticazione
#@app.route('/protected')
#@oidc.require_login
#def protected():
    #info = oidc.user_getinfo(['preferred_username', 'email', 'sub'])
    #return jsonify({
        #'message': 'Accesso protetto riuscito!',
        #'username': info.get('preferred_username'),
        #'sub': info.get('sub'),
        #'email': info.get('email')
    #})

@app.route('/protected')
@oidc.require_login
def protected():
    info = oidc.user_getinfo(['preferred_username', 'email', 'sub'])
    sub = info.get('sub')

    app.logger.info(f"Accesso alla route protetta da utente con sub: {sub}")

    if sub:
        db = get_db()
        if db:
            try:
                cur = db.cursor()

                # Verifica se il sub esiste già
                cur.execute("SELECT id_keycloak FROM users WHERE id_keycloak = %s", sub)
                existing_user = cur.fetchone()

                # Se il sub non esiste, lo inserisce
                if not existing_user:
                    app.logger.info(f"Nuovo utente rilevato con sub: {sub}. Procedendo con l'inserimento nel database")
                    cur.execute("INSERT INTO users (id_keycloak) VALUES (%s)",sub)
                    db.commit()
                    app.logger.info(f"Nuovo utente inserito con successo nel database: {info.get('preferred_username')}")
                else:
                    app.logger.info(f"Utente già presente nel database con sub: {sub}")

                cur.close()

            except Exception as e:
                error_message = f"Errore durante l'operazione sul database: {e}"
                app.logger.error(error_message)
                db.rollback()
                return jsonify({
                    'message': 'Errore durante l\'accesso al database',
                    'error': error_message
                }), 500
    else:
        app.logger.error("Nessun sub ricevuto dall'autenticazione")
        return jsonify({
            'message': 'Errore: sub non trovato',
        }), 400

    app.logger.info(f"Accesso protetto completato con successo per l'utente: {info.get('preferred_username')}")
    return jsonify({
        'message': 'Accesso protetto riuscito!',
        'username': info.get('preferred_username'),
        'sub': sub,
        'email': info.get('email')
    })



@app.route('/login')
def login():
    return oidc.redirect_to_auth_server(request.args.get('next', '/'))

@app.route('/logout')
def logout():
    pass

def main():
    app.run(debug=True)
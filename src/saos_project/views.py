from saos_project import app, oidc
from saos_project.const import ALLOWED_EXTENSIONS, MAX_CONTENT_LENGTH
from flask import render_template, request, send_from_directory, abort, session
from werkzeug.utils import secure_filename
from saos_project.user import get_user_info, insert_user, get_user_roles, get_sub_by_id, get_users_and_files, get_user_by_sub
from saos_project.file import search_file, save_file, allowed_file, generate_safe_filename, search_files
import os

# Gestione dell'errore per file troppo grandi
@app.errorhandler(413)
def too_large(e):
    return f'File troppo grande. Dimensione massima: {MAX_CONTENT_LENGTH/1024/1024}MB', 413
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

@app.route('/admin')
@oidc.require_login
def admin():
    # Verifica se l'utente ha il ruolo di Admin
    roles = get_user_roles()
    if 'Admin' not in roles:
        abort(403)

    users_files = get_users_and_files()
    return render_template('admin.html', users_files=users_files)

@app.route('/uploads/<filename>')
@oidc.require_login
def uploaded_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        app.logger.error(f"Errore durante il recupero del file: {e}")
        abort(404)

@app.route('/login')
def login():
    return oidc.redirect_to_auth_server(request.args.get('next', '/'))

@app.route('/logout')
def logout():
    pass
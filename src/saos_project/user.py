import json
from itertools import groupby
import requests
from saos_project import app, oidc
from saos_project.db import get_db
from flask import jsonify
import jwt

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
            'ruolo': roles[0] if roles else None
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
    roles_url = f"{user_url}/role-mappings/realm"

    headers = {'Authorization': f'Bearer {token}'}
    VALID_ROLES = {'admin', 'viewer', 'editor'}

    # Ottieni informazioni base dell'utente
    response = requests.get(user_url, headers=headers)
    if response.status_code == 200:
        user = response.json()
        app.logger.info(f"Dati raw utente da Keycloak: {user}")  # Log per debug

        # Proviamo diversi campi possibili per lo username
        username = (user.get('username') or
                    user.get('preferred_username') or
                    user.get('userName') or
                    user.get('user_name') or
                    '')

        app.logger.info(f"Username trovato: {username}")  # Log per debug

        # Ottieni i ruoli
        roles = []
        roles_response = requests.get(roles_url, headers=headers)
        if roles_response.status_code == 200:
            raw_roles = roles_response.json()
            all_roles = [role.get('name', '').lower() for role in raw_roles]
            roles = [role for role in all_roles if role in VALID_ROLES]

        user_info = {
            'username': username,
            'email': user.get('email', ''),
            'nome': user.get('firstName', '') or user.get('given_name', ''),
            'cognome': user.get('lastName', '') or user.get('family_name', ''),
            'telefono': user.get('telefono', ''),
            'data_nascita': user.get('data_nascita', ''),
            'indirizzo': user.get('indirizzo', ''),
            'citta': user.get('citta', ''),
            'roles': roles
        }

        app.logger.info(f"Informazioni utente complete: {user_info}")  # Log per debug
        return user_info
    elif response.status_code == 404:
        app.logger.error(f"Utente con sub {sub_id} non trovato in Keycloak")
        return None
    else:
        app.logger.error(f"Errore nella chiamata a Keycloak: {response.status_code} {response.text}")
        raise Exception(f"User lookup failed: {response.status_code} {response.text}")

def get_user_roles():
    access_token = oidc.get_access_token()
    decoded = jwt.decode(access_token, options={"verify_signature": False})
    roles = decoded.get('realm_access', {}).get('roles', [])
    # Filtra solo i ruoli permessi
    roles = [role for role in roles if role in ("Viewer", "Editor", "Admin")]
    return roles

def get_users_and_files():
    db = get_db()
    if not db:
        return None
    users_files = []
    try:
        cur = db.cursor()
        cur.execute("""
                    SELECT u.id, u.id_keycloak, f.original_filename, f.pathname, f.status
                    FROM users u
                             LEFT JOIN files f ON u.id = f.user_id
                    ORDER BY u.id
                    """)
        results = cur.fetchall()
        cur.close()

        # Raggruppa per user_id
        for user_id, group in groupby(results, key=lambda x: x[0]):
            group_list = list(group)
            id_keycloak = group_list[0][1]

            # Ottieni informazioni utente da Keycloak
            user_info = get_user_by_sub(id_keycloak)

            files = [
                {'filename': row[2], 'pathname': row[3], 'status': row[4]}
                for row in group_list
                if row[2] and row[3] and row[4]
            ]

            users_files.append({
                'user_id': user_id,
                'user_info': user_info,
                'files': files
            })

    except Exception as e:
        error_message = f"Errore durante l'operazione sul database: {e}"
        app.logger.error(error_message)
        return None

    return users_files
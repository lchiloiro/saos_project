import psycopg2
from saos_project import app
from saos_project import DB_CONFIG
from flask import g

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
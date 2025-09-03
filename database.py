import sqlite3

DATABASE_FILE = "bot_database.db"

def get_db_connection():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row # Permite acessar colunas pelo nome
    return conn

def init_db():
    """Inicializa o banco de dados e cria as tabelas se não existirem."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela para guardar os templates de eventos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS templates (
        template_name TEXT NOT NULL,
        role_name TEXT NOT NULL,
        emoji TEXT NOT NULL,
        role_limit INTEGER NOT NULL,
        PRIMARY KEY (template_name, emoji)
    )
    ''')

    # Tabela para rastrear os eventos ativos criados pelo bot
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS active_events (
        message_id INTEGER PRIMARY KEY,
        channel_id INTEGER NOT NULL,
        guild_id INTEGER NOT NULL,
        template_name TEXT NOT NULL,
        FOREIGN KEY (template_name) REFERENCES templates (template_name)
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Banco de dados inicializado.")

# --- Funções para gerenciar Templates ---

def get_template_roles(template_name):
    """Busca todas as roles de um template específico."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role_name, emoji, role_limit FROM templates WHERE template_name = ?", (template_name,))
    roles = cursor.fetchall()
    conn.close()
    return roles

def get_all_template_names():
    """Retorna uma lista com os nomes de todos os templates."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT template_name FROM templates")
    templates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return templates

# --- Funções para gerenciar Eventos Ativos ---

def add_active_event(message_id, channel_id, guild_id, template_name):
    """Adiciona um novo evento ativo ao banco de dados."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO active_events (message_id, channel_id, guild_id, template_name) VALUES (?, ?, ?, ?)",
                   (message_id, channel_id, guild_id, template_name))
    conn.commit()
    conn.close()

def get_event_details(message_id):
    """Busca os detalhes de um evento ativo pelo ID da mensagem."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_events WHERE message_id = ?", (message_id,))
    event = cursor.fetchone()
    conn.close()
    return event
    
def populate_initial_data():
    """Insere os dados iniciais dos templates no banco de dados se ele estiver vazio."""
    TEMPLATES_INICIAIS = {
        "raid": {
            "roles": {
                "🛡️": {"nome": "Tanque", "limite": 1},
                "➕": {"nome": "Healer", "limite": 1},
                "⚔️": {"nome": "DPS", "limite": 3},
                "❓": {"nome": "Reserva", "limite": 5}
            }
        },
        "dungeon": {
            "roles": {
                "🛡️": {"nome": "Tanque", "limite": 1},
                "➕": {"nome": "Healer", "limite": 1},
                "⚔️": {"nome": "DPS", "limite": 3}
            }
        }
    }

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM templates")
    if cursor.fetchone()[0] > 0:
        print("O banco de dados de templates já está populado.")
        conn.close()
        return

    print("Populando o banco de dados de templates com dados iniciais...")
    for template_name, data in TEMPLATES_INICIAIS.items():
        for emoji, role_info in data["roles"].items():
            cursor.execute("INSERT INTO templates (template_name, role_name, emoji, role_limit) VALUES (?, ?, ?, ?)",
                           (template_name, role_info["nome"], emoji, role_info["limite"]))
    
    conn.commit()
    conn.close()
    print("Templates iniciais inseridos com sucesso.")

# Para rodar este script diretamente e popular o banco
if __name__ == '__main__':
    init_db()
    populate_initial_data()
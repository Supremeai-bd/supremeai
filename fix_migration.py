import re

file_path = 'backend/alembic_migrations/versions/j9k0l1m2n3o4_add_missing_live_model_tables.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('from sqlalchemy.dialects import postgresql', 'from sqlalchemy.dialects import postgresql\nfrom sqlalchemy.engine.reflection import Inspector')

upgrade_start = '''def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn.engine) if hasattr(conn, 'engine') else Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()'''

content = content.replace('def upgrade():\n    conn = op.get_bind()', upgrade_start)

def replacer(match):
    table_name = match.group(1)
    return f'    if \"{table_name}\" not in existing_tables:\n        op.create_table(\n            \"{table_name}\"'

content = re.sub(r'    op\.create_table\(\n        \"([^\"\n]+)\"', replacer, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

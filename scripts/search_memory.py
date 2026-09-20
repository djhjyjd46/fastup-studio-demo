import os
import re
import sys
import sqlite3
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(repo, 'scripts', 'memory_index.db')

def parse_markdown_chunks(filepath, rel_path):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return []

    lines = content.splitlines()
    if not lines:
        return []

    # Extract frontmatter if present
    tags = ""
    date = ""
    if content.startswith('---'):
        fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            t_match = re.search(r'tags:\s*\[(.*?)\]', fm_text)
            if t_match: tags = t_match.group(1)
            d_match = re.search(r'date:\s*(\d{4}-\d{2}-\d{2})', fm_text)
            if d_match: date = d_match.group(1)

    chunks = []
    current_header = os.path.basename(rel_path)
    current_lines = []
    start_line = 1

    for idx, line in enumerate(lines, 1):
        if line.startswith('#'):
            if current_lines:
                chunk_text = "\n".join(current_lines).strip()
                if len(chunk_text) > 30:
                    chunks.append({
                        'rel_path': rel_path,
                        'header': current_header,
                        'start_line': start_line,
                        'end_line': idx - 1,
                        'tags': tags,
                        'date': date,
                        'content': chunk_text
                    })
                current_lines = []
            current_header = line.strip('#').strip()
            start_line = idx
        current_lines.append(line)

    if current_lines:
        chunk_text = "\n".join(current_lines).strip()
        if len(chunk_text) > 30:
            chunks.append({
                'rel_path': rel_path,
                'header': current_header,
                'start_line': start_line,
                'end_line': len(lines),
                'tags': tags,
                'date': date,
                'content': chunk_text
            })

    return chunks

def build_index():
    print("Building memory index database...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS memory_chunks")
    cur.execute("DROP TABLE IF EXISTS memory_fts")

    cur.execute("""
    CREATE TABLE memory_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        header TEXT,
        start_line INTEGER,
        end_line INTEGER,
        tags TEXT,
        date TEXT,
        content TEXT
    )
    """)

    cur.execute("""
    CREATE VIRTUAL TABLE memory_fts USING fts5(
        file_path,
        header,
        tags,
        content,
        content='memory_chunks',
        content_rowid='id'
    )
    """)

    all_chunks = []
    for root, dirs, files in os.walk(repo):
        # Каталоги с сырыми данными третьих лиц и мусором сессий в индекс не берём.
        # leads_by_1000/ и leads_test/ — списки обзвона с реальными телефонами компаний
        # (см. .gitignore и CLAUDE.md про сырые персональные данные): до 2026-09-05 они
        # давали 1333 чанка из 8063, то есть каждый шестой результат поиска по памяти был
        # куском телефонной базы. scratch/ и .backups/ — временные файлы, не память.
        skip_dirs = ['.git', 'node_modules', '__pycache__', '.venv', 'live-pages',
                     'leads_by_1000', 'leads_test', 'scratch', '.backups']
        for d in skip_dirs:
            if d in dirs: dirs.remove(d)
        for f in files:
            if f.endswith('.md') or f.endswith('.txt'):
                filepath = os.path.join(root, f)
                rel = os.path.relpath(filepath, repo)
                chunks = parse_markdown_chunks(filepath, rel)
                all_chunks.extend(chunks)

    for c in all_chunks:
        cur.execute("""
        INSERT INTO memory_chunks (file_path, header, start_line, end_line, tags, date, content)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (c['rel_path'], c['header'], c['start_line'], c['end_line'], c['tags'], c['date'], c['content']))
        
        rowid = cur.lastrowid
        cur.execute("""
        INSERT INTO memory_fts (rowid, file_path, header, tags, content)
        VALUES (?, ?, ?, ?, ?)
        """, (rowid, c['rel_path'], c['header'], c['tags'], c['content']))

    conn.commit()
    print(f"Indexed {len(all_chunks)} markdown chunks across repository!")
    conn.close()

def search_memory(query, limit=5):
    if not os.path.exists(db_path):
        build_index()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Sanitize FTS query
    clean_query = ' '.join(re.findall(r'\w+', query))
    if not clean_query:
        print("Empty query.")
        return

    sql = """
    SELECT c.file_path, c.header, c.start_line, c.end_line, c.content, rank
    FROM memory_fts f
    JOIN memory_chunks c ON f.rowid = c.id
    WHERE memory_fts MATCH ?
    ORDER BY rank
    LIMIT ?
    """

    try:
        cur.execute(sql, (clean_query, limit))
        results = cur.fetchall()
    except Exception as e:
        # Fallback to LIKE
        cur.execute("""
        SELECT file_path, header, start_line, end_line, content, 0
        FROM memory_chunks
        WHERE content LIKE ? OR header LIKE ?
        LIMIT ?
        """, (f"%{query}%", f"%{query}%", limit))
        results = cur.fetchall()

    print(f"\nSearch results for '{query}' (Found: {len(results)}):\n" + "="*60)
    for r in results:
        file_p, header, s_line, e_line, content, score = r
        snippet = content[:300].replace('\n', ' ')
        print(f"\n📄 [{file_p}: L{s_line}-L{e_line}] — {header}")
        print(f"   {snippet}...")

    conn.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--reindex':
            build_index()
        else:
            search_memory(" ".join(sys.argv[1:]))
    else:
        build_index()

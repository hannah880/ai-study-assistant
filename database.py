import sqlite3
import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_NAME = BASE_DIR / "study_assistant.db"


def connect():

    connection = sqlite3.connect(
        DATABASE_NAME
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def create_tables():

    connection = connect()
    cursor = connection.cursor()

    # -------------------------
    # Quiz results
    # -------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            percentage REAL NOT NULL,
            completed_at TEXT NOT NULL
        )
    """)

    # -------------------------
    # Uploaded documents
    # -------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            uploaded_at TEXT NOT NULL
        )
    """)

    # -------------------------
    # Document chunks
    # -------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding TEXT NOT NULL,

            FOREIGN KEY (document_id)
                REFERENCES documents(id)
                ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()


# -------------------------
# Quiz results
# -------------------------

def save_quiz_result(
        topic,
        score,
        total,
        percentage
):

    connection = connect()
    cursor = connection.cursor()

    completed_at = (
        datetime.now().isoformat()
    )

    cursor.execute("""
        INSERT INTO quiz_results (
            topic,
            score,
            total,
            percentage,
            completed_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        topic,
        score,
        total,
        percentage,
        completed_at
    ))

    connection.commit()
    connection.close()


def get_quiz_results():

    connection = connect()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            topic,
            score,
            total,
            percentage,
            completed_at
        FROM quiz_results
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()

    connection.close()

    results = []

    for row in rows:

        results.append({
            "id": row[0],
            "topic": row[1],
            "score": row[2],
            "total": row[3],
            "percentage": row[4],
            "completed_at": row[5]
        })

    return results


# -------------------------
# Save uploaded document
# -------------------------

def save_document(
        filename,
        chunks,
        embeddings
):

    if len(chunks) != len(embeddings):

        raise ValueError(
            "Each document chunk must have an embedding."
        )

    connection = connect()
    cursor = connection.cursor()

    try:

        uploaded_at = (
            datetime.now().isoformat()
        )

        cursor.execute("""
            INSERT INTO documents (
                filename,
                uploaded_at
            )
            VALUES (?, ?)
        """, (
            filename,
            uploaded_at
        ))

        document_id = (
            cursor.lastrowid
        )

        for index, (
                chunk,
                embedding
        ) in enumerate(
            zip(chunks, embeddings)
        ):

            embedding_json = (
                json.dumps(
                    list(embedding)
                )
            )

            cursor.execute("""
                INSERT INTO document_chunks (
                    document_id,
                    chunk_index,
                    chunk_text,
                    embedding
                )
                VALUES (?, ?, ?, ?)
            """, (
                document_id,
                index,
                chunk,
                embedding_json
            ))

        connection.commit()

        return True

    except sqlite3.IntegrityError:

        connection.rollback()

        return False

    finally:

        connection.close()


# -------------------------
# Load saved documents
# -------------------------

def get_saved_documents():

    connection = connect()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            filename,
            uploaded_at
        FROM documents
        ORDER BY id
    """)

    rows = cursor.fetchall()

    connection.close()

    documents = []

    for row in rows:

        documents.append({
            "id": row[0],
            "filename": row[1],
            "uploaded_at": row[2]
        })

    return documents


def get_saved_document_chunks():

    connection = connect()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            documents.filename,
            document_chunks.chunk_text,
            document_chunks.embedding
        FROM document_chunks

        JOIN documents
        ON document_chunks.document_id
           = documents.id

        ORDER BY
            documents.id,
            document_chunks.chunk_index
    """)

    rows = cursor.fetchall()

    connection.close()

    saved_chunks = []

    for row in rows:

        saved_chunks.append({
            "filename": row[0],
            "chunk": row[1],
            "embedding": json.loads(
                row[2]
            )
        })

    return saved_chunks
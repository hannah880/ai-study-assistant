import sqlite3
from datetime import datetime


DATABASE_NAME = "study_assistant.db"


def connect():
    return sqlite3.connect(DATABASE_NAME)


def create_tables():

    connection = connect()
    cursor = connection.cursor()

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

    connection.commit()
    connection.close()


def save_quiz_result(topic, score, total, percentage):

    connection = connect()
    cursor = connection.cursor()

    completed_at = datetime.now().isoformat()

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
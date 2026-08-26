from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel, Field
from ollama import Client
from pypdf import PdfReader
from io import BytesIO
import math

from database import (
    create_tables,
    save_quiz_result,
    get_quiz_results
)


app = FastAPI()

client = Client(host="http://localhost:11434")


# Create database tables when the app starts
create_tables()


# Stores information from uploaded PDFs
uploaded_chunks = []
chunk_embeddings = []
chunk_sources = []
uploaded_documents = []

# Stores the most recently generated quiz
latest_quiz = None


# -------------------------
# Request / response models
# -------------------------

class QuestionRequest(BaseModel):
    question: str


class QuizRequest(BaseModel):
    topic: str
    number_of_questions: int = Field(
        default=5,
        ge=1,
        le=10
    )


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_answer: str
    explanation: str


class QuizResponse(BaseModel):
    topic: str
    questions: list[QuizQuestion]


class QuizSubmission(BaseModel):
    answers: list[str]


class FlashcardRequest(BaseModel):
    topic: str
    number_of_flashcards: int = Field(
        default=5,
        ge=1,
        le=15
    )


class Flashcard(BaseModel):
    front: str
    back: str


class FlashcardResponse(BaseModel):
    topic: str
    flashcards: list[Flashcard]


# -------------------------
# Home
# -------------------------

@app.get("/")
def home():

    return {
        "message": "AI Study Assistant backend is running"
    }


# -------------------------
# Helper functions
# -------------------------

def split_text(
        text,
        chunk_size=500,
        overlap=50
):

    words = text.split()

    chunks = []
    start = 0

    while start < len(words):

        end = start + chunk_size

        chunk = " ".join(
            words[start:end]
        )

        chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def cosine_similarity(
        vector1,
        vector2
):

    dot_product = sum(
        a * b
        for a, b in zip(
            vector1,
            vector2
        )
    )

    magnitude1 = math.sqrt(
        sum(
            a * a
            for a in vector1
        )
    )

    magnitude2 = math.sqrt(
        sum(
            b * b
            for b in vector2
        )
    )

    if magnitude1 == 0 or magnitude2 == 0:
        return 0

    return dot_product / (
            magnitude1 * magnitude2
    )


# -------------------------
# Upload PDFs
# -------------------------

@app.post("/upload")
async def upload_pdf(
        file: UploadFile = File(...)
):

    if not file.filename:

        return {
            "error": "Please upload a PDF file."
        }

    if not file.filename.lower().endswith(".pdf"):

        return {
            "error": "Please upload a PDF file."
        }

    if file.filename in uploaded_documents:

        return {
            "error": (
                "This document has already "
                "been uploaded."
            )
        }

    contents = await file.read()

    reader = PdfReader(
        BytesIO(contents)
    )

    text = ""

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:

            text += (
                    page_text + "\n"
            )

    if not text.strip():

        return {
            "error": (
                "No text could be extracted "
                "from this PDF."
            )
        }

    # Split document into chunks
    new_chunks = split_text(
        text
    )

    # Generate embeddings
    embedding_response = client.embed(
        model="embeddinggemma",
        input=new_chunks
    )

    new_embeddings = (
        embedding_response.embeddings
    )

    # Store chunks
    uploaded_chunks.extend(
        new_chunks
    )

    # Store embeddings
    chunk_embeddings.extend(
        new_embeddings
    )

    # Remember which PDF each chunk came from
    for chunk in new_chunks:

        chunk_sources.append(
            file.filename
        )

    uploaded_documents.append(
        file.filename
    )

    return {
        "filename": file.filename,
        "characters_extracted": len(text),
        "chunks_created": len(new_chunks),
        "documents_loaded": len(
            uploaded_documents
        ),
        "message": (
            "PDF processed and "
            "added successfully."
        )
    }


# -------------------------
# View uploaded documents
# -------------------------

@app.get("/documents")
def get_documents():

    return {
        "documents": uploaded_documents,
        "total_documents": len(
            uploaded_documents
        ),
        "total_chunks": len(
            uploaded_chunks
        )
    }


# -------------------------
# Ask questions using RAG
# -------------------------

@app.post("/ask")
def ask_question(
        request: QuestionRequest
):

    if not uploaded_chunks:

        return {
            "error": (
                "Please upload your study notes "
                "before asking a question."
            )
        }

    # Generate embedding for the question
    question_response = client.embed(
        model="embeddinggemma",
        input=request.question
    )

    question_embedding = (
        question_response.embeddings[0]
    )

    similarities = []

    # Compare question with document chunks
    for index, embedding in enumerate(
            chunk_embeddings
    ):

        score = cosine_similarity(
            question_embedding,
            embedding
        )

        similarities.append(
            (
                score,
                index
            )
        )

    # Highest similarity first
    similarities.sort(
        reverse=True
    )

    # Retrieve top 4 chunks
    top_results = (
        similarities[:4]
    )

    context_parts = []
    sources = []

    for score, index in top_results:

        source = (
            chunk_sources[index]
        )

        chunk = (
            uploaded_chunks[index]
        )

        context_parts.append(
            f"Source: {source}\n{chunk}"
        )

        if source not in sources:

            sources.append(
                source
            )

    context = (
        "\n\n---\n\n".join(
            context_parts
        )
    )

    prompt = f"""
Use ONLY the study notes below to answer the student's question.

If the answer cannot be found in the notes, say:
"I could not find this information in the uploaded notes."

RELEVANT STUDY NOTES:

{context}

STUDENT QUESTION:

{request.question}
"""

    response = client.chat(
        model="llama3.2:3b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful study assistant. "
                    "Answer questions using only "
                    "the provided study notes."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return {
        "question": request.question,
        "answer": (
            response.message.content
        ),
        "sources": sources
    }


# -------------------------
# Generate AI quiz
# -------------------------

@app.post("/quiz")
def generate_quiz(
        request: QuizRequest
):

    global latest_quiz

    if not uploaded_chunks:

        return {
            "error": (
                "Please upload your study notes "
                "before generating a quiz."
            )
        }

    # Embed quiz topic
    topic_response = client.embed(
        model="embeddinggemma",
        input=request.topic
    )

    topic_embedding = (
        topic_response.embeddings[0]
    )

    similarities = []

    # Compare topic with chunks
    for index, embedding in enumerate(
            chunk_embeddings
    ):

        score = cosine_similarity(
            topic_embedding,
            embedding
        )

        similarities.append(
            (
                score,
                index
            )
        )

    similarities.sort(
        reverse=True
    )

    # Retrieve top 5 chunks
    top_results = (
        similarities[:5]
    )

    context_parts = []

    for score, index in top_results:

        context_parts.append(
            uploaded_chunks[index]
        )

    context = (
        "\n\n---\n\n".join(
            context_parts
        )
    )

    prompt = f"""
Create a multiple-choice quiz using ONLY the study notes below.

The quiz topic is:
{request.topic}

Create exactly:
{request.number_of_questions} questions.

For every question:
- Include exactly 4 answer options
- Include one correct answer
- Include a short explanation
- Only use information from the supplied study notes

Return the topic as:
{request.topic}

STUDY NOTES:

{context}
"""

    response = client.chat(
        model="llama3.2:3b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an educational quiz generator. "
                    "Only create questions from the "
                    "provided study notes."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        format=QuizResponse.model_json_schema(),
        options={
            "temperature": 0
        }
    )

    quiz = (
        QuizResponse.model_validate_json(
            response.message.content
        )
    )

    # Save quiz temporarily
    # so it can be marked
    latest_quiz = quiz

    return quiz


# -------------------------
# Submit quiz answers
# -------------------------

@app.post("/quiz/submit")
def submit_quiz(
        submission: QuizSubmission
):

    if latest_quiz is None:

        return {
            "error": (
                "Please generate "
                "a quiz first."
            )
        }

    if (
            len(submission.answers)
            !=
            len(latest_quiz.questions)
    ):

        return {
            "error": (
                "Please submit an answer "
                "for every question."
            )
        }

    score = 0
    results = []

    for index, question in enumerate(
            latest_quiz.questions
    ):

        student_answer = (
            submission.answers[index]
        )

        is_correct = (
                student_answer.strip().lower()
                ==
                question.correct_answer.strip().lower()
        )

        if is_correct:

            score += 1

        results.append({
            "question": (
                question.question
            ),
            "your_answer": (
                student_answer
            ),
            "correct_answer": (
                question.correct_answer
            ),
            "correct": (
                is_correct
            ),
            "explanation": (
                question.explanation
            )
        })

    total = len(
        latest_quiz.questions
    )

    percentage = (
                         score / total
                 ) * 100

    percentage = round(
        percentage,
        1
    )

    # Save quiz result permanently
    # inside SQLite
    save_quiz_result(
        topic=latest_quiz.topic,
        score=score,
        total=total,
        percentage=percentage
    )

    return {
        "topic": latest_quiz.topic,
        "score": score,
        "total": total,
        "percentage": percentage,
        "results": results
    }


# -------------------------
# Progress tracking
# -------------------------

@app.get("/progress")
def get_progress():

    quiz_history = (
        get_quiz_results()
    )

    if not quiz_history:

        return {
            "total_quizzes": 0,
            "average_percentage": 0,
            "quiz_history": []
        }

    total_percentage = sum(
        result["percentage"]
        for result in quiz_history
    )

    average_percentage = (
            total_percentage
            / len(quiz_history)
    )

    return {
        "total_quizzes": len(
            quiz_history
        ),
        "average_percentage": round(
            average_percentage,
            1
        ),
        "quiz_history": quiz_history
    }


# -------------------------
# Generate AI flashcards
# -------------------------

@app.post("/flashcards")
def generate_flashcards(
        request: FlashcardRequest
):

    if not uploaded_chunks:

        return {
            "error": (
                "Please upload your study notes "
                "before generating flashcards."
            )
        }

    # Embed requested topic
    topic_response = client.embed(
        model="embeddinggemma",
        input=request.topic
    )

    topic_embedding = (
        topic_response.embeddings[0]
    )

    similarities = []

    # Compare topic with document chunks
    for index, embedding in enumerate(
            chunk_embeddings
    ):

        score = cosine_similarity(
            topic_embedding,
            embedding
        )

        similarities.append(
            (
                score,
                index
            )
        )

    similarities.sort(
        reverse=True
    )

    # Retrieve top 5 chunks
    top_results = (
        similarities[:5]
    )

    context_parts = []

    for score, index in top_results:

        context_parts.append(
            uploaded_chunks[index]
        )

    context = (
        "\n\n---\n\n".join(
            context_parts
        )
    )

    prompt = f"""
Create study flashcards using ONLY the study notes below.

Topic:
{request.topic}

Create exactly:
{request.number_of_flashcards} flashcards.

Each flashcard must contain:

Front:
A clear question or key term.

Back:
A concise answer or explanation.

Only use information found in the supplied study notes.

Return the topic as:
{request.topic}

STUDY NOTES:

{context}
"""

    response = client.chat(
        model="llama3.2:3b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an educational flashcard generator. "
                    "Create clear and accurate flashcards "
                    "using only the provided study notes."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        format=(
            FlashcardResponse.model_json_schema()
        ),
        options={
            "temperature": 0
        }
    )

    flashcards = (
        FlashcardResponse.model_validate_json(
            response.message.content
        )
    )

    return flashcards
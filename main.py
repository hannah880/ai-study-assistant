from fastapi import FastAPI, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from ollama import Client
from pypdf import PdfReader
from io import BytesIO
from pathlib import Path
import math

from database import (
    create_tables,
    save_quiz_result,
    get_quiz_results,
    save_document,
    get_saved_documents,
    get_saved_document_chunks
)


# -------------------------
# App setup
# -------------------------

app = FastAPI()

client = Client(
    host="http://localhost:11434"
)


# -------------------------
# AI models
# -------------------------

ASK_MODEL = "llama3.2:3b"
GENERATION_MODEL = "llama3.2:1b"
EMBEDDING_MODEL = "embeddinggemma"


# -------------------------
# Frontend setup
# -------------------------

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

app.mount(
    "/static",
    StaticFiles(directory=FRONTEND_DIR),
    name="static"
)


# -------------------------
# Database setup
# -------------------------

create_tables()


# -------------------------
# Study data
# -------------------------

uploaded_chunks = []
chunk_embeddings = []
chunk_sources = []
uploaded_documents = []

latest_quiz = None


# -------------------------
# Load saved study notes
# -------------------------

def load_saved_study_data():

    saved_documents = get_saved_documents()
    saved_chunks = get_saved_document_chunks()

    for document in saved_documents:
        uploaded_documents.append(
            document["filename"]
        )

    for item in saved_chunks:

        uploaded_chunks.append(
            item["chunk"]
        )

        chunk_embeddings.append(
            item["embedding"]
        )

        chunk_sources.append(
            item["filename"]
        )


load_saved_study_data()


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

    options: list[str] = Field(
        min_length=4,
        max_length=4
    )

    # 0 = first option
    # 1 = second option
    # 2 = third option
    # 3 = fourth option
    correct_option_index: int = Field(
        ge=0,
        le=3
    )

    explanation: str


class QuizResponse(BaseModel):
    topic: str
    questions: list[QuizQuestion]


class PublicQuizQuestion(BaseModel):
    question: str
    options: list[str]


class PublicQuizResponse(BaseModel):
    topic: str
    questions: list[PublicQuizQuestion]


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
# Frontend
# -------------------------

@app.get("/")
def home():

    return FileResponse(
        FRONTEND_DIR / "index.html"
    )


@app.get("/health")
def health():

    return {
        "message":
            "AI Study Assistant backend is running"
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

    return (
            dot_product
            /
            (
                    magnitude1
                    *
                    magnitude2
            )
    )


def find_relevant_chunks(
        search_text,
        number_of_chunks
):

    search_response = client.embed(
        model=EMBEDDING_MODEL,
        input=search_text
    )

    search_embedding = (
        search_response.embeddings[0]
    )

    similarities = []

    for index, embedding in enumerate(
            chunk_embeddings
    ):

        score = cosine_similarity(
            search_embedding,
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

    return similarities[
        :number_of_chunks
    ]


def quiz_is_valid(
        quiz,
        requested_number
):

    # Must contain exactly the requested
    # number of questions
    if len(quiz.questions) != requested_number:
        return False

    for question in quiz.questions:

        # Must contain four options
        if len(question.options) != 4:
            return False

        # Remove whitespace and ignore
        # capitalisation when checking duplicates
        normalised_options = [
            option.strip().lower()
            for option in question.options
        ]

        # All four options must be different
        if len(set(normalised_options)) != 4:
            return False

        # Questions/options cannot be empty
        if not question.question.strip():
            return False

        for option in question.options:

            if not option.strip():
                return False

    return True


# -------------------------
# Upload PDFs
# -------------------------

@app.post("/upload")
async def upload_pdf(
        file: UploadFile = File(...)
):

    if not file.filename:

        return {
            "error":
                "Please upload a PDF file."
        }

    if not file.filename.lower().endswith(
            ".pdf"
    ):

        return {
            "error":
                "A PDF file needs to be uploaded."
        }

    if file.filename in uploaded_documents:

        return {
            "error":
                "This document has already been uploaded."
        }

    contents = await file.read()

    try:

        reader = PdfReader(
            BytesIO(contents)
        )

    except Exception:

        return {
            "error":
                "The PDF could not be read."
        }

    text = ""

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    if not text.strip():

        return {
            "error":
                "No text could be extracted from this PDF."
        }

    new_chunks = split_text(text)

    embedding_response = client.embed(
        model=EMBEDDING_MODEL,
        input=new_chunks
    )

    new_embeddings = (
        embedding_response.embeddings
    )

    saved = save_document(
        filename=file.filename,
        chunks=new_chunks,
        embeddings=new_embeddings
    )

    if not saved:

        return {
            "error":
                "This document has already been saved."
        }

    uploaded_chunks.extend(
        new_chunks
    )

    chunk_embeddings.extend(
        new_embeddings
    )

    for chunk in new_chunks:

        chunk_sources.append(
            file.filename
        )

    uploaded_documents.append(
        file.filename
    )

    return {
        "filename":
            file.filename,

        "characters_extracted":
            len(text),

        "chunks_created":
            len(new_chunks),

        "documents_loaded":
            len(uploaded_documents),

        "message":
            "PDF processed and saved successfully."
    }


# -------------------------
# View uploaded documents
# -------------------------

@app.get("/documents")
def get_documents():

    return {
        "documents":
            uploaded_documents,

        "total_documents":
            len(uploaded_documents),

        "total_chunks":
            len(uploaded_chunks)
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
            "error":
                "Please upload your study notes "
                "before asking a question."
        }

    top_results = find_relevant_chunks(
        request.question,
        4
    )

    context_parts = []
    sources = []

    for score, index in top_results:

        source = chunk_sources[index]
        chunk = uploaded_chunks[index]

        context_parts.append(
            f"Source: {source}\n{chunk}"
        )

        if source not in sources:

            sources.append(
                source
            )

    context = "\n\n---\n\n".join(
        context_parts
    )

    prompt = f"""
Use ONLY the study notes below to answer the student's question.

If the answer cannot be found in the notes, say:
"This information is not found in the uploaded notes."

Keep the answer clear and concise.

RELEVANT STUDY NOTES:

{context}

STUDENT QUESTION:

{request.question}
"""

    response = client.chat(
        model=ASK_MODEL,
        messages=[
            {
                "role":
                    "system",

                "content":
                    "You are a helpful study assistant. "
                    "Answer questions using only "
                    "the provided study notes."
            },
            {
                "role":
                    "user",

                "content":
                    prompt
            }
        ]
    )

    return {
        "question":
            request.question,

        "answer":
            response.message.content,

        "sources":
            sources
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
            "error":
                "Please upload your study notes "
                "before generating a quiz."
        }

    top_results = find_relevant_chunks(
        request.topic,
        3
    )

    context_parts = []

    for score, index in top_results:

        context_parts.append(
            uploaded_chunks[index]
        )

    context = "\n\n---\n\n".join(
        context_parts
    )

    prompt = f"""
Create a multiple-choice quiz using ONLY the study notes below.

Topic:
{request.topic}

Create exactly {request.number_of_questions} questions.

IMPORTANT RULES:

- Every question must have exactly 4 answer options.
- All 4 options must be different.
- Never repeat an option.
- There must be exactly one correct option.
- correct_option_index must be a number from 0 to 3.
- 0 means the first option.
- 1 means the second option.
- 2 means the third option.
- 3 means the fourth option.
- The explanation must agree with the correct option.
- Keep questions and explanations concise.
- Use only information contained in the notes.

STUDY NOTES:

{context}
"""

    # Try twice in case the smaller
    # local model produces invalid options
    for attempt in range(2):

        response = client.chat(
            model=GENERATION_MODEL,
            messages=[
                {
                    "role":
                        "system",

                    "content":
                        "You generate accurate educational "
                        "multiple-choice quizzes using only "
                        "the supplied study material."
                },
                {
                    "role":
                        "user",

                    "content":
                        prompt
                }
            ],
            format=(
                QuizResponse.model_json_schema()
            ),
            options={
                "temperature": 0
            }
        )

        full_quiz = (
            QuizResponse.model_validate_json(
                response.message.content
            )
        )

        if quiz_is_valid(
                full_quiz,
                request.number_of_questions
        ):
            break

    else:

        return {
            "error":
                "The AI could not create a valid quiz. "
                "Please try again."
        }

    # Store the answer key only
    # on the backend
    latest_quiz = full_quiz

    # Send only questions and options
    # to the browser
    public_questions = []

    for question in full_quiz.questions:

        public_questions.append(
            PublicQuizQuestion(
                question=question.question,
                options=question.options
            )
        )

    return PublicQuizResponse(
        topic=full_quiz.topic,
        questions=public_questions
    )


# -------------------------
# Submit quiz answers
# -------------------------

@app.post("/quiz/submit")
def submit_quiz(
        submission: QuizSubmission
):

    if latest_quiz is None:

        return {
            "error":
                "Please generate a quiz first."
        }

    if (
            len(submission.answers)
            !=
            len(latest_quiz.questions)
    ):

        return {
            "error":
                "Please submit an answer "
                "for every question."
        }

    score = 0
    results = []

    for index, question in enumerate(
            latest_quiz.questions
    ):

        student_answer = (
            submission.answers[index]
        )

        # Backend works out the actual
        # correct option text
        correct_answer = (
            question.options[
                question.correct_option_index
            ]
        )

        is_correct = (
                student_answer.strip().lower()
                ==
                correct_answer.strip().lower()
        )

        if is_correct:
            score += 1

        results.append({
            "question":
                question.question,

            "your_answer":
                student_answer,

            "correct_answer":
                correct_answer,

            "correct":
                is_correct,

            "explanation":
                question.explanation
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

    save_quiz_result(
        topic=latest_quiz.topic,
        score=score,
        total=total,
        percentage=percentage
    )

    return {
        "topic":
            latest_quiz.topic,

        "score":
            score,

        "total":
            total,

        "percentage":
            percentage,

        "results":
            results
    }


# -------------------------
# Progress tracking
# -------------------------

@app.get("/progress")
def get_progress():

    quiz_history = get_quiz_results()

    if not quiz_history:

        return {
            "total_quizzes": 0,
            "average_percentage": 0,
            "weakest_topic": None,
            "strongest_topic": None,
            "topic_progress": [],
            "quiz_history": []
        }

    total_percentage = sum(
        result["percentage"]
        for result in quiz_history
    )

    average_percentage = (
            total_percentage
            /
            len(quiz_history)
    )

    topic_scores = {}

    for result in quiz_history:

        topic = result["topic"]
        percentage = result["percentage"]

        if topic not in topic_scores:
            topic_scores[topic] = []

        topic_scores[
            topic
        ].append(
            percentage
        )

    topic_progress = []

    for topic, scores in topic_scores.items():

        topic_average = (
                sum(scores)
                /
                len(scores)
        )

        topic_progress.append({
            "topic":
                topic,

            "average_score":
                round(
                    topic_average,
                    1
                ),

            "quizzes_completed":
                len(scores)
        })

    topic_progress.sort(
        key=lambda item:
        item["average_score"]
    )

    weakest_topic = (
        topic_progress[0]["topic"]
    )

    strongest_topic = (
        topic_progress[-1]["topic"]
    )

    return {
        "total_quizzes":
            len(quiz_history),

        "average_percentage":
            round(
                average_percentage,
                1
            ),

        "weakest_topic":
            weakest_topic,

        "strongest_topic":
            strongest_topic,

        "topic_progress":
            topic_progress,

        "quiz_history":
            quiz_history
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
            "error":
                "Please upload your study notes "
                "before generating flashcards."
        }

    top_results = find_relevant_chunks(
        request.topic,
        3
    )

    context_parts = []

    for score, index in top_results:

        context_parts.append(
            uploaded_chunks[index]
        )

    context = "\n\n---\n\n".join(
        context_parts
    )

    prompt = f"""
Create study flashcards using ONLY the study notes below.

Topic:
{request.topic}

Create exactly {request.number_of_flashcards} flashcards.

For each flashcard:

Front:
A short question or key term.

Back:
A concise answer or explanation.

Rules:

- Only use information from the notes.
- Keep each flashcard concise.
- Do not add outside information.

STUDY NOTES:

{context}
"""

    response = client.chat(
        model=GENERATION_MODEL,
        messages=[
            {
                "role":
                    "system",

                "content":
                    "You generate concise educational "
                    "flashcards using only the supplied "
                    "study material."
            },
            {
                "role":
                    "user",

                "content":
                    prompt
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
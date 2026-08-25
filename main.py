from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel, Field
from ollama import Client
from pypdf import PdfReader
from io import BytesIO
import math


app = FastAPI()

client = Client(host="http://localhost:11434")


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
    number_of_questions: int = Field(default=5, ge=1, le=10)


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

def split_text(text, chunk_size=500, overlap=50):

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


def cosine_similarity(vector1, vector2):

    dot_product = sum(
        a * b
        for a, b in zip(vector1, vector2)
    )

    magnitude1 = math.sqrt(
        sum(a * a for a in vector1)
    )

    magnitude2 = math.sqrt(
        sum(b * b for b in vector2)
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
            "error": "This document has already been uploaded."
        }

    contents = await file.read()

    reader = PdfReader(
        BytesIO(contents)
    )

    text = ""

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    if not text.strip():
        return {
            "error": "No text could be extracted from this PDF."
        }

    # Split document into chunks
    new_chunks = split_text(text)

    # Generate embeddings
    embedding_response = client.embed(
        model="embeddinggemma",
        input=new_chunks
    )

    new_embeddings = (
        embedding_response.embeddings
    )

    # Store chunks and embeddings
    uploaded_chunks.extend(
        new_chunks
    )

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
        "documents_loaded": len(uploaded_documents),
        "message": "PDF processed and added successfully."
    }


# -------------------------
# View uploaded documents
# -------------------------

@app.get("/documents")
def get_documents():

    return {
        "documents": uploaded_documents,
        "total_documents": len(uploaded_documents),
        "total_chunks": len(uploaded_chunks)
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

    # Embed the student's question
    question_response = client.embed(
        model="embeddinggemma",
        input=request.question
    )

    question_embedding = (
        question_response.embeddings[0]
    )

    similarities = []

    # Compare question with every chunk
    for index, embedding in enumerate(
            chunk_embeddings
    ):

        score = cosine_similarity(
            question_embedding,
            embedding
        )

        similarities.append(
            (score, index)
        )

    # Highest similarity first
    similarities.sort(
        reverse=True
    )

    # Retrieve top 4 chunks
    top_results = similarities[:4]

    context_parts = []
    sources = []

    for score, index in top_results:

        source = chunk_sources[index]
        chunk = uploaded_chunks[index]

        context_parts.append(
            f"Source: {source}\n{chunk}"
        )

        if source not in sources:
            sources.append(source)

    context = "\n\n---\n\n".join(
        context_parts
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
        "answer": response.message.content,
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

    # Find notes relevant to the topic
    topic_response = client.embed(
        model="embeddinggemma",
        input=request.topic
    )

    topic_embedding = (
        topic_response.embeddings[0]
    )

    similarities = []

    for index, embedding in enumerate(
            chunk_embeddings
    ):

        score = cosine_similarity(
            topic_embedding,
            embedding
        )

        similarities.append(
            (score, index)
        )

    similarities.sort(
        reverse=True
    )

    # Use 5 most relevant chunks
    top_results = similarities[:5]

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

    quiz = QuizResponse.model_validate_json(
        response.message.content
    )

    # Save the quiz so it can be marked later
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
            "error": "Please generate a quiz first."
        }

    if len(submission.answers) != len(latest_quiz.questions):
        return {
            "error": "Please submit an answer for every question."
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
            "question": question.question,
            "your_answer": student_answer,
            "correct_answer": question.correct_answer,
            "correct": is_correct,
            "explanation": question.explanation
        })

    percentage = (
                         score / len(latest_quiz.questions)
                 ) * 100

    return {
        "score": score,
        "total": len(latest_quiz.questions),
        "percentage": round(percentage, 1),
        "results": results
    }
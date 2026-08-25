from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from ollama import Client
from pypdf import PdfReader
from io import BytesIO
import math

app = FastAPI()

client = Client(host="http://localhost:11434")

# Stores information from all uploaded PDFs
uploaded_chunks = []
chunk_embeddings = []
chunk_sources = []
uploaded_documents = []


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def home():
    return {"message": "AI Study Assistant backend is running"}


def split_text(text, chunk_size=500, overlap=50):
    words = text.split()

    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])

        chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def cosine_similarity(vector1, vector2):
    dot_product = sum(a * b for a, b in zip(vector1, vector2))

    magnitude1 = math.sqrt(sum(a * a for a in vector1))
    magnitude2 = math.sqrt(sum(b * b for b in vector2))

    if magnitude1 == 0 or magnitude2 == 0:
        return 0

    return dot_product / (magnitude1 * magnitude2)


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return {"error": "Please upload a PDF file."}

    if file.filename in uploaded_documents:
        return {"error": "This document has already been uploaded."}

    contents = await file.read()

    reader = PdfReader(BytesIO(contents))

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    if not text.strip():
        return {"error": "No text could be extracted from this PDF."}

    new_chunks = split_text(text)

    embedding_response = client.embed(
        model="embeddinggemma",
        input=new_chunks
    )

    new_embeddings = embedding_response.embeddings

    # Add the new document instead of replacing existing documents
    uploaded_chunks.extend(new_chunks)
    chunk_embeddings.extend(new_embeddings)

    for chunk in new_chunks:
        chunk_sources.append(file.filename)

    uploaded_documents.append(file.filename)

    return {
        "filename": file.filename,
        "characters_extracted": len(text),
        "chunks_created": len(new_chunks),
        "documents_loaded": len(uploaded_documents),
        "message": "PDF processed and added successfully."
    }


@app.get("/documents")
def get_documents():
    return {
        "documents": uploaded_documents,
        "total_documents": len(uploaded_documents),
        "total_chunks": len(uploaded_chunks)
    }


@app.post("/ask")
def ask_question(request: QuestionRequest):

    if not uploaded_chunks:
        return {
            "error": "Please upload your study notes before asking a question."
        }

    question_response = client.embed(
        model="embeddinggemma",
        input=request.question
    )

    question_embedding = question_response.embeddings[0]

    similarities = []

    for index, embedding in enumerate(chunk_embeddings):

        score = cosine_similarity(
            question_embedding,
            embedding
        )

        similarities.append((score, index))

    similarities.sort(reverse=True)

    # Retrieve the four most relevant pieces of notes
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

    context = "\n\n---\n\n".join(context_parts)

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
                    "Answer questions using only the provided study notes."
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
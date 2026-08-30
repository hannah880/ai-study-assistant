# AI Study Assistant

 This is an AI-powered study assistant built with **Python, FastAPI, local LLMs and Retrieval-Augmented Generation (RAG)**.

This is where users can study by uploading a pdf of their study notes and ask ai questions, do quizzes and flashcards based off what they have uploaded. Progress of the user will also be saved.

The AI runs locally using **Ollama**, meaning no paid AI API is required.

---

## Demo

### Home Page
<img width="1469" height="774" alt="Screenshot 2026-08-30 at 19 08 49" src="https://github.com/user-attachments/assets/753885d5-a8cc-479e-b3cd-1f03f0ec4379" /> 


### Ask AI


### AI Quiz



### Progress Tracking


---

## Features

- Upload PDF study notes
- Extracts and processes text from PDFs
- Generate vector embeddings using EmbeddingGemma
- Retrieve relevant information using semantic search and cosine similarity
- Ask AI questions based on what has been uploaded
- Display the source document used for answers
- Multiple-choice quizzes from selected topics are generated
- Marking of quiz answers
- Show explanations after submission
- Correct answers will be in green and incorrect answers in red
- Generate interactive AI flashcards
- Quiz scores and performance are tracked
- Identify strongest and weakest topics
- Store quiz history using SQLite
- Persist uploaded document embeddings between application restarts
- Run AI models locally using Ollama

---

## Technologies

### Backend

- Python
- FastAPI
- SQLite
- Pydantic
- PyPDF

### AI

- Ollama
- Llama 3.2 3B
- Llama 3.2 1B
- EmbeddingGemma
- Retrieval-Augmented Generation (RAG)
- Vector embeddings
- Cosine similarity

### Frontend

- HTML
- CSS
- JavaScript

### Development Tools

- Git
- GitHub
- IntelliJ IDEA

---

## How It Works

The application uses a Retrieval-Augmented Generation pipeline:

When a user asks a question:

1. The question is converted into a vector embedding.
2. The application compares it with embeddings from the uploaded notes.
3. Cosine similarity is used to identify the most relevant chunks.
4. Only the relevant study material is passed to the language model.
5. The model generates an answer based on the retrieved notes.

This allows the AI to answer questions using the student's own material rather than relying only on general model knowledge.

---

## Quiz System

The quiz feature uses retrieved study-note content to generate multiple-choice questions.

The application:

- Generates four different answer options
- Keeps the correct answer hidden before submission
- Validates generated quiz options
- Marks answers automatically
- Calculates the final percentage
- Provides explanations
- Stores quiz results for progress tracking

Correct questions are highlighted in **green**, while incorrect questions are highlighted in **red**.

---

## Progress Tracking

Quiz results are stored using SQLite.

The progress dashboard displays:

- Total quizzes completed
- Average score
- Quiz history
- Topic performance
- Strongest topic
- Weakest topic

This allows students to identify areas that may need more revision.

---

## Local AI Models

The project uses different local models for different tasks:

**Llama 3.2 3B**

Used for question answering where higher-quality responses are preferred.

**Llama 3.2 1B**

Used for quiz and flashcard generation to improve response speed.

**EmbeddingGemma**

Used to generate vector embeddings for semantic retrieval.

All AI processing runs locally through Ollama.

---

## Project Structure

```text
ai-study-assistant/
├── main.py
├── database.py
├── requirements.txt
├── README.md
├── .gitignore
└── frontend/
    ├── index.html
    ├── styles.css
    └── app.js
---

## What I Learned

This project helped me gain experience with:

- Building REST APIs using FastAPI
- RAG
- Working with vector embeddings and semantic search
- Integrating local large language models
- Processing PDF documents
- Designing persistent storage with SQLite
- Connecting a JavaScript frontend to a Python backend
- Using Pydantic for structured AI output
- Validating AI-generated content
- Managing application state and persistent data
- Git and GitHub version control
- Debugging and improving AI-generated outputs

---

## Future Improvements

- User accounts
- Separate progress tracking for multiple users
- Support for additional file formats
- Spaced-repetition flashcards
- More detailed learning analytics
- Improved document management
- Cloud deployment

---

<details>

<summary><strong>Run Locally</strong></summary>

<br>

The application uses local Ollama models, so Ollama and the required models must be installed to use the full AI functionality.

### Clone the repository

```bash
git clone <repository-url>
```

```bash
cd ai-study-assistant
```

### Create a virtual environment

```bash
python -m venv .venv
```

Activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

### Install Python dependencies

```bash
pip install -r requirements.txt
```

### Download the AI models

```bash
ollama pull llama3.2:3b
ollama pull llama3.2:1b
ollama pull embeddinggemma
```

### Start the application

```bash
python -m uvicorn main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

</details>

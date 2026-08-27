let currentQuiz = null;


// -------------------------
// Navigation
// -------------------------

const navigationButtons =
    document.querySelectorAll(".nav-button");

const sections =
    document.querySelectorAll(".page-section");


navigationButtons.forEach(button => {

    button.addEventListener("click", () => {

        navigationButtons.forEach(nav => {
            nav.classList.remove("active");
        });

        sections.forEach(section => {
            section.classList.remove(
                "active-section"
            );
        });

        button.classList.add("active");

        const target =
            button.dataset.section;

        document
            .getElementById(target)
            .classList.add("active-section");


        if (target === "progress-section") {
            loadProgress();
        }

        if (target === "upload-section") {
            loadDocuments();
        }

    });

});


// -------------------------
// Upload PDF
// -------------------------

document
    .getElementById("upload-button")
    .addEventListener(
        "click",
        uploadPDF
    );


async function uploadPDF() {

    const fileInput =
        document.getElementById(
            "pdf-file"
        );

    const message =
        document.getElementById(
            "upload-message"
        );


    if (!fileInput.files.length) {

        message.textContent =
            "Please choose a PDF first.";

        message.className =
            "message error";

        return;
    }


    const formData =
        new FormData();

    formData.append(
        "file",
        fileInput.files[0]
    );


    message.textContent =
        "Uploading and processing PDF...";

    message.className =
        "message";


    try {

        const response = await fetch(
            "/upload",
            {
                method: "POST",
                body: formData
            }
        );

        const data =
            await response.json();


        if (data.error) {

            message.textContent =
                data.error;

            message.className =
                "message error";

            return;
        }


        message.textContent =
            `${data.filename} uploaded successfully.`;

        message.className =
            "message success";

        fileInput.value = "";

        loadDocuments();

    } catch (error) {

        message.textContent =
            "Something went wrong while uploading.";

        message.className =
            "message error";

    }

}


// -------------------------
// Documents
// -------------------------

document
    .getElementById("refresh-documents")
    .addEventListener(
        "click",
        loadDocuments
    );


async function loadDocuments() {

    const container =
        document.getElementById(
            "document-list"
        );


    try {

        const response =
            await fetch("/documents");

        const data =
            await response.json();


        if (data.documents.length === 0) {

            container.innerHTML = `
                <p class="muted">
                    No documents uploaded yet.
                </p>
            `;

            return;
        }


        container.innerHTML =
            data.documents
                .map(documentName => `
                    <div class="document-item">
                        ${escapeHTML(documentName)}
                    </div>
                `)
                .join("");

    } catch (error) {

        container.innerHTML = `
            <p class="error">
                Could not load documents.
            </p>
        `;

    }

}


// -------------------------
// Ask AI
// -------------------------

document
    .getElementById("ask-button")
    .addEventListener(
        "click",
        askQuestion
    );


async function askQuestion() {

    const input =
        document.getElementById(
            "question-input"
        );

    const question =
        input.value.trim();

    const card =
        document.getElementById(
            "answer-card"
        );

    const output =
        document.getElementById(
            "answer-output"
        );

    const sources =
        document.getElementById(
            "source-output"
        );


    if (!question) {

        alert(
            "Enter a question first."
        );

        return;
    }


    card.classList.remove(
        "hidden"
    );

    output.textContent =
        "Thinking...";

    sources.textContent = "";


    try {

        const response =
            await fetch(
                "/ask",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        question: question
                    })
                }
            );


        const data =
            await response.json();


        if (data.error) {

            output.textContent =
                data.error;

            return;
        }


        output.textContent =
            data.answer;


        if (
            data.sources &&
            data.sources.length > 0
        ) {

            sources.textContent =
                "Sources: "
                + data.sources.join(", ");

        }

    } catch (error) {

        output.textContent =
            "Something went wrong while generating the answer.";

    }

}


// -------------------------
// Generate Quiz
// -------------------------

document
    .getElementById("generate-quiz")
    .addEventListener(
        "click",
        generateQuiz
    );


async function generateQuiz() {

    const topic =
        document.getElementById(
            "quiz-topic"
        ).value.trim();

    const numberOfQuestions =
        Number(
            document.getElementById(
                "quiz-count"
            ).value
        );

    const container =
        document.getElementById(
            "quiz-container"
        );


    if (!topic) {

        alert(
            "Enter a quiz topic."
        );

        return;
    }


    container.classList.remove(
        "hidden"
    );

    container.innerHTML = `
        <div class="card">
            Generating quiz...
        </div>
    `;


    try {

        const response =
            await fetch(
                "/quiz",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        topic: topic,
                        number_of_questions:
                            numberOfQuestions
                    })
                }
            );


        const data =
            await response.json();


        if (data.error) {

            container.innerHTML = `
                <div class="card error">
                    ${escapeHTML(data.error)}
                </div>
            `;

            return;
        }


        currentQuiz = data;

        displayQuiz(data);

    } catch (error) {

        container.innerHTML = `
            <div class="card error">
                Something went wrong while
                generating the quiz.
            </div>
        `;

    }

}


function displayQuiz(quiz) {

    const container =
        document.getElementById(
            "quiz-container"
        );


    let html = `
        <div class="card">
            <h2>
                ${escapeHTML(quiz.topic)} Quiz
            </h2>

            <p>
                Select one answer for each question.
            </p>
        </div>
    `;


    quiz.questions.forEach(
        (question, questionIndex) => {

            html += `
                <div class="quiz-question">

                    <h3>
                        ${questionIndex + 1}.
                        ${escapeHTML(question.question)}
                    </h3>
            `;


            question.options.forEach(
                option => {

                    html += `
                        <label class="quiz-option">

                            <input
                                type="radio"
                                name="question-${questionIndex}"
                                value="${escapeAttribute(option)}"
                            >

                            ${escapeHTML(option)}

                        </label>
                    `;

                }
            );


            html += `
                    <div
                        id="result-${questionIndex}"
                    ></div>

                </div>
            `;

        }
    );


    html += `
        <button
            class="primary-button"
            onclick="submitQuiz()"
        >
            Submit Quiz
        </button>
    `;


    container.innerHTML = html;

}


// -------------------------
// Submit Quiz
// -------------------------

async function submitQuiz() {

    if (!currentQuiz) {
        return;
    }


    const answers = [];


    for (
        let i = 0;
        i < currentQuiz.questions.length;
        i++
    ) {

        const selected =
            document.querySelector(
                `input[name="question-${i}"]:checked`
            );


        if (!selected) {

            alert(
                `Please answer question ${i + 1}.`
            );

            return;
        }


        answers.push(
            selected.value
        );

    }


    try {

        const response =
            await fetch(
                "/quiz/submit",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        answers: answers
                    })
                }
            );


        const data =
            await response.json();


        if (data.error) {

            alert(data.error);

            return;
        }


        showQuizResults(data);

    } catch (error) {

        alert(
            "Something went wrong while submitting the quiz."
        );

    }

}


function showQuizResults(data) {

    const container =
        document.getElementById(
            "quiz-container"
        );


    const scoreCard =
        document.createElement(
            "div"
        );

    scoreCard.className =
        "score-card";


    scoreCard.innerHTML = `
        <h2>
            Quiz Complete
        </h2>

        <p>
            Score:
            <strong>
                ${data.score}/${data.total}
            </strong>
        </p>

        <p>
            Percentage:
            <strong>
                ${data.percentage}%
            </strong>
        </p>
    `;


    container.prepend(
        scoreCard
    );


    data.results.forEach(
        (result, index) => {

            const resultContainer =
                document.getElementById(
                    `result-${index}`
                );


            resultContainer.className =
                "quiz-result";


            if (result.correct) {

                resultContainer.innerHTML = `
                    <strong>
                        Correct
                    </strong>

                    <p>
                        ${escapeHTML(
                            result.explanation
                        )}
                    </p>
                `;

            } else {

                resultContainer.innerHTML = `
                    <strong>
                        Incorrect
                    </strong>

                    <p>
                        Correct answer:
                        ${escapeHTML(
                            result.correct_answer
                        )}
                    </p>

                    <p>
                        ${escapeHTML(
                            result.explanation
                        )}
                    </p>
                `;

            }

        }
    );

}


// -------------------------
// Flashcards
// -------------------------

document
    .getElementById("generate-flashcards")
    .addEventListener(
        "click",
        generateFlashcards
    );


async function generateFlashcards() {

    const topic =
        document.getElementById(
            "flashcard-topic"
        ).value.trim();

    const count =
        Number(
            document.getElementById(
                "flashcard-count"
            ).value
        );

    const container =
        document.getElementById(
            "flashcard-container"
        );


    if (!topic) {

        alert(
            "Enter a flashcard topic."
        );

        return;
    }


    container.innerHTML = `
        <div class="card">
            Generating flashcards...
        </div>
    `;


    try {

        const response =
            await fetch(
                "/flashcards",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        topic: topic,
                        number_of_flashcards:
                            count
                    })
                }
            );


        const data =
            await response.json();


        if (data.error) {

            container.innerHTML = `
                <div class="card error">
                    ${escapeHTML(data.error)}
                </div>
            `;

            return;
        }


        displayFlashcards(
            data.flashcards
        );

    } catch (error) {

        container.innerHTML = `
            <div class="card error">
                Something went wrong while
                generating flashcards.
            </div>
        `;

    }

}


function displayFlashcards(
    flashcards
) {

    const container =
        document.getElementById(
            "flashcard-container"
        );


    container.innerHTML = "";


    flashcards.forEach(
        flashcard => {

            const card =
                document.createElement(
                    "div"
                );

            card.className =
                "flashcard";


            card.dataset.front =
                flashcard.front;

            card.dataset.back =
                flashcard.back;

            card.dataset.showingBack =
                "false";


            card.innerHTML = `
                <div class="flashcard-label">
                    Question
                </div>

                <div class="flashcard-text">
                    ${escapeHTML(
                        flashcard.front
                    )}
                </div>
            `;


            card.addEventListener(
                "click",
                () => flipFlashcard(card)
            );


            container.appendChild(
                card
            );

        }
    );

}


function flipFlashcard(card) {

    const showingBack =
        card.dataset.showingBack
        === "true";


    if (showingBack) {

        card.innerHTML = `
            <div class="flashcard-label">
                Question
            </div>

            <div class="flashcard-text">
                ${escapeHTML(
                    card.dataset.front
                )}
            </div>
        `;

        card.dataset.showingBack =
            "false";

    } else {

        card.innerHTML = `
            <div class="flashcard-label">
                Answer
            </div>

            <div class="flashcard-text">
                ${escapeHTML(
                    card.dataset.back
                )}
            </div>
        `;

        card.dataset.showingBack =
            "true";

    }

}


// -------------------------
// Progress
// -------------------------

document
    .getElementById("refresh-progress")
    .addEventListener(
        "click",
        loadProgress
    );


async function loadProgress() {

    try {

        const response =
            await fetch("/progress");

        const data =
            await response.json();


        document
            .getElementById(
                "total-quizzes"
            )
            .textContent =
                data.total_quizzes;


        document
            .getElementById(
                "average-score"
            )
            .textContent =
                `${data.average_percentage}%`;


        document
            .getElementById(
                "strongest-topic"
            )
            .textContent =
                data.strongest_topic
                || "-";


        document
            .getElementById(
                "weakest-topic"
            )
            .textContent =
                data.weakest_topic
                || "-";


        displayTopicProgress(
            data.topic_progress
        );


        displayQuizHistory(
            data.quiz_history
        );

    } catch (error) {

        console.error(
            "Could not load progress.",
            error
        );

    }

}


function displayTopicProgress(
    topics
) {

    const container =
        document.getElementById(
            "topic-progress"
        );


    if (!topics.length) {

        container.innerHTML = `
            <p class="muted">
                Complete quizzes to
                see your progress.
            </p>
        `;

        return;
    }


    container.innerHTML =
        topics
            .map(topic => `

                <div class="progress-row">

                    <div class="progress-heading">

                        <span>
                            ${escapeHTML(
                                topic.topic
                            )}
                        </span>

                        <span>
                            ${topic.average_score}%
                        </span>

                    </div>

                    <div class="progress-bar">

                        <div
                            class="progress-fill"
                            style="width:
                            ${topic.average_score}%"
                        >
                        </div>

                    </div>

                </div>

            `)
            .join("");

}


function displayQuizHistory(
    history
) {

    const container =
        document.getElementById(
            "quiz-history"
        );


    if (!history.length) {

        container.innerHTML = `
            <p class="muted">
                No quiz history yet.
            </p>
        `;

        return;
    }


    container.innerHTML =
        history
            .map(item => `

                <div class="history-item">

                    <div>
                        <strong>
                            ${escapeHTML(
                                item.topic
                            )}
                        </strong>

                        <div class="muted">
                            ${formatDate(
                                item.completed_at
                            )}
                        </div>
                    </div>

                    <strong>
                        ${item.percentage}%
                    </strong>

                </div>

            `)
            .join("");

}


// -------------------------
// Utility functions
// -------------------------

function escapeHTML(value) {

    const div =
        document.createElement(
            "div"
        );

    div.textContent =
        String(value);

    return div.innerHTML;

}


function escapeAttribute(value) {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll('"', "&quot;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");

}


function formatDate(value) {

    const date =
        new Date(value);

    return date.toLocaleString();

}


// Load initial data

loadDocuments();
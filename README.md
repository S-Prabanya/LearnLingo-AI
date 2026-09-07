# 🌐 LearnLingo AI

## 🤖 AI-Powered Language Learning Platform

**LearnLingo AI** is an intelligent web-based language learning platform designed to make language learning more interactive, accessible, and engaging.

The platform allows **teachers to create and manage lessons** while students can access learning content, translations, and audio pronunciation through a simple web interface.

> 🧠 LearnLingo AI combines language learning with AI-powered translation and text-to-speech technologies to provide an interactive learning experience.

---

## 🎯 Project Objective

The main objective of LearnLingo AI is to provide a simple and effective digital platform for language learning.

The system helps:

- 👩‍🏫 Teachers create and manage language lessons
- 👨‍🎓 Students access lessons through their accounts
- 🌍 Learners understand content using translation
- 🔊 Students improve pronunciation using audio
- 🤖 AI-based tools enhance the overall learning experience

---

## ✨ Features

- 👩‍🏫 Teacher Registration and Login
- 👨‍🎓 Student Registration and Login
- 📚 Create and Manage Lessons
- ✏️ Edit Existing Lessons
- 🗑️ Delete Lessons
- 🌐 Language Translation
- 🔊 Text-to-Speech Audio Generation
- 🎧 Audio Pronunciation Support
- 🗃️ Database-based User and Lesson Management
- 💻 Simple and User-Friendly Web Interface

---

## 👩‍🏫 Teacher Module

Teachers can:

- Create a teacher account
- Login securely
- Create new lessons
- Add learning content
- Manage existing lessons
- Edit lesson information
- Delete lessons when required
- Provide learning materials for students

---

## 👨‍🎓 Student Module

Students can:

- Create a student account
- Login to the learning platform
- View available lessons
- Access language learning content
- View translated content
- Listen to pronunciation through generated audio
- Learn languages interactively

---

## 🤖 AI-Based Functionalities

LearnLingo AI integrates intelligent language-processing features such as:

### 🌐 Translation

Lesson content can be translated into different languages, helping students understand unfamiliar words and sentences.

### 🔊 Text-to-Speech

Text content can be converted into speech so that students can listen to the pronunciation of words and sentences.

This helps improve:

- Pronunciation
- Listening skills
- Language comprehension
- Vocabulary learning

---

## 🛠️ Tech Stack

![Python](https://img.shields.io/badge/Python-3.x-blue)
![Flask](https://img.shields.io/badge/Flask-Web_Framework-black)
![SQLite](https://img.shields.io/badge/SQLite-Database-lightblue)
![HTML](https://img.shields.io/badge/HTML5-Web-orange)
![CSS](https://img.shields.io/badge/CSS3-Styling-blue)

- **Python** – Backend development
- **Flask** – Web application framework
- **SQLite** – Database management
- **HTML** – Web page structure
- **CSS** – User interface styling
- **Deep Translator** – Language translation
- **gTTS** – Text-to-Speech generation

---

## 📂 Project Structure

```text
LearnLingo-AI/
│
├── app.py
├── edubhasha.db
├── README.md
│
├── static/
│   ├── audio/
│   ├── images/
│   └── style.css
│
├── templates/
│   ├── index.html
│   ├── lesson.html
│   ├── edit_lesson.html
│   ├── student.html
│   ├── student_login.html
│   ├── student_signup.html
│   ├── teacher.html
│   ├── teacher_login.html
│   └── teacher_signup.html
│
└── .gitignore
```

---

## ⚙️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/S-Prabanya/LearnLingo-AI.git
```

### 2. Open the Project Folder

```bash
cd LearnLingo-AI
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
```

### 4. Activate the Virtual Environment

#### Windows

```bash
venv\Scripts\activate
```

#### Linux / macOS

```bash
source venv/bin/activate
```

### 5. Install Required Packages

```bash
pip install flask deep-translator gTTS
```

---

## ▶️ Run the Application

Start the Flask application using:

```bash
python app.py
```

Then open the local URL displayed in the terminal, usually:

```text
http://127.0.0.1:5000
```

---

## 🔄 Application Workflow

```text
User
 │
 ├───────────────┐
 │               │
 ▼               ▼
Teacher        Student
 │               │
 ▼               ▼
Login           Login
 │               │
 ▼               ▼
Create /        View
Manage          Lessons
Lessons           │
 │                ▼
 ▼            Translation
Database           +
              Audio Support
                   │
                   ▼
            Language Learning
```

---

## 🚀 Future Enhancements

- 🎙️ Speech Recognition
- 🗣️ Pronunciation Assessment
- 🤖 AI-Based Conversational Practice
- 📊 Student Progress Tracking
- 📝 Automated Quizzes
- 🏆 Gamification and Rewards
- 📱 Mobile-Friendly Interface
- 🌍 Support for More Languages

---

## 👩‍💻 Developed By

**S. Prabanya**

GitHub: **S-Prabanya**

---

## 📌 Repository

**LearnLingo-AI**

An AI-powered platform designed to make language learning simple, interactive, and accessible.

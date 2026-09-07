from deep_translator import GoogleTranslator, MyMemoryTranslator

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    session
)

from gtts import gTTS
from openai import OpenAI

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

import sqlite3
import os
import uuid
import json
import re


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)


app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "learnlingo-ai-development-secret-key"
)


DATABASE = "edubhasha.db"


AUDIO_FOLDER = os.path.join(
    "static",
    "audio"
)


os.makedirs(
    AUDIO_FOLDER,
    exist_ok=True
)


# =========================================================
# OPENAI CLIENT
# =========================================================

openai_client = OpenAI()


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():

    connection = sqlite3.connect(
        DATABASE
    )

    connection.row_factory = (
        sqlite3.Row
    )

    return connection


# =========================================================
# CHECK COLUMN
# =========================================================

def column_exists(
    connection,
    table_name,
    column_name
):

    columns = connection.execute(
        f"""
        PRAGMA table_info({table_name})
        """
    ).fetchall()


    return any(
        column[1] == column_name
        for column in columns
    )


# =========================================================
# CREATE DATABASE
# =========================================================

def create_database():

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()


    # -----------------------------------------------------
    # LESSONS
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lessons (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            class_name TEXT NOT NULL,

            subject TEXT NOT NULL,

            title TEXT NOT NULL,

            content TEXT NOT NULL,

            teacher_id TEXT

        )
        """
    )


    # -----------------------------------------------------
    # LESSON OWNERSHIP MIGRATION
    # -----------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(lessons)"
    )

    lesson_columns = cursor.fetchall()

    lesson_column_names = [
        column[1]
        for column in lesson_columns
    ]

    if "teacher_id" not in lesson_column_names:

        cursor.execute(
            """
            ALTER TABLE lessons
            ADD COLUMN teacher_id TEXT
            """
        )


    # Preserve old lesson data.
    # Lessons created before teacher ownership existed
    # are assigned to the demo teacher T001.
    cursor.execute(
        """
        UPDATE lessons
        SET teacher_id = 'T001'
        WHERE teacher_id IS NULL
           OR TRIM(teacher_id) = ''
        """
    )


    # -----------------------------------------------------
    # TRANSLATIONS
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS translations (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lesson_id INTEGER,

            language TEXT NOT NULL,

            translated_text TEXT NOT NULL,

            UNIQUE(
                lesson_id,
                language
            )

        )
        """
    )


    # -----------------------------------------------------
    # AI SIMPLIFICATIONS
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_simplifications (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lesson_id INTEGER UNIQUE,

            simplified_text TEXT NOT NULL

        )
        """
    )


    # -----------------------------------------------------
    # AI QUIZZES
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_quizzes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            lesson_id INTEGER UNIQUE,

            quiz_json TEXT NOT NULL

        )
        """
    )


    # -----------------------------------------------------
    # TEACHERS
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS teachers (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            teacher_id TEXT UNIQUE NOT NULL,

            name TEXT NOT NULL,

            email TEXT,

            password_hash TEXT NOT NULL

        )
        """
    )


    # -----------------------------------------------------
    # STUDENTS
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS students (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id TEXT UNIQUE NOT NULL,

            name TEXT NOT NULL,

            class_name TEXT NOT NULL,

            email TEXT,

            password_hash TEXT NOT NULL

        )
        """
    )


    # -----------------------------------------------------
    # QUIZ ATTEMPTS / STUDENT PROGRESS
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS quiz_attempts (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id TEXT NOT NULL,

            lesson_id INTEGER NOT NULL,

            score INTEGER NOT NULL,

            total_questions INTEGER NOT NULL,

            attempted_at DATETIME DEFAULT CURRENT_TIMESTAMP

        )
        """
    )


    connection.commit()


    # -----------------------------------------------------
    # ADD EMAIL COLUMN TO OLD DATABASE
    # -----------------------------------------------------

    if not column_exists(
        connection,
        "teachers",
        "email"
    ):

        connection.execute(
            """
            ALTER TABLE teachers
            ADD COLUMN email TEXT
            """
        )


    if not column_exists(
        connection,
        "students",
        "email"
    ):

        connection.execute(
            """
            ALTER TABLE students
            ADD COLUMN email TEXT
            """
        )


    connection.commit()


    # -----------------------------------------------------
    # DEMO TEACHER
    # -----------------------------------------------------

    teacher = connection.execute(
        """
        SELECT *
        FROM teachers
        WHERE teacher_id = ?
        """,
        (
            "T001",
        )
    ).fetchone()


    if teacher is None:

        connection.execute(
            """
            INSERT INTO teachers
            (
                teacher_id,
                name,
                email,
                password_hash
            )

            VALUES (?, ?, ?, ?)
            """,
            (
                "T001",
                "Demo Teacher",
                "teacher@learnlingo.com",
                generate_password_hash(
                    "teacher123"
                )
            )
        )


    # -----------------------------------------------------
    # DEMO STUDENT
    # -----------------------------------------------------

    student = connection.execute(
        """
        SELECT *
        FROM students
        WHERE student_id = ?
        """,
        (
            "S001",
        )
    ).fetchone()


    if student is None:

        connection.execute(
            """
            INSERT INTO students
            (
                student_id,
                name,
                class_name,
                email,
                password_hash
            )

            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "S001",
                "Demo Student",
                "Class 1",
                "student@learnlingo.com",
                generate_password_hash(
                    "student123"
                )
            )
        )


    connection.commit()

    connection.close()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# TEACHER SIGN UP
# =========================================================

@app.route(
    "/teacher-signup",
    methods=[
        "GET",
        "POST"
    ]
)
def teacher_signup():

    # Already logged in
    if session.get("teacher_id"):

        return redirect(
            url_for(
                "teacher"
            )
        )


    error = None


    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()


        teacher_id = request.form.get(
            "teacher_id",
            ""
        ).strip().upper()


        email = request.form.get(
            "email",
            ""
        ).strip().lower()


        password = request.form.get(
            "password",
            ""
        )


        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        # ---------------------------------------------
        # VALIDATION
        # ---------------------------------------------

        if not name:

            error = (
                "Please enter your name."
            )


        elif not teacher_id:

            error = (
                "Please enter a Teacher ID."
            )


        elif not email:

            error = (
                "Please enter your email address."
            )


        elif not password:

            error = (
                "Please enter a password."
            )


        elif len(password) < 6:

            error = (
                "Password must contain at least 6 characters."
            )


        elif password != confirm_password:

            error = (
                "Password and Confirm Password do not match."
            )


        else:

            connection = (
                get_db_connection()
            )


            existing_id = (
                connection.execute(
                    """
                    SELECT id
                    FROM teachers
                    WHERE teacher_id = ?
                    """,
                    (
                        teacher_id,
                    )
                ).fetchone()
            )


            existing_email = (
                connection.execute(
                    """
                    SELECT id
                    FROM teachers
                    WHERE LOWER(email) = ?
                    """,
                    (
                        email,
                    )
                ).fetchone()
            )


            if existing_id:

                error = (
                    "Teacher ID is already registered."
                )


            elif existing_email:

                error = (
                    "This email is already registered."
                )


            else:

                connection.execute(
                    """
                    INSERT INTO teachers
                    (
                        teacher_id,
                        name,
                        email,
                        password_hash
                    )

                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        teacher_id,
                        name,
                        email,
                        generate_password_hash(
                            password
                        )
                    )
                )


                connection.commit()

                connection.close()


                return redirect(
                    url_for(
                        "teacher_login",
                        registered="success"
                    )
                )


            connection.close()


    return render_template(
        "teacher_signup.html",
        error=error
    )


# =========================================================
# TEACHER LOGIN
# =========================================================

@app.route(
    "/teacher-login",
    methods=[
        "GET",
        "POST"
    ]
)
def teacher_login():

    if session.get(
        "teacher_id"
    ):

        return redirect(
            url_for(
                "teacher"
            )
        )


    error = None


    registered = (
        request.args.get(
            "registered"
        )
    )


    if request.method == "POST":

        teacher_id = request.form.get(
            "teacher_id",
            ""
        ).strip().upper()


        password = request.form.get(
            "password",
            ""
        )


        connection = (
            get_db_connection()
        )


        teacher = connection.execute(
            """
            SELECT *
            FROM teachers
            WHERE teacher_id = ?
            """,
            (
                teacher_id,
            )
        ).fetchone()


        connection.close()


        if (
            teacher
            and
            check_password_hash(
                teacher[
                    "password_hash"
                ],
                password
            )
        ):

            session.clear()


            session[
                "user_type"
            ] = "teacher"


            session[
                "teacher_id"
            ] = teacher[
                "teacher_id"
            ]


            session[
                "teacher_name"
            ] = teacher[
                "name"
            ]


            return redirect(
                url_for(
                    "teacher"
                )
            )


        error = (
            "Invalid Teacher ID or Password."
        )


    return render_template(
        "teacher_login.html",
        error=error,
        registered=registered
    )


# =========================================================
# STUDENT SIGN UP
# =========================================================

@app.route(
    "/student-signup",
    methods=[
        "GET",
        "POST"
    ]
)
def student_signup():

    if session.get(
        "student_id"
    ):

        return redirect(
            url_for(
                "student"
            )
        )


    error = None


    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()


        student_id = request.form.get(
            "student_id",
            ""
        ).strip().upper()


        class_name = request.form.get(
            "class_name",
            ""
        ).strip()


        email = request.form.get(
            "email",
            ""
        ).strip().lower()


        password = request.form.get(
            "password",
            ""
        )


        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        # ---------------------------------------------
        # VALIDATION
        # ---------------------------------------------

        if not name:

            error = (
                "Please enter your name."
            )


        elif not student_id:

            error = (
                "Please enter a Student ID."
            )


        elif class_name not in [
            "Class 1",
            "Class 2",
            "Class 3",
            "Class 4",
            "Class 5"
        ]:

            error = (
                "Please select a valid class."
            )


        elif not email:

            error = (
                "Please enter your email address."
            )


        elif not password:

            error = (
                "Please enter a password."
            )


        elif len(password) < 6:

            error = (
                "Password must contain at least 6 characters."
            )


        elif (
            password
            !=
            confirm_password
        ):

            error = (
                "Password and Confirm Password do not match."
            )


        else:

            connection = (
                get_db_connection()
            )


            existing_id = (
                connection.execute(
                    """
                    SELECT id
                    FROM students
                    WHERE student_id = ?
                    """,
                    (
                        student_id,
                    )
                ).fetchone()
            )


            existing_email = (
                connection.execute(
                    """
                    SELECT id
                    FROM students
                    WHERE LOWER(email) = ?
                    """,
                    (
                        email,
                    )
                ).fetchone()
            )


            if existing_id:

                error = (
                    "Student ID is already registered."
                )


            elif existing_email:

                error = (
                    "This email is already registered."
                )


            else:

                connection.execute(
                    """
                    INSERT INTO students
                    (
                        student_id,
                        name,
                        class_name,
                        email,
                        password_hash
                    )

                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        student_id,
                        name,
                        class_name,
                        email,
                        generate_password_hash(
                            password
                        )
                    )
                )


                connection.commit()

                connection.close()


                return redirect(
                    url_for(
                        "student_login",
                        registered="success"
                    )
                )


            connection.close()


    return render_template(
        "student_signup.html",
        error=error
    )


# =========================================================
# STUDENT LOGIN
# =========================================================

@app.route(
    "/student-login",
    methods=[
        "GET",
        "POST"
    ]
)
def student_login():

    if session.get(
        "student_id"
    ):

        return redirect(
            url_for(
                "student"
            )
        )


    error = None


    registered = (
        request.args.get(
            "registered"
        )
    )


    if request.method == "POST":

        student_id = request.form.get(
            "student_id",
            ""
        ).strip().upper()


        password = request.form.get(
            "password",
            ""
        )


        connection = (
            get_db_connection()
        )


        student_data = (
            connection.execute(
                """
                SELECT *
                FROM students
                WHERE student_id = ?
                """,
                (
                    student_id,
                )
            ).fetchone()
        )


        connection.close()


        if (
            student_data
            and
            check_password_hash(
                student_data[
                    "password_hash"
                ],
                password
            )
        ):

            session.clear()


            session[
                "user_type"
            ] = "student"


            session[
                "student_id"
            ] = student_data[
                "student_id"
            ]


            session[
                "student_name"
            ] = student_data[
                "name"
            ]


            session[
                "student_class"
            ] = student_data[
                "class_name"
            ]


            return redirect(
                url_for(
                    "student"
                )
            )


        error = (
            "Invalid Student ID or Password."
        )


    return render_template(
        "student_login.html",
        error=error,
        registered=registered
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route(
    "/logout"
)
def logout():

    session.clear()


    return redirect(
        url_for(
            "home"
        )
    )


# =========================================================
# TEACHER DASHBOARD
# =========================================================

@app.route(
    "/teacher"
)
def teacher():

    if (
        session.get(
            "user_type"
        )
        !=
        "teacher"
    ):

        return redirect(
            url_for(
                "teacher_login"
            )
        )


    teacher_id = session.get(
        "teacher_id"
    )


    connection = (
        get_db_connection()
    )


    # -----------------------------------------------------
    # ONLY THIS TEACHER'S UPLOADED LESSONS
    # -----------------------------------------------------

    lessons = (
        connection.execute(
            """
            SELECT *
            FROM lessons
            WHERE teacher_id = ?
            ORDER BY id DESC
            """,
            (
                teacher_id,
            )
        ).fetchall()
    )


    # -----------------------------------------------------
    # PERFORMANCE SUMMARY FOR THIS TEACHER'S LESSONS ONLY
    # -----------------------------------------------------

    summary = connection.execute(
        """
        SELECT
            (
                SELECT COUNT(*)
                FROM students
            ) AS total_students,

            (
                SELECT COUNT(
                    DISTINCT qa.student_id
                )
                FROM quiz_attempts qa
                INNER JOIN lessons l
                    ON l.id = qa.lesson_id
                WHERE l.teacher_id = ?
            ) AS students_attempted,

            (
                SELECT COUNT(*)
                FROM quiz_attempts qa
                INNER JOIN lessons l
                    ON l.id = qa.lesson_id
                WHERE l.teacher_id = ?
            ) AS total_attempts,

            (
                SELECT
                    COALESCE(
                        ROUND(
                            AVG(
                                (qa.score * 1.0)
                                /
                                NULLIF(
                                    qa.total_questions,
                                    0
                                )
                                * 100
                            ),
                            2
                        ),
                        0
                    )
                FROM quiz_attempts qa
                INNER JOIN lessons l
                    ON l.id = qa.lesson_id
                WHERE l.teacher_id = ?
            ) AS class_average_percentage
        """,
        (
            teacher_id,
            teacher_id,
            teacher_id
        )
    ).fetchone()


    # -----------------------------------------------------
    # STUDENT PERFORMANCE FOR THIS TEACHER'S LESSONS ONLY
    # -----------------------------------------------------

    student_performance = connection.execute(
        """
        SELECT
            s.student_id,
            s.name,
            s.class_name,

            COUNT(
                CASE
                    WHEN l.teacher_id = ?
                    THEN qa.id
                END
            ) AS attempts,

            COALESCE(
                MAX(
                    CASE
                        WHEN l.teacher_id = ?
                        THEN qa.score
                    END
                ),
                0
            ) AS best_score,

            COALESCE(
                ROUND(
                    AVG(
                        CASE
                            WHEN l.teacher_id = ?
                            THEN qa.score
                        END
                    ),
                    2
                ),
                0
            ) AS average_score,

            (
                SELECT qa2.score
                FROM quiz_attempts qa2
                INNER JOIN lessons l2
                    ON l2.id = qa2.lesson_id
                WHERE qa2.student_id = s.student_id
                  AND l2.teacher_id = ?
                ORDER BY qa2.id DESC
                LIMIT 1
            ) AS latest_score,

            (
                SELECT qa3.total_questions
                FROM quiz_attempts qa3
                INNER JOIN lessons l3
                    ON l3.id = qa3.lesson_id
                WHERE qa3.student_id = s.student_id
                  AND l3.teacher_id = ?
                ORDER BY qa3.id DESC
                LIMIT 1
            ) AS latest_total,

            (
                SELECT l4.title
                FROM quiz_attempts qa4
                INNER JOIN lessons l4
                    ON l4.id = qa4.lesson_id
                WHERE qa4.student_id = s.student_id
                  AND l4.teacher_id = ?
                ORDER BY qa4.id DESC
                LIMIT 1
            ) AS latest_lesson

        FROM students s

        LEFT JOIN quiz_attempts qa
            ON qa.student_id = s.student_id

        LEFT JOIN lessons l
            ON l.id = qa.lesson_id

        GROUP BY
            s.student_id,
            s.name,
            s.class_name

        ORDER BY
            s.class_name,
            s.name
        """,
        (
            teacher_id,
            teacher_id,
            teacher_id,
            teacher_id,
            teacher_id,
            teacher_id
        )
    ).fetchall()


    connection.close()


    return render_template(
        "teacher.html",

        lessons=lessons,

        teacher_name=session.get(
            "teacher_name"
        ),

        teacher_id=teacher_id,

        total_students=(
            summary["total_students"]
            if summary
            else 0
        ),

        students_attempted=(
            summary["students_attempted"]
            if summary
            else 0
        ),

        total_quiz_attempts=(
            summary["total_attempts"]
            if summary
            else 0
        ),

        class_average_percentage=(
            summary[
                "class_average_percentage"
            ]
            if summary
            else 0
        ),

        student_performance=student_performance
    )


# =========================================================
# ADD LESSON
# =========================================================

@app.route(
    "/add_lesson",
    methods=[
        "POST"
    ]
)
def add_lesson():

    if (
        session.get(
            "user_type"
        )
        !=
        "teacher"
    ):

        return redirect(
            url_for(
                "teacher_login"
            )
        )


    class_name = request.form[
        "class_name"
    ]


    subject = request.form[
        "subject"
    ]


    title = request.form[
        "title"
    ]


    content = request.form[
        "content"
    ]


    connection = (
        get_db_connection()
    )


    connection.execute(
        """
        INSERT INTO lessons
        (
            class_name,
            subject,
            title,
            content,
            teacher_id
        )

        VALUES (?, ?, ?, ?, ?)
        """,
        (
            class_name,
            subject,
            title,
            content,
            session.get(
                "teacher_id"
            )
        )
    )


    connection.commit()

    connection.close()


    return redirect(
        url_for(
            "teacher"
        )
    )



# =========================================================
# EDIT LESSON
# =========================================================

@app.route(
    "/edit_lesson/<int:lesson_id>",
    methods=[
        "GET",
        "POST"
    ]
)
def edit_lesson(
    lesson_id
):

    if (
        session.get(
            "user_type"
        )
        !=
        "teacher"
    ):

        return redirect(
            url_for(
                "teacher_login"
            )
        )


    teacher_id = session.get(
        "teacher_id"
    )


    connection = (
        get_db_connection()
    )


    lesson = connection.execute(
        """
        SELECT *
        FROM lessons
        WHERE id = ?
          AND teacher_id = ?
        """,
        (
            lesson_id,
            teacher_id
        )
    ).fetchone()


    if not lesson:

        connection.close()

        return (
            "Lesson not found or access denied.",
            404
        )


    if request.method == "POST":

        class_name = (
            request.form.get(
                "class_name",
                ""
            ).strip()
        )

        subject = (
            request.form.get(
                "subject",
                ""
            ).strip()
        )

        title = (
            request.form.get(
                "title",
                ""
            ).strip()
        )

        content = (
            request.form.get(
                "content",
                ""
            ).strip()
        )


        if (
            not class_name
            or
            not subject
            or
            not title
            or
            not content
        ):

            connection.close()

            return (
                "All lesson fields are required.",
                400
            )


        connection.execute(
            """
            UPDATE lessons

            SET
                class_name = ?,
                subject = ?,
                title = ?,
                content = ?

            WHERE id = ?
              AND teacher_id = ?
            """,
            (
                class_name,
                subject,
                title,
                content,
                lesson_id,
                teacher_id
            )
        )


        # Clear cached translations and AI content because
        # the lesson text may have changed.
        connection.execute(
            """
            DELETE FROM translations
            WHERE lesson_id = ?
            """,
            (
                lesson_id,
            )
        )


        connection.execute(
            """
            DELETE FROM ai_simplifications
            WHERE lesson_id = ?
            """,
            (
                lesson_id,
            )
        )


        connection.execute(
            """
            DELETE FROM ai_quizzes
            WHERE lesson_id = ?
            """,
            (
                lesson_id,
            )
        )


        connection.commit()

        connection.close()


        return redirect(
            url_for(
                "teacher"
            )
        )


    connection.close()


    return render_template(
        "edit_lesson.html",

        lesson=lesson,

        teacher_name=session.get(
            "teacher_name"
        )
    )



# =========================================================
# DELETE LESSON
# =========================================================

@app.route(
    "/delete_lesson/<int:lesson_id>",
    methods=[
        "POST"
    ]
)
def delete_lesson(
    lesson_id
):

    if (
        session.get(
            "user_type"
        )
        !=
        "teacher"
    ):

        return redirect(
            url_for(
                "teacher_login"
            )
        )


    teacher_id = session.get(
        "teacher_id"
    )


    connection = (
        get_db_connection()
    )


    lesson = connection.execute(
        """
        SELECT id
        FROM lessons
        WHERE id = ?
          AND teacher_id = ?
        """,
        (
            lesson_id,
            teacher_id
        )
    ).fetchone()


    if not lesson:

        connection.close()

        return (
            "Lesson not found or access denied.",
            404
        )


    # Remove dependent records first.
    connection.execute(
        """
        DELETE FROM quiz_attempts
        WHERE lesson_id = ?
        """,
        (
            lesson_id,
        )
    )


    connection.execute(
        """
        DELETE FROM translations
        WHERE lesson_id = ?
        """,
        (
            lesson_id,
        )
    )


    connection.execute(
        """
        DELETE FROM ai_simplifications
        WHERE lesson_id = ?
        """,
        (
            lesson_id,
        )
    )


    connection.execute(
        """
        DELETE FROM ai_quizzes
        WHERE lesson_id = ?
        """,
        (
            lesson_id,
        )
    )


    connection.execute(
        """
        DELETE FROM lessons
        WHERE id = ?
          AND teacher_id = ?
        """,
        (
            lesson_id,
            teacher_id
        )
    )


    connection.commit()

    connection.close()


    return redirect(
        url_for(
            "teacher"
        )
    )


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route(
    "/student"
)
def student():

    if (
        session.get(
            "user_type"
        )
        !=
        "student"
    ):

        return redirect(
            url_for(
                "student_login"
            )
        )


    connection = (
        get_db_connection()
    )


    lessons = connection.execute(
        """
        SELECT *
        FROM lessons
        ORDER BY
            class_name,
            subject,
            title
        """
    ).fetchall()


    student_id = session.get(
        "student_id"
    )


    progress = connection.execute(
        """
        SELECT
            COUNT(*) AS attempts,
            COALESCE(MAX(score), 0) AS best_score,
            COALESCE(ROUND(AVG(score), 2), 0) AS average_score
        FROM quiz_attempts
        WHERE student_id = ?
        """,
        (
            student_id,
        )
    ).fetchone()


    latest_attempt = connection.execute(
        """
        SELECT
            qa.id,
            qa.lesson_id,
            qa.score,
            qa.total_questions,
            qa.attempted_at,
            l.title AS lesson_title,
            l.subject AS subject
        FROM quiz_attempts qa
        LEFT JOIN lessons l
            ON l.id = qa.lesson_id
        WHERE qa.student_id = ?
        ORDER BY qa.id DESC
        LIMIT 1
        """,
        (
            student_id,
        )
    ).fetchone()


    connection.close()


    return render_template(
        "student.html",

        lessons=lessons,

        student_name=session.get(
            "student_name"
        ),

        student_id=student_id,

        student_class=session.get(
            "student_class"
        ),

        attempts=(
            progress["attempts"]
            if progress
            else 0
        ),

        best_score=(
            progress["best_score"]
            if progress
            else 0
        ),

        average_score=(
            progress["average_score"]
            if progress
            else 0
        ),

        latest_attempt=latest_attempt
    )


# =========================================================
# SAVE QUIZ ATTEMPT
# =========================================================

@app.route(
    "/save_quiz_attempt",
    methods=[
        "POST"
    ]
)
def save_quiz_attempt():

    if (
        session.get(
            "user_type"
        )
        !=
        "student"
    ):

        return jsonify({
            "success": False,
            "message": "Please login as a student."
        }), 401


    data = (
        request.get_json()
        or
        {}
    )


    lesson_id = data.get(
        "lesson_id"
    )

    score = data.get(
        "score"
    )

    total_questions = data.get(
        "total_questions"
    )


    try:

        lesson_id = int(
            lesson_id
        )

        score = int(
            score
        )

        total_questions = int(
            total_questions
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "success": False,
            "message": "Invalid quiz attempt data."
        }), 400


    if total_questions <= 0:

        return jsonify({
            "success": False,
            "message": "Total questions must be greater than zero."
        }), 400


    if (
        score < 0
        or
        score > total_questions
    ):

        return jsonify({
            "success": False,
            "message": "Invalid quiz score."
        }), 400


    connection = (
        get_db_connection()
    )


    lesson = connection.execute(
        """
        SELECT id
        FROM lessons
        WHERE id = ?
        """,
        (
            lesson_id,
        )
    ).fetchone()


    if lesson is None:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Lesson not found."
        }), 404


    connection.execute(
        """
        INSERT INTO quiz_attempts
        (
            student_id,
            lesson_id,
            score,
            total_questions
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            session.get(
                "student_id"
            ),
            lesson_id,
            score,
            total_questions
        )
    )


    connection.commit()

    connection.close()


    return jsonify({
        "success": True,
        "message": "Quiz progress saved successfully."
    })


# =========================================================
# VIEW LESSON
# =========================================================

@app.route(
    "/lesson/<int:lesson_id>"
)
def view_lesson(
    lesson_id
):

    if (
        session.get(
            "user_type"
        )
        !=
        "student"
    ):

        return redirect(
            url_for(
                "student_login"
            )
        )


    connection = (
        get_db_connection()
    )


    lesson = connection.execute(
        """
        SELECT *
        FROM lessons
        WHERE id = ?
        """,
        (
            lesson_id,
        )
    ).fetchone()


    connection.close()


    if lesson is None:

        return (
            "Lesson not found",
            404
        )


    return render_template(
        "lesson.html",
        lesson=lesson
    )


# =========================================================
# VALID TRANSLATION
# =========================================================

def valid_translation(
    text
):

    if not text:

        return False


    error_words = [

        "Error 500",

        "Server Error",

        "That's an error",

        "Please try again later",

        "<html",

        "<!DOCTYPE"

    ]


    for word in error_words:

        if (
            word.lower()
            in
            text.lower()
        ):

            return False


    return True


# =========================================================
# TRANSLATE
# =========================================================

@app.route(
    "/translate",
    methods=[
        "POST"
    ]
)
def translate():

    data = (
        request.get_json()
        or
        {}
    )


    text = data.get(
        "text",
        ""
    ).strip()


    language = data.get(
        "language",
        "en"
    )


    lesson_id = data.get(
        "lesson_id"
    )


    if not text:

        return jsonify({

            "success": False,

            "message":
                "Lesson content is empty."

        })


    # -----------------------------------------------------
    # ENGLISH
    # -----------------------------------------------------

    if language == "en":

        return jsonify({

            "success": True,

            "translated_text":
                text,

            "source":
                "original"

        })


    # -----------------------------------------------------
    # CACHE
    # -----------------------------------------------------

    if lesson_id:

        connection = (
            get_db_connection()
        )


        cached = connection.execute(
            """
            SELECT translated_text
            FROM translations

            WHERE lesson_id = ?

            AND language = ?
            """,
            (
                lesson_id,
                language
            )
        ).fetchone()


        connection.close()


        if cached:

            return jsonify({

                "success":
                    True,

                "translated_text":
                    cached[
                        "translated_text"
                    ],

                "source":
                    "cache"

            })


    # -----------------------------------------------------
    # LANGUAGE MAP
    # -----------------------------------------------------

    language_map = {

        "ta": "ta",

        "hi": "hi",

        "bn": "bn",

        "ur": "ur",

        "te": "te",

        "ml": "ml",

        "kn": "kn"

    }


    target_language = (
        language_map.get(
            language
        )
    )


    if not target_language:

        return jsonify({

            "success": False,

            "message":
                "Unsupported language."

        })


    translated_text = None

    translator_used = None


    # -----------------------------------------------------
    # GOOGLE TRANSLATOR
    # -----------------------------------------------------

    try:

        result = GoogleTranslator(
            source="auto",
            target=target_language
        ).translate(
            text
        )


        if valid_translation(
            result
        ):

            translated_text = (
                result
            )

            translator_used = (
                "Google"
            )


    except Exception as error:

        print(
            "GOOGLE TRANSLATION ERROR:",
            repr(error)
        )


    # -----------------------------------------------------
    # MY MEMORY FALLBACK
    # -----------------------------------------------------

    if translated_text is None:

        try:

            result = MyMemoryTranslator(
                source="en",
                target=target_language
            ).translate(
                text
            )


            if valid_translation(
                result
            ):

                translated_text = (
                    result
                )

                translator_used = (
                    "MyMemory"
                )


        except Exception as error:

            print(
                "MYMEMORY ERROR:",
                repr(error)
            )


    if translated_text is None:

        return jsonify({

            "success": False,

            "message":
                "Translation service is temporarily unavailable."

        })


    # -----------------------------------------------------
    # SAVE CACHE
    # -----------------------------------------------------

    if lesson_id:

        try:

            connection = (
                get_db_connection()
            )


            connection.execute(
                """
                INSERT OR REPLACE
                INTO translations
                (
                    lesson_id,
                    language,
                    translated_text
                )

                VALUES (?, ?, ?)
                """,
                (
                    lesson_id,
                    language,
                    translated_text
                )
            )


            connection.commit()

            connection.close()


        except Exception as error:

            print(
                "TRANSLATION CACHE ERROR:",
                repr(error)
            )


    return jsonify({

        "success":
            True,

        "translated_text":
            translated_text,

        "source":
            translator_used

    })


# =========================================================
# AI SIMPLIFICATION
# =========================================================

@app.route(
    "/simplify",
    methods=[
        "POST"
    ]
)
def simplify():

    data = (
        request.get_json()
        or
        {}
    )


    text = data.get(
        "text",
        ""
    ).strip()


    lesson_id = data.get(
        "lesson_id"
    )


    class_name = data.get(
        "class_name",
        "Primary School"
    )


    subject = data.get(
        "subject",
        "General"
    )


    if not text:

        return jsonify({

            "success": False,

            "message":
                "Lesson content is empty."

        })


    # -----------------------------------------------------
    # CACHE
    # -----------------------------------------------------

    if lesson_id:

        connection = (
            get_db_connection()
        )


        cached = connection.execute(
            """
            SELECT simplified_text

            FROM ai_simplifications

            WHERE lesson_id = ?
            """,
            (
                lesson_id,
            )
        ).fetchone()


        connection.close()


        if cached:

            return jsonify({

                "success":
                    True,

                "simplified_text":
                    cached[
                        "simplified_text"
                    ],

                "source":
                    "cache"

            })


    # -----------------------------------------------------
    # OPENAI
    # -----------------------------------------------------

    try:

        prompt = f"""
You are LearnLingo AI, a friendly educational assistant
for primary-school students.

Student Class: {class_name}
Subject: {subject}

Simplify the lesson below.

Rules:

1. Use very simple English.
2. Use short and clear sentences.
3. Keep the original meaning correct.
4. Explain difficult ideas using easy words.
5. Give a simple real-life example only if useful.
6. Do not add unrelated information.
7. Keep the explanation short.
8. Do not use Markdown headings.
9. Return only the simplified lesson.

Lesson:

{text}
"""


        response = (
            openai_client.responses.create(

                model=
                    "gpt-5.6-luna",

                input=
                    prompt
            )
        )


        simplified_text = (
            response.output_text.strip()
        )


        if not simplified_text:

            return jsonify({

                "success":
                    False,

                "message":
                    "AI did not generate an explanation."

            })


        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        if lesson_id:

            connection = (
                get_db_connection()
            )


            connection.execute(
                """
                INSERT OR REPLACE
                INTO ai_simplifications
                (
                    lesson_id,
                    simplified_text
                )

                VALUES (?, ?)
                """,
                (
                    lesson_id,
                    simplified_text
                )
            )


            connection.commit()

            connection.close()


        return jsonify({

            "success":
                True,

            "simplified_text":
                simplified_text,

            "source":
                "OpenAI"

        })


    except Exception as error:

        print(
            "OPENAI SIMPLIFY ERROR:",
            repr(error)
        )


        return jsonify({

            "success":
                False,

            "message":
                "AI simplification is temporarily unavailable."

        })


# =========================================================
# CLEAN OPENAI JSON
# =========================================================

def clean_json_response(
    text
):

    text = text.strip()


    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )


    text = re.sub(
        r"^```\s*",
        "",
        text
    )


    text = re.sub(
        r"\s*```$",
        "",
        text
    )


    return text.strip()


# =========================================================
# GENERATE FRESH QUIZ
# =========================================================

@app.route(
    "/generate_quiz",
    methods=[
        "POST"
    ]
)
def generate_quiz():

    data = (
        request.get_json()
        or
        {}
    )


    text = data.get(
        "text",
        ""
    ).strip()


    lesson_id = data.get(
        "lesson_id"
    )


    class_name = data.get(
        "class_name",
        "Primary School"
    )


    subject = data.get(
        "subject",
        "General"
    )


    title = data.get(
        "title",
        "Lesson"
    )


    previous_questions = data.get(
        "previous_questions",
        []
    )


    if not text:

        return jsonify({

            "success": False,

            "message":
                "Lesson content is empty."

        })


    previous_questions = (
        previous_questions[
            -20:
        ]
    )


    if previous_questions:

        previous_text = "\n".join(

            [
                f"- {question}"

                for question
                in previous_questions
            ]

        )


    else:

        previous_text = (
            "No previous questions yet."
        )


    try:

        prompt = f"""
You are LearnLingo AI, an educational assistant
for primary-school children.

Create a NEW set of exactly 5 multiple-choice questions
from the lesson below.

Student Class: {class_name}
Subject: {subject}
Lesson Title: {title}

IMPORTANT:

The following questions were already shown to the student:

{previous_text}

Do NOT repeat those questions.

Generate 5 fresh questions that test different points
from the lesson whenever possible.

Rules:

1. Generate exactly 5 questions.
2. Questions must come only from the lesson.
3. Keep questions simple and child-friendly.
4. Each question must have exactly 4 options.
5. Only one option must be correct.
6. answer_index must be 0, 1, 2 or 3.
7. Do not use information outside the lesson.
8. Avoid repeating previous questions.
9. Avoid simply changing one or two words in an old question.
10. Test different facts or ideas whenever possible.
11. Return ONLY valid JSON.
12. Do not include Markdown.
13. Do not include any explanation outside JSON.

Use exactly this JSON structure:

[
  {{
    "question": "Question text",
    "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
    ],
    "answer_index": 0
  }}
]

Lesson:

{text}
"""


        response = (
            openai_client.responses.create(

                model=
                    "gpt-5.6-luna",

                input=
                    prompt
            )
        )


        raw_output = (
            response.output_text
        )


        cleaned_output = (
            clean_json_response(
                raw_output
            )
        )


        quiz_data = json.loads(
            cleaned_output
        )


        # -------------------------------------------------
        # VALIDATE
        # -------------------------------------------------

        if not isinstance(
            quiz_data,
            list
        ):

            raise ValueError(
                "Quiz is not a list."
            )


        if len(
            quiz_data
        ) != 5:

            raise ValueError(
                "AI must generate exactly 5 questions."
            )


        for question in quiz_data:

            if (
                "question"
                not in
                question
            ):

                raise ValueError(
                    "Question text missing."
                )


            if (
                "options"
                not in
                question
            ):

                raise ValueError(
                    "Question options missing."
                )


            if (
                "answer_index"
                not in
                question
            ):

                raise ValueError(
                    "Answer index missing."
                )


            if len(
                question[
                    "options"
                ]
            ) != 4:

                raise ValueError(
                    "Every question must have exactly 4 options."
                )


            if question[
                "answer_index"
            ] not in [
                0,
                1,
                2,
                3
            ]:

                raise ValueError(
                    "Invalid answer index."
                )


        # -------------------------------------------------
        # SAVE LATEST QUIZ
        # -------------------------------------------------

        if lesson_id:

            try:

                connection = (
                    get_db_connection()
                )


                connection.execute(
                    """
                    INSERT OR REPLACE
                    INTO ai_quizzes
                    (
                        lesson_id,
                        quiz_json
                    )

                    VALUES (?, ?)
                    """,
                    (
                        lesson_id,

                        json.dumps(
                            quiz_data
                        )
                    )
                )


                connection.commit()

                connection.close()


            except Exception as error:

                print(
                    "QUIZ SAVE ERROR:",
                    repr(error)
                )


        return jsonify({

            "success":
                True,

            "quiz":
                quiz_data,

            "source":
                "OpenAI"

        })


    except Exception as error:

        print(
            "OPENAI QUIZ ERROR:",
            repr(error)
        )


        return jsonify({

            "success":
                False,

            "message":
                "Unable to generate AI quiz."

        })


# =========================================================
# TEXT TO SPEECH
# =========================================================

@app.route(
    "/text_to_speech",
    methods=[
        "POST"
    ]
)
def text_to_speech():

    data = (
        request.get_json()
        or
        {}
    )


    text = data.get(
        "text",
        ""
    ).strip()


    language = data.get(
        "language",
        "en"
    )


    if not text:

        return jsonify({

            "success":
                False,

            "message":
                "No text available for speech."

        })


    supported_languages = {

        "en": "en",

        "ta": "ta",

        "hi": "hi",

        "bn": "bn",

        "ur": "ur",

        "te": "te",

        "ml": "ml",

        "kn": "kn"

    }


    tts_language = (
        supported_languages.get(
            language
        )
    )


    if not tts_language:

        return jsonify({

            "success":
                False,

            "message":
                "Selected language is not supported for audio."

        })


    try:

        file_name = (
            str(
                uuid.uuid4()
            )
            +
            ".mp3"
        )


        file_path = os.path.join(
            AUDIO_FOLDER,
            file_name
        )


        tts = gTTS(

            text=text,

            lang=tts_language,

            slow=False

        )


        tts.save(
            file_path
        )


        audio_url = url_for(
            "static",

            filename=
                "audio/"
                +
                file_name
        )


        return jsonify({

            "success":
                True,

            "audio_url":
                audio_url

        })


    except Exception as error:

        print(
            "TTS ERROR:",
            repr(error)
        )


        return jsonify({

            "success":
                False,

            "message":
                "Unable to generate audio."

        })


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    create_database()


    app.run(
        debug=True
    )
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key'


def init_db():
    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()

    # Проверяем столбцы
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]

    # Создаём таблицы
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'ученик',
        theme TEXT DEFAULT 'dark'
    )''')

    if 'age' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN age INTEGER")
    if 'birth_date' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN birth_date TEXT")
    if 'phone' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    if 'email' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")

    if 'requested_role' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN requested_role TEXT")

    c.execute('''CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        creator_id INTEGER NOT NULL,
        max_attempts INTEGER DEFAULT 1,
        FOREIGN KEY (creator_id) REFERENCES users (id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        FOREIGN KEY (test_id) REFERENCES tests (id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER NOT NULL,
        answer_text TEXT NOT NULL,
        is_correct BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (question_id) REFERENCES questions (id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS test_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        total_questions INTEGER NOT NULL,
        FOREIGN KEY (test_id) REFERENCES tests (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')

    # Создаём админа
    c.execute("SELECT id FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password, role) VALUES ('admin', '5682', 'администратор')")

    conn.commit()
    conn.close()


def get_user_theme():
    if 'user_id' in session:
        conn = sqlite3.connect('quiz.db')
        c = conn.cursor()
        c.execute("SELECT theme FROM users WHERE id = ?", (session['user_id'],))
        result = c.fetchone()
        conn.close()
        if result:
            return result[0]
    return 'dark'


def has_permission(required_role):
    if 'user_id' not in session:
        return False
    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE id = ?", (session['user_id'],))
    user_role = c.fetchone()
    conn.close()
    if not user_role:
        return False
    role = user_role[0]
    if required_role == 'ученик':
        return True
    elif required_role == 'учитель':
        return role in ['учитель', 'модератор', 'администратор']
    elif required_role == 'модератор':
        return role in ['модератор', 'администратор']
    elif required_role == 'администратор':
        return role == 'администратор'
    return False


# === МАРШРУТЫ ===

@app.route('/')
def index():
    theme = get_user_theme()
    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tests")
    tests = c.fetchall()
    conn.close()
    return render_template('index.html', tests=tests, theme=theme)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('quiz.db')
        c = conn.cursor()
        c.execute("SELECT id, username, role FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[2]
            flash('Вы успешно вошли!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = 'ученик'
        conn = sqlite3.connect('quiz.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
            conn.commit()
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Пользователь с таким именем уже существует', 'error')
        finally:
            conn.close()
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


@app.route('/create_test', methods=['GET', 'POST'])
def create_test():
    if not has_permission('учитель'):
        flash('У вас нет прав для создания тестов', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        max_attempts = int(request.form.get('max_attempts', 1))

        conn = sqlite3.connect('quiz.db')
        c = conn.cursor()
        c.execute("INSERT INTO tests (name, description, creator_id, max_attempts) VALUES (?, ?, ?, ?)",
                  (name, description, session['user_id'], max_attempts))
        test_id = c.lastrowid

        q_num = 1
        while f'question_{q_num}' in request.form:
            question_text = request.form[f'question_{q_num}']
            if question_text.strip():
                c.execute("INSERT INTO questions (test_id, question) VALUES (?, ?)", (test_id, question_text))
                question_id = c.lastrowid

                a_num = 1
                while f'answer_{q_num}_{a_num}' in request.form:
                    answer_text = request.form[f'answer_{q_num}_{a_num}']
                    is_correct = f'correct_{q_num}_{a_num}' in request.form
                    if answer_text.strip():
                        c.execute("INSERT INTO answers (question_id, answer_text, is_correct) VALUES (?, ?, ?)",
                                  (question_id, answer_text, is_correct))
                    a_num += 1
            q_num += 1

        conn.commit()
        conn.close()
        flash('Тест успешно создан!', 'success')
        return redirect(url_for('my_tests'))

    return render_template('create_test.html')


@app.route('/my_tests')
def my_tests():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tests WHERE creator_id = ?", (session['user_id'],))
    tests = c.fetchall()
    conn.close()

    theme = get_user_theme()
    return render_template('my_tests.html', tests=tests, theme=theme)


@app.route('/edit_test/<int:test_id>', methods=['GET', 'POST'])
def edit_test(test_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("SELECT * FROM tests WHERE id = ? AND creator_id = ?", (test_id, session['user_id']))
    test = c.fetchone()

    if not test:
        conn.close()
        flash('Тест не найден или доступ запрещён', 'error')
        return redirect(url_for('my_tests'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        max_attempts = int(request.form.get('max_attempts', 1))

        c.execute("UPDATE tests SET name = ?, description = ?, max_attempts = ? WHERE id = ?",
                  (name, description, max_attempts, test_id))

        # Удаляем старые вопросы и ответы
        c.execute("DELETE FROM answers WHERE question_id IN (SELECT id FROM questions WHERE test_id = ?)", (test_id,))
        c.execute("DELETE FROM questions WHERE test_id = ?", (test_id,))

        # Добавляем новые
        q_num = 1
        while f'question_{q_num}' in request.form:
            question_text = request.form[f'question_{q_num}']
            if question_text.strip():
                c.execute("INSERT INTO questions (test_id, question) VALUES (?, ?)", (test_id, question_text))
                question_id = c.lastrowid

                a_num = 1
                while f'answer_{q_num}_{a_num}' in request.form:
                    answer_text = request.form[f'answer_{q_num}_{a_num}']
                    is_correct = f'correct_{q_num}_{a_num}' in request.form
                    if answer_text.strip():
                        c.execute("INSERT INTO answers (question_id, answer_text, is_correct) VALUES (?, ?, ?)",
                                  (question_id, answer_text, is_correct))
                    a_num += 1
            q_num += 1

        conn.commit()
        conn.close()
        flash('Тест обновлён', 'success')
        return redirect(url_for('my_tests'))

    # Получаем вопросы и ответы
    c.execute("SELECT * FROM questions WHERE test_id = ?", (test_id,))
    questions = c.fetchall()
    question_answers = {}
    for q in questions:
        c.execute("SELECT * FROM answers WHERE question_id = ?", (q[0],))
        question_answers[q[0]] = c.fetchall()

    conn.close()
    theme = get_user_theme()
    return render_template('edit_test.html', test=test, questions=questions, question_answers=question_answers,
                           theme=theme)


@app.route('/delete_test/<int:test_id>')
def delete_test(test_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("SELECT id FROM tests WHERE id = ? AND creator_id = ?", (test_id, session['user_id']))
    test = c.fetchone()

    if test:
        c.execute("DELETE FROM answers WHERE question_id IN (SELECT id FROM questions WHERE test_id = ?)", (test_id,))
        c.execute("DELETE FROM questions WHERE test_id = ?", (test_id,))
        c.execute("DELETE FROM test_results WHERE test_id = ?", (test_id,))
        c.execute("DELETE FROM tests WHERE id = ?", (test_id,))
        conn.commit()
        flash('Тест удалён', 'success')
    else:
        flash('Тест не найден или доступ запрещён', 'error')

    conn.close()
    return redirect(url_for('my_tests'))


@app.route('/test/<int:test_id>')
def take_test(test_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()

    c.execute("SELECT id, creator_id, max_attempts, name FROM tests WHERE id = ?", (test_id,))
    test_data = c.fetchone()
    if not test_data:
        conn.close()
        flash('Тест не найден', 'error')
        return redirect(url_for('index'))

    test_id, creator_id, max_attempts, test_name = test_data
    is_creator = (creator_id == session['user_id'])

    if not is_creator:
        c.execute("SELECT COUNT(*) FROM test_results WHERE test_id = ? AND user_id = ?", (test_id, session['user_id']))
        attempts_count = c.fetchone()[0]
        if attempts_count >= max_attempts:
            conn.close()
            flash(f'Вы исчерпали количество попыток ({max_attempts}) для этого теста', 'error')
            return redirect(url_for('index'))

    c.execute("SELECT * FROM questions WHERE test_id = ?", (test_id,))
    questions = c.fetchall()

    question_answers = {}
    for q in questions:
        c.execute("SELECT * FROM answers WHERE question_id = ?", (q[0],))
        question_answers[q[0]] = c.fetchall()

    conn.close()
    theme = get_user_theme()
    return render_template('take_test.html',
                           test_id=test_id,
                           questions=questions,
                           question_answers=question_answers,
                           theme=theme,
                           test_name=test_name)


@app.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()

    c.execute("SELECT id, creator_id, max_attempts FROM tests WHERE id = ?", (test_id,))
    test = c.fetchone()
    if not test:
        conn.close()
        flash('Тест не найден', 'error')
        return redirect(url_for('index'))

    creator_id, max_attempts = test[1], test[2]
    is_creator = (creator_id == session['user_id'])

    if not is_creator:
        c.execute("SELECT COUNT(*) FROM test_results WHERE test_id = ? AND user_id = ?", (test_id, session['user_id']))
        attempts_count = c.fetchone()[0]
        if attempts_count >= max_attempts:
            conn.close()
            flash('Количество попыток исчерпано', 'error')
            return redirect(url_for('index'))

    c.execute("SELECT id FROM questions WHERE test_id = ?", (test_id,))
    question_ids = [row[0] for row in c.fetchall()]

    score = 0
    total_questions = len(question_ids)

    for q_id in question_ids:
        user_answer_id = request.form.get(f'question_{q_id}')
        if user_answer_id:
            c.execute("SELECT is_correct FROM answers WHERE id = ? AND question_id = ?", (int(user_answer_id), q_id))
            correct = c.fetchone()
            if correct and correct[0]:
                score += 1

    c.execute("INSERT INTO test_results (test_id, user_id, score, total_questions) VALUES (?, ?, ?, ?)",
              (test_id, session['user_id'], score, total_questions))
    conn.commit()
    conn.close()

    return redirect(url_for('result', test_id=test_id, score=score, total=total_questions))


@app.route('/result')
def result():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    test_id = request.args.get('test_id')
    score = request.args.get('score')
    total = request.args.get('total')

    if not all([test_id, score, total]):
        flash('Ошибка: данные результата недоступны', 'error')
        return redirect(url_for('index'))

    test_id, score, total = int(test_id), int(score), int(total)

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()

    c.execute("SELECT creator_id FROM tests WHERE id = ?", (test_id,))
    creator = c.fetchone()
    is_creator = creator and creator[0] == session['user_id']

    c.execute("SELECT id FROM test_results WHERE test_id = ? AND user_id = ?", (test_id, session['user_id']))
    user_result = c.fetchone()

    if not is_creator and not user_result:
        conn.close()
        flash('Доступ к результату запрещён', 'error')
        return redirect(url_for('index'))

    conn.close()
    theme = get_user_theme()
    return render_template('result.html', score=score, total=total, theme=theme)


@app.route('/test_history')
def test_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()

    c.execute("""SELECT t.name, tr.score, tr.total_questions 
                 FROM test_results tr 
                 JOIN tests t ON tr.test_id = t.id 
                 WHERE tr.user_id = ?""", (session['user_id'],))
    taken_test_results = c.fetchall()

    conn.close()
    theme = get_user_theme()
    return render_template('test_history.html', taken_test_results=taken_test_results, theme=theme)


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("SELECT role, requested_role FROM users WHERE id = ?", (session['user_id'],))
    user_role, requested_role = c.fetchone()
    conn.close()

    if request.method == 'POST':
        theme = request.form.get('theme', 'dark')
        request_teacher = request.form.get('request_teacher')

        conn = sqlite3.connect('quiz.db')
        c = conn.cursor()
        c.execute("UPDATE users SET theme = ? WHERE id = ?", (theme, session['user_id']))

        if request_teacher and user_role != 'учитель' and requested_role != 'учитель':
            c.execute("UPDATE users SET requested_role = 'учитель' WHERE id = ?", (session['user_id'],))
            flash('Запрос на роль учителя отправлен', 'success')
        elif request_teacher and requested_role == 'учитель':
            flash('Запрос уже отправлен', 'info')

        conn.commit()
        conn.close()
        flash('Настройки сохранены', 'success')
        return redirect(url_for('settings'))

    theme = get_user_theme()
    return render_template('settings.html', theme=theme, user_role=user_role, requested_role=requested_role)


@app.route('/admin')
def admin_panel():
    if not has_permission('администратор'):
        flash('У вас нет прав для доступа к админке', 'error')
        return redirect(url_for('index'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("SELECT id, username, role, requested_role FROM users")
    users = c.fetchall()
    conn.close()

    theme = get_user_theme()
    return render_template('admin.html', users=users, theme=theme)


@app.route('/admin/users')
def admin_users():
    if not has_permission('модератор'):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("SELECT id, username, role, requested_role FROM users ORDER BY id")
    users = c.fetchall()
    conn.close()

    theme = get_user_theme()
    return render_template('admin_users.html', users=users, theme=theme)


@app.route('/admin/tests')
def admin_tests():
    if not has_permission('модератор'):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("""
        SELECT t.id, t.name, u.username, u.role, COUNT(q.id) as q_count,
               (SELECT COUNT(*) FROM test_results WHERE test_id = t.id) as attempts
        FROM tests t
        JOIN users u ON t.creator_id = u.id
        LEFT JOIN questions q ON t.id = q.test_id
        GROUP BY t.id, t.name, u.username, u.role
        ORDER BY t.id DESC
    """)
    tests = c.fetchall()
    conn.close()

    theme = get_user_theme()
    return render_template('admin_tests.html', tests=tests, theme=theme)


# ✅ КЛЮЧЕВОЙ МАРШРУТ — ИСПРАВЛЯЕТ BuildError
@app.route('/admin/delete_test/<int:test_id>')
def admin_delete_test(test_id):
    if not has_permission('модератор'):
        flash('У вас нет прав для удаления тестов', 'error')
        return redirect(url_for('admin_tests'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()

    # Проверяем существование теста
    c.execute("SELECT id FROM tests WHERE id = ?", (test_id,))
    if not c.fetchone():
        conn.close()
        flash('Тест не найден', 'error')
        return redirect(url_for('admin_tests'))

    # Удаляем всё
    c.execute("DELETE FROM answers WHERE question_id IN (SELECT id FROM questions WHERE test_id = ?)", (test_id,))
    c.execute("DELETE FROM questions WHERE test_id = ?", (test_id,))
    c.execute("DELETE FROM test_results WHERE test_id = ?", (test_id,))
    c.execute("DELETE FROM tests WHERE id = ?", (test_id,))
    conn.commit()
    conn.close()

    flash('Тест успешно удалён', 'success')
    return redirect(url_for('admin_tests'))


@app.route('/admin/requests')
def admin_requests():
    if not has_permission('модератор'):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.username, u.role, u.requested_role
        FROM users u
        WHERE u.requested_role = 'учитель'
        ORDER BY u.id
    """)
    requests = c.fetchall()
    conn.close()

    theme = get_user_theme()
    return render_template('admin_requests.html', requests=requests, theme=theme)


@app.route('/admin/stats')
def admin_stats():
    if not has_permission('модератор'):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM tests")
    total_tests = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM test_results")
    total_attempts = c.fetchone()[0]

    conn.close()

    theme = get_user_theme()
    return render_template('admin_stats.html',
                           total_users=total_users,
                           total_tests=total_tests,
                           total_attempts=total_attempts,
                           theme=theme)


@app.route('/admin/grant_teacher/<int:user_id>')
def grant_teacher(user_id):
    if not has_permission('модератор'):
        flash('У вас нет прав для подтверждения роли', 'error')
        return redirect(url_for('index'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("UPDATE users SET role = 'учитель', requested_role = NULL WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('Роль учителя подтверждена', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/reject_request/<int:user_id>')
def reject_request(user_id):
    if not has_permission('модератор'):
        flash('У вас нет прав для отклонения запросов', 'error')
        return redirect(url_for('admin_requests'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    # Сбрасываем запрос, не удаляя пользователя
    c.execute("UPDATE users SET requested_role = NULL WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('Запрос отклонён', 'success')
    return redirect(url_for('admin_requests'))


@app.route('/admin/change_role/<int:user_id>', methods=['POST'])
def change_role(user_id):
    if not has_permission('администратор'):
        flash('У вас нет прав для изменения роли', 'error')
        return redirect(url_for('admin_panel'))

    new_role = request.form['new_role']
    # ✅ Разрешаем 'администратор' тоже
    if new_role not in ['ученик', 'учитель', 'модератор', 'администратор']:
        flash('Недопустимая роль', 'error')
        return redirect(url_for('admin_panel'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()
    flash('Роль изменена', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/change_password/<int:user_id>', methods=['POST'])
def change_password(user_id):
    if not has_permission('администратор'):
        flash('У вас нет прав для изменения пароля', 'error')
        return redirect(url_for('admin_panel'))

    new_password = request.form['new_password']

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
    conn.commit()
    conn.close()
    flash('Пароль изменён', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if not has_permission('администратор'):
        flash('У вас нет прав для удаления пользователя', 'error')
        return redirect(url_for('admin_panel'))

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('Пользователь удалён', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/add_user', methods=['POST'])
def add_user():
    if not has_permission('администратор'):
        flash('У вас нет прав для добавления пользователя', 'error')
        return redirect(url_for('admin_panel'))

    username = request.form['username']
    password = request.form['password']
    role = request.form.get('role', 'ученик')

    conn = sqlite3.connect('quiz.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        flash('Пользователь добавлен', 'success')
    except sqlite3.IntegrityError:
        flash('Пользователь с таким именем уже существует', 'error')
    finally:
        conn.close()

    return redirect(url_for('admin_panel'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
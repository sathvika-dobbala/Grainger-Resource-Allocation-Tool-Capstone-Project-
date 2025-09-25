from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

# --- Database helper ---
def get_db_connection():
    conn = sqlite3.connect('employees.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- Routes ---

@app.route('/')
def index():
    conn = get_db_connection()
    skills = conn.execute('SELECT * FROM EmployeeSkills').fetchall()
    conn.close()
    return render_template('index.html', skills=skills)

@app.route('/add', methods=('POST',))
def add():
    employee_name = request.form['employee_name']
    skill = request.form['skill']
    conn = get_db_connection()
    conn.execute('INSERT INTO EmployeeSkills (employee_name, skill) VALUES (?, ?)',
                 (employee_name, skill))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM EmployeeSkills WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/update/<int:id>', methods=('POST',))
def update(id):
    new_skill = request.form['skill']
    conn = get_db_connection()
    conn.execute('UPDATE EmployeeSkills SET skill = ? WHERE id = ?',
                 (new_skill, id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)

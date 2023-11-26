import hashlib
import flask
import sqlite3
import json
import datetime

server_start_time = datetime.datetime.now()

authorized_users = dict()

database = sqlite3.connect('database.db', check_same_thread=False)
app = flask.Flask(__name__)

database_cursor = database.cursor()

# database_cursor.execute("""CREATE TABLE users (login text, name text, password text)""")
# database_cursor.execute("""CREATE TABLE users_notes (login text, note_text text, time integer)""")

database.commit()


def get_user_ip():
    return flask.request.environ.get('HTTP_X_REAL_IP', flask.request.remote_addr)


def registration_user(login, name, password):
    database_cursor.execute("""INSERT INTO users (login, name, password) VALUES (?, ?, ?)""",
                            (login, name, str(hashlib.sha1(password.encode("utf8")).hexdigest())))
    database.commit()


def add_note(login, note_text):
    note_time = (datetime.datetime.now() - server_start_time).seconds
    database_cursor.execute(f"""INSERT INTO users_notes (login, note_text, time) VALUES (?, ?, ?)""",
                            (login, note_text, note_time))
    database.commit()


def get_all_notes(login):
    return database_cursor.execute(
        """SELECT time, note_text FROM users_notes WHERE login = ? ORDER BY time DESC""", (login,)).fetchall()


def delete_note(login, time):
    database_cursor.execute(f"""DELETE FROM users_notes WHERE login = ? AND time = ?""", (login, time))
    database.commit()


def change_note(login, time, new_text):
    note_time = (datetime.datetime.now() - server_start_time).seconds
    database_cursor.execute(
        """UPDATE users_notes SET note_text = ?, time = ? WHERE login = ? AND time = ?""",
        (new_text, note_time, login, time))
    database.commit()


def change_account_data(login, new_login, new_name, new_password):
    old_account_data = database_cursor.execute(
        f"""SELECT login, name, password FROM users WHERE login = ?""", (login,)).fetchall()
    if new_login == '':
        new_login = old_account_data[0][0]
    if new_name == '':
        new_name = old_account_data[0][1]
    if new_password == '':
        new_password = old_account_data[0][2]
    database_cursor.execute(
        f"""UPDATE users SET login = ?, name = ?, password = ? WHERE login = ?""",
        (new_login, new_name, str(hashlib.sha1(new_password.encode("utf8")).hexdigest()), login))
    database.commit()


def account_data(login):
    print(database_cursor.execute(f"""SELECT login, name FROM users WHERE login = ?""", (login, )).fetchall())
    return database_cursor.execute(f"""SELECT login, name FROM users WHERE login = ?""", (login, )).fetchall()


def is_authorized():
    ip = get_user_ip()
    return ip in authorized_users


def login_is_free(login):
    if len(database_cursor.execute("""SELECT login FROM users WHERE login = ?""", (login,)).fetchall()) == 0:
        return True
    return False


def check_password(login, password):
    return database_cursor.execute(f"""SELECT password FROM users WHERE login = ?""", (login,)).fetchall()[0][0] == str(
        hashlib.sha1(password.encode("utf8")).hexdigest())


def count_notes(login):
    return len(database_cursor.execute(f"""SELECT * FROM users_notes WHERE login = ?""", (login,)).fetchall())


def get_notes_dict(login):
    notes_dict = dict()
    count = 0
    for i in get_all_notes(login):
        notes_dict[count] = i[1]
        count += 1
    return notes_dict


def get_note_time(login, number):
    return get_all_notes(login)[number][0]


@app.route("/")
@app.route("/home")
def main():
    if is_authorized():
        return flask.render_template("main_authorized.html")
    return flask.render_template("main_unauthorized.html")


@app.route("/login", methods=["POST", "GET"])
def login_data():
    if is_authorized():
        return flask.redirect("/notes")
    elif flask.request.method == "POST":
        login = flask.request.form.get("floatingInput")
        password = flask.request.form.get("floatingPassword")
        if not login_is_free(login) and check_password(login, password):
            authorized_users[get_user_ip()] = login
            return flask.redirect("/notes")
        return flask.render_template("login.html")
    return flask.render_template("login.html")


@app.route("/notes", methods=["POST", "GET"])
def notes():
    if not is_authorized():
        return flask.redirect("/login")

    login = authorized_users[get_user_ip()]
    if flask.request.method == "POST":
        update_data = json.loads(flask.request.get_data())
        if update_data["number"] == "None":
            if update_data["text"] == "None":
                return flask.redirect("/notes")
            add_note(login, update_data["text"])
        else:
            if update_data["text"] == "None":
                delete_note(login, get_note_time(login, update_data["number"]))
                return flask.redirect("/notes")
            change_note(login, get_note_time(login, update_data["number"]), update_data["text"])
        return flask.redirect("/notes")

    number = count_notes(login)
    notes_dict = get_notes_dict(login)
    return flask.render_template("notes.html", number=number, data_array=notes_dict)


@app.route("/account", methods=["POST", "GET"])
def account():
    if not is_authorized():
        return flask.redirect("/login")
    login = authorized_users[get_user_ip()]
    new_login = login
    if flask.request.method == "POST":
        new_login = flask.request.form.get("login")
        new_name = flask.request.form.get("name")
        new_password = flask.request.form.get("password")
        change_account_data(login, new_login, new_name, new_password)
        authorized_users[get_user_ip()] = new_login
    data = account_data(new_login)
    return flask.render_template("account.html", login=data[0][0], name=data[0][1])


@app.route("/registration", methods=["POST", "GET"])
def registration():
    if flask.request.method == "POST":
        login = flask.request.form.get("login")
        password = flask.request.form.get("password")
        name = flask.request.form.get("name")
        if login_is_free(login):
            registration_user(login, name, password)
            authorized_users[get_user_ip()] = login
            return flask.redirect("/notes")
        return flask.redirect("/registration")
    return flask.render_template("registration.html")


@app.route("/exit")
def logout():
    del authorized_users[get_user_ip()]
    return flask.redirect("/login")


if __name__ == '__main__':
    app.run()

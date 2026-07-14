from flask import Flask, render_template

from config import Config
from database.db import init_db
from routes.auth import auth
from routes.dashboard import dashboard
from routes.face import face
from routes.text import text
from routes.voice import voice
from routes.reports import reports

app = Flask(__name__)
app.config.from_object(Config)

app.register_blueprint(auth)
app.register_blueprint(dashboard)
app.register_blueprint(face)
app.register_blueprint(text)
app.register_blueprint(voice)
app.register_blueprint(reports)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
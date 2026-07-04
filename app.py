from flask import Flask, render_template

from config import Config
from database.db import init_db
from routes.auth import auth
from routes.dashboard import dashboard

app = Flask(__name__)
app.config.from_object(Config)

app.register_blueprint(auth)
app.register_blueprint(dashboard)


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
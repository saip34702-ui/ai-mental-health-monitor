from flask import Blueprint, render_template, redirect, session

dashboard = Blueprint("dashboard", __name__)


@dashboard.route("/dashboard")
def user_dashboard():
    if "user_id" not in session:
        return redirect("/login")

    return render_template("dashboard.html", name=session["user_name"])
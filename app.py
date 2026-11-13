"""EuropeTravel web application.

Run locally with:  flask run   (or: python app.py)
"""
from flask import Flask, jsonify, render_template


def create_app():
    app = Flask(__name__)
    app.json.sort_keys = False

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

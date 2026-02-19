from flask import jsonify, render_template, request
from sqlalchemy.exc import IntegrityError


class AppError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": err.message}), err.status_code
        return render_template("error.html", message=err.message), err.status_code

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(_err):
        app.logger.warning("Database integrity error")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Conflict. Resource already exists."}), 409
        return render_template("error.html", message="Conflict. Resource already exists."), 409

    @app.errorhandler(400)
    def bad_request(_err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Bad request"}), 400
        return render_template("error.html", message="Bad request"), 400

    @app.errorhandler(401)
    def unauthorized(_err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Unauthorized"}), 401
        return render_template("error.html", message="Unauthorized"), 401

    @app.errorhandler(403)
    def forbidden(_err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Forbidden"}), 403
        return render_template("error.html", message="Forbidden"), 403

    @app.errorhandler(404)
    def not_found(_err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("error.html", message="Page not found"), 404

    @app.errorhandler(500)
    def server_error(_err):
        app.logger.exception("Internal server error")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("error.html", message="Something went wrong."), 500

from flask import Flask
from config import Config
from routes.main import bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)

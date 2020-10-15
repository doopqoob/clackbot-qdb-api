import os
import postgres

from flask import Flask
from flask import request

from dotenv import load_dotenv

app = Flask(__name__)


@app.before_first_request
def init_db():
    postgres.init_db()


@app.route('/')
def hello_world():
    return 'Hello World!', 200


@app.route('/addquote', methods=['POST'])
def add_quote():
    id = postgres.add_quote(request.get_json())
    if not id:
        message = {"message": "Something went wrong adding your quote"}
        return message, 500

    message = {"id": id}
    return message, 201


@app.route('/delquote')
def del_quote():
    id = request.args.get('id')
    if not id:
        message = {"message": "Quote ID not supplied"}
        return message, 500

    status = postgres.del_quote(id)
    if status:
        message = {"message": "Success!"}
        return message, 200
    else:
        message = {"message": "Failed to delete quote"}
        return message, 500


@app.route('/getquote')
def get_quote():
    quote_id = request.args.get('id')
    quote = None

    if quote_id:
        quote = postgres.get_quote(quote_id)
    else:
        quote = postgres.get_random_quote()

    if quote:
        return quote, 200
    else:
        message = {"message": "Quote not found"}
        return message, 404


# @app.route('/initdb')
# def init_db():
#     DB_INIT_KEY = os.getenv('DB_INIT_KEY')
#     user_init_key = request.args.get('key')
#     if DB_INIT_KEY == user_init_key:
#         postgres.init_db()
#         message = {"message": "Success!"}
#         return message, 201
#     else:
#         message = {"message": "Unauthorized"}
#         return message, 403


if __name__ == '__main__':
    app.run()

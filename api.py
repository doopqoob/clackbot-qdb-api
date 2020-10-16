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
    """Hello World! This API does not face the internet, so this only gets called as a test"""
    return 'Hello World!', 200


@app.route('/addquote', methods=['POST'])
def add_quote():
    """Add a quote to the database."""
    # Get the JSON from the request and send it to the postgres module. If everything is successful, the
    # postgres module will return the ID of the newly-created quote entry in the DB.
    id = postgres.add_quote(request.get_json())
    if not id:
        message = {"message": "Something went wrong adding your quote"}
        return message, 500

    # Return the new quote ID
    message = {"id": id}
    return message, 201


@app.route('/delquote')
def del_quote():
    """Delete a quote from the database given its unique ID."""
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
    """Get a quote from the database given its unique ID. If no ID is given, return a random quote."""
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


@app.route('/addvotemessage')
def add_vote_message():
    message_id = int(request.args.get('message_id'))
    quote_id = request.args.get('quote_id')

    if not message_id:
        message = {"message": "Message ID not supplied"}
        return message, 500

    if not quote_id:
        message = {"message": "Quote ID not supplied"}
        return message, 500

    status = postgres.add_quote_message(message_id, quote_id)

    if not status:
        message = {"message": "Something went wrong adding your message"}
        return message, 500

    message = {"message": "Success!"}
    return message, 201

@app.route('/vote', methods=['POST'])
def vote():
    """Vote on a quote"""
    ballot = request.get_json()

    # Test to see if required arguments were supplied.
    if not ballot:
        message = {"message": "Ballot not supplied"}
        return message, 500

    if not ballot['message_id']:
        message = {"message": "Message ID not supplied"}
        return message, 500

    if not ballot['voter']:
        message = {"message": "Voter ID not supplied"}
        return message, 500

    # Put the ballot in the ballot box
    result = postgres.vote(ballot)
    if not result:
        message = {"message": "Something went wrong with your vote"}
        return message, 500
    else:
        message = {"message": "Vote successful!"}
        return message, 201


if __name__ == '__main__':
    app.run()

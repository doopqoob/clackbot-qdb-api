import psycopg2
import psycopg2.extras
import os

from uuid import UUID


def connect_db():
    """Return a connection to the database"""
    DB_HOST = os.getenv('DB_HOST')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')

    db = None
    try:
        db = psycopg2.connect(host=DB_HOST,
                              dbname='clackbot-quotes',
                              user=DB_USER,
                              password=DB_PASSWORD)
    except psycopg2.Error as error:
        print(f'Error connecting to db: {error}')
        return None

    return db


def init_db():
    """Initialize the database"""
    db = connect_db()

    cursor = db.cursor()

    sql_file = open('schema.sql', 'r')
    sql = sql_file.read()

    try:
        cursor.execute(sql)
    except psycopg2.Error as error:
        print(f'Error executing SQL: {error}')
        db.close()
        return False

    try:
        db.commit()
    except psycopg2.Error as error:
        print(f'Error committing changes to DB: {error}')
        db.close()
        return False

    db.close()


def insert(query, data, return_inserted_row_id=False):
    """Inserts one row of data into the database, optionally returning the ID of the inserted row"""
    db = connect_db()

    if not db:
        return False

    # Get a cursor for data insertion
    cursor = db.cursor()

    # This must be called to be able to work with UUID objects in postgres for some reason
    psycopg2.extras.register_uuid()

    # Execute the query
    try:
        cursor.execute(query, data)
    except psycopg2.Error as error:
        print(f'Error executing SQL INSERT query: {error}')
        db.close()
        return False

    # Commit changes
    try:
        db.commit()
    except psycopg2.Error as error:
        print(f'Error committing changes to DB: {error}')
        db.close()
        return False

    # Success!
    if return_inserted_row_id:
        # get the id of the newly-created row
        id = cursor.fetchone()[0]

        # close the database connection and return the id
        db.close()
        return id
    else:
        db.close()
        return True


def select(query, data=None, real_dict_cursor=False):
    """Queries the database and returns all rows."""
    db = connect_db()
    if not db:
        return None

    # Get a cursor for data insertion
    cursor = None
    if real_dict_cursor:
        cursor = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cursor = db.cursor()

    # This must be called to be able to work with UUID objects in postgres for some reason
    psycopg2.extras.register_uuid()

    # Execute the query
    try:
        if data:
            cursor.execute(query, data)
        else:
            cursor.execute(query)
    except psycopg2.Error as error:
        print(f'Error executing SQL query: {error}')
        db.close()
        return None

    # Get all rows from the DB. If there are no rows in the DB, this will return None.
    rows = cursor.fetchall()

    # Close the DB connection and return the rows
    db.close()
    return rows


def add_user_info(user):
    """
    Given a user data structure, add the user to the database. There's no need to return an ID from this function
    as we use Discord's unique user ID as our own.
    """
    # Perform some basic input validation
    if not isinstance(user['id'], int):
        return False
    if not isinstance(user['discriminator'], int):
        return False
    if not isinstance(user['handle'], str):
        return False

    # Build the query.
    # This query has an ON CONFLICT ... DO UPDATE clause, which means that user name will be updated any time
    # someone inserts an existing user into the db.
    query = "INSERT INTO discord_user (id, handle, discriminator) VALUES (%s, %s, %s) " \
            "ON CONFLICT (id) DO UPDATE SET handle = %s, discriminator = %s WHERE discord_user.id = %s"

    # data fields have to match every %s in order, which is why you see the same values twice,
    # in a different order each time.
    data = (user['id'], user['handle'], user['discriminator'], user['handle'], user['discriminator'], user['id'])

    # Perform the insert
    status = insert(query, data)

    return status


def get_user_info(user_id):
    """Given a user's unique ID, get the user's info, or return None if the user's id is not in the database"""
    # Validate that user_id is a number
    if not isinstance(user_id, int):
        return False

    # Query for the user's id
    query = "SELECT * FROM discord_user WHERE id = %s"
    data = (user_id,)

    rows = select(query, data, real_dict_cursor=True)

    # Get user data from the returned row(s).
    # Having more than one match or a returned row that doesn't match is Something That Should Never Happen(tm) but it's
    # accounted for anyway here.
    user = None

    for row in rows:
        quote_id = int(row['id'])

        if quote_id != user_id:
            continue

        user = {"id": quote_id,
                "handle": row['handle'],
                "discriminator": row['discriminator']}

    return user


def add_quote_metadata(quote):
    """Adds quote metadata and returns a unique ID so that the quote content can reference the metadata"""
    # Add or update user info in the db so it can be referenced in the quote metadata.
    # add_user_info() returns False on failure and True on success; it's possible, therefore, to test for problems with
    # user input or the database itself.
    status = add_user_info(quote['said_by'])
    if not status:
        return False

    status = add_user_info(quote['added_by'])
    if not status:
        return False

    # build the query
    query = "INSERT INTO quote_metadata (said_by, added_by) VALUES (%s, %s) RETURNING id"
    data = (quote['said_by']['id'], quote['added_by']['id'])

    # insert the data
    id = insert(query, data, return_inserted_row_id=True)

    if id:
        return id
    else:
        return False


def add_quote_content(quote_id, quote):
    """Adds actual quote content to db given the id from add_quote_metadata and the quote data structure."""
    # Test the id to make sure it's a valid uuid


    # Build the query
    query = "INSERT INTO quote_content (id, line_number, line) VALUES (%s, %s, %s)"

    # Insert the individual lines in the order they were received
    for line_number, line in enumerate(quote['quote']):
        data = (quote_id, line_number, line)
        insert(query, data)

    # Everything went well if execution gets to this point
    return True


def add_quote(quote):
    """Inserts a quote into the database."""
    print(quote)
    print(type(quote))
    quote_id = add_quote_metadata(quote)
    if not quote_id:
        return False

    result = add_quote_content(quote_id, quote)
    if not result:
        return False

    # Well, that was easy!
    return quote_id


def get_quote(quote_id):
    """get a quote by id"""
    # check quote_id to ensure it's a uuid
    if isinstance(quote_id, str):
        try:
            UUID(quote_id, version=4)
        except ValueError:
            return False

        # convert quote_id from string to uuid
        quote_id = UUID(quote_id, version=4)

    # Build the query
    query = "SELECT *, " \
            "du_said_by.handle as said_by_handle, " \
            "du_said_by.id as said_by_id, " \
            "du_said_by.discriminator as said_by_discriminator, " \
            "du_added_by.handle as added_by_handle, " \
            "du_added_by.id as added_by_id, " \
            "du_added_by.discriminator as added_by_discriminator " \
            "FROM quote_metadata " \
            "INNER JOIN discord_user du_said_by on quote_metadata.said_by = du_said_by.id " \
            "INNER JOIN discord_user AS du_added_by ON quote_metadata.added_by = du_added_by.id " \
            "INNER JOIN quote_content qc on quote_metadata.id = qc.id " \
            "WHERE quote_metadata.visible = true AND quote_metadata.id = %s " \
            "ORDER BY qc.line_number"

    data = (quote_id,)

    # Execute the query and get rows of data
    rows = select(query, data, real_dict_cursor=True)

    # Start building the quote structure
    quote = {"id": quote_id}

    # iterate through all rows returned by the db
    for row in rows:
        if 'added_at' not in quote:
            quote['added_at'] = row['added_at']

        if 'said_by' not in quote:
            quote['said_by'] = {}
            quote['said_by']['id'] = int(row['said_by_id'])
            quote['said_by']['handle'] = row['said_by_handle']
            quote['said_by']['discriminator'] = row['said_by_discriminator']

        if 'added_by' not in quote:
            quote['added_by'] = {}
            quote['added_by']['id'] = int(row['added_by_id'])
            quote['added_by']['handle'] = row['added_by_handle']
            quote['added_by']['discriminator'] = row['added_by_discriminator']

        if 'quote' not in quote:
            quote['quote'] = []

        quote['quote'].append(row['line'])

    if 'quote' not in quote:
        return None

    # Get quote's score
    query = "SELECT COALESCE(SUM(vote),0) AS score FROM quote_vote WHERE quote_id = %s"
    data = (quote_id,)

    # Execute the query
    rows = select(query, data, real_dict_cursor=True)

    quote['score'] = rows[0]['score']

    return quote


def get_random_quote_id():
    """select quote ID at random from the DB"""
    # Build the query
    query = "SELECT id FROM quote_metadata WHERE visible = true ORDER BY random() LIMIT 1"

    rows = select(query, real_dict_cursor=True)

    if rows is None:
        return False

    return rows[0]['id']


def get_random_quote():
    """get a quote at random from the db"""
     # get a random quote id
    quote_id = get_random_quote_id()
    quote = get_quote(quote_id)
    return quote


def del_quote(quote_id):
    """Delete a quote from the DB"""
    # Verify that id is a uuid
    try:
        UUID(quote_id, version=4)
    except ValueError:
        return False

    # convert quote_id from string to uuid
    quote_id = UUID(quote_id, version=4)

    # build query - note that the quote isn't actually deleted; it's just set to "invisible" so that
    # an administrator can manually undelete if necessary
    query = "UPDATE quote_metadata SET visible = false WHERE id = %s"
    data = (quote_id,)

    # We use 'insert' here but it should work just fine
    status = insert(query, data)
    return status


def add_quote_message(message_id, quote_id):
    """After sending a quote to a channel, make a note of the message ID to track up- and down-votes"""
    if isinstance(quote_id, str):
        try:
            UUID(quote_id, version=4)
        except ValueError:
            return False

        # convert quote_id from string to uuid
        quote_id = UUID(quote_id, version=4)

    if not isinstance(message_id, int):
        return False

    # Build the query
    query = "INSERT INTO quote_message (id, quote_id) VALUES (%s, %s)"
    data = (message_id, quote_id)

    # Insert the data
    insert(query, data)

    # Success!
    return True


def get_quote_id(message_id):
    """Given a numeric message ID, return ID of the associated quote"""
    if not isinstance(message_id, int):
        return False

    query = "SELECT quote_id FROM quote_message WHERE id = %s"
    data = (message_id,)

    rows = select(query, data)
    quote_id = rows[0]

    if quote_id is None:
        return False

    return quote_id[0]


def vote(ballot):
    """Vote on a quote. The single argument 'ballot' is a data structure like so:
    {
        "message_id": int
        "voter_id": {
            "id": int
            "handle": string
            "discriminator": int
        }
        "vote": int
    }
    """
    # check message id to be sure it's an integer
    if not isinstance(ballot['message_id'], int):
        return False

    # get quote ID from message ID
    quote_id = get_quote_id(ballot['message_id'])

    if not quote_id:
        return False

    # integerize vote in case someone submits a float quote vote somehow
    ballot['vote'] = int(ballot['vote'])

    # reduce votes to -1, 0, or 1 so that someone can't stuff the ballot box by submitting a
    # vote of, oh, let's say 2147483647.
    if ballot['vote'] > 1:
        ballot['vote'] = 1

    elif ballot['vote'] < -1:
        ballot['vote'] = -1

    # add voter to db so they can be referenced by the quote_vote table
    status = add_user_info(ballot['voter_id'])
    if not status:
        # something went wrong if this executes
        return False

    # The db schema contains a unique constraint preventing any user from voting more than once on the same quote,
    # so there's no need to check that here.

    # Build the query, allowing a user to update their vote (from downvote to upvote, or to 0 if so desired)
    query = "INSERT INTO quote_vote (quote_id, vote, voter) VALUES (%s, %s, %s) " \
            "ON CONFLICT ON CONSTRAINT vote_record DO UPDATE " \
            "SET vote = %s WHERE quote_vote.quote_id = %s AND quote_vote.voter = %s"
    data = (quote_id, ballot['vote'], ballot['voter_id']['id'], ballot['vote'], quote_id, ballot['voter_id']['id'])

    # Insert the data
    insert(query, data)

    # Success!
    return True

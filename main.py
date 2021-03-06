from flask import Flask, render_template, session, request, \
    copy_current_request_context
from flask_socketio import SocketIO, emit, disconnect
import jellyfish

import random

# TODO css styling
# TODO rewrite as class to get rid of global variables

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None

app = Flask(__name__)
app.static_folder = 'static'
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
wordlist = list()

with open("words.txt", "r", encoding='utf-8') as filestream:
    for line in filestream:
        wordlist = wordlist + line.split(",")

word = ""
connected_clients = {}
Schreiber = ()
Schreiber_geraten = ()
Rater = ""
Hinweise = {}
random.seed()


@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode)


@socketio.event
def disconnect_request():
    @copy_current_request_context
    def can_disconnect():
        disconnect()

    session['receive_count'] = session.get('receive_count', 0) + 1
    # for this emit we use a callback function
    # when the callback function is invoked we know that the message has been
    # received and it is safe to disconnect
    emit('my_response',
         'Disconnected!', callback=can_disconnect)
    try:
        del connected_clients[request.sid]
    except KeyError:
        pass


@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected', request.sid)


@socketio.event
def name_setzen(name):
    global connected_clients, Schreiber
    connected_clients[request.sid] = name

    emit('my_response',  "dein Name: " + connected_clients[request.sid])
    connected_clients_string = ""
    for key in connected_clients:
        connected_clients_string = connected_clients_string + connected_clients[key] + ", "
    connected_clients_string = connected_clients_string[:-2]
    emit('connected_players', connected_clients_string, broadcast=True)
    Schreiber = list(connected_clients.keys())

@socketio.event
def start():
    global Schreiber, connected_clients, Rater, word, wordlist, Schreiber_geraten
    if len(connected_clients) < 3:
        emit('my_response', "zu wenig spieler", broadcast=True)
        return

    emit('my_response' "spiel startet", broadcast=True)
    emit('input_visibility', "start_off", broadcast=True)
    word = wordlist[random.randrange(0, len(wordlist) + 1)]
    wordlist.remove(word)
    Rater = Schreiber.pop(0)
    Schreiber_geraten = Schreiber.copy()
    emit('my_response', connected_clients[Rater] + " muss raten", broadcast=True)
    for person in Schreiber:
        emit('my_response',  "das Wort ist: " + word, room=person)
        emit('input_visibility', "clue_on", room=person)

    emit('my_response', "du musst raten", room=Rater)


@socketio.event
def my_word(message):
    global Hinweise, Schreiber, Rater,Schreiber_geraten
    #session['receive_count'] = session.get('receive_count', 0) + 1
    Hinweise[request.sid] = message["data"]
    emit('input_visibility', "clue_off")

    emit('my_response', "abgegeben: " + message['data'])
    Schreiber_geraten.remove(request.sid)
    not_submitted_string = ""
    for person in Schreiber_geraten:
        not_submitted_string += (connected_clients[person]) + ", "
    not_submitted_string = not_submitted_string[:-2]
    if Schreiber_geraten:
        emit('my_response', "noch nicht abgegeben haben: " + not_submitted_string, broadcast=True)

    else:
        emit('my_response', "Hinweise gesammelt", broadcast=True)
        emit('input_visibility', "guess_on", room=Rater)

        cleaned_prompts = hinweise_checken(Hinweise.values())
        if cleaned_prompts:
            emit('my_response',  "die Hinweise sind: " + cleaned_prompts, broadcast=True)
        else:
            emit('my_response',  "die Hinweise sind: " + "keine Hinweise ??brig :(", broadcast=True)


@socketio.event
def my_guess(message):
    global word, Schreiber, Rater, Hinweise
    distance = jellyfish.damerau_levenshtein_distance(word, message["data"])
    if distance <= 2:
        emit('my_response',  "du hast: " + word + " richtig geraten", broadcast=True)
    else:
        emit('my_response',
             " leider falsch, du hast geraten:" + message["data"] + " , das wort war aber: " + word, broadcast=True)
    # emit('restart',broadcast=True)
    emit("input_visibility", "clue_off", broadcast=True)
    emit("input_visibility", "guess_off", broadcast=True)
    emit('input_visibility', "start_on", broadcast=True)
    Schreiber.append(Rater)
    Rater = ""
    Hinweise = {}


# @socketio.event
# def my_broadcast_event(message):
#     global connected_clients
#     session['receive_count'] = session.get('receive_count', 0) + 1
#     emit('my_response',
#          {'data': connected_clients[request.sid] + " sagt: " + message['data'], 'count': session['receive_count']},
#          broadcast=True)

# @socketio.event
# def connect():
#     emit('my_response', {'data': 'Connected', 'count': 0})
def hinweise_checken(raw_words):
    global word
    returnlist = list()
    raw_words = list(raw_words)
    for guess in raw_words:
        if jellyfish.damerau_levenshtein_distance(word, guess) <= 2:
            return None

    while raw_words:
        neu = True
        current_guess = raw_words.pop(0)
        for guess in raw_words:
            if jellyfish.damerau_levenshtein_distance(current_guess, guess) < 2 or current_guess in guess:
                neu = False
                raw_words.remove(guess)

        if neu:
            returnlist.append(current_guess)

    returnstring = ' '.join(returnlist)

    return returnstring


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)

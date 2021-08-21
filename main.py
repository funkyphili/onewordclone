from flask import Flask, render_template, session, request, \
    copy_current_request_context
from flask_socketio import SocketIO, emit, disconnect
import jellyfish

import random
#TODO css styling

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
         {'data': 'Disconnected!', 'count': session['receive_count']},
         callback=can_disconnect)
    try:
        del connected_clients[request.sid]
    except KeyError:
        pass


@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected', request.sid)


@socketio.event
def name_setzen(name):
    global connected_clients
    connected_clients[request.sid] = name

    emit('my_response', {'data': "dein Name: " + connected_clients[request.sid], 'count': 0})
    connected_clients_string = ""
    for key in connected_clients:
        connected_clients_string = connected_clients_string + connected_clients[key] + ", "

    emit('connected_players', connected_clients_string, broadcast=True)


@socketio.event
def start():
    global Schreiber, connected_clients, Rater, word,wordlist
    if len(connected_clients) < 3:
        emit('my_response', {'data': "zu wenig spieler", 'count': 0}, broadcast=True)
        return

    emit('my_response', {'data': "spiel startet", 'count': 0}, broadcast=True)
    emit('input_visibility', "start_off", broadcast=True)
    word = wordlist[random.randrange(0, len(wordlist) + 1)]
    wordlist.remove(word)
    Schreiber = list(connected_clients.keys())
    random.shuffle(Schreiber)
    Rater = Schreiber.pop()

    for person in Schreiber:
        emit('my_response', {'data': "das Wort ist: " + word, 'count': 0}, room=person)
        emit('input_visibility', "clue_on", room=person)

    emit('my_response', {'data': "du musst raten", 'count': 0}, room=Rater)


@socketio.event
def my_word(message):
    global Hinweise, Schreiber, Rater
    string = ""
    session['receive_count'] = session.get('receive_count', 0) + 1
    Hinweise[request.sid] = message["data"]
    # print(Hinweise)
    emit('my_response',
         {'data': "abgegeben " + message['data'], 'count': session['receive_count']})
    emit('input_visibility', "clue_off")
    #print(len(Hinweise))
    #print(len(Schreiber))
    if len(Hinweise) == len(Schreiber):
        emit('my_response', {'data': "Hinweise gesammelt", 'count': 0}, broadcast=True)
        emit('input_visibility', "guess_on", room=Rater)


        emit('my_response', {'data': "die Hinweise sind: " + hinweise_checken(Hinweise.values()), 'count': 0},
                 broadcast=True)

        # emit('my_response', {'data': "die Hinweise sind: " + "keine Hinweise Übrig :(", 'count': 0},
        #          broadcast=True)


@socketio.event
def my_guess(message):
    global word, Schreiber, Rater, Hinweise
    distance = jellyfish.damerau_levenshtein_distance(word, message["data"])
    if distance <= 2:
        emit('my_response', {'data': "du hast: " + word + " richtig geraten", 'count': 0}, broadcast=True)
    else:
        emit('my_response', {'data': " leider falsch, du hast geraten:" + message["data"] +  " , das wort war aber: " + word, 'count': 0}, broadcast=True)
    # emit('restart',broadcast=True)
    emit("input_visibility", "clue_off", broadcast=True)
    emit("input_visibility", "guess_off", broadcast=True)
    emit('input_visibility', "start_on", broadcast=True)
    Schreiber = ()
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

    neu = True
    while raw_words:
        neu = True
        current_guess = raw_words.pop(0)
        for guess in raw_words:
            if jellyfish.damerau_levenshtein_distance(current_guess, guess) < 2:
                neu = False
                raw_words.remove(guess)

        if neu:
            returnlist.append(current_guess)

    returnstring = ' '.join(returnlist)

    return returnstring


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)

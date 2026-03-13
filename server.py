from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Valthera Community BOT 3 is running."

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

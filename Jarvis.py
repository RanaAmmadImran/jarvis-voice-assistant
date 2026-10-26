"""
Simple JARVIS (girl voice) - made with Python only

Install once (in terminal / command prompt):
    pip install SpeechRecognition pyttsx3 pywhatkit wikipedia pyaudio

Run:
    python jarvis.py
"""

import datetime
import webbrowser

import pyttsx3
import pywhatkit
import speech_recognition as sr
import wikipedia

# ---------- 1. VOICE (girl voice) ----------
engine = pyttsx3.init()
voices = engine.getProperty("voices")

# Pick a female voice (on Windows, "Zira" is the female voice)
for v in voices:
    if "zira" in v.name.lower() or "female" in v.name.lower():
        engine.setProperty("voice", v.id)
        break
else:
    if len(voices) > 1:
        engine.setProperty("voice", voices[1].id)  # usually female

engine.setProperty("rate", 175)  # speaking speed


def speak(text):
    print("Jarvis:", text)
    engine.say(text)
    engine.runAndWait()


# ---------- 2. LISTEN (your microphone) ----------
recognizer = sr.Recognizer()


def listen():
    with sr.Microphone() as mic:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(mic, duration=0.5)
        audio = recognizer.listen(mic, phrase_time_limit=7)
    try:
        text = recognizer.recognize_google(audio).lower()
        print("You:", text)
        return text
    except Exception:
        return ""


# ---------- 3. CONTACTS (put your own numbers with country code) ----------
contacts = {
    "ali": "+923001234567",
    "mama": "+923007654321",
}


# ---------- 4. WHATSAPP ----------
def send_whatsapp(name, message):
    number = contacts.get(name)
    if not number:
        speak(f"I don't have {name} in my contacts.")
        return
    speak(f"Sending message to {name}")
    # Opens WhatsApp Web in browser (you must be logged in) and sends
    pywhatkit.sendwhatmsg_instantly(number, message, wait_time=15, tab_close=True)
    speak("Message sent.")


# ---------- 5. COMMANDS ----------
def run_command(cmd):
    # Greeting
    if cmd in ("hi", "hello", "hey jarvis", "hello jarvis"):
        speak("Hello! How can I help you?")

    # Time and date
    elif "time" in cmd:
        speak("The time is " + datetime.datetime.now().strftime("%I:%M %p"))
    elif "date" in cmd:
        speak("Today is " + datetime.datetime.now().strftime("%d %B %Y"))

    # WhatsApp: say "send message to ali hello how are you"
    elif cmd.startswith("send message to"):
        rest = cmd.replace("send message to", "").strip()
        parts = rest.split(" ", 1)
        if len(parts) == 2:
            send_whatsapp(parts[0], parts[1])
        else:
            speak("Please say the name and the message.")

    # Search and tell the answer: "search python programming"
    elif cmd.startswith("search"):
        topic = cmd.replace("search", "").strip()
        speak(f"Searching {topic}")
        try:
            answer = wikipedia.summary(topic, sentences=2)
            speak(answer)
        except Exception:
            speak("I could not find a short answer, opening Google.")
            webbrowser.open("https://www.google.com/search?q=" + topic)

    # Play on YouTube: "play believer"
    elif cmd.startswith("play"):
        song = cmd.replace("play", "").strip()
        speak(f"Playing {song}")
        pywhatkit.playonyt(song)

    # Open websites
    elif "open youtube" in cmd:
        webbrowser.open("https://youtube.com")
        speak("Opening YouTube")
    elif "open google" in cmd:
        webbrowser.open("https://google.com")
        speak("Opening Google")

    # Stop
    elif cmd in ("exit", "stop", "bye", "goodbye"):
        speak("Goodbye!")
        return False

    elif cmd:
        speak("Sorry, I did not understand that.")

    return True


# ---------- 6. MAIN LOOP ----------
speak("Jarvis is ready.")
running = True
while running:
    command = listen()
    if command:
        running = run_command(command)
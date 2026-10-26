import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import webbrowser

import speech_recognition as sr

# so Urdu letters can be printed without crashing
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ===== 1. VOICE (Windows speech for English, girl / boy switch) =====
def run_powershell(script, text=""):
    env = dict(os.environ)
    env["JULLIE_TEXT"] = text
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )


def get_voice_names():
    r = run_powershell(
        "Add-Type -AssemblyName System.Speech; "
        "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() "
        "| ForEach-Object { $_.VoiceInfo.Name }"
    )
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


voice_names = get_voice_names()
print("Voices found on this laptop:", voice_names)

FEMALE_NAMES = ("zira", "hazel", "susan", "female", "samantha")
MALE_NAMES = ("david", "mark", "george", "male", "james")

current_voice = None
current_gender = "girl"
language = "english"


def set_voice(gender):
    global current_voice
    names = FEMALE_NAMES if gender == "girl" else MALE_NAMES
    for name in voice_names:
        if any(n in name.lower() for n in names):
            current_voice = name
            return True
    return False


set_voice("girl")

# Urdu voice already installed in Windows (works offline), if any
windows_urdu_voice = None
for name in voice_names:
    if any(k in name.lower() for k in ("urdu", "uzma", "asad")):
        windows_urdu_voice = name
        break


def has_urdu(text):
    return bool(re.search(r"[\u0600-\u06FF]", text))


def speak_windows(text, voice):
    select = f"$s.SelectVoice('{voice}'); " if voice else ""
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"{select}$s.Volume = 100; $s.Speak($env:JULLIE_TEXT)"
    )
    run_powershell(script, text)


def speak_urdu_online(text):
    """Urdu girl voice = Uzma, boy voice = Asad (needs internet)."""
    import asyncio

    import edge_tts
    import pygame

    voice = "ur-PK-UzmaNeural" if current_gender == "girl" else "ur-PK-AsadNeural"
    path = os.path.join(tempfile.gettempdir(), "jullie_urdu.mp3")
    asyncio.run(edge_tts.Communicate(text, voice).save(path))
    pygame.mixer.init()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(100)
    pygame.mixer.music.unload()
    pygame.mixer.quit()


def speak(text):
    print("Jullie:", text)
    try:
        if has_urdu(text):
            try:
                speak_urdu_online(text)  # best Urdu voice (internet)
            except Exception:
                if windows_urdu_voice:
                    speak_windows(text, windows_urdu_voice)  # offline voice
                else:
                    print("(Urdu voice needs internet, or an Urdu voice in Windows.)")
            return
        speak_windows(text, current_voice)
    except Exception as e:
        print("Voice error:", e)


def reply(text, urdu=None):
    """Say it in the language you chose. Pass your own Urdu text if you have it."""
    if language == "urdu":
        ur = urdu or translate(text, "urdu")
        if ur:
            speak(ur)
            return
        print("(Urdu translation is not installed, so I will speak English.)")
    speak(text)


# ===== 2. LISTEN (online first, offline Vosk if no internet) =====
recognizer = sr.Recognizer()


def listen():
    with sr.Microphone() as mic:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(mic, duration=0.5)
        audio = recognizer.listen(mic, phrase_time_limit=7)
    try:
        text = recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return ""
    except Exception:
        try:
            text = json.loads(recognizer.recognize_vosk(audio)).get("text", "")
        except Exception:
            print("Offline model not found. Put the Vosk folder named 'model' next to this file.")
            return ""
    text = text.lower().strip()
    print("You:", text)
    return text


# ===== 3. TRANSLATION (offline, Argos) =====
def translate(text, to_lang):
    try:
        import argostranslate.translate as t
    except ImportError:
        return None
    try:
        src, dst = ("en", "ur") if to_lang == "urdu" else ("ur", "en")
        out = []
        for part in text.split("\n"):
            part = part.strip()
            if part:
                out.append(t.translate(part, src, dst))
        return "\n".join(out)
    except Exception as e:
        print("Translation error:", e)
        return None


# ===== 4. DOCUMENTS (txt, pdf, docx) =====
document_text = ""


def pick_and_read_document():
    from tkinter import Tk, filedialog

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Choose a document",
        filetypes=[("Documents", "*.txt *.pdf *.docx")],
    )
    root.destroy()
    if not path:
        return ""

    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    if ext == ".pdf":
        from pypdf import PdfReader

        return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    if ext == ".docx":
        import docx

        return "\n".join(p.text for p in docx.Document(path).paragraphs)
    return ""


def short_summary(text, sentences=3):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:sentences])


# ===== 5. LAPTOP CONTROL (offline, Windows) =====
def laptop_control(cmd):
    import pyautogui

    if "whatsapp" in cmd and any(w in cmd for w in ("open", "kholo", "karo", "start", "chalao")):
        reply("Opening WhatsApp", "واٹس ایپ کھولا جا رہا ہے۔")
        try:
            os.startfile("whatsapp:")  # WhatsApp desktop app
        except Exception:
            webbrowser.open("https://web.whatsapp.com")  # if no desktop app
        return True

    if "open notepad" in cmd:
        subprocess.Popen("notepad"); reply("Opening Notepad", "نوٹ پیڈ کھولا جا رہا ہے۔")
    elif "open word" in cmd or "open microsoft word" in cmd:
        os.system("start winword"); reply("Opening Microsoft Word", "مائیکروسافٹ ورڈ کھولا جا رہا ہے۔")
    elif "open excel" in cmd:
        os.system("start excel"); reply("Opening Microsoft Excel", "مائیکروسافٹ ایکسل کھولا جا رہا ہے۔")
    elif "open powerpoint" in cmd:
        os.system("start powerpnt"); reply("Opening PowerPoint", "پاور پوائنٹ کھولا جا رہا ہے۔")
    elif "open calculator" in cmd:
        subprocess.Popen("calc"); reply("Opening Calculator", "کیلکولیٹر کھولا جا رہا ہے۔")
    elif "open paint" in cmd:
        subprocess.Popen("mspaint"); reply("Opening Paint", "پینٹ کھولا جا رہا ہے۔")
    elif "open chrome" in cmd:
        os.system("start chrome"); reply("Opening Chrome", "کروم کھولا جا رہا ہے۔")
    elif "open file explorer" in cmd or "open my computer" in cmd:
        subprocess.Popen("explorer"); reply("Opening File Explorer", "فائل ایکسپلورر کھولا جا رہا ہے۔")
    elif "volume up" in cmd:
        for _ in range(5): pyautogui.press("volumeup")
        reply("Volume increased", "آواز بڑھا دی گئی۔")
    elif "volume down" in cmd:
        for _ in range(5): pyautogui.press("volumedown")
        reply("Volume decreased", "آواز کم کر دی گئی۔")
    elif "mute" in cmd:
        pyautogui.press("volumemute"); reply("Muted", "آواز بند کر دی گئی۔")
    elif "screenshot" in cmd:
        name = "screenshot_" + datetime.datetime.now().strftime("%H%M%S") + ".png"
        pyautogui.screenshot(name); reply("Screenshot saved", "اسکرین شاٹ محفوظ ہو گیا۔")
    elif "minimize all" in cmd or "show desktop" in cmd:
        pyautogui.hotkey("win", "d"); reply("Done", "ہو گیا۔")
    elif ("lock" in cmd and "laptop" in cmd) or cmd == "lock screen":
        reply("Locking the laptop", "لیپ ٹاپ لاک کیا جا رہا ہے۔")
        os.system("rundll32.exe user32.dll,LockWorkStation")
    elif "cancel shutdown" in cmd:
        os.system("shutdown /a"); reply("Shutdown cancelled", "شٹ ڈاؤن منسوخ کر دیا گیا۔")
    elif "shutdown" in cmd or "shut down" in cmd:
        reply("Laptop will shut down in 30 seconds. Say cancel shutdown to stop.",
              "لیپ ٹاپ تیس سیکنڈ میں بند ہو جائے گا۔ روکنے کے لیے کینسل شٹ ڈاؤن کہیں۔")
        os.system("shutdown /s /t 30")
    elif "restart" in cmd:
        reply("Laptop will restart in 30 seconds. Say cancel shutdown to stop.",
              "لیپ ٹاپ تیس سیکنڈ میں دوبارہ چالو ہوگا۔ روکنے کے لیے کینسل شٹ ڈاؤن کہیں۔")
        os.system("shutdown /r /t 30")
    else:
        return False
    return True


# ===== 6. WHATSAPP SEND (needs internet) =====
contacts = {
    "ali": "+923001234567",
    "mama": "+923007654321",
}


def send_whatsapp(name, message):
    number = contacts.get(name)
    if not number:
        reply(f"I don't have {name} in my contacts.", f"{name} میرے رابطوں میں نہیں ہے۔")
        return
    try:
        import pywhatkit

        reply(f"Sending message to {name}", f"{name} کو پیغام بھیجا جا رہا ہے۔")
        pywhatkit.sendwhatmsg_instantly(number, message, wait_time=15, tab_close=True)
        reply("Message sent.", "پیغام بھیج دیا گیا۔")
    except Exception:
        reply("I need internet to send WhatsApp messages.", "واٹس ایپ پیغام کے لیے انٹرنیٹ چاہیے۔")


# ===== 7. CALCULATOR =====
NUMBER_WORDS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
                "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"}


def try_calculate(cmd):
    """Handles: 'calculate 3 plus 4', 'add 3 and 4 in calculator', 'what is 10 times 5'"""
    text = cmd
    for w, d in NUMBER_WORDS.items():
        text = re.sub(rf"\b{w}\b", d, text)
    if re.search(r"\badd\b", text):
        text = re.sub(r"\band\b", "+", text)
    for a, b in (("multiplied by", "*"), ("divided by", "/"), ("plus", "+"), ("minus", "-"),
                 ("times", "*"), ("multiply", "*"), ("into", "*"), ("divide", "/"), ("x", "*")):
        text = re.sub(rf"\b{a}\b", b, text)

    expr = "".join(re.findall(r"\d+\.?\d*|[+\-*/]", text))
    if not re.fullmatch(r"\d+\.?\d*([+\-*/]\d+\.?\d*)+", expr):
        return False

    try:
        result = eval(expr)  # safe: expr contains only numbers and + - * /
    except ZeroDivisionError:
        reply("You cannot divide by zero.", "صفر سے تقسیم نہیں ہو سکتی۔")
        return True
    if isinstance(result, float):
        result = int(result) if result.is_integer() else round(result, 4)

    if "calculator" in cmd:
        import pyautogui

        subprocess.Popen("calc")
        time.sleep(3)  # wait for Calculator to open
        pyautogui.write(expr, interval=0.1)
        pyautogui.press("enter")

    reply(f"The answer is {result}", f"جواب {result} ہے۔")
    return True


# ===== 8. USER NAME (asked the first time, then remembered) =====
NAME_FILE = "user_name.txt"
user_name = ""


def get_user_name(force=False):
    global user_name
    if not force and os.path.exists(NAME_FILE):
        with open(NAME_FILE, encoding="utf-8") as f:
            user_name = f.read().strip()
        if user_name:
            return

    user_name = ""
    for _ in range(3):
        speak("Hello, I am Jullie. What is your name?")
        heard = listen()
        for p in ("my name is", "i am", "i'm", "this is", "it's", "name is", "call me"):
            heard = heard.replace(p, "")
        heard = heard.strip().title()
        if heard:
            user_name = heard
            break

    if not user_name:
        user_name = input("I could not hear you. Please type your name: ").strip() or "Friend"

    with open(NAME_FILE, "w", encoding="utf-8") as f:
        f.write(user_name)


# ===== 9. COMMANDS =====
def run_command(cmd):
    global document_text, language, current_gender
    words = cmd.split()

    if any(w in words for w in ("hi", "hello", "hey")):
        reply(f"Hello {user_name}! I am Jullie. How can I help you?",
              f"ہیلو {user_name}! میں جولی ہوں۔ میں آپ کی کیسے مدد کروں؟")
    elif "change my name" in cmd:
        get_user_name(force=True)
        reply(f"Okay {user_name}, I will remember your name.",
              f"ٹھیک ہے {user_name}، میں آپ کا نام یاد رکھوں گی۔")
    elif "my name" in cmd:
        reply(f"Your name is {user_name}.", f"آپ کا نام {user_name} ہے۔")
    elif "your name" in cmd or "who are you" in cmd:
        reply("My name is Jullie. I am your personal assistant.",
              "میرا نام جولی ہے۔ میں آپ کی ذاتی اسسٹنٹ ہوں۔")

    # ---- voice ----
    elif "girl voice" in cmd or "female voice" in cmd:
        current_gender = "girl"
        set_voice("girl")
        reply("Okay, I am speaking in girl voice now.", "ٹھیک ہے، اب لڑکی کی آواز میں بات ہوگی۔")
    elif "boy voice" in cmd or "male voice" in cmd:
        current_gender = "boy"
        set_voice("boy")
        reply("Okay, I am speaking in boy voice now.", "ٹھیک ہے، اب لڑکے کی آواز میں بات ہوگی۔")

    # ---- language ----
    elif "urdu" in cmd:
        language = "urdu"
        if document_text and any(k in cmd for k in ("translate", "explain", "summar", "read")):
            if "summar" in cmd or "explain" in cmd:
                reply(short_summary(document_text))
            else:
                reply(document_text[:1500])
        else:
            reply("Okay, I will speak Urdu now.", "ٹھیک ہے، اب ہم اردو میں بات کریں گے۔")
    elif "english" in cmd:
        language = "english"
        reply("Okay, I will speak English.")

    # ---- documents ----
    elif "open document" in cmd or "read document" in cmd or "load document" in cmd:
        reply("Please choose your document.", "براہ کرم اپنی دستاویز منتخب کریں۔")
        document_text = pick_and_read_document()
        if document_text.strip():
            n = len(document_text.split())
            reply(f"Document loaded. It has {n} words.", f"دستاویز کھل گئی۔ اس میں {n} الفاظ ہیں۔")
        else:
            reply("I could not read any text from that file.", "اس فائل سے کوئی متن نہیں پڑھا جا سکا۔")
    elif "summar" in cmd or "explain" in cmd:
        if not document_text:
            reply("Please say open document first.", "پہلے ڈاکیومنٹ کھولنے کو کہیں۔")
        else:
            reply(short_summary(document_text))
    elif "read it" in cmd or "read the document" in cmd:
        if not document_text:
            reply("Please say open document first.", "پہلے ڈاکیومنٹ کھولنے کو کہیں۔")
        else:
            reply(document_text[:1500])

    # ---- calculator ----
    elif try_calculate(cmd):
        pass

    # ---- time / date ----
    elif "time" in cmd:
        t = datetime.datetime.now().strftime("%I:%M %p")
        reply(f"The time is {t}", f"ابھی وقت {t} ہے۔")
    elif "date" in cmd:
        d = datetime.datetime.now().strftime("%d %B %Y")
        reply(f"Today is {d}", f"آج کی تاریخ {d} ہے۔")

    # ---- WhatsApp send ----
    elif cmd.startswith("send message to"):
        rest = cmd.replace("send message to", "").strip()
        parts = rest.split(" ", 1)
        if len(parts) == 2:
            send_whatsapp(parts[0], parts[1])
        else:
            reply("Please say the name and the message.", "براہ کرم نام اور پیغام بتائیں۔")

    # ---- search (internet) ----
    elif cmd.startswith("search"):
        topic = cmd.replace("search", "").strip()
        reply(f"Searching {topic}", f"{topic} تلاش کیا جا رہا ہے۔")
        try:
            import wikipedia

            reply(wikipedia.summary(topic, sentences=2))
        except Exception:
            reply("I need internet for searching. Opening Google if you are online.",
                  "تلاش کے لیے انٹرنیٹ چاہیے۔")
            webbrowser.open("https://www.google.com/search?q=" + topic)

    elif cmd.startswith("play"):
        song = cmd.replace("play", "").strip()
        try:
            import pywhatkit

            reply(f"Playing {song}", f"{song} چلایا جا رہا ہے۔")
            pywhatkit.playonyt(song)
        except Exception:
            reply("I need internet to play from YouTube.", "یوٹیوب کے لیے انٹرنیٹ چاہیے۔")

    elif "open youtube" in cmd:
        webbrowser.open("https://youtube.com"); reply("Opening YouTube", "یوٹیوب کھولا جا رہا ہے۔")
    elif "open google" in cmd:
        webbrowser.open("https://google.com"); reply("Opening Google", "گوگل کھولا جا رہا ہے۔")

    elif cmd in ("exit", "stop", "bye", "goodbye"):
        reply("Goodbye!", "خدا حافظ!")
        return False

    elif laptop_control(cmd):
        pass

    elif cmd:
        reply("Sorry, I did not understand that.", "معاف کیجیے، بات سمجھ نہیں آئی۔")

    return True


# ===== 10. MAIN LOOP =====
get_user_name()
speak(f"Nice to meet you, {user_name}. I am ready.")
running = True
while running:
    command = listen()
    for name in ("jullie", "julie"):
        command = command.replace(name, "").strip()
    if command:
        running = run_command(command)
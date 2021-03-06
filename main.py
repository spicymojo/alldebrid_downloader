import asyncio
import time
from getpass import getpass

from telethon.errors import SessionPasswordNeededError

from api.alldebrid import Alldebrid
from datetime import datetime
from resources.config import AlldebridAPI, TelegramApi
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import ImportChatInviteRequest
import re

import requests, os

errors = ""
downloaded_files = []
NEWSPAPER = 'NEWSPAPER'
MAGAZINE = 'MAGAZINE'

# Class Message
class Message:
    def __init__(self, type, filename,url, date):
        self.type = type
        self.filename = filename.strip()
        self.url = url
        self.date = date

    def get_message(self):
        return self.filename + "," + self.date + "," + self.url

    def get_type(self):
        return self.type

    def get_dated_filename(self):
        return self.filename + ", " + self.date

    def print(self):
        return self.get_message()

# Telegram - Configuration and connection
def start_telegram():
    client = tlg_connect(api_id, api_hash, phone_number)
    return client

def get_telegram_messages(client, chat, messages_limit):
    return client.get_messages(chat, limit=messages_limit)

def get_sended_newspapers_from_today(client, chat, messages_limit):
    filtered_newspapers = []
    messages = client.get_messages(chat, limit=messages_limit)
    for message in messages:
        if (is_today(message.date) and message.file is not None):
            filtered_newspapers.append(message.file.name.split(",")[0].strip())
    return filtered_newspapers

def get_sended_magazines(client, magazines_chat, magazines_chat_limit):
    filtered_magazines = []
    telegram_sended_magazines = get_telegram_messages(client, magazines_chat, magazines_chat_limit)
    for magazine in telegram_sended_magazines:
        if (magazine.file is not None):
            filtered_magazines.append(magazine.file.name.split(",")[0].strip())
    return filtered_magazines

def wait_for_code(client):
    code = input('Enter the code you just received: ')
    try:
        self_user = client.sign_in(code=code)
    except Exception:
        pw = getpass('Two step verification is enabled. Please enter your password: ')
        self_user = client.sign_in(password=pw)
        if self_user is None:
            return None

def tlg_connect(api_id, api_hash, phone_number):
    print('Trying to connect to Telegram...')
    client = TelegramClient("Session", api_id, api_hash)
    if not client.start():
        print('Could not connect to Telegram servers.')
        return None
    else:
        if not client.is_user_authorized():
            print('Session file not found. This is the first run, sending code request...')
            client.sign_in(phone_number)
            client = wait_for_code(client)

    print('Sign in success.')
    print()
    return client

# Telegram - Get messages
def append_file_message(file_list, file_type, msg, message_date):
    if file_type == MAGAZINE:
        formatted_msg = get_formatted_message(msg, "#revistas ")
        file_list.append(build_file_message(msg, MAGAZINE, formatted_msg, message_date))
    else:
        formatted_msg = get_formatted_message(msg, "#diarios ")
        file_list.append(build_file_message(msg, NEWSPAPER, formatted_msg, message_date))


def get_links_from_telegram(client, source_chat):
    print("Getting links from Telegram...")
    files = []

    messages_list = get_telegram_messages(client, source_chat, source_chat_limit)

    for message in messages_list:
        try:
            if (is_today(message.date)):
                msg = message.raw_text
                if msg is not None and "@" not in msg:
                    msg = message.message.split("\n")
                    wanted, file_type = we_want(msg)
                    if wanted:
                        append_file_message(files, file_type, msg, message.date)
        except TypeError as e:
            print("Error processing one of the messages:\n " + e)

    # Return the messages data list
    if (len(files)) != 0:
        print(str(len(files)) + " newspapers and magazines found")
    return files

# Telegram - Chat entities
def get_chat_entity(chat_list, chat_name):
    for chat in chat_list:
        if chat_name in chat.name:
            return chat.id

# Telegram - Find chats
def find_chat_entities(client):
    chat_list = client.iter_dialogs()
    newspapers_chat = get_chat_entity(chat_list, newspapers_chat_name)
    magazines_chat = get_chat_entity(chat_list, magazines_chat_name)
    return newspapers_chat, magazines_chat

# Telegram - Check sended files
def get_sended_files(client, newspapers_chat,magazines_chat):
    print("Obtaining already sended files...")
    telegram_sended_newspapers = get_sended_newspapers_from_today(client, newspapers_chat, newspapers_chat_limit)
    telegram_sended_magazines = get_sended_magazines(client, magazines_chat, magazines_chat_limit)

    return telegram_sended_newspapers, telegram_sended_magazines

# Telegram - Send files and messages
def send_day_message(tg_client, newspapers_chat):
    messages = tg_client.get_messages(newspapers_chat, limit=newspapers_chat_limit)
    for message in messages:
        if is_today(message.date) and "#" in message.message:
            return;
    tg_client.send_message(newspapers_chat, "# " + str(pretty_print_date(datetime.now())))


def send_files(tg_client, newspapers_chat, magazines_chat):
    print("\nStart sending files to Telegram...")
    print(str(len(downloaded_files)) + " files to send")
    sended_files = []

    send_day_message(tg_client, newspapers_chat)

    for file in downloaded_files:
        if file.filename not in sended_files:
            try:
                if file.type == NEWSPAPER:
                    tg_client.send_file(newspapers_chat, file.filename, force_document=True)
                elif file.type == MAGAZINE:
                    tg_client.send_file(magazines_chat, file.filename, force_document=True)
                sended_files.append(file.filename)
                print("Just sended " + file.filename)
            except Exception:
                print("Error while sending " + file.filename)

    print("Files sended!\n")

def send_message_to_admin(tg_client):
    newspapers = str(len(downloaded_files))

    file_list = []
    for file in downloaded_files:
        file_list.append(file.filename)

    tg_client.send_message(admin_alias,"Hello! Your bot here\n" + newspapers + " files sended to Telegram Group:\n " + str(file_list))

def send_not_new_files_message(tg_client):
    tg_client.send_message(admin_alias,"Hello! Your bot here! Nothing new on sight, so I didnt do shit")
    print("Nothing new to download, stopping")

# Date methods
def is_today(date):
    return date.day == datetime.now().day

def pretty_print_date(date):
    months = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")
    day = date.day
    month = months[date.month-1]
    current_date = "{} de {}".format(day, month)

    return current_date

# Alldebrid & Downloads
def download(files):
    print("\nConnecting to AllDebrid\n")
    alldebrid = Alldebrid()
    errors = list()
    ok = 0

    for file in files:
        http_response = alldebrid.download_link(file.url)
        file.filename = file.get_dated_filename() + ".pdf"
        if http_response["status"] != "error":
            converted_link = http_response["data"]["link"]
            file.url = converted_link

            while "  " in file.filename:
                file.filename = file.filename.replace("  "," ")

            download_file(file)
            downloaded_files.append(file)
            ok = ok + 1
        else:
            errors.append(file.filename)
    print_results(ok,errors)

def download_file(file):

    if not os.path.isfile(file.filename):
        try:
            if downloads_path != "":
                file.filename = downloads_path + "/" + file.filename
            else:
                file.filename = file.filename.replace(r"/"," ")
            print("  Downloading " + file.filename + " ...")
            open(file.filename, "wb").write(requests.get(file.url).content)
        except Exception:
            print("Error downloading " + file.filename)

# File management
def open_link_file(path):
    return open(path, "r")

def get_filenames_from_wanted_files(clean_files):
    clean_filenames = []
    for file in clean_files:
        clean_filenames.append(file.filename.strip())
    return clean_filenames


def remove_files_from_filenames(clean_files, clean_names):
    filtered_clean_files = []
    for file in clean_files:
        if file.filename in clean_names:
            filtered_clean_files.append(file)
    return filtered_clean_files


def remove_already_sended_files(files_that_we_want, sended_newspapers, sended_magazines):
    print("We want to download " + str(len(files_that_we_want)) + " files")
    print("Checking for already sended files...")
    not_filtered_files = len(files_that_we_want)
    clean_names = get_filenames_from_wanted_files(files_that_we_want)

    filtered_clean_names = []
    for name in clean_names:
        if name not in sended_newspapers and name not in sended_magazines:
            filtered_clean_names.append(name)

    files_that_we_want = remove_files_from_filenames(files_that_we_want, filtered_clean_names)
    print((str(not_filtered_files - len(files_that_we_want)) + " files already sended, so we removed them"))
    return files_that_we_want

def clean_list(files, sended_newspapers, sended_magazines):
    files_that_we_want = []
    if files:
        for f in files:
            if f is not None and f not in files_that_we_want:
                files_that_we_want.append(f)

    files_that_we_want = remove_already_sended_files(files_that_we_want, sended_newspapers, sended_magazines)
    return files_that_we_want

# Aux - Messages
def get_formatted_message(msg, key):
    return msg[0].replace(key, "")

# Find char for splitting
def find_separation_char(formatted_msg):
    char = None
    if "+" in formatted_msg:
        char = "+"
    elif "-" in formatted_msg:
        char = "-"
    elif "/" in formatted_msg:
        char = "/"
    return char

# Format date for building message
def format_date_from_message(msg):
    date = None
    if msg[0].rsplit("-")[1] is not None:
        date = msg[0].rsplit("-")[1]
    else:
        date = msg[0].rsplit("-")
    return date

# Building message for file
def build_file_message(msg, type, formatted_msg, date):
    char = find_separation_char(formatted_msg)
    title = ""
    try:
        title = formatted_msg.rsplit(char)[0]
        while char in title:
            title = formatted_msg.rsplit(char)[0]
    except Exception:
        print("Error building message" + msg[0])

    if title:
        for url in msg:
            if url_domains[0] in url:
                if (type == MAGAZINE):
                    date = format_date_from_message(msg)
                    return Message(type, title, url, date)
                return Message(type, title, url, pretty_print_date(date))


# Aux - Make decissions
def we_want(file):
    filename = file[0].split("-")[0].strip().upper()
    if filename in newspapers_filter:
        return True, NEWSPAPER
    elif filename in magazines_filter:
        return True, MAGAZINE
    return False, None

def obtain_daily_filename(filename):
    filename = str(filename + " - " + pretty_print_date(datetime.now()) + ".pdf")
    return filename

def print_results(ok, errors):
    print("\nDone! " + str(ok - len(errors)) + " files downloaded.")
    if (len(errors) > 0):
        print("Files failed: " + str(len(errors)))
        for e in errors:
            print(" * " + e)

# Files maganement
def remove_pdf_files():
    for parent, dirnames, filenames in os.walk('.'):
        for fn in filenames:
            if fn.lower().endswith('.pdf'):
                try:
                    os.remove(os.path.join(fn))
                except Exception:
                    print("Error removing file " + fn)

def count_pdf_files():
    counter = 0
    for parent, dirnames, filenames in os.walk('.'):
        for fn in filenames:
            if fn.lower().endswith('.pdf'):
                counter = counter + 1
    return counter

# Cleaning methods
def clean():
        print("Cleaning the files...")
        remove_pdf_files()
        if (count_pdf_files() == 0):
            print("Done! All clean for tomorrow!")
        else:
            print("Delete error, some files are still in the folder. Please check")


def find_pastebin_url_and_hash():
    pastebin = requests.get(pastebin_url).text
    regex = r"[-a-zA-Z0-9@:%_\+.~#?&//=]{2,256}\.[a-z]{2,4}\b(\/[-a-zA-Z0-9@:%_\+.~#?&//=]*)?"
    pastebin_urls = re.findall(regex, pastebin)
    if 2 == len(pastebin_urls):
        source_chat_url = telegram_url_prefix + pastebin_urls[1]
    else:
        source_chat_url = telegram_url_prefix + pastebin_urls[0]
    channel_hash = source_chat_url[source_chat_url.rfind('/') + 1:].replace("+","")
    return source_chat_url, channel_hash


def leave_old_channel_and_join_new_one(tg_client, chat_list):
    for chat in chat_list:
        if TelegramApi.source_chat_name in chat.name:
            try:
                tg_client.delete_dialog(chat.id)
                time.sleep(2)
                print("Deleted channel " + chat.name)
            except Exception:
                print("Cannot delete channel " + source_chat_name)

    source_chat_url, source_chat_hash = find_pastebin_url_and_hash()
    updates = tg_client(ImportChatInviteRequest(source_chat_hash))
    time.sleep(2)
    print("Joined channel " + updates.chats[0].title)
    return tg_client.get_entity(updates.chats[0].id)


def main():
    tg_client = start_telegram()
    newspapers_chat, magazines_chat = find_chat_entities(tg_client)
    chat_list = tg_client.get_dialogs()
    source_chat = leave_old_channel_and_join_new_one(tg_client, chat_list)
    files_to_download = get_links_from_telegram(tg_client, source_chat)
    if (len(files_to_download) == 0):
        print("No new files to download. Stopping")
        return;
    sended_newspapers, sended_magazines = get_sended_files(tg_client, newspapers_chat, magazines_chat)
    files_to_download = clean_list(files_to_download, sended_newspapers, sended_magazines)

    if (len(files_to_download) > 0):
        download(files_to_download)
        send_files(tg_client, newspapers_chat, magazines_chat)
        send_message_to_admin(tg_client)
        clean()
    else:
        send_not_new_files_message(tg_client)

# General config
url_domains = TelegramApi.url_domains
admin_alias = TelegramApi.admin_alias
downloads_path = AlldebridAPI.downloads_path
pastebin_url = AlldebridAPI.pastebin_url
telegram_url_prefix = AlldebridAPI.telegram_url_prefix

# Telegram
api_id = TelegramApi.api_id
api_hash = TelegramApi.api_hash
phone_number = TelegramApi.phone_number

# Source chat
source_chat_name = TelegramApi.source_chat_name
source_chat_limit = TelegramApi.source_chat_limit

# Newspapers chat
newspapers_chat_name = TelegramApi.newspapers_chat_name
newspapers_chat_limit = TelegramApi.newspapers_chat_limit
newspapers_filter = AlldebridAPI.newspapers_filter

# Magazines chat
magazines_chat_name = TelegramApi.magazines_chat_name
magazines_chat_limit = TelegramApi.magazines_chat_limit
magazines_filter = AlldebridAPI.magazines_filter

main()
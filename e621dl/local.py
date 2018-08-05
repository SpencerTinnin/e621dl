# Internal Imports
import configparser
import datetime
import os

# Personal Imports
from e621dl import constants

def make_config():
    with open('config.ini', 'wt', encoding = 'utf_8_sig') as outfile:
        outfile.write(constants.DEFAULT_CONFIG_TEXT)
        print("[i] New default config file created. Please add tag groups to this file.'")
    raise SystemExit

def get_config():
    config = configparser.ConfigParser()

    if not os.path.isfile('config.ini'):
        print("[!] No config file found.")
        make_config()

    with open('config.ini', 'rt', encoding = 'utf_8_sig') as infile:
        config.read_file(infile)

    return config

def get_date(days_to_check):
    ordinal_check_date = datetime.date.today().toordinal() - (days_to_check - 1)

    if ordinal_check_date < 1:
        ordinal_check_date = 1
    elif ordinal_check_date > datetime.date.today().toordinal():
        ordinal_check_date = datetime.date.today().toordinal()

    return datetime.date.fromordinal(ordinal_check_date).strftime('%Y-%m-%d')

def substitute_illegals(char):
    illegals = ['\\', ':', '*', '?', '\"', '<', '>', '|', ' ']
    return '_' if char in illegals else char

def make_path(dir_name, filename, ext):
    clean_dir_name = ''.join([substitute_illegals(char) for char in dir_name]).lower()

    if not os.path.isdir(f"downloads/{clean_dir_name}"):
        os.makedirs(f"downloads/{clean_dir_name}")

    return f"downloads/{clean_dir_name}/{filename}.{ext}"

def get_files_dict():
    filedict={}
    for root, dirs, files in os.walk('downloads/'):
        for file in files:
            filedict[file]='{}/{}'.format(root,file)
    
    return filedict

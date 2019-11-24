# Internal Imports
import configparser
import datetime
import os
import atexit
from threading import Lock, Condition
from collections import deque
import sqlite3
import pickle
from time import sleep
from functools import lru_cache
import hashlib
from threading import Thread
from shutil import get_terminal_size
from contextlib import contextmanager

# External Imports
import colorama

# Personal Imports
from . import constants

class StatPrinter(Thread):
    def __init__(self):
        super().__init__(daemon=True)

        colorama.init()
        self.messages = deque()
        self._increments = deque()
        self._show = True
        
    def run(self):
        lines = {'status' : 'Just starting',
                 'checked tag' : 'None so far',
                 'posts so far' : 0,
                 'last file downloaded' : 'None so far',
                 'current section' : 'None so far',
                 'last warning' : 'None so far',
                 'connection retries' : 0,
                 'already exist': 0,
                 'downloaded' : 0,
                 'copied' : 0,
                 'filtered' : 0,
                 'not found on e621' : 0,
                 
                 }
        while True:
            while self.messages:
                lines.update(self.messages.popleft())
            
            while self._increments:
                k, v = self._increments.popleft()
                lines[k] += v
                
            
            if not self._show:
                sleep(0.5)
                continue
                
            columns = get_terminal_size((80, 20)).columns
            self.reset_screen()
            for k,v in lines.items():
                v = 'None so far' if v == 0 else v
                print(f"{k}: {v}"[:columns])
            sleep(0.5)
            
    def reset_screen(self):
        print("\033[1J\033[1;1H", end='')

    def change_status(self, text):
        self.messages.append({'status' : text})

    def change_tag(self, text):
        self.messages.append({'checked tag' : text})
    
    def change_file(self, text):
        self.messages.append({'last file downloaded' : text})

    def change_section(self, text):
        self.messages.append({'current section' : text})
    
    def change_warning(self, text):
        self.messages.append({'last warning' : text})
    
    def increment_retries(self):
        self._increments.append(('connection retries', 1))
    
    def increment_downloaded(self):
        self._increments.append(('downloaded', 1))
    
    def increment_copied(self):
        self._increments.append(('copied' , 1))
    
    def increment_not_found(self):
        self._increments.append(('not found on e621' , 1))

    def increment_old(self):
        self._increments.append(('already exist' , 1))    

    def increment_posts(self, amount):
        self._increments.append(('posts so far' , amount))
    
    def increment_filtered(self, amount):
        self._increments.append(('filtered' , amount))
    
    
    
    def show(self, val = True):
        self._show = val
        

printer = StatPrinter()

class ActiveDownloadsSet:
    def __init__(self, max_downloads = 2):
        self._cv = Condition(lock=Lock())
        self._active_downloads = set()
        self._max_downloads = max_downloads
        
    def add_id(self, id):
        def _predicate():
            return (len(self._active_downloads) < self._max_downloads
                   and id not in self._active_downloads)
            
        with self._cv:
            self._cv.wait_for(_predicate)
            self._active_downloads.add(id)
            
    def remove_id(self, id):
        with self._cv:
            self._active_downloads.discard(id)
            self._cv.notify_all()
            
    @contextmanager
    def context_id(self, id):
        self.add_id(id)
        try:
            yield
        finally:
            self.remove_id(id)
            
class DownloadQueue:
    def __init__(self):
        self._lock = Lock()
        
        try:
            self.load()
        except:
            self.reset()

        self.aborted = False

    def popleft(self):
        with self._lock:
            return self._deque.popleft()

    def append(self, arg, maxlen=10):
        while True:
            with self._lock:
                if len(self._deque) < maxlen:
                    break
            sleep(0.0001)
        
        with self._lock:
            return self._deque.append(arg)
    
    def save(self):
        with self._lock:
            with open('download_queue.pickle', 'wb') as download_queue_file:
                pickle.dump((
                             self.last_id,
                             self.completed,
                             self._deque,
                             self.completed_deque,
                             self.config_hash
                            ), download_queue_file, protocol=pickle.HIGHEST_PROTOCOL)
                
    def load(self):
        with self._lock:
            with open('download_queue.pickle', 'rb') as download_queue_file:
                (self.last_id,
                 self.completed,
                 self._deque,
                 self.completed_deque,
                 self.config_hash) = pickle.load(download_queue_file)
    
    def last(self):
        with self._lock:
            return self._deque[-1]

    def first(self):
        with self._lock:
            return self._deque[0]
    
    def reset(self):
        self._deque=deque()
        self.completed=False
        self.last_id = 0x7F_FF_FF_FF
        self.completed_deque=deque()
        try:
            self.config_hash #checking if hash exists
        except:
            self.config_hash=None
        
    def completed_gen(self, name):
        with self._lock:
            self.completed_deque.append(name)
            self.last_id = 0x7F_FF_FF_FF
    
    def check_config_hash(self, hash):
        with self._lock:
            if self.config_hash != hash:
                if self._deque or not self.completed:
                    printer.change_warning("config.ini changed, resetting saved queue")
                self.reset()
                self.config_hash = hash
            
    def in_gens(self, name):
        with self._lock:
            return name in self.completed_deque

class PostsStorage:
    def __init__(self):
        pass
    
    def append(self, posts):
        self.cur.executemany('INSERT OR REPLACE INTO posts VALUES (?,?)',
            ( (post.id, pickle.dumps(post, protocol = pickle.HIGHEST_PROTOCOL) ) for post in posts) )
        self.conn.commit()
        
    def close(self):
        self.cur.close()
        self.conn.close()
        
    def connect(self):
        self.conn = sqlite3.connect('posts.db')
        self.cur = self.conn.cursor()
        self.cur.executescript(
            '''CREATE TABLE IF NOT EXISTS posts (
                id     INTEGER PRIMARY KEY
                               UNIQUE
                               NOT NULL,
                struct BLOB
            ) WITHOUT ROWID;'''
        )
        self.conn.commit()
        self.cur.arraysize=constants.MAX_RESULTS
        
    def gen(self, last_id, **dummy):
        self.cur.execute('SELECT struct FROM posts WHERE id<=? ORDER BY id DESC', (last_id,))
        results=[pickle.loads(result[0]) for result in self.cur.fetchmany()]
        while results:
            yield results
            results=[pickle.loads(result[0]) for result in self.cur.fetchmany()]

_handler_gc_protection = [] #in case of lambdas

#On Ctrl-C, Ctrl-Z or window close in Windows
#or terminal close, Ctrl-C or kill in posix
#we will execute close_handler
#and than immediately we will exit from python
#if no signals recieved, close_handler
#will be executed on normal exit
#or on interrupt
def save_on_exit_events(close_handler):
    del _handler_gc_protection[:]
        
    try: #posix
        from signal import signal, SIGHUP, SIGINT, SIGTERM
        SIGNAMES={ i:str(i) for i in (SIGHUP, SIGINT, SIGTERM) }

        def nixhandler(signum, frame):
            try:
                close_handler()
            finally:
                os._exit(0)

        for i in SIGNAMES:
            signal(i, nixhandler)
            
        _handler_gc_protection.append(nixhandler)
            
    except ImportError: #win. CTRL_CLOSE_EVENT not working with standart signal handling
        from ctypes import windll, WINFUNCTYPE, CFUNCTYPE
        from ctypes.wintypes import DWORD, BOOL
        
        HANDLER_TYPE=WINFUNCTYPE(BOOL, DWORD)
        
        SetConsoleCtrlHandler = windll.kernel32.SetConsoleCtrlHandler
        SetConsoleCtrlHandler.reltype = BOOL
        SetConsoleCtrlHandler.argtypes = ( HANDLER_TYPE, BOOL )
        
        CTRL_C_EVENT = 0
        CTRL_BREAK_EVENT = 1
        CTRL_CLOSE_EVENT = 2

        SIGNAMES = { CTRL_C_EVENT:'CTRL_C_EVENT', CTRL_BREAK_EVENT:'CTRL_BREAK_EVENT', CTRL_CLOSE_EVENT:'CTRL_CLOSE_EVENT'}
        
        @HANDLER_TYPE
        def winhandler(sig):
            try:
                close_handler()
            finally:
                os._exit(0)
        
        SetConsoleCtrlHandler(winhandler, 1)
        _handler_gc_protection.append(winhandler)
        
    _handler_gc_protection.append(close_handler)
    atexit.register(close_handler)

def _check(tag, tags):
    return tag in tags

def make_check_funk(source_template, tags):
    tags_screened=[tag.replace("'","\\'") for tag in tags]
    source=source_template.format(*tags_screened)
    func_str=f'def f(tags): return {source}'
    glob_dict={}
    exec(func_str,glob_dict)
    return glob_dict['f']

FORBIDDEN_TAG_CHARS=r'%,#*'
def tags_and_source_template(line):
    
    if any((c in FORBIDDEN_TAG_CHARS) for c in line):
        printer.change_warning(f"[-]: characters {FORBIDDEN_TAG_CHARS} are forbidden")
    
    line = ' ' + line # anything except '\\' is fine to prepend, actually
    new_line = [' ']
    
    for prev, cur in zip(line[:-1],line[1:]):
        if prev=='\\':
            if cur not in '|&()':
                printer.change_warning("[!]: only characters '|&()' can be screened")
                raise SystemExit
            else:
                new_line.append(cur)
        elif cur in '-|&()':
            if cur == '-' and new_line[-1] != ' ':
                new_line.append( cur ) #if '-' in a middle of a tag
            else:
                new_line.extend( (' ',cur,' ') )
        elif cur == '~' and new_line[-1]==' ':
            printer.change_warning("[!]: character '~' cannot be first character")
            raise SystemExit
        else:
            new_line.extend( cur )
                
    new_line=''.join(new_line) #making string from 'StringBuffer' list
    tokens=[token for token in new_line.split(' ') if token]
    
    tags=[token.replace('\\','') for token in tokens if token not in '-|&()']
    #source_template=[token if token in ('-|&()') else "check('{}',tags)" for token in tokens]
    #source_template = ''.join(source_template).replace('-',' not ').replace('|',' or ').replace('&',' and ')
    source_template=[token if token in ('-|&()') else "('{}' in tags)" for token in tokens]
    source_template=[' not ' if token == '-' else token for token in source_template]
    source_template=[' or ' if token == '|' else token for token in source_template]
    source_template=[' and ' if token == '&' else token for token in source_template]
    source_template = ''.join(source_template)
    
    try:
        make_check_funk(source_template, tags)(tags) # syntax validation
    except:
        source_template = source_template.replace("('{}' in tags)","{}")
        printer.show(False)
        print(f'[!] Error in condition.')
        print(f"[!] Check if all '()|&' characters are properly screened and all braces are closed")
        print(f"[!] See source:\n    {source_template}")
        raise SystemExit
    
    return source_template, tags
    


def make_config():
    with open('config.ini', 'wt', encoding = 'utf_8_sig') as outfile:
        outfile.write(constants.DEFAULT_CONFIG_TEXT)
    printer.show(False)
    print("[!] New default config file created. Please add tag groups to this file.")
    raise SystemExit

def filehash(filename):
    hash = hashlib.md5()
    with open(filename, "rb") as f:
        hash.update(f.read())
    return hash.hexdigest()

def get_config():
    config = configparser.ConfigParser()

    if not os.path.isfile('config.ini'):
        printer.change_warning("[!] No config file found.")
        make_config()

    with open('config.ini', 'rt', encoding = 'utf_8_sig') as infile:
        config.read_file(infile)

    return config, filehash('config.ini')

def get_date(days_to_check):
    ordinal_check_date = datetime.date.today().toordinal() - (days_to_check - 1)

    if ordinal_check_date < 1:
        ordinal_check_date = 1
    elif ordinal_check_date > datetime.date.today().toordinal():
        ordinal_check_date = datetime.date.today().toordinal()

    return datetime.date.fromordinal(ordinal_check_date).strftime('%Y-%m-%d')

def substitute_illegals(char):
    illegals = [':', '*', '?', '\"', '<', '>', '|']
    path_chars = ['\\', '/']
    char = '_' if char in illegals else char
    char = '/' if char in path_chars else char
    return char

def substitute_illegals_filename(filename):
    illegals = [':', '*', '?', '\"', '<', '>', '|', '\\', '/']
    return ''.join([char if char not in illegals else '_' for char in filename])

@lru_cache(maxsize=512, typed=False)
def make_new_dir(dir_name):
    clean_dir_name = ''.join([substitute_illegals(char) for char in dir_name]).lower()
    os.makedirs(f"downloads/{clean_dir_name}", exist_ok=True)
    return clean_dir_name

def make_path(dir_name, filename):
    return f"downloads/{make_new_dir(dir_name)}/{substitute_illegals_filename(filename)}"

def make_cache_folder():
    try:
        os.mkdir("cache")
    except FileExistsError:
        pass
    
def get_files_dict(have_cache):
    filedict={}
    for root, dirs, files in os.walk('downloads/'):
        for file in files:
            splitted=file.split('.')
            if splitted[-1]=='request':
                id=file.split('.')[-3] #id section
            else:
                id=file.split('.')[-2] #id section
            id=int(id)
            filedict[id]='{}/{}'.format(root,file)
    
    if have_cache:
        for root, dirs, files in os.walk('cache/'):
            for file in files:
                id=file.split('.')[-2] #id section
                id=int(id)
                filedict[id]='{}/{}'.format(root,file)
    
    return filedict
    
def validate_format(format):
    post = {i:i for i in constants.DEFAULT_SLOTS}
    try:
        dummy = format.format(**post)
    except:
        printer.change_warning(f"Invalid format: {format}")

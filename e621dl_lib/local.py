# Internal Imports
import configparser
import datetime
import os
import atexit
import sys
from threading import Thread, Lock, Condition
from collections import deque
import sqlite3
import pickle
from time import sleep
from functools import lru_cache
import hashlib
from shutil import get_terminal_size, move
from contextlib import contextmanager, suppress
import glob
import re
import json

# External Imports
import colorama
from natsort import natsorted
from atomicwrites import atomic_write, replace_atomic

# Personal Imports
from . import constants

class StatPrinter(Thread):
    def __init__(self):
        super().__init__(daemon=True)

        colorama.init()
        self.messages = deque()
        self._increments = deque()
        self._show = True
        self._is_running = True
        
        self.lines = {'status' : 'Just starting',
                      'checked tag' : 'None so far',
                      'current config' : 'None so far',
                      'current section' : 'None so far',
                      'recent warning' : 'None so far',
                      'recent file downloaded' : 'None so far',
                      'connection retries' : 0,
                      'posts so far' : 0,
                      'already exist': 0,
                      'downloaded' : 0,
                      'copied' : 0,
                      'filtered' : 0,
                      'not found on e621' : 0,
                      }

    def stop(self):
        self._is_running = False
        
    def step(self):
        while self.messages:
            self.lines.update(self.messages.popleft())
        
        while self._increments:
            k, v = self._increments.popleft()
            self.lines[k] += v
            
        
        if not self._show:
            return
            
        columns = get_terminal_size((80, 20)).columns
        self.reset_screen()
        for k,v in self.lines.items():
            v = 'None so far' if v == 0 else v
            print(f"{k}: {v}"[:columns])

    def run(self):

        while self._is_running:
            self.step()
            sleep(0.5)
           
    def reset_screen(self):
        print("\033[1J\033[1;1H", end='')

    def change_status(self, text):
        self.messages.append({'status' : text})

    def change_tag(self, text):
        self.messages.append({'checked tag' : text})
    
    def change_file(self, text):
        self.messages.append({'recent file downloaded' : text})

    def change_config(self, text):
        self.messages.append({'current config' : text})
    
    def change_section(self, text):
        self.messages.append({'current section' : text})
    
    def change_warning(self, text):
        self.messages.append({'recent warning' : text})
    
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
            sleep(0.02)
        
        with self._lock:
            return self._deque.append(arg)
    
    def save(self):
        with self._lock:
            with atomic_write('download_queue.pickle', mode='wb', overwrite=True) as download_queue_file:
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
        
    def is_reset(self):
        return self.last_id == 0x7F_FF_FF_FF
       
    def completed_gen(self, name):
        with self._lock:
            self.completed_deque.append(name)
            self.last_id = 0x7F_FF_FF_FF
    
    def check_config_hash(self, hash):
        with self._lock:
            if self.config_hash != hash:
                self.reset()
                self.config_hash = hash
            
    def in_gens(self, name):
        with self._lock:
            return name in self.completed_deque

class ConfigQueue:
    def __init__(self):
        #Because we can 
        self._lock = Lock()
        try:
            self.load()
        except:
            self.reset()

    def save(self):
        with self._lock:
            with atomic_write('config_queue.pickle', mode='wb', overwrite=True) as config_queue_file:
                pickle.dump((
                             self.config_set,
                             self.completed_set,
                             self.reset_filedb,
                            ), config_queue_file, protocol=pickle.HIGHEST_PROTOCOL)
                
    def load(self):
        with self._lock:
            with open('config_queue.pickle', 'rb') as config_queue_file:
                (self.config_set,
                 self.completed_set,
                 self.reset_filedb,) = pickle.load(config_queue_file)

    def reset(self):
        with self._lock:
            self.config_set=set()
            self.completed_set=set()
            self.reset_filedb = True
        
    def change_if_not_same(self, new_set):
        with self._lock:
            if new_set != self.config_set:
                self.config_set=new_set
                self.completed_set=set()
                self.reset_filedb = True
        
    def reset_if_complete(self):
        with self._lock:
            if self.config_set == self.completed_set:
                self.completed_set = set()
                self.reset_filedb = True
    
    def add(self, config):
        with self._lock:
            self.completed_set.add(config)
            
    def get_remaining(self):
        with self._lock:
            return natsorted(self.config_set - self.completed_set)

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
        self.cur.arraysize= constants.MAX_RESULTS_OFFLINE
        
    def gen(self, last_id, **dummy):
        self.cur.execute('SELECT struct FROM posts WHERE id<=? ORDER BY id DESC', (last_id,))
        results=[pickle.loads(result[0]) for result in self.cur.fetchmany()]
        #TODO: recreate days_ago based on created_at
        while results:
            yield results
            results=[pickle.loads(result[0]) for result in self.cur.fetchmany()]

class PathesStorage:
    def __init__(self):
        self.conn = sqlite3.connect('files.db', isolation_level=None)
        self.cur = self.conn.cursor()
    
    def begin(self):
        self.cur.execute("BEGIN;")        
    
    def add_pathes(self, directories, filename):
        #self.cur.execute("BEGIN TRANSACTION;")
        for directory in directories:
            filepath = self.make_path(directory, filename)
            self.cur.execute('INSERT OR REPLACE INTO new_files VALUES (?);', (filepath,))
    
    def add_all_time_downloaded(self, directories, filename):
        for directory in directories:
            filepath = self.make_path(directory, filename)
            self.cur.execute('INSERT OR REPLACE INTO downloaded VALUES (?);', (filepath,))
    
    def commit(self):
        self.cur.execute("COMMIT;")
    
    @lru_cache(maxsize=None, typed=False)
    def make_new_dir(self, dir_name):
        return ''.join([substitute_illegals(char) for char in dir_name]).lower().replace('\\','/')

    def make_path(self, dir_name, filename):
        return f"downloads/{self.make_new_dir(dir_name)}/{substitute_illegals_filename(filename)}"

    def remove_old(self):
        self.cur.execute('''
            SELECT fullpath FROM old_files
            EXCEPT
            SELECT fullpath FROM new_files;''')
        for (filename, ) in self.cur:
            with suppress(FileNotFoundError):
                os.remove(filename)

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
    with open('configs/config.ini', 'wt', encoding = 'utf_8_sig') as outfile:
        outfile.write(constants.DEFAULT_CONFIG_TEXT)
    printer.stop()
    printer.join()
    printer.reset_screen()
    print("[!] New default config file created in folder 'configs'.")
    print("Please add tag groups to this file.")
    print("You can add additional config files,")
    print("they will be processed in natural order:")
    print("https://en.wikipedia.org/wiki/Natural_sort_order")
    sys.exit()

def make_pools_config():
    if os.path.exists('pools.ini'):
        return
    with open('pools.ini', 'wt', encoding = 'utf_8_sig') as outfile:
        outfile.write(constants.DEFAULT_POOLS_CONFIG)
    printer.stop()
    printer.join()
    printer.reset_screen()
    print("[!] You selected to download pools in one of your configs")
    print("But there is no pools.ini template")
    print("The file was created in a root folder of e621dl")
    print("Please edit it as you see fit and restart the app")
    sys.exit()

def filehash(filename):
    hash = hashlib.md5()
    with open(filename, "rb") as f:
        hash.update(f.read())
    return hash.hexdigest()

def get_configs():
    if not os.path.isdir('configs'):
        os.mkdir('configs')
        if os.path.isfile('config.ini'):
            move('config.ini', 'configs/configs.ini')
            printer.change_warning("[!] config.ini was moved to 'config' folders")
        else:
            make_config()
            return set()
            
    return set(glob.glob('configs/*.ini'))
        
    
def get_config(filename='config.ini'):
    config = configparser.ConfigParser()


    with open(filename, 'rt', encoding = 'utf_8_sig') as infile:
        config.read_file(infile)

    return config, filehash(filename)

def get_date(days_to_check):
    ordinal_check_date = datetime.date.today().toordinal() - (days_to_check - 1)

    if ordinal_check_date < 1:
        ordinal_check_date = 1
    elif ordinal_check_date > datetime.date.today().toordinal():
        ordinal_check_date = datetime.date.today().toordinal()

    return datetime.date.fromordinal(ordinal_check_date).strftime('%Y-%m-%d')

#TODO: Replace this all with translate
def substitute_illegals(char):
    illegals = [':', '*', '?', '\"', '<', '>', '|']
    path_chars = ['\\', '/']
    char = '_' if char in illegals else char
    char = '/' if char in path_chars else char
    return char

def substitute_illegals_filename(filename):
    illegals = {':'  : 'ː',
                '*'  : '❋',
                '"'  : 'ᐦ',
                '?'  : 'ʔ', 
                '<'  : 'ᐸ', 
                '>'  : 'ᐳ', 
                '|'  : '╎', 
                '\\' : '╲', 
                '/'  : '╱'}
    
    return ''.join([char if char not in illegals else illegals[char] for char in filename])

@lru_cache(maxsize=None, typed=False)
def make_new_dir(dir_name):
    clean_dir_name = ''.join([substitute_illegals(char) for char in dir_name]).lower().replace('\\','/')
    os.makedirs(f"downloads/{clean_dir_name}", exist_ok=True)
    return clean_dir_name

def make_path(dir_name, filename):
    return f"downloads/{make_new_dir(dir_name)}/{substitute_illegals_filename(filename)}"

def make_cache_folder():
    try:
        os.mkdir("cache")
    except FileExistsError:
        pass
    
IMAGE_MATCH =  re.compile(r".*?(\d+?)\.(?:jpg|png|gif|swf|webm)$")
    
def get_all_time_downloaded():
    conn = sqlite3.connect('files.db', isolation_level=None)
    cur = conn.cursor()
    
    cur.execute('''
        SELECT fullpath FROM downloaded;''')
        
    # deleting them
    result = set()
    for (fullpath, ) in cur:
        result.add(fullpath)
    return result
    
def get_files_dict(reset_filedb, reset_all_time_downloaded):
    #args = [arg.strip().lower() for arg in sys.argv]
    filedict={}

    for root, dirs, files in os.walk('cache/'):
        for file in files:
            try:
                id=file.split('.')[-2] #id section
                id=int(id)
                filepath='{}/{}'.format(root.replace('\\','/').lower(),file)
                filedict[id]=filepath
            except (IndexError,ValueError):
                pass
                    
    conn = sqlite3.connect('files.db', isolation_level=None)
    cur = conn.cursor()

    cur.executescript(
        '''
        BEGIN TRANSACTION;
        
        CREATE TABLE IF NOT EXISTS old_files (
            fullpath    TEXT PRIMARY KEY
                           UNIQUE
                           NOT NULL
        ) WITHOUT ROWID;
        
        CREATE TABLE IF NOT EXISTS new_files (
            fullpath    TEXT PRIMARY KEY
                           UNIQUE
                           NOT NULL
        ) WITHOUT ROWID;
        
        CREATE TABLE IF NOT EXISTS downloaded (
            fullpath    TEXT PRIMARY KEY
                           UNIQUE
                           NOT NULL
        );
        
        COMMIT;
        '''
    )


    if reset_filedb:
        cur.executescript(
            '''
            BEGIN TRANSACTION;
            
            DELETE FROM old_files;
            DELETE FROM new_files;
            
            COMMIT;
            '''
        )
    
    if reset_all_time_downloaded:
        cur.executescript(
            '''
            BEGIN TRANSACTION;

            DELETE FROM downloaded;
            
            COMMIT;
            '''
        )
    
    conn.commit()
    cur.execute("BEGIN TRANSACTION;")
    for root, dirs, files in os.walk('downloads/'):
        for file in files:
            match = IMAGE_MATCH.match(file)
            if match:
                id=int(match[1])
                filepath='{}/{}'.format(root.replace('\\','/').lower(),file)
                if id not in filedict:
                    filedict[id]=filepath
                if reset_filedb:
                    cur.execute('INSERT INTO old_files VALUES (?);', (filepath,))
    cur.execute("COMMIT;")
    conn.commit()
    
    return filedict


def append_files(filedict, pathes):
    conn = sqlite3.connect('files.db', isolation_level=None)
    cur = conn.cursor()
    cur.execute("BEGIN TRANSACTION;")
    for path in pathes:
        file=os.path.basename(newpath)
        match = IMAGE_MATCH.match(file)
        if match:
            id=int(match[1])
            filepath=path.replace('\\','/').lower()
            filedict[id]=filepath
            cur.execute('INSERT INTO old_files VALUES (?);', (filepath,))
    cur.execute("COMMIT;")
    conn.commit()

def prune_cache():
    conn = sqlite3.connect('files.db', isolation_level=None)
    cur = conn.cursor()
    cur.executescript(
        '''
        BEGIN TRANSACTION;
        DROP TABLE IF EXISTS used_ids;
        
        CREATE TABLE used_ids (
            id    INTEGER PRIMARY KEY
                           UNIQUE
                           NOT NULL
        ) WITHOUT ROWID;

        DROP TABLE IF EXISTS cached_files;
        
        CREATE TABLE cached_files (
            id    INTEGER PRIMARY KEY
                           UNIQUE
                           NOT NULL,
            fullpath       TEXT 
                           UNIQUE
                           NOT NULL   
        ) WITHOUT ROWID;
        
        COMMIT;
        '''
    )
    
    # making a list of all files that are in "downloads/"
    conn.commit()
    cur.execute("BEGIN TRANSACTION;")
    for root, dirs, files in os.walk('downloads/'):
        for file in files:
            match = IMAGE_MATCH.match(file)
            if match:
                id=int(match[1])
                cur.execute('INSERT OR IGNORE INTO used_ids VALUES (?);', (id,))
    cur.execute("COMMIT;")
    conn.commit()
    
    # making a list of all files that are in "cache/"
    cur.execute("BEGIN TRANSACTION;")
    for root, dirs, files in os.walk('cache/'):
        for file in files:
            try:
                id=file.split('.')[-2] #id section
                id=int(id)
                filepath='{}/{}'.format(root.replace('\\','/').lower(),file)
                cur.execute('INSERT INTO cached_files VALUES (?,?);', (id,filepath))
            except (IndexError, ValueError):
                pass
    cur.execute("COMMIT;")
    conn.commit()
    
    # finding files that are in cache but not in downloads
    cur.execute('''
        SELECT fullpath FROM cached_files
        LEFT JOIN used_ids
        ON used_ids.id = cached_files.id
        WHERE used_ids.id IS NULL;''')
        
    # deleting them
    for (filename, ) in cur:
        with suppress(FileNotFoundError):
            os.remove(filename)
    
def validate_format(format):
    post = {i:i for i in constants.DEFAULT_SLOTS}
    try:
        dummy = format.format(**post)
    except:
        printer.change_warning(f"Invalid format: {format}")


def get_blocked_posts():
    os.makedirs("to_blocked_posts", exist_ok=True)
    
    #Creating file if it was accidentally removed
    with open("blocked_posts.txt" , "a"):
        pass
    
    blocked_ids = set()
    with open("blocked_posts.txt" , "r") as f:
        for line in f:
            blocked_ids.add(int(line))
    
    for root, dirs, files in os.walk('to_blocked_posts/'):
        for file in files:
            match = IMAGE_MATCH.match(file)
            if match:
                id=int(match[1])
                blocked_ids.add(id)
    
    with open("blocked_posts_new.txt" , "w") as f:
        for id in sorted(blocked_ids):
            print(id, file=f)
            
    replace_atomic("blocked_posts_new.txt", "blocked_posts.txt")
    for root, dirs, files in os.walk('to_blocked_posts/'):
        for file in files:
            filepath='{}/{}'.format(root,file)
            os.remove(filepath)
            
    return blocked_ids

def remove_empty_folders():
    for root, dirs, files in os.walk('downloads/', topdown=False):
        try:
            os.rmdir(root)
        except (OSError, FileNotFoundError):
            pass

def get_cookies():
    if not os.path.exists("cfcookie.txt"):
        return None
    
    with open("cfcookie.txt", "r") as f:
        try:
            cookie_dict = json.load(f)
        except json.decoder.JSONDecodeError:
            return None
            
    
    __cfduid = None
    cf_clearance = None
    for cookie in cookie_dict:
        if 'name' in cookie and cookie['name'] == "__cfduid":
            __cfduid = cookie['value'] 
        
        if 'Name raw' in cookie and cookie['Name raw'] == "__cfduid":
            __cfduid = cookie['Content raw'] 
        
        
        if 'name' in cookie and cookie['name'] == "cf_clearance":
            cf_clearance = cookie['value']
            
        if 'Name raw' in cookie and cookie['Name raw'] == "cf_clearance":
            cf_clearance = cookie['Content raw']
            
    if __cfduid is None or cf_clearance is None:
        return None
    
    return f"__cfduid={__cfduid}; cf_clearance={cf_clearance};"

def reset_pools():
    if os.path.exists("pools.pickle"):
        os.remove("pools.pickle")
        
def load_pools():
    if not os.path.exists("pools.pickle"):
        return {}
    with open('pools.pickle', 'rb') as f:
        return pickle.load(f)
        
def save_pools(pools):
    with atomic_write('pools.pickle', mode='wb', overwrite=True) as f:
        pickle.dump(pools, f, protocol=pickle.HIGHEST_PROTOCOL)
        
# https://stackoverflow.com/a/312464/3921746
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]
        
def generate_pools_config(pools):
    if not pools:
        return

    lines = []

    for i, pool in enumerate(list(pools)):
        lines.append(f"""
[<prefilter_{i+1}>]
tags = pool:{pool}
""")

    for pool, folders in pools.items():
        folders = set(folders)
        for folder in folders:
            lines.append(f"""
[{folder}]
tags = pool:{pool}
""")

    with open('pools.ini', 'rt', encoding = 'utf_8_sig') as f:
        prefix_config = f.read()

    with open('configs/pools.generated', 'wt', encoding = 'utf_8_sig') as f:
        f.write(prefix_config)
        f.write('\n')
        f.write("\n".join(lines))
        
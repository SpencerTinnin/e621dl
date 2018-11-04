# Internal Imports
import configparser
import datetime
import os

#concurrent.futures.Executor
#this is gonna be awesome

# Personal Imports
from e621dl import constants

def _check(tag, tags):
    return tag in tags

def make_check_funk(source_template, tags):
    tags_screened=[tag.replace("'","\\'") for tag in tags]
    source=source_template.format(*tags_screened)
    func_str=f'def f(tags): return {source}'
    loc={}
    exec(func_str,{'check':_check},loc)
    return loc['f']

FORBIDDEN_TAG_CHARS=r'%,#*'
def tags_and_source_template(line):
    
    if any((c in FORBIDDEN_TAG_CHARS) for c in line):
        print(f"[-]: characters {FORBIDDEN_TAG_CHARS} are forbidden")
    
    line = ' ' + line # anything except '\\' is fine to prepend, actually
    new_line = [' ']
    
    for prev, cur in zip(line[:-1],line[1:]):
        if prev=='\\':
            if cur not in '|&()':
                print("[!]: only characters '|&()' can be screened")
                raise SystemExit
            else:
                new_line.append(cur)
        elif cur in '-|&()':
            if cur == '-' and new_line[-1] != ' ':
                new_line.append( cur )
            else:
                new_line.extend( (' ',cur,' ') )
        elif cur == '~' and new_line[-1]==' ':
            print("[!]: character '~' cannot be first character")
            raise SystemExit
        else:
            new_line.extend( cur )
                
    new_line=''.join(new_line)
    tokens=[token for token in new_line.split(' ') if token]
    
    tags=[token.replace('\\','') for token in tokens if token not in '-|&()']
    source_template=[token if token in ('-|&()') else "check('{}',tags)" for token in tokens]
    source_template = ''.join(source_template).replace('-',' not ').replace('|',' or ').replace('&',' and ')
    
    try:
        make_check_funk(source_template, tags)(tags) # syntax validation
    except:
        source_template = source_template.replace("check(\'{}\',tags)","{}")
        print(f'[!] Error in condition.')
        print(f"[!] Check if all '()|&' characters are properly screened and all braces are closed")
        print(f"[!] See source:\n    {source_template}")
        raise SystemExit
    
    return source_template, tags
    


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
    illegals = ['\\', ':', '*', '?', '\"', '<', '>', '|', '/']
    return '_' if char in illegals else char

def make_path(dir_name, filename, ext):
    clean_dir_name = ''.join([substitute_illegals(char) for char in dir_name]).lower()

    os.makedirs(f"downloads/{clean_dir_name}", exist_ok=True)

    return f"downloads/{clean_dir_name}/{filename}.{ext}"

def make_cache_folder():
    try:
        os.mkdir("cache")
    except FileExistsError:
        pass
    
def get_files_dict(cachefunc):
    filedict={}
    for root, dirs, files in os.walk('downloads/'):
        for file in files:
            filedict[file]='{}/{}'.format(root,file)
    
    if cachefunc:
        for root, dirs, files in os.walk('cache/'):
            for file in files:
                filedict[file]='{}/{}'.format(root,file)
    
    return filedict
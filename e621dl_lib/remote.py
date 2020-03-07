# Internal Imports
import os
from time import sleep, time
from datetime import datetime
from functools import lru_cache
import sqlite3
import pickle
import re
from html import unescape
from urllib.parse import urlparse
import json

# Personal Imports
from . import constants
from .local import printer

# Vendor Imports
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests.exceptions import ConnectionError, ReadTimeout

TIMEOUT = constants.CONNECTION_TIMEOUT

class Post:
    __slots__ = constants.DEFAULT_SLOTS
    def __init__(self, post, metatags):
        self.id=post["id"]
        # datetime.fromisoformat('2020-03-06T13:47:53.354-05:00')
        created_at_datetime = datetime.fromisoformat(post["created_at"])
        created_at_timestamp = created_at_datetime.timestamp()
        created_at_timestamp_tz = created_at_datetime.tzname()
        created_at_timestamp_s = int(created_at_timestamp)
        created_at_timestamp_n = (created_at_timestamp - created_at_timestamp_s) * 1000_000_000
        
        self.days_ago=int(datetime.now().timestamp()-created_at_timestamp)/86400 # day have 3600*24==86400 seconds
        self.created_at= {'s': int(created_at_timestamp),
                          'n': created_at_timestamp_n,
                          'tz': created_at_timestamp_tz,
                          }
                          
        self.created_at_string = post["created_at"]
        self.tag_ex = post["tags"]
        self.tags = []
        for dummy_cat, taglist in self.tag_ex.items():
            self.tags += taglist
        self.tags += metatags
        
        self.rating = post["rating"]
        
        file = post["file"]
        self.md5 = file["md5"]
        self.file_ext = file["ext"]
        self.file_url = file["url"]
        self.file_size = file["size"]
        self.width = file["width"]
        self.height = file["height"]
        
        score = post["score"]
        self.score = score["total"]
        self.score_up = score["up"]
        self.score_down = score["down"]
        
        self.fav_count = post["fav_count"]
        self.sources = post["sources"]
        self.artist = '_'.join(self.tag_ex["artist"])
        self.description = post["description"]
        self.pools = post["pools"]
        self.creator_id = post["uploader_id"]
        
    def generate(self):
        return {name:getattr(self,name,'Unknown') for name in self.__slots__}

def make_posts_list(json_list, metatags):
    post_list=[]
    for post in json_list:
        if post["file"]["url"]:
            post_list.append(Post(post, metatags))
    return post_list

def requests_retry_session(
    retries = 5,
    backoff_factor = 0.3,
    status_forcelist = (500, 502, 504),
    session = None,
):
    session = session or requests.Session()
    retry = Retry(
        total = retries,
        read = retries,
        connect = retries,
        backoff_factor = backoff_factor,
        status_forcelist = status_forcelist,
        method_whitelist = frozenset(['GET', 'POST'])
    )
    adapter = HTTPAdapter(max_retries = retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def retrying_get(s, *args, **kwargs):
    for i in range(1,100):
        try:
            return s.get(*args, **kwargs)
        except (ConnectionError, ReadTimeout):
            printer.increment_retries()
            
    return s.get(*args, **kwargs)
    
    
def retrying_post(s, *args, **kwargs):
    for i in range(1,100):
        try:
            return s.post(*args, **kwargs)
        except (ConnectionError, ReadTimeout):
            printer.increment_retries()
            
    return s.post(*args, **kwargs)

def check_cloudflare(response):
    if response.status_code != 403:
        return False
    elif not response.text.lower().find("cloudflare") >= 0:
        return False
    else:
        return True
    
def solve_captcha(session, response):
    text = response.text
    url = response.url
    splitted=urlparse(url)
    baseurl=f"{splitted.scheme}://{splitted.netloc}"
    
    # Zalgo. He comes.
    # To be fair, you can use regexps to search in
    # an html with a known structure.
    hidden_input_re = re.compile('<input type="hidden" name="(.*?)" value="(.*?)"')
    textarea_re = re.compile('<textarea .*? name="(.*?)"')
    form_re = re.compile('<form .*? action="(.*?)" method="(.*?)"')
    iframe_re = re.compile('<iframe src="(.*?)"')
    
    try:
        hidden_name, hidden_value = hidden_input_re.search(text).groups()
    except:
        printer.change_warning("unexpected absense of hidden input")
        return False
    
    try:
        textarea_name, = textarea_re.search(text).groups()
    except:
        printer.change_warning("unexpected absense of textarea")
        return False
        
    try:
        form_url, form_method = form_re.search(text).groups()
    except:
        printer.change_warning("unexpected absense of form")
        return False
    
    try:
        iframe_url, = iframe_re.search(text).groups()
    except:
        printer.change_warning("unexpected absense of iframe")
        return False
    
    form_method = form_method.lower()
    
    printer.show(False)
    sleep(0.2)
    printer.reset_screen()
    print("Install Referer Control extension in your browser, then")
    print("set up (temporarily) referer for 'https://www.google.com/recaptcha/*'")
    print("to 'https://e621.net', then")
    print("open this link in the browser:")
    print(iframe_url)
    print("after successful recaptcha solving")
    print("copy text field content here:")
    textarea_value=input()
    
    printer.show()
    
    if form_url[0] == "/":
        form_url = baseurl+form_url
    
    payload={
                hidden_name:hidden_value,
                textarea_name:textarea_value,
            }
    
    if form_method == "get":
        response = retrying_get(session, form_url, params=payload, timeout=TIMEOUT)
    elif form_method == "post":
        response = retrying_post(session, form_url, data=payload, timeout=TIMEOUT)
    else:
        printer.change_warning("unknown method")
    
    return not check_cloudflare(response) #means we solve a captcha

def delayed_post(url, payload, session):
    # Take time before and after getting the requests response.
    start = time()
    if payload:
        response = retrying_post(session, url, data = payload, timeout=TIMEOUT)
    else:
        response = retrying_post(session, url, timeout=TIMEOUT)
    elapsed = time() - start

    # Citation from e621:api
    # "You should make a best effort not to make 
    # more than one request per second over a sustained period."
    if elapsed < 1.0:
        sleep(1.0 - elapsed)

    if check_cloudflare(response):
        solve_captcha(session, response)
        return delayed_post(url, payload, session)
    
    return response


def delayed_get(url, payload, session):
    # Take time before and after getting the requests response.
    start = time()
    if payload:
        response = retrying_get(session, url, data = payload, timeout=TIMEOUT)
    else:
        response = retrying_get(session, url, timeout=TIMEOUT)
    elapsed = time() - start

    # Citation from e621:api
    # "You should make a best effort not to make 
    # more than one request per second over a sustained period."
    if elapsed < 1.0:
        sleep(1.0 - elapsed)

    if check_cloudflare(response):
        solve_captcha(session, response)
        return delayed_get(url, payload, session)
    
    return response

def get_github_release(session):
    url = 'https://api.github.com/repos/lurkbbs/e621dl/releases/latest'

    response = retrying_get(session, url, timeout=TIMEOUT)
    response.raise_for_status()

    return response.json()['tag_name'].strip('v')

def get_posts(last_id, search_tags, earliest_date, session, api_key, login, **dummy):
 
    metatags =[tag for tag in search_tags if ':' in tag and tag[0] not in '~-' and '*' not in tag]
    search_string = ' '.join(search_tags)
    url = 'https://e621.net/posts.json'
    
    reordered = False
    
    tags = f"date:>={earliest_date} {search_string}"
    
    if any("order:" in metatag for metatag in metatags):
        payload = {
            'limit': constants.MAX_RESULTS,
            'page': 1,
            'tags': tags,
        }
        reordered = True
    else:
        payload = {
            'limit': constants.MAX_RESULTS,
        }
        if last_id in (0x7F_FF_FF_FF, None):
            payload["tags"] = tags
        else:
            payload["tags"] = f"id:<{last_id} {tags}"

    if api_key and login:
        payload["login"] = login
        payload["api_key"] = api_key

    while True:
        start = time()
        response = retrying_get(session, url, data=payload, timeout=TIMEOUT)

        while check_cloudflare(response):
            solve_captcha(session, response)
            elapsed = time() - start
            if elapsed < 1.0:
                sleep(1.0 - elapsed)
            response = retrying_get(session, url, data=payload, timeout=TIMEOUT)
        
        response.raise_for_status()

        posts_orig = response.json()["posts"]
        results=make_posts_list(posts_orig, metatags)
        
 
        if results:
            yield results
        
        if len(posts_orig) < constants.MAX_RESULTS:
            break
        elif reordered:
            payload['page'] += 1
            if payload['page'] > 750:
                break
        else:
            last_id = posts_orig[-1]["id"]
            payload["tags"] = f"id:<{last_id} {tags}"
        
        elapsed = time() - start
        if elapsed < 1.0:
            sleep(1.0 - elapsed)

def get_known_post(post_id, api_key, login, session):
    url = f'https://e621.net/posts/{post_id}.json'

    if api_key and login:
        response = delayed_get(url, {'login':login, 'api_key': api_key}, session)
    else:
        response = delayed_get(url, None, session)
    response.raise_for_status()

    return response.json()["post"]

@lru_cache(maxsize=512, typed=False)
def get_tag_alias(user_tag, api_key, login, session):
    prefix = ''
    
    if user_tag[0] == '~':
        prefix = '~'
        user_tag = user_tag[1:]
        return prefix+get_tag_alias(user_tag, api_key, login, session)

    if user_tag[0] == '-':
        prefix = '-'
        user_tag = user_tag[1:]
        return prefix+get_tag_alias(user_tag, api_key, login, session)

    if ':' in user_tag:
        printer.change_warning(f"Impossible to check if {user_tag} is valid.")
        return user_tag    

    url = 'https://e621.net/tags.json'
    if api_key and login:
        payload = {'search[name_matches]': user_tag, 'login':login, 'api_key': api_key}
    else:
        payload = {'search[name_matches]': user_tag}
        
    response = delayed_get(url, payload, session)
    response.raise_for_status()

    results = response.json()

    #if at least one tag was found for tag with "*"
    if '*' in user_tag:
        if results:
            printer.change_tag(f"{user_tag} is valid.")
            return user_tag
        else:
            printer.show(False)
            print(f"[!] The tag {prefix}{user_tag} is spelled incorrectly or does not exist.")
            raise SystemExit
            return ''
    
    if not ("tags" in results and not results["tags"]):
        for tag in results:
            if user_tag == tag['name']:
                printer.change_tag(f"{prefix}{user_tag} is valid.")
                return f"{prefix}{user_tag}"


    # At this point, we found no tag 
    # and we are starting to search aliases
    
    pagenum = 1
    def alias_chunk():
        url = 'https://e621.net/tag_aliases.json'
        if api_key and login:
            payload = {'search[status]': 'Approved', 'search[name_matches]': user_tag, 'page': pagenum, 'login':login, 'api_key': api_key}
        else:
            payload = {'search[status]': 'Approved', 'search[name_matches]': user_tag, 'page': pagenum}
        response = delayed_get(url, payload, session)
        response.raise_for_status()

        results = response.json()
        return results

    results = alias_chunk()
    while results:
        if ("tag_aliases" in results and not results["tag_aliases"]):
            break;
            
        for tag in results:
            if user_tag == tag['antecedent_name']:

                actual_tag = tag["consequent_name"]
                printer.change_tag(f"{prefix}{user_tag} was changed to {prefix}{actual_tag}.")

                return f"{prefix}{actual_tag}"
        
        pagenum += 1
        if pagenum >= 750:
            break
        results = alias_chunk()

    printer.show(False)
    print(f"[!] The tag {prefix}{user_tag} is spelled incorrectly or does not exist.")
    raise SystemExit
    return ''

def download_post(url, path, session, cachefunc, duplicate_func, api_key, login):
    if f".{constants.PARTIAL_DOWNLOAD_EXT}" not in path:
        path += f".{constants.PARTIAL_DOWNLOAD_EXT}"

    # Creates file if it does not exist so that os.path.getsize does not raise an exception.
    try:
        open(path, 'x')
    except FileExistsError:
        pass

    def stream_download():
        header = {'Range': f"bytes={os.path.getsize(path)}-"}
        if api_key and login:
            response = retrying_get(session, url, stream = True, headers = header, data={'login':login, 'api_key': api_key}, timeout=TIMEOUT)
        else:
            response = retrying_get(session, url, stream = True, headers = header, timeout=TIMEOUT)
            
        if response.ok:    
            with open(path, 'ab') as outfile:
                for chunk in response.iter_content(chunk_size = 8192):
                    outfile.write(chunk)
            newpath=path.replace(f".{constants.PARTIAL_DOWNLOAD_EXT}", '')
            os.rename(path, newpath)
            printer.change_file(newpath)
            if cachefunc:
                basename=os.path.basename(newpath)
                cachepath='.'.join(basename.split('.')[-2:])
                try:
                    duplicate_func(newpath, f"cache/{cachepath}")
                except FileExistsError:
                    os.remove(newpath)
                    duplicate_func(f"cache/{cachepath}", newpath)
                    
                    
            return True

        else:
            os.remove(path)
            return False

    for i in range(1,100):
        try:
            return stream_download()
        except (ConnectionError, ReadTimeout):
            printer.increment_retries()
            
    return stream_download()
    
    
def finish_partial_downloads(session, cachefunc, duplicate_func, api_key, login):
    for root, dirs, files in os.walk('downloads/'):
        for file in files:
            if file.endswith(constants.PARTIAL_DOWNLOAD_EXT):
                printer.change_warning(f" Partial download {file} found.")

                path = os.path.join(root, file)
                url = get_known_post(file.split('.')[-3], api_key, login, session)['file']['url']

                download_post(url, path, session, cachefunc, duplicate_func, api_key, login)

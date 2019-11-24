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
    def __init__(self, attrs, metatags):
        for key, value in attrs.items():
            if key == 'artist':
                value='_'.join(unescape(value))
            if key in self.__slots__:
                setattr(self, key, value)

        self.days_ago=(datetime.now()-datetime.fromtimestamp(attrs['created_at']['s'])).days
        self.tags = self.tags.split() + metatags
        
    def generate(self):
        return {name:getattr(self,name,'Unknown') for name in self.__slots__}

def make_posts_list(json_list, metatags):
    post_list=[]
    for post in json_list:
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
    elif not response.text.lower().find("cloudflare"):
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
    response = retrying_post(session, url, data = payload, timeout=TIMEOUT)
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

def get_github_release(session):
    url = 'https://api.github.com/repos/lurkbbs/e621dl/releases/latest'

    response = retrying_get(session, url, timeout=TIMEOUT)
    response.raise_for_status()

    return response.json()['tag_name'].strip('v')

def get_posts(last_id, search_tags, earliest_date, session, **dummy):
 
    metatags =[tag for tag in search_tags if ':' in tag and tag[0] not in '~-' and '*' not in tag]
    search_string = ' '.join(search_tags)
    url = 'https://e621.net/post/index.json'
    reordered = False
    
    if any("order:" in metatag for metatag in metatags):
        payload = {
            'limit': constants.MAX_RESULTS,
            'page': 1,
            'tags': f"date:>={earliest_date} {search_string}"
            #'tags': search_string
        }
        reordered = True
    else:
        payload = {
            'limit': constants.MAX_RESULTS,
            'before_id': last_id,
            'tags': f"date:>={earliest_date} {search_string}"
            #'tags': search_string
        }

    while True:
        start = time()
        response = retrying_post(session, url, data = payload, timeout=TIMEOUT)
        
        while check_cloudflare(response):
            solve_captcha(session, response)
            elapsed = time() - start
            if elapsed < 1.0:
                sleep(1.0 - elapsed)
            response = retrying_post(session, url, data = payload, timeout=TIMEOUT)
        
        response.raise_for_status()

        results=make_posts_list(response.json(), metatags)
        if results:
            yield results
        
        if len(results) < constants.MAX_RESULTS:
            break
        elif reordered:
            payload['page'] += 1
            if payload['page'] > 750:
                break
        else:
            last_id = results[-1].id
            payload['before_id']   = last_id
        
        elapsed = time() - start
        if elapsed < 1.0:
            sleep(1.0 - elapsed)

def get_known_post(post_id, session):
    url = 'https://e621.net/post/show.json'
    payload = {'id': post_id}

    response = delayed_post(url, payload, session)
    response.raise_for_status()

    return response.json()

@lru_cache(maxsize=512, typed=False)
def get_tag_alias(user_tag, session):
    prefix = ''
    
    if user_tag[0] == '~':
        prefix = '~'
        user_tag = user_tag[1:]
        return prefix+get_tag_alias(user_tag, session)

    if user_tag[0] == '-':
        prefix = '-'
        user_tag = user_tag[1:]
        return prefix+get_tag_alias(user_tag, session)

    if ':' in user_tag:
        printer.change_warning(f"Impossible to check if {user_tag} is valid.")
        return user_tag    

    url = 'https://e621.net/tag/index.json'
    payload = {'name': user_tag}

    response = delayed_post(url, payload, session)
    response.raise_for_status()

    results = response.json()

    #if at least one tag was found for tag with "*"
    if '*' in user_tag and results:
        printer.change_tag(f"{user_tag} is valid.")
        return user_tag

    for tag in results:
        if user_tag == tag['name']:
            printer.change_tag(f"{prefix}{user_tag} is valid.")
            return f"{prefix}{user_tag}"

    pagenum = 1
    def alias_chunk():
        url = 'https://e621.net/tag_alias/index.json'
        payload = {'approved': 'true', 'query': user_tag, 'page': pagenum}

        response = delayed_post(url, payload, session)
        response.raise_for_status()

        results = response.json()
        return results

    results = alias_chunk()
    while results:
        for tag in results:
            if user_tag == tag['name']:
                url = 'https://e621.net/tag/show.json'
                payload = {'id': tag['alias_id']}

                response = delayed_post(url, payload, session)
                response.raise_for_status()

                results = response.json()

                printer.change_tag(f"{prefix}{user_tag} was changed to {prefix}{results['name']}.")

                return f"{prefix}{results['name']}"
        
        pagenum += 1
        results = alias_chunk()
    printer.show(False)
    print(f"[!] The tag {prefix}{user_tag} is spelled incorrectly or does not exist.")
    raise SystemExit
    return ''

def download_post(url, path, session, cachefunc, duplicate_func):
    if f".{constants.PARTIAL_DOWNLOAD_EXT}" not in path:
        path += f".{constants.PARTIAL_DOWNLOAD_EXT}"

    # Creates file if it does not exist so that os.path.getsize does not raise an exception.
    try:
        open(path, 'x')
    except FileExistsError:
        pass

    def stream_download():
        header = {'Range': f"bytes={os.path.getsize(path)}-"}
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
                duplicate_func(newpath, f"cache/{cachepath}")
            return True

        else:
            os.remove(path)
            printer.change_warning(f"Error code {response.status_code} with {url}")
            return False

    for i in range(1,100):
        try:
            return stream_download()
        except (ConnectionError, ReadTimeout):
            printer.increment_retries()
            
    return stream_download()
    
    
def finish_partial_downloads(session, cachefunc, duplicate_func):
    for root, dirs, files in os.walk('downloads/'):
        for file in files:
            if file.endswith(constants.PARTIAL_DOWNLOAD_EXT):
                printer.change_warning(f" Partial download {file} found.")

                path = os.path.join(root, file)
                url = get_known_post(file.split('.')[-3], session)['file_url']

                download_post(url, path, session, cachefunc, duplicate_func)

# Internal Imports
import os
from time import sleep, time
from datetime import datetime
from functools import lru_cache
import sqlite3
import pickle

# Personal Imports
from . import constants

# Vendor Imports
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class Post:
    __slots__=['id','tags','rating','id','md5','file_ext','file_url','score','fav_count','days_ago']
    def __init__(self, attrs):
        for key, value in attrs.items():
            if key in self.__slots__:
                setattr(self, key, value)

        self.days_ago=(datetime.now()-datetime.fromtimestamp(attrs['created_at']['s'])).days
        self.tags = self.tags.split()

def make_posts_list(json_list):
    post_list=[]
    for post in json_list:
        post_list.append(Post(post))
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

def delayed_post(url, payload, session):
    # Take time before and after getting the requests response.
    start = time()
    response = session.post(url, data = payload)
    elapsed = time() - start

    # If the response took less than 0.5 seconds (only 2 requests are allowed per second as per the e621 API)
    # Wait for the rest of the 0.5 seconds.
    if elapsed < 0.5:
        sleep(0.5 - elapsed)

    return response

def get_github_release(session):
    url = 'https://api.github.com/repos/wulfre/e621dl/releases/latest'

    response = session.get(url)
    response.raise_for_status()

    return response.json()['tag_name'].strip('v')

def get_posts(last_id, search_string, earliest_date, session, **dummy):
    #raise NotImplementedError('not now')
    url = 'https://e621.net/post/index.json'
    payload = {
        'limit': constants.MAX_RESULTS,
        'before_id': last_id,
        'tags': f"date:>={earliest_date} {search_string}"
    }

    while True:
        start = time()
        response = session.post(url, data = payload)
        #response = delayed_post(url, payload, session)
        response.raise_for_status()

        results=make_posts_list(response.json())
        if results:
            yield results
        
        if len(results) < constants.MAX_RESULTS:
            break
        else:
            last_id = results[-1].id
            payload['before_id']   = last_id
        
        elapsed = time() - start
        if elapsed < 0.5:
            sleep(0.5 - elapsed)

def get_known_post(post_id, session):
    url = 'https://e621.net/post/show.json'
    payload = {'id': post_id}

    response = delayed_post(url, payload, session)
    response.raise_for_status()

    return response.json()

@lru_cache(maxsize=512, typed=False)
def get_tag_alias(user_tag, session):
    prefix = ''
    
    if ':' in user_tag:
        print(f"[!] It is not possible to check if {user_tag} is valid.")
        return user_tag

    if user_tag[0] == '~':
        prefix = '~'
        user_tag = user_tag[1:]
        return prefix+get_tag_alias(user_tag, session)

    if user_tag[0] == '-':
        prefix = '-'
        user_tag = user_tag[1:]
        return prefix+get_tag_alias(user_tag, session)

    url = 'https://e621.net/tag/index.json'
    payload = {'name': user_tag}

    response = delayed_post(url, payload, session)
    response.raise_for_status()

    results = response.json()

    if '*' in user_tag and results:
        print(f"[+] The tag {user_tag} is valid.")
        return user_tag

    for tag in results:
        if user_tag == tag['name']:
            print(f"[+] The tag {prefix}{user_tag} is valid.")
            return f"{prefix}{user_tag}"

    url = 'https://e621.net/tag_alias/index.json'
    payload = {'approved': 'true', 'query': user_tag}

    response = delayed_post(url, payload, session)
    response.raise_for_status()

    results = response.json()

    for tag in results:
        if user_tag == tag['name']:
            url = 'https://e621.net/tag/show.json'
            payload = {'id': tag['alias_id']}

            response = delayed_post(url, payload, session)
            response.raise_for_status()

            results = response.json()

            print(f"[+] The tag {prefix}{user_tag} was changed to {prefix}{results['name']}.")

            return f"{prefix}{results['name']}"

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

    header = {'Range': f"bytes={os.path.getsize(path)}-"}
    response = session.get(url, stream = True, headers = header)
    
    if response.ok:    
        with open(path, 'ab') as outfile:
            for chunk in response.iter_content(chunk_size = 8192):
                outfile.write(chunk)

        newpath=path.replace(f".{constants.PARTIAL_DOWNLOAD_EXT}", '')
        os.rename(path, newpath)
        if cachefunc:
            duplicate_func(newpath, f"cache/{os.path.basename(newpath)}")
        return True

    else:
        os.remove(path)
        print(f"[!] The downoad URL {url} is not available. Error code: {response.status_code}.")
        return False

def finish_partial_downloads(session, cachefunc, duplicate_func):
    for root, dirs, files in os.walk('downloads/'):
        for file in files:
            if file.endswith(constants.PARTIAL_DOWNLOAD_EXT):
                print(f"[!] Partial download {file} found.")

                path = os.path.join(root, file)
                url = get_known_post(file.split('.')[0], session)['file_url']

                download_post(url, path, session, cachefunc, duplicate_func)

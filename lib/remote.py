# Internal Imports
import os
from time import sleep
from timeit import default_timer
from functools import lru_cache

# External Imports
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Personal Imports
from . import constants
from . import local

def delayed_post(url, payload, session):
    # Take time before and after getting the requests response.
    start = default_timer()
    response = session.post(url, data = payload)
    elapsed = default_timer() - start

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

def get_posts(search_string, earliest_date, last_id, session):
    url = 'https://e621.net/post/index.json'
    payload = {
        'limit': constants.MAX_RESULTS,
        'before_id': str(last_id),
        'tags': 'date:>=' + str(earliest_date) + ' ' + search_string
    }

    response = delayed_post(url, payload, session)
    response.raise_for_status()

    return response.json()

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
        print('[!] It is not possible to check if' + user_tag + ' is valid.')
        return user_tag

    if user_tag[0] == '~':
        prefix = '~'
        user_tag = user_tag[1:]

    if user_tag[0] == '-':
        prefix = '-'
        user_tag = user_tag[1:]

    url = 'https://e621.net/tag/index.json'
    payload = {'name': user_tag}

    response = delayed_post(url, payload, session)
    response.raise_for_status()

    results = response.json()

    if '*' in user_tag and results:
        print('[✓] The tag ' + user_tag + ' is valid.')
        return user_tag

    for tag in results:
        if user_tag == tag['name']:
            print('[✓] The tag ' + prefix + user_tag + ' is valid.')
            return prefix + user_tag

    url = 'https://e621.net/tag_alias/index.json'
    payload = {'approved': 'true', 'query': user_tag}

    response = delayed_post(url, payload, session)
    response.raise_for_status()

    results = response.json()

    for tag in results:
        if user_tag == tag['name']:
            url = 'https://e621.net/tag/show.json'
            payload = {'id': str(tag['alias_id'])}

            response = delayed_post(url, payload, session)
            response.raise_for_status()

            results = response.json()

            print('[✓] The tag ' + prefix + user_tag + ' was changed to ' + prefix + results['name'] + '.')

            return prefix + results['name']

    print('[!] The tag ' + prefix + user_tag + ' is spelled incorrectly or does not exist.')
    raise SystemExit

def download_post(url, path, session):
    if '.' + constants.PARTIAL_DOWNLOAD_EXT not in path:
        path += '.' + constants.PARTIAL_DOWNLOAD_EXT

    try:
        open(path, 'x')
    except FileExistsError:
        pass

    header = {'Range': 'bytes=' + str(os.path.getsize(path)) + '-'}
    response = session.get(url, stream = True, headers = header)
    
    if response.status_code in range(400,499+1):
        print('[!] url ' + url + ' is not available, error code: ' +str(response.status_code))
        os.remove(path)
        return False
    
    response.raise_for_status()

    with open(path, 'ab') as outfile:
        for chunk in response.iter_content(chunk_size = 8192):
            outfile.write(chunk)

    os.rename(path, path.replace('.' + constants.PARTIAL_DOWNLOAD_EXT, ''))
    return True

def finish_partial_downloads(session):
    for root, dirs, files in os.walk('downloads/'):
        for file in files:
            if file.endswith(constants.PARTIAL_DOWNLOAD_EXT):
                print('[!] Partial download ' + file + ' found.')

                path = os.path.join(root, file)
                url = get_known_post(file.split('.')[0], session)['file_url']

                download_post(url, path, session)

def requests_retry_session(
    retries=6,
    backoff_factor=0.1,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        method_whitelist=frozenset(['GET', 'POST'])
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
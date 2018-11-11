#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Internal Imports
import os
import pickle
from distutils.version import StrictVersion
from fnmatch import fnmatch
from shutil import copy
from collections import deque
from threading import Thread, Lock
from time import sleep

# Personal Imports
from e621dl import constants
from e621dl import local
from e621dl import remote
                
download_queue = local.DownloadQueue()

dprint=print
def print(*args,**kwargs): return None

def prefilter_build_index(session, prefilter, max_days_ago, blacklist, cond_func):
    def print(*args, **kwargs):
        pass
    
    storage = local.PostsStorage()
    try:
        if not prefilter:
            return []
           
        print('')
        print("[i] Doing prefiltering...")

        if download_queue.completed:
            return
        
        last_id = download_queue.last_id
        
        search_string = ' '.join(prefilter[:5])
        local_blacklist = set(blacklist + [tag[1:] for tag in prefilter if tag[0]=='-'])
        local_anylist   = {tag[1:] for tag in prefilter if tag[0]=='~'}
        local_whitelist = {tag for tag in prefilter if tag[0] not in ('-','~')}
        
        for results in remote.get_posts(search_string, local.get_date(max_days_ago), last_id, session):
        #for results in storage:
            storage.append(results)
            filtered_results=[]
            # Gets the id of the last post found in the search so that the search can continue.
            # If the number of results is less than the max, the next searches will always return 0 results.
            # Because of this, the last id is set to 0 which is the base case for exiting the while loop.

            for post in results:
                tags = post.tags.split()
                
                if local_whitelist and not all(True if any(fnmatch(tag, mask) for tag in tags) else False for mask in local_whitelist):
                    print(f"[-] Post {post.id} was skipped for missing a requested tag.")
                # Using fnmatch allows for wildcards to be properly filtered.
                elif local_blacklist and[x for x in tags if any(fnmatch(x, y) for y in local_blacklist)]:
                    print(f"[-] Post {post.id} was skipped for having a blacklisted tag.")
                    pass
                elif local_anylist and not [x for x in tags if any(fnmatch(x, y) for y in local_anylist)]:
                    print(f"[-] Post {post.id} was skipped for missing any of optional tag.")
                elif not cond_func(tags):
                    print(f"[-] Post {post.id} was skipped for failing condition")
                    pass
                else:
                    print(f"[+] Post {post.id} passed global filtering.")
                    filtered_results.append(post)
            download_queue.append(filtered_results)        
            last_id = results[-1].id
            download_queue.last_id=last_id
    finally:
        download_queue.completed = True
          
def main():
    # Create the requests session that will be used throughout the run.
    with remote.requests_retry_session() as session:
        # Set the user-agent. Requirements are specified at https://e621.net/help/show/api#basics.
        session.headers['User-Agent'] = f"e621dl (Wulfre and lurkbbs) -- Version {constants.VERSION}"
        
        # Check if a new version is released on github. If so, notify the user.
        if StrictVersion(constants.VERSION) < StrictVersion(remote.get_github_release(session)):
            print('A NEW VERSION OF e621dl IS AVAILABLE ON GITHUB AT https://github.com/Wulfre/e621dl/releases/latest.')

        print(f"[i] Running e621dl version {constants.VERSION}.")

        print('')
        print("[i] Parsing config...")

        config = local.get_config()

        # Initialize the lists that will be used to filter posts.
        blacklist = []
        searches = []

        # Initialize user configured options in case any are missing.
        include_md5 = False # The md5 checksum is not appended to file names.
        default_days_ago=1
        default_date = local.get_date(default_days_ago) # Get posts from one day before execution.
        default_score = -0x7F_FF_FF_FF # Allow posts of any score to be downloaded.
        default_favs = 0
        default_ratings = ['s'] # Allow only safe posts to be downloaded.
        
        duplicate_func = copy
        cachefunc = lambda: None
        prefilter = []
        max_days_ago = default_days_ago
        cond_func = lambda x: True
        
        # Iterate through all sections (lines enclosed in brackets: []).
        for section in config.sections():

            # Get values from the "Other" section. Currently only used for file name appending.
            if section.lower() == 'other':
                for option, value in config.items(section):
                    if option.lower() == 'include_md5':
                        if value.lower() == 'true':
                            include_md5 = True
                    elif option.lower() == 'make_hardlinks':
                        if value.lower() == 'true':
                            duplicate_func = os.link
                    
                    elif option.lower() == 'make_cache':
                        if value.lower() == 'true':
                            local.make_cache_folder()
                            cachefunc = duplicate_func

            # Get values from the "Defaults" section. This overwrites the initialized default_* variables.
            elif section.lower() == 'defaults':
                for option, value in config.items(section):
                    if option.lower() in {'days_to_check', 'days'}:
                        default_days_ago = int(value)
                        default_date = local.get_date(default_days_ago)
                        max_days_ago = max(max_days_ago, default_days_ago)
                    elif option.lower() in {'min_score', 'score'}:
                        default_score = int(value)
                    elif option.lower() in {'min_favs', 'favs'}:
                        default_favs = int(value)
                    elif option.lower() in {'ratings', 'rating'}:
                        default_ratings = value.replace(',', ' ').lower().strip().split()
            elif section.lower() == 'prefilter':
                for option, value in config.items(section):
                    if option.lower() in {'tags','tag'}:
                        prefilter = [remote.get_tag_alias(tag.lower(), session) for tag in value.replace(',', ' ').lower().strip().split()]
                    elif option.lower() in {'condition', 'conditions'}:
                        source_template, tags = local.tags_and_source_template(value.lower().strip())
                        tags = [remote.get_tag_alias(tag.lower(), session) for tag in tags]
                        cond_func = local.make_check_funk(source_template, tags)
                        
            # Get values from the "Blacklist" section. Tags are aliased to their acknowledged names.
            elif section.lower() == 'blacklist':
                for option, value in config.items(section):
                    if option.lower() in {'tags', 'tag'}:
                        blacklist = [remote.get_tag_alias(tag.lower(), session) for tag in value.replace(',', ' ').lower().strip().split()]

            # If the section name is not one of the above, it is assumed to be the values for a search.
            else:

                # Initialize the list of tags that will be searched.
                section_tags = []

                # Default options are set in case the user did not declare any for the specific section.
                section_date = default_date
                section_score = default_score
                section_favs = default_favs
                section_ratings = default_ratings
                section_cond_func = lambda x: True
                section_blacklist = []
                section_whitelist = []
                section_anylist = []
                section_days_ago = default_days_ago

                # Go through each option within the section to find search related values.
                for option, value in config.items(section):

                    # Get the tags that will be searched for. Tags are aliased to their acknowledged names.
                    if option.lower() in {'tags', 'tag'}:
                        section_tags = [remote.get_tag_alias(tag.lower(), session) for tag in value.replace(',', ' ').lower().strip().split()]
                        section_blacklist += [tag[1:] for tag in section_tags if tag[0]=='-']
                        section_anylist   += [tag[1:] for tag in section_tags if tag[0]=='~']
                        section_whitelist += [tag for tag in section_tags if tag[0] not in ('-','~')]
                        

                    # Overwrite default options if the user has a specific value for the section
                    elif option.lower() in {'days_to_check', 'days'}:
                        section_days_ago=int(value)
                        section_date = local.get_date(section_days_ago)
                        max_days_ago = max(max_days_ago, section_days_ago)
                    elif option.lower() in {'blacklist', 'blacklist_tags', 'blacklisted'}:
                        section_blacklist += [remote.get_tag_alias(tag.lower(), session) for tag in value.replace(',', ' ').lower().strip().split()]
                    elif option.lower() in {'min_score', 'score'}:
                        section_score = int(value)
                    elif option.lower() in {'min_favs', 'favs'}:
                        section_favs = int(value)
                    elif option.lower() in {'ratings', 'rating'}:
                        section_ratings = value.replace(',', ' ').lower().strip().split()
                    elif option.lower() in {'condition', 'conditions'}:
                        source_template, tags = local.tags_and_source_template(value.lower().strip())
                        tags = [remote.get_tag_alias(tag.lower(), session) for tag in tags]
                        section_cond_func = local.make_check_funk(source_template, tags)

                # Append the final values that will be used for the specific section to the list of searches.
                # Note section_tags is a list within a list.
                searches.append({'directory': section.strip(), 'tags': section_tags, 'ratings': section_ratings, 'min_score': section_score, 'min_favs': section_favs, 'earliest_date': section_date, 'days_ago': section_days_ago, 'section_blacklist': section_blacklist, 'section_whitelist': section_whitelist, 'section_cond_func': section_cond_func, 'section_anylist': section_anylist})

                
                
        print('')
        print("[i] Checking for partial downloads...")

        remote.finish_partial_downloads(session, cachefunc, duplicate_func)
        
        print('')
        print("[i] Building downloaded files dict...")
        files = local.get_files_dict(cachefunc)

        #----------HAAAAAAAAAAAAAAAAAX ---------
        print("[DEBUG] before_id is", download_queue.last_id)
        local.save_on_exit_events(download_queue.save) #here, because we do not download anything before this point
        #input()
        queue_thread=Thread(target=prefilter_build_index, args=(session, prefilter, max_days_ago, blacklist, cond_func))
        queue_thread.start()
        #prefilter_build_index(session, prefilter, max_days_ago, blacklist, cond_func)
        #----------HAAAAAAAAAAAAAAAAAX end -----
        
        while True:
            try:
                chunk = download_queue.first()
            except:
                if download_queue.completed:
                    break
                else:
                    sleep(0.5)
                    continue
            for search in searches:
                print('')

                # Creates the string to be sent to the API.
                # Currently only 5 items can be sent directly so the rest are discarded to be filtered out later.
                if len(search['tags']) > 5:
                    search_string = ' '.join(search['tags'][:5])
                else:
                    search_string = ' '.join(search['tags'])

                # Initializes last_id (the last post found in a search) to an enormous number so that the newest post will be found.
                # This number is hard-coded because on 64-bit archs, sys.maxsize() will return a number too big for e621 to use.
                last_id = 0x7F_FF_FF_FF
                
                # making for filtering out <-tagname>s from prefilter
                # and if there are <-tagname> in fourth or more position in config
                local_blacklist=set(blacklist+search['section_blacklist'])
                local_whitelist=set(search['section_whitelist'])
                local_anylist = set(search['section_anylist'])
                # Sets up a loop that will continue indefinitely until the last post of a search has been found.
                while True:
                    print("[i] Getting posts...")
                    results = chunk if chunk else remote.get_posts(search_string, search['earliest_date'], last_id, session)

                    # Gets the id of the last post found in the search so that the search can continue.
                    # If the number of results is less than the max, the next searches will always return 0 results.
                    # Because of this, the last id is set to 0 which is the base case for exiting the while loop.
                    if len(results) < constants.MAX_RESULTS:
                        last_id = 0
                    else:
                        last_id = results[-1].id
                        
                    for post in results:
                        tags = post.tags.split()
                        #if not all tag mask in whitelist have at least one match in tags skip post
                        if local_whitelist and not all(True if any(fnmatch(tag, mask) for tag in tags) else False for mask in local_whitelist):
                            print(f"[-] Post {post.id} was skipped for missing a requested tag.")
                            pass
                        elif post.rating not in search['ratings']:
                            #print(f"[-] Post {post.id} was skipped for missing a requested rating.")
                            pass
                        # Using fnmatch allows for wildcards to be properly filtered.
                        # if at least one tag is in local_blacklist
                        elif local_blacklist and [x for x in tags if any(fnmatch(x, y) for y in local_blacklist)]:
                            #print(f"[-] Post {post.id} was skipped for having a blacklisted tag.")
                            pass
                        # if not even one tag in local_anylist
                        elif local_anylist and not [x for x in tags if any(fnmatch(x, y) for y in local_anylist)]:
                            print(f"[-] Post {post.id} was skipped for missing any of optional tag.")
                        elif int(post.score) < search['min_score']:
                            #print(f"[-] Post {post.id} was skipped for having a low score.")
                            pass
                        elif int(post.fav_count) < search['min_favs']:
                            #print(f"[-] Post {post.id} was skipped for having a low favorite count.")
                            pass
                        elif not search['section_cond_func'](tags):
                            #print(f"[-] Post {post.id} was skipped for failing condition.")
                            pass
                        elif post.days_ago >= search['days_ago']:
                            print(f"[-] Post {post.id} was skipped for being too old")
                        else:
                            #it turns out make_path is a great resource hog. So we will call it only when we need it
                            if include_md5:
                                filename='{}.{}.{}'.format(post.id,post.md5,post.file_ext)
                                path = local.make_path(search['directory'], f"{post.id}.{post.md5}", post.file_ext)
                            else:
                                filename='{}.{}'.format(post.id,post.file_ext)
                                path = local.make_path(search['directory'], post.id, post.file_ext)
                            
                            if os.path.isfile(path):
                                print(f"[-] Post {post.id} was already downloaded.")

                            elif filename in files:
                                print(f"[-] Post {post.id} was already downloaded to another folder")
                                duplicate_func(files[filename], path)
                            else:
                                print(f"[+] Post {post.id} is being downloaded.")
                                if remote.download_post(post.file_url, path, session, cachefunc, duplicate_func):
                                    files[filename]=path
                            

                    # Break while loop. End program.
                    if last_id == 0 or chunk:
                        break

            download_queue.popleft()
        # End program.
    
    
    #----------HAAAAAAAAAAAAAAAAAX ---------
    download_queue.reset()
    
    #----------HAAAAAAAAAAAAAAAAAX end -----
    
    print('')
    input("[+] All searches complete. Press ENTER to exit...")
    raise SystemExit
    
    
# This block will only be read if e621dl.py is directly executed as a script. Not if it is imported.
if __name__ == '__main__':
    main()
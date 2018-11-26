#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Internal Imports
import os
import pickle
import re
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

storage = local.PostsStorage()


def process_results(results, whitelist, blacklist, anylist, cond_func, ratings, min_score, min_favs, days_ago, **dummy):
    filtered_results=[]

    for post in results:
        tags = post.tags
        
        if whitelist and not all( any(reg.fullmatch(tag) for tag in tags) for reg in whitelist ):
            continue
        elif blacklist and any( any(reg.fullmatch(tag) for tag in tags) for reg in blacklist ):
            continue
        elif anylist and not any(any(reg.fullmatch(tag) for tag in tags) for reg in anylist):
            continue
        elif not cond_func(set(tags)):
            continue
        elif post.rating not in ratings:
            continue
        elif int(post.score) < min_score:
            continue
        elif int(post.fav_count) < min_favs:
            continue
        elif post.days_ago >= days_ago:
            continue    
        else:
            #print('really')
            filtered_results.append(post)
    return filtered_results

#@profile
def prefilter_build_index(kwargses, use_db):
    
    if use_db:
        storage.connect()
    
    try:

        if download_queue.completed:
            return
        
        last_id = download_queue.last_id
        
        for kwargs in kwargses:

            print('')
            print(f"[i] getting tags for {kwargs['directory']}")            
            gen = kwargs['gen_funcs']
            append_func=kwargs['append_func']
            max_days_ago=kwargs['days_ago']
            
            for results in gen(last_id, **kwargs):
                append_func(results)
                filtered_results=process_results(results, **kwargs)
                download_queue.append(filtered_results)
                post=results[-1]
                download_queue.last_id=post.id
                if post.days_ago >= max_days_ago:
                    break
            
            last_id = 0x7F_FF_FF_FF
            download_queue.completed_gen(kwargs['directory'])        
        download_queue.completed = True    
    finally:
        download_queue.aborted = True
        if use_db:
            storage.close()
          
#@profile
def main():
    # Create the requests session that will be used throughout the run.
    local.save_on_exit_events(download_queue.save)
    with remote.requests_retry_session() as session:
        # Set the user-agent. Requirements are specified at https://e621.net/help/show/api#basics.
        session.headers['User-Agent'] = f"e621dl (lurkbbs) -- Version {constants.VERSION}"
        
        # Check if a new version is released on github. If so, notify the user.
        # if StrictVersion(constants.VERSION) < StrictVersion(remote.get_github_release(session)):
        #    print('A NEW VERSION OF e621dl IS AVAILABLE ON GITHUB AT https://github.com/Wulfre/e621dl/releases/latest.')

        print(f"[i] Running e621dl version {constants.VERSION}.")

        print('')
        print("[i] Parsing config...")

        config, hash = local.get_config()
        download_queue.check_config_hash(hash)

        # Initialize the lists that will be used to filter posts.
        blacklist = []
        searches = []

        # Initialize user configured options in case any are missing.
        include_md5 = False # The md5 checksum is not appended to file names.
        default_days_ago = 1
        default_date = local.get_date(default_days_ago) # Get posts from one day before execution.
        default_score = -0x7F_FF_FF_FF # Allow posts of any score to be downloaded.
        default_favs = 0
        default_ratings = ['s'] # Allow only safe posts to be downloaded.
        
        duplicate_func = copy
        cachefunc = None
        prefilter = None
        max_days_ago = default_days_ago
        cond_func = lambda x: True
        default_gen_func = remote.get_posts
        default_append_func = lambda x: None
        
        use_db = False
        allow_append = False
        
        # Iterate through all sections (lines enclosed in brackets: []).
        for section in config.sections():

            make_cache_flag=False
            # Get values from the "Settings" section. Currently only used for file name appending.
            if section.lower() == 'settings':
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
                            make_cache_flag=True
                    elif option.lower() in {'maintain_db','db','use_db','database', 'maintain_database' }:
                        if value.lower() == 'true':
                            default_append_func = storage.append
                            use_db = True
                            allow_append = True

                if make_cache_flag:
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
                    elif option.lower() in {'posts_from', 'posts_func', 'posts_source', 'post_from','post_func', 'post_source'}:
                        if value.lower() in {'db','database','local'}:
                            default_gen_func=storage.gen
                            default_append_func = lambda x: None
                            use_db = True
                        
            # Get values from the "Blacklist" section. Tags are aliased to their acknowledged names.
            elif section.lower() == 'blacklist':
                for option, value in config.items(section):
                    if option.lower() in {'tags', 'tag'}:
                        blacklist = [remote.get_tag_alias(tag.lower(), session) for tag in value.replace(',', ' ').lower().strip().split()]

        # If the section name is not one of the above, it is assumed to be the values for a search.
        # two for cycles in case of e.g 'blacklist' is in the end of a config file 
        for section in config.sections():
            if section.lower() not in {'settings','defaults','blacklist'}:

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
                section_blacklisted = []
                section_days_ago = default_days_ago
                section_gen_func = default_gen_func
                section_append_func = default_append_func

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
                        section_blacklisted = [remote.get_tag_alias(tag.lower(), session) for tag in value.replace(',', ' ').lower().strip().split()]
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
                    elif option.lower() in {'posts_from', 'posts_func', 'posts_source', 'post_from','post_func', 'post_source'}:
                        if value.lower() in {'db','database','local'}:
                            section_gen_func=storage.gen
                            section_append_func = lambda x: None
                            use_db = True
                        else:
                            section_gen_func=remote.get_posts
                            if allow_append:
                                section_append_func = storage.append
                
                section_tags += ['-'+tag for tag in blacklist+section_blacklisted]
                section_search_string = ' '.join(section_tags[:5])
                section_blacklist=[re.compile(re.escape(mask).replace('\\*','.*')) for mask in section_blacklist+blacklist+section_blacklisted]
                section_whitelist=[re.compile(re.escape(mask).replace('\\*','.*')) for mask in section_whitelist]
                section_anylist = [re.compile(re.escape(mask).replace('\\*','.*')) for mask in section_anylist]
                # Append the final values that will be used for the specific section to the list of searches.
                # Note section_tags is a list within a list.
                
                section_dict = {'directory': section.strip(),
                                 'search_string': section_search_string,
                                 'ratings': section_ratings,
                                 'min_score': section_score,
                                 'min_favs': section_favs, 
                                 'earliest_date': section_date, 
                                 'days_ago': section_days_ago, 
                                 'blacklist': section_blacklist, 
                                 'whitelist': section_whitelist, 
                                 'anylist': section_anylist,
                                 'cond_func': section_cond_func,
                                 'gen_funcs': section_gen_func,
                                 'append_func': section_append_func,
                                 'session'  : session}
                if section.lower() == 'prefilter':
                    prefilter=section_dict
                else:
                    searches.append(section_dict)
        
        
        
        print('')
        print("[i] Checking for partial downloads...")

        remote.finish_partial_downloads(session, cachefunc, duplicate_func)
        
        print('')
        print("[i] Building downloaded files dict...")
        files = local.get_files_dict(bool(cachefunc)) 

        
        
        if prefilter:
            prefilter['days_ago'] = max_days_ago
            kwargs = [prefilter]
        else:
            kwargs = [search for search in searches if not download_queue.in_gens(search['directory'])]

        queue_thread=Thread(target=prefilter_build_index, args=(kwargs, use_db))
        queue_thread.start()
        
        while True:
            try:
                chunk = download_queue.first()
            except:
            
                if download_queue.aborted:
                    break
                else:
                    sleep(0.5)
                    continue

            for search in searches:
                # Sets up a loop that will continue indefinitely until the last post of a search has been found.
                results = process_results(chunk,**search)
                directory = search['directory']
                    
                for post in results:
                    if include_md5:
                        filename='{}.{}.{}'.format(post.id,post.md5,post.file_ext)
                        path = local.make_path(directory, f"{post.id}.{post.md5}", post.file_ext)
                    else:
                        filename='{}.{}'.format(post.id, post.file_ext)
                        path = local.make_path(directory, post.id, post.file_ext)
                    
                    if os.path.isfile(path):
                        continue

                    elif filename in files:
                        duplicate_func(files[filename], path)
                        continue
                    else:
                        print(f"[+] Post {post.id} is being downloaded.")
                        if remote.download_post(post.file_url, path, session, cachefunc, duplicate_func):
                            files[filename]=path

            download_queue.popleft()
        # End program.
    
    
    if download_queue.completed:
        download_queue.reset()
        
    print('')
    print("[+] All searches complete. Press ENTER to exit...")
    raise SystemExit
    
    
# This block will only be read if e621dl.py is directly executed as a script. Not if it is imported.
if __name__ == '__main__':
    main()
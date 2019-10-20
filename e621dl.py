#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Internal Imports
import os
import re
from distutils.version import StrictVersion
from shutil import copy
from threading import Thread
from time import sleep
from concurrent.futures import ThreadPoolExecutor
from traceback import print_exc

# Personal Imports
from e621dl_lib import constants
from e621dl_lib import local
from e621dl_lib import remote
                
download_queue = local.DownloadQueue()

storage = local.PostsStorage()


def default_condition(x):
    return True

def has_actual_search(whitelist, blacklist, anylist, cond_func, **dummy):
    return whitelist or blacklist or anylist or cond_func != default_condition
    

def process_result(post, whitelist, blacklist, anylist, cond_func, ratings, min_score, min_favs, days_ago, **dummy):
    tags = post.tags
    if whitelist and not all( any(reg.fullmatch(tag) for tag in tags) for reg in whitelist ):
        return []
    elif blacklist and any( any(reg.fullmatch(tag) for tag in tags) for reg in blacklist ):
        return []
    elif anylist and not any(any(reg.fullmatch(tag) for tag in tags) for reg in anylist):
        return []
    elif not cond_func(set(tags)):
        return []
    elif post.rating not in ratings:
        return []
    elif int(post.score) < min_score:
        return []
    elif int(post.fav_count) < min_favs:
        return []
    elif post.days_ago >= days_ago:
        return []   
    else:
        return [post]
        

def process_results(results, **dummy):
    filtered_results=[]

    for post in results:
        filtered_results += process_result(post, **dummy)
        
    return filtered_results

#TODO: describe how this all works. God this is not intuitive
def get_directories(post, root_dirs, search, searches_dict):
    subdirectories = search['subdirectories']
    
    if not subdirectories:
        return ['/'.join(root_dirs)]
    
    results = []
    for directory in subdirectories:
        #preventing recursions in cases like cat/dog/cat/dog/...
        if directory in root_dirs:
            continue
        if process_result(post, **searches_dict[directory]):
            results += get_directories(post, root_dirs + [directory], searches_dict[directory], searches_dict)
            
    # if no results for subdirectories found
    # and current directory has some conditions to search
    # we place file here
    if not results and has_actual_search(**search):
        return ['/'.join(root_dirs)]
    else:
        return results
    

def get_files(post, format, root_dir, files, session, cachefunc, duplicate_func, search, searches_dict):
    if format:
        id_ext = f'{post.id}.{post.file_ext}'
        custom_prefix = format.format(**post.generate())[:100]
        filename = f'{custom_prefix}.{id_ext}'
    else:
        filename = f'{post.id}.{post.file_ext}'
    
    
    for directory in get_directories(post, [root_dir], search, searches_dict):
        file_id=post.id
        path = local.make_path(directory, filename)

        if os.path.isfile(path):
            continue
        elif file_id in files:
            duplicate_func(files[file_id], path)
            continue
        else:
            if remote.download_post(post.file_url, path, session, cachefunc, duplicate_func):
                files[file_id]=path
                
#@profile
def prefilter_build_index(kwargses, use_db):
    
    if use_db:
        storage.connect()
    
    try:

        if download_queue.completed:
            return
        
        last_id = download_queue.last_id
        
        for kwargs in kwargses:

            directory = kwargs['directory']
            print('')
            local.printer.change_section(directory)
            gen = kwargs['gen_funcs']
            append_func=kwargs['append_func']
            max_days_ago=kwargs['days_ago']
            
            results_num = 0
            
            for results in gen(last_id, **kwargs):
                results_num += len(results)
                local.printer.change_post(results_num)
                append_func(results)
                filtered_results=process_results(results, **kwargs)
                download_queue.append( (directory, filtered_results) )
                post=results[-1]
                download_queue.last_id=post.id
                if post.days_ago >= max_days_ago:
                    break
                if kwargs['posts_countdown'] <= 0:
                    break
            
            last_id = 0x7F_FF_FF_FF
            download_queue.completed_gen(directory)
        download_queue.completed = True
    except:
        local.printer.show(False)
        print("Exception in api iterator:")
        print_exc()
    finally:
        download_queue.aborted = True
        if use_db:
            storage.close()
          
#@profile
def main():
    # Create the requests session that will be used throughout the run.
    
    local.printer.start()
    
    local.save_on_exit_events(download_queue.save)
    with remote.requests_retry_session() as session:
        # Set the user-agent. Requirements are specified at https://e621.net/help/show/api#basics.
        session.headers['User-Agent'] = f"e621dl (lurkbbs) -- Version {constants.VERSION}"
        
        local.printer.change_status("Parsing config")

        config, hash = local.get_config()
        download_queue.check_config_hash(hash)

        # Initialize the lists that will be used to filter posts.
        blacklist = []
        searches = []
        searches_dict = {}

        # Initialize user configured options in case any are missing.
        include_md5 = False # The md5 checksum is not appended to file names.
        default_days_ago = 1
        default_date = local.get_date(default_days_ago) # Get posts from one day before execution.
        default_score = -0x7F_FF_FF_FF # Allow posts of any score to be downloaded.
        default_favs = 0
        default_ratings = ['s'] # Allow only safe posts to be downloaded.
        default_posts_limit = float('inf')
        default_format = ''
        default_subdirectories = set()
        
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
                            include_md5 =  True
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
                    elif option.lower() in {'limit', 'max_downloads', 'posts_limit', 'files_limit'}:
                        if value.lower() != 'inf':
                            default_posts_limit = int(value)
                        else:
                            default_posts_limit = float('inf')
                    elif option.lower() in {'format', 'default_format'}:
                        default_format = value.strip()
                    elif option.lower() in {'posts_from', 'posts_func', 'posts_source', 'post_from','post_func', 'post_source'}:
                        if value.lower() in {'db','database','local'}:
                            default_gen_func=storage.gen
                            default_append_func = lambda x: None
                            use_db = True
                    elif option.lower() in {'subfolder', 'subfolders', 'subdir', 'subdirs', 'subdirectory', 'subdirectories'}:
                        default_subdirectories.update( value.replace(',', ' ').lower().strip().split() )
                    
            # Get values from the "Blacklist" section. Tags are aliased to their acknowledged names.
            elif section.lower() == 'blacklist':
                for option, value in config.items(section):
                    if option.lower() in {'tags', 'tag'}:
                        blacklist = [remote.get_tag_alias(tag.lower(), session) for tag in value.replace(',', ' ').lower().strip().split()]

        # Making use of include_md5
        if include_md5 and len(default_format) == 0:
            default_format = '{id}.{md5}'

        # If the section name is not one of the above, it is assumed to be the values for a search.
        # two for cycles in case of e.g 'blacklist' is in the end of a config file 
        for section in config.sections():
            section_id = section.lower().strip()
            if section_id not in {'settings','defaults','blacklist'}:

                # Initialize the list of tags that will be searched.
                section_tags = []

                # Default options are set in case the user did not declare any for the specific section.
                section_date = default_date
                section_score = default_score
                section_favs = default_favs
                section_ratings = default_ratings
                section_cond_func = default_condition
                section_blacklist = []
                section_whitelist = []
                section_anylist = []
                section_blacklisted = []
                section_days_ago = default_days_ago
                section_gen_func = default_gen_func
                section_append_func = default_append_func
                section_post_limit = default_posts_limit
                section_format = default_format
                section_subdirectories = set() #default_subdirectories.copy()

                # Go through each option within the section to find search related values.
                for option, value in config.items(section):

                    # Get the tags that will be searched for. Tags are aliased to their acknowledged names.
                    if option.lower() in {'tags', 'tag'}:
                        section_tags = [remote.get_tag_alias(tag.lower(), session) for tag in value.replace(',', ' ').lower().strip().split()]
                        section_blacklist += [tag[1:] for tag in section_tags if tag[0]=='-']
                        section_anylist   += [tag[1:] for tag in section_tags if tag[0]=='~']
                        section_whitelist += [tag for tag in section_tags if tag[0] not in ('-','~')]
                        
                    elif option.lower() in {'subfolder', 'subfolders', 'subdir', 'subdirs', 'subdirectory', 'subdirectories'}:
                        section_subdirectories.update( value.replace(',', ' ').lower().strip().split() )
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
                    elif option.lower() in {'limit', 'max_downloads', 'posts_limit', 'files_limit'}:
                        if value.lower() != 'inf':
                            section_post_limit = int(value)
                        else:
                            section_post_limit = float('inf')
                    elif option.lower() in {'format', 'default_format'}:
                        section_format = value.strip()
                    elif option.lower() in {'condition', 'conditions'}:
                        if value.lower().strip():
                            source_template, tags = local.tags_and_source_template(value.lower().strip())
                            tags = [remote.get_tag_alias(tag.lower(), session) for tag in tags]
                            section_cond_func = local.make_check_funk(source_template, tags)
                    elif option.lower() in {'posts_from', 'posts_func', 'posts_source', 'post_from', 'post_func', 'post_source'}:
                        if value.lower() in {'db','database','local'}:
                            section_gen_func=storage.gen
                            section_append_func = lambda x: None
                            use_db = True
                        else:
                            section_gen_func=remote.get_posts
                            if allow_append:
                                section_append_func = storage.append
                
                section_tags += ['-'+tag for tag in blacklist+section_blacklisted]
                section_search_tags = section_tags[:5]
                section_blacklist=[re.compile(re.escape(mask).replace('\\*','.*')) for mask in section_blacklist+blacklist+section_blacklisted]
                section_whitelist=[re.compile(re.escape(mask).replace('\\*','.*')) for mask in section_whitelist]
                section_anylist = [re.compile(re.escape(mask).replace('\\*','.*')) for mask in section_anylist]
                
                if has_actual_search(section_whitelist, section_blacklist, section_anylist, section_cond_func):
                    section_subdirectories.update(default_subdirectories)
                # Append the final values that will be used for the specific section to the list of searches.
                # Note section_tags is a list within a list.
                
                if section_id[0] == "*":
                    section_directory = section_id[1:]
                else:
                    section_directory = section_id
                    
                section_dict = { 'directory': section_directory,
                                 'search_tags': section_search_tags,
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
                                 'posts_countdown': section_post_limit,
                                 'format':section_format,
                                 'subdirectories': section_subdirectories,
                                 'session'  : session}
                
                if section.lower() == 'prefilter':
                    prefilter=section_dict
                else:
                    searches_dict[section_directory] = section_dict
                    if section_id[0] != "*":
                        searches.append(section_dict)

        local.printer.change_tag("all tags are valid")
        local.printer.change_status("Checking for partial downloads")

        remote.finish_partial_downloads(session, cachefunc, duplicate_func)
        
        local.printer.change_status("Building downloaded files dict")
        files = local.get_files_dict(bool(cachefunc)) 
        
        
        if prefilter:
            prefilter['days_ago'] = max_days_ago
            kwargs = [prefilter]
        else:
            kwargs = [search for search in searches if not download_queue.in_gens(search['directory'])]

        local.printer.change_status("Downloading files")
        queue_thread=Thread(target=prefilter_build_index, args=(kwargs, use_db))
        queue_thread.start()
        
        download_pool=ThreadPoolExecutor(max_workers=2)
        
        while True:
            try:
                chunk_directory, chunk = download_queue.first()
            except:
            
                if download_queue.aborted:
                    break
                else:
                    sleep(0.5)
                    continue
    
            for search in searches:
                # Sets up a loop that will continue indefinitely until the last post of a search has been found.
                directory = search['directory']
                format = search['format']
                if chunk_directory.lower() not in (directory.lower(), 'prefilter'):
                    continue

                results = process_results(chunk, **search)
                futures = []
                
                for post in results:
                    if search['posts_countdown'] <= 0:
                        break
                        
                    futures.append(download_pool.submit(get_files,
                        post, format, directory, files,
                        session, cachefunc, duplicate_func, search, searches_dict))
                    
                    # TODO: Make sure that file in download queue
                    # actually downloaded and only then decrease counter.
                    search['posts_countdown'] -= 1
                    

                for future in futures:
                    if future.exception():
                        try:
                            raise future.exception()
                        except: #Pull request a better way
                            local.printer.show(False)
                            sleep(0.101)
                            print("Exception during download:")
                            print_exc()
                            download_queue.save()
                            os._exit(0)

            download_queue.popleft()
        # End program.
    
    
    if download_queue.completed:
        download_queue.reset()
        
    local.printer.change_status("All complete")
    raise SystemExit
    
    
# This block will only be read if e621dl.py is directly executed as a script. Not if it is imported.
if __name__ == '__main__':
    main()
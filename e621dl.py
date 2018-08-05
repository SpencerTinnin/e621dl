# Internal Imports
import os
from distutils.version import StrictVersion
from fnmatch import fnmatch
from shutil import copy

# Personal Imports
from lib import constants
from lib import local
from lib import remote

# This block will only be read if e621dl.py is directly executed by python. Not if it is imported.
if __name__ == '__main__':

    # Create the requests session that will be used throughout the run and set the user-agent.
    # The user-agent requirements are specified at (https://e621.net/help/show/api#basics).
    with remote.requests_retry_session() as session:
        session.headers['User-Agent'] = constants.USER_AGENT
        
        # Check if a new version is released on github. If so, notify the user.
        if StrictVersion(constants.VERSION) < StrictVersion(remote.get_github_release(session)):
            print('A NEW VERSION OF E621DL IS AVAILABLE ON GITHUB: (https://github.com/Wulfre/e621dl/releases/latest).')

        print('[i] Running e621dl version ' + constants.VERSION + '.')

        print('')

        print('[i] Checking for partial downloads...')

        remote.finish_partial_downloads(session)

        print('')

        print('[i] Parsing config...')

        config = local.get_config()

        # Initialize the lists that will be used to filter posts.
        blacklist = []
        searches = []
        files = local.get_files_dict()
        # Initialize user configured options in case any are missing.
        include_md5 = False # The md5 checksum is not appended to file names.
        default_date = local.get_date(1) # Get posts from one day before execution.
        default_score = -0x7FFFFFFF # Allow posts of any score to be downloaded.
        default_favs = 0
        default_ratings = ['s'] # Allow only safe posts to be downloaded.
        duplicate_func = copy
        
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

            # Get values from the "Defaults" section. This overwrites the initialized default_* variables.
            elif section.lower() == 'defaults':
                for option, value in config.items(section):
                    if option.lower() in {'days_to_check', 'days'}:
                        default_date = local.get_date(int(value))
                    elif option.lower() in {'min_score', 'score'}:
                        default_score = int(value)
                    elif option.lower() in {'min_favs', 'favs'}:
                        default_favs = int(value)
                    elif option.lower() in {'ratings', 'rating'}:
                        default_ratings = value.replace(',', ' ').lower().strip().split()

            # Get values from the "Blacklist" section. Tags are aliased to their acknowledged names.
            elif section.lower() == 'blacklist':
                blacklist = [remote.get_tag_alias(tag.lower(), session) for tag in config.get(section, 'tags').replace(',', ' ').lower().strip().split()]

            # If the section name is not one of the above, it is assumed to be the values for a search.
            else:

                # Initialize the list of tags that will be searched.
                section_tags = []

                # Default options are set in case the user did not declare any for the specific section.
                section_date = default_date
                section_score = default_score
                section_favs = default_favs
                section_ratings = default_ratings

                # Go through each option within the section to find search related values.
                for option, value in config.items(section):

                    # Get the tags that will be searched for. Tags are aliased to their acknowledged names.
                    if option.lower() in {'tags', 'tag'}:
                        section_tags = [remote.get_tag_alias(tag.lower(), session) for tag in value.replace(',', ' ').lower().strip().split()]

                    # Overwrite default options if the user has a specific value for the section
                    elif option.lower() in {'days_to_check', 'days'}:
                        section_date = local.get_date(int(value))
                    elif option.lower() in {'min_score', 'score'}:
                        section_score = int(value)
                    elif option.lower() in {'min_favs', 'favs'}:
                        section_favs = int(value)
                    elif option.lower() in {'ratings', 'rating'}:
                        section_ratings = value.replace(',', ' ').lower().strip().split()

                # Append the final values that will be used for the specific section to the list of searches.
                # Note section_tags is a list within a list.
                searches.append([section, section_tags, section_ratings, section_score, section_favs, section_date])

        for search in searches:
            print('')

            # Re-assign each element of the search list to an easier to remember name. There is probably a better way.
            directory = search[0]
            tags = search[1]
            ratings = search[2]
            min_score = search[3]
            min_favs = search[4]
            earliest_date = search[5]

            # Create the list that holds the title of each column in the search result table.
            # Keeping the titles in a list allows the use of list comprehension and the sum function.
            col_titles = ['downloaded', 'duplicate', 'rating conflict', 'blacklisted', 'missing tag', 'low score', 'low favorites']

            # Calculates the length of a row in the search results table including spacers so that text can be centered.
            row_len = sum(len(x) for x in col_titles) + ((len(col_titles) * 3) - 1)

            # Prints the title of the search, the titles of the results columns, and the table around it.
            #print('┌' + '─' * row_len + '┐')
            #print('│{:^{width}}│'.format(directory, width = row_len))
            #print('├─' + '─' * len(col_titles[0]) + '─┬─' + '─' * len(col_titles[1]) + '─┬─' + '─' * len(col_titles[2]) + '─┬─' + '─' * len(col_titles[3]) + '─┬─' + '─' * len(col_titles[4]) + '─┬─' + '─' * len(col_titles[5]) + '─┬─' + '─' * len(col_titles[6]) + '─┤')
            #print('│ ' + ' │ '.join(col_titles) + ' │')
            #print('├─' + '─' * len(col_titles[0]) + '─┼─' + '─' * len(col_titles[1]) + '─┼─' + '─' * len(col_titles[2]) + '─┼─' + '─' * len(col_titles[3]) + '─┼─' + '─' * len(col_titles[4]) + '─┼─' + '─' * len(col_titles[5]) + '─┼─' + '─' * len(col_titles[6]) + '─┤')

            # Initializes the results of each post in the search.
            in_storage = 0
            bad_rating = 0
            blacklisted = 0
            bad_tag = 0
            bad_score = 0
            bad_fav_count = 0
            downloaded = 0

            # Creates the string to be sent to the API.
            # Currently only 5 items can be sent directly so the rest are discarded to be filtered out later.
            if len(tags) > 5:
                search_string = ' '.join(tags[:5])
            else:
                search_string = ' '.join(tags)

            # Initializes last_id (the last post found in a search) to an enormous number so that the newest post will be found.
            # This number is hard-coded because on 64-bit archs, sys.maxsize() will return a number too big for e621 to use.
            last_id = 0x7FFFFFFF

            # Sets up a loop that will continue indefinitely until the last post of a search has been found.
            while True:
                print('[i] Getting posts...')
                results = remote.get_posts(search_string, earliest_date, last_id, session)

                # Gets the id of the last post found in the search so that the search can continue.
                # If the number of results is less than the max, the next searches will always return 0 results.
                # Because of this, the last id is set to 0 which is the base case for exiting the while loop.
                if len(results) < constants.MAX_RESULTS:
                    last_id = 0
                else:
                    last_id = results[-1]['id']

                # This dummy result makes sure that the for loop is always executed even for 0 real results.
                # This is so the table will print 0.
                dummy_id = 'There is no way this dummy will ever break as a long string. Probably.'
                results.append({'id':dummy_id, 'md5':dummy_id, 'file_ext':dummy_id})

                for post in results:
                    if include_md5:
                        filename='{}.{}.{}'.format(post['id'],post['md5'],post['file_ext'])
                        path = local.make_path(directory, str(post['id']) + '.' + str(post['md5']), post['file_ext'])
                    else:
                        filename='{}.{}'.format(post['id'],post['file_ext'])
                        path = local.make_path(directory, str(post['id']), post['file_ext'])

                    if post['id'] == dummy_id:
                        pass
                    elif os.path.isfile(path):
                        print('[✗] Post ' + str(post['id']) + ' was already downloaded.')
                        in_storage += 1
                    elif filename in files:
                        print('[✗] Post {} was already downloaded to another folder'.format( str(post['id']) ))
                        duplicate_func(files[filename], path)
                        in_storage += 1
                        
                    elif post['rating'] not in ratings:
                        print('[✗] Post ' + str(post['id']) + ' does not have a requested rating.')
                        bad_rating += 1

                    # Using fnmatch allows for wildcards to be properly filtered.
                    elif [x for x in post['tags'].split() if any(fnmatch(x, y) for y in blacklist)]:
                        print('[✗] Post ' + str(post['id']) + ' contains a blacklisted tag.')
                        blacklisted += 1
                    elif not set(tags[4:]).issubset(post['tags'].split()):
                        print('[✗] Post ' + str(post['id']) + ' is missing a requested tag.')
                        bad_tag += 1
                    elif int(post['score']) < min_score:
                        print('[✗] Post ' + str(post['id']) + ' has a low score.')
                        bad_score += 1
                    elif int(post['fav_count']) < min_favs:
                        print('[✗] Post ' + str(post['id']) + ' has a low favorite count.')
                        bad_fav_count += 1
                    else:
                        print('[✓] Post ' + str(post['id']) + ' is being downloaded.')
                        if remote.download_post(post['file_url'], path, session):
                            downloaded += 1
                            files[filename]=path
                    # Prints the numerical values of the search results.
                    #print('│ {:^{width0}} │ {:^{width1}} │ {:^{width2}} │ {:^{width3}} │ {:^{width4}} │ {:^{width5}} │ {:^{width6}} │'.format(
                        #str(downloaded), str(in_storage), str(bad_rating), str(blacklisted), str(bad_tag), str(bad_score), str(bad_fav_count),
                        #width0 = len(col_titles[0]), width1 = len(col_titles[1]), width2 = len(col_titles[2]), width3 = len(col_titles[3]), width4 = len(col_titles[4]), width5 = len(col_titles[5]), width6 = len(col_titles[6])
                        #), end = '\r', flush = True)

                # Print bottom of table. Break while loop. End program.
                if last_id == 0:
                    #print('')
                    #print('└─' + '─' * len(col_titles[0]) + '─┴─' + '─' * len(col_titles[1]) + '─┴─' + '─' * len(col_titles[2]) + '─┴─' + '─' * len(col_titles[3]) + '─┴─' + '─' * len(col_titles[4]) + '─┴─' + '─' * len(col_titles[5]) + '─┴─' + '─' * len(col_titles[6]) + '─┘')

                    break

    # End program.
    print('')
    input('[✓] All searches complete. Press ENTER to exit...')
    raise SystemExit

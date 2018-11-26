[![Github All Releases](https://img.shields.io/github/downloads/lurkbbs/e621dl/total.svg)](https://github.com/lurkbbs/e621dl/releases/latest)

# What is **e621dl**?

**e621dl** is an automated script, originally by [**@wwyaiykycnf**](https://github.com/wwyaiykycnf), which downloads images from e621.net. It can be used to create a local mirror of your favorite searches, and keep these searches up to date as new posts are uploaded.

# How does **e621dl** work?

Put very simply, when **e621dl** starts, it determines the following based on the `config.ini` file:

- Which tags you would like to avoid seeing by reading the blacklist section.
- Which searches you would like to perform by reading your search group sections.

Once it knows these things, it goes through the searches one by one, and downloads _only_ content that matches your search request, and has passed through all specified filters.

Main features of this fork:
- Search requests and file downloads work _in parallel_, so you do not need to wait file downloads to get new portion of tags to filter.
- **Duplicate** files are not downloaded again, they either copied or **hardlinked** from existing files. Think of _hardlink_ as of _another name and path for the same file_. That means hardlinks cannot be used across different disks, and if you change content in one hardlink, it will stay changed in another. But they take about zero space. This default option for duplicates, there is a settings to use plain file copy.
- If you need to stop e621dl, or there was some random error, it will continue search and download right were it stopped. On Windows, you can just close console window. Same for Linux consoles. More specifically for `SIGHUP`,`SIGINT` and `SIGTERM` signals.
- You can use `~`, `-` and `*` wildcards for every tags, not only first five. Be aware, only firs five can reduce number of requests to e621 API.
- You can use **advanced boolean conditions** for further filtering.
- You can cache all files downloaded before to cache folder. This is default behavior, actually.
- You can store all posts info from API to local database. This also default behavior.
- You can use said database as source of file link and filtered data instead of API. Combined with cache and deduplication, you can recreate downloads folder at any time with different filters. One limitation is you cannot use metatags with database search.
- You can use one API or DB prefilter to iterate over posts, with other searches using prefiltered results. Limitation is you cannot use metatags anywhere except for prefilter.

# Installing and Setting Up **e621dl**

- Download [the latest executable release of **e621dl**](https://github.com/lurkbbs/e621dl/releases).

*or*

- Download and install [the latest release of Python 3](https://www.python.org/downloads/release/python-3).
    - Make sure you check ":ballot_box_with_check: Add to PATH" on Windows during installation.
- Open admin command line and type `pip install requests`
- Download [the latest *source* release of **e621dl**](https://github.com/lurkbbs/e621dl/releases).
    - Decompress the archive into any directory you would like.

# Running **e621dl**
## Running **e621dl** from the Windows executable.

- Double click the e621dl.exe icon to run the program. It will close immediately on completion.
    - If you would like to read the output after the execution is complete, run the program through the command prompt in the directory that you placed the .exe file. On windows, you can Shift+Click on empty space of a folder and select _PowerShell_ (or _Command line_, depending on your settings). 

## Running **e621dl** from source.

You must install all of this program's python dependencies for it to run properly from source. They can be installed by running the following command in your command shell: `pip install [package name]`.
*You must run your command shell with admin/sudo permissions for the installation of new packages to be successful.*

The required packages for **e621dl** are currently:
- [requests](https://python-requests.org)

Open your command shell in the directory you decompressed e621dl into, and run the command `py e621dl.py`. Depending on your system, the command `py` may default to Python 2. In this case you should run `py -3 e621dl.py`. Sometimes, your system may not recognize the `py` command at all. In this case you should run `python3 e621dl.py`. In some cases where Python 3 was the first installed version of Python, the command `python e621dl.py` will be used. On Windows, if you associated python with *.py files during python installation, you can just double click on e621.py or in commandline enter `e621dl.py`.

The most common error that occurs when running a Python 3 program in Python 2 is `SyntaxError: Missing parentheses in call to 'print'`.

## First Run

The first time you run **e621dl**, you will see the following errors:

```
[i] Running e621dl version 5.0.0.

[i] Parsing config...
[!] No config file found.
[i] New default config file created. Please add tag groups to this file.'
```

These errors are normal behavior for a first run, and should not raise any alarm. **e621dl** is telling you that it was unable to find a `config.ini` file, so a generic one was created.

## Add search groups to the config file.

Create sections in the `config.ini` to specify which posts you would like to download. In the default config file, an example is provided for you. This example is replecated below. Each section will have its own directory inside the downloads folder.

```
;;;;;;;;;;;;;;;;;;;
;; SEARCH GROUPS ;;
;;;;;;;;;;;;;;;;;;;

; New search groups can be created by writing the following. (Do not include semicolons.):
; [Directory Name]
; days = 1
; ratings = s, q, e
; min_score = -100
; min_favs = 0
; tags = tag1 ~tag2 -tag3 tag* ...
; condition = tag | (tag_with_\&_or_\| & \(with_braces\))
; blacklisted = tag_blocked another_blocked
; post_source = api 
; ;post_source = db


; comma as separator is optional
; Example:
; [Cute Cats]
; days = 30
; ratings = s
; min_score = 5
; min_favs = 0
; tags = cat, cute 

; Example:
; [Cute Cats or Dogs]
; tags =  ~cat ~dog cute

; Example:
; [Cute Cats and no Dogs]
; tags =  cat -dog cute

; Example:
; [Conditional Cat]
; tags = cat
; condition = -sad & ( (cute & happy) | (smile & closed_eyes) )

; Example:
; [Cat-like]
; tags = cat*

; Example:
; [Video Cat]
; tags = cat type:webm


; Example:
; [Blacklisted Cat]
; tags = cat
; blacklisted = dog 

; Example:
; [Database Cat]
; tags = cat
; post_source = db
```

The following characters are not allowed in search group names: `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`, `/` as they can cause issues in windows file directories. If any of these characters are used, they will be replaced with the `_` character.

Commas or spaces are used to separate tags and ratings.

One side effect of the workaround used to search an unlimited number tags is that you may only use up to 5 meta tags `:` and they must be the first 5 items in the group. See [the e621 cheatsheet](https://e621.net/help/show/cheatsheet) for more information on these special types of tags.

### Search Group Keys, Values, and Descriptions

Key                   | Acceptable Values               | Description
--------------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------
[]                    | Nearly Anything                 | The search group name which will be used to title console output and name folders. See above for restrictions.
days                  | Integer from `1` to ∞           | How many days into the past to check for new posts.
ratings               | Characters `s`, `q`, and/or `e` | Acceptable explicitness ratings for downloaded posts. Characters stand for safe, questionable, and explicit, respectively.
min_score             | Integer from -∞ to ∞            | Lowest acceptable score for downloaded posts. Posts with higher scores than this number will also be downloaded.
min_favs              | Integer from 0 to ∞             | Same as _min_score_, but for favorites.
tags                  | Nearly Anything                 | Tags which will be used to perform the post search. See above for restrictions.
blacklisted           | Nearly Anything                 | Essentialy the same as _-tags_ at the and of a tag list.
post_source           | `api` or `db`                   | If `api`, e621 will be used to search and filter posts and files. If `db`, links to files from local database will be used. See below for details.
condition             | Nearly Anything                 | If you need for a fine-grained filter, you can use boolean conditions where `&` means `and`, `|` means `or` and `-` means `not`. See below for details.

### Conditions

`condition` option allows you to use fine-grained filter on any non-metatags. It is a boolean expression where where `&` means `and`, `|` means `or`, `-` means `not` and everything else is interpreted as a tagname. Since a tag can be of any characters except `%,#\*` and first characters cannot be `-~`, if you want to use tags with `|&()` characters, you should screen it with `\` symbol, like that:

`digital_media_\(artwork\)` for `digital_media_(artwork)`

`:\|` for `:|`

`dungeons_\&_dragons` for `dungeons_&_dragons`

etc.

Let's examine condition from example above:

`condition = -sad & ( (cute & happy) | (smile & closed_eyes) )`

Think of this as

```
condition =  NOT <"sad" in post tags>  AND
				(
                	( <"cute" in post tags> AND <"happy" in post tags>)
             		OR (<"smile" in post tags> AND <"closed_eyes" in post tags>)
                )
```
This means that if there is tag "sad" in post, condition is not fulfilled. Otherwise, if in post there are both tag `cute` and tag `happy`, condition will be fulfilled. If one of them or both are not in post, then if there are both tag `smile` and tag `closed_eyes`, condition will be fulfilled anyway. If not, condition is false and file will not be downloaded. Note: if there are all four tags, condition also will be fulfilled. There is no `if` operator either.

### Database as a source of filenames

By default, all posts' info are stored in local database. So, if `post_source` set to `db`, all info, e.g. rating, creation date or link to file will be from there, not from e621 api. In combination with local file cache, this can be used to recreate folders with new filtering, more strict or more relaxed. `api` is default, but this can be overwritten in `Defaults` section.

## Section [Defaults]

This section sets default values for all search groups and for prefilter. Default values can be set for this search group optinons:
* days
* ratings
* min_score
* min_favs
* post_source

See details on every option in _Search Group Keys, Values, and Descriptions_.

## Section [Blacklist]

This section have only one option, `tags`, an essentially every tags from here are appended to search string with `-` before tag name. It's here mostly for historical reason than anything else.

## Section [Settings]

Settings for e621dl. All settings are boolean values that accept `true` or `false`.

Name               |       Description
-------------------|-----------------------------
include_md5        | If `true`, files in folder will look like {id}.{md5}.{ext}. Otherwise, it will look line {id}.{ext} . As of e621dl 5.0.0, deduplication will not work if this value changed after some files are dowloaded  between new and old files. In short, please don't change this after something was downloaded.
make_hardlinks     | If `true`, if a file was already downloaded somewhere else, hardlink will be created. Otherwise, full copy of a file will be created.
make_cache         | If `true`, every downloaded file will be hardlinked/copied to `cache` folder.
db                 | If `true`, every post info will be stored in local database. If it's false, but database already is created, it can be used as a post info source, but no entries will be updated/created.

Default values:

```
[Settings]
include_md5 = false
make_hardlinks = true
make_cache = true
db = true
```

## Section [Prefilter]

If this section exists, filters from here will be used as first step filtering, and search string from here will be the only string to request from either API or DB. Here is an example:

```
[Prefilter]
tags = ~cat ~dog ~parrot ~owl

[Cats]
tags = cat

[Dogs]
tags = dog

[Parrot]
tags = parrot

[Owl]
tags = owl
```

This way we will iterate over both tags without redundant overlapping for every tag search string.

Prefilter has exactly the same parameters as regular searches, but days are actually maximum days of all searches.

## Normal Operation

Once you have added at least one group to the tags file, you should see something similar to this when you run **e621dl**:

```
[i] Running e621dl version 5.0.0.

[i] Parsing config...
[i] config.ini changed, resetting saved queue
[+] The tag cat is valid.
[+] The tag dog is valid.
[+] The tag parrot is valid.
[+] The tag owl is valid.

[i] Checking for partial downloads...

[i] Building downloaded files dict...

[i] getting tags for Prefilter
[+] Post {id1} is being downloaded.
[+] Post {id2} is being downloaded.
[+] Post {id3} is being downloaded.
.......................................
[+] Post {id_last} is being downloaded.

[+] All searches complete. Press ENTER to exit...
```

Only posts that are actually downloaded will generate text. Every skipped or duplicated will not generate anything.

# Automation of **e621dl**

It should be recognized that **e621dl**, as a script, can be scheduled to run as often as you like, keeping the your local collections always up-to-date, however, the methods for doing this are dependent on your platform, and are outside the scope of this quick-guide.

# Feedback and Requests

If you have any ideas on how to make this script run better, or for features you would like to see in the future, [open an issue](https://github.com/lurkbbs/e621dl/issues) and I will try to read it as soon as possible.

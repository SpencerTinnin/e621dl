[![Github All Releases](https://img.shields.io/github/downloads/lurkbbs/e621dl/total.svg)](https://github.com/lurkbbs/e621dl/releases/latest)

# What is **e621dl**?

**e621dl** is an automated script, originally by [**@wwyaiykycnf**](https://github.com/wwyaiykycnf), which downloads images from e621.net. It can be used to create a local mirror of your favorite searches, and keep these searches up to date as new posts are uploaded.

# How does **e621dl** work?

Put very simply, when **e621dl** starts, it determines the following based on config files:

- Which tags you would like to avoid seeing by reading the blacklist section.
- Which searches you would like to perform by reading your search group sections.

Once it knows these things, it goes through the searches one by one, and downloads _only_ content that matches your search request, and has passed through all specified filters.

Main features of this fork:
- Search requests and file downloads work _in parallel_, so you do not need to wait file downloads to get new portion of tags to filter.
- **Duplicates** are not downloaded again, they either copied or **hardlinked** from existing files. Think of _hardlink_ as of _another name and path for the same file_. That means hardlinks cannot be used across different disks, and if you change content in one hardlink, it will stay changed in another. But they take about zero space. Since on Windows you have to be admin or enable Developer Mode (Win10 only), this **option is disabled by default**. To enable it, add `make_hardlinks = true` to `[Settings]` and be sure either Developer Mode is enabled or that the app runs with admin privilege.
- If you need to stop e621dl, or there was some random error, it will continue search and download right were it stopped. On Windows, you can just close console window. Same for Linux consoles. More specifically for `SIGHUP`,`SIGINT` and `SIGTERM` signals.
- You can use **advanced boolean conditions** for further filtering.
- You can cache all files downloaded before to cache folder. This is **not** default behavior.
- You can store all posts info from API to local database. This is also **not** default behavior.
- You can use said database as source of file link and filtered data instead of API. Combined with cache and deduplication, you can recreate downloads folder at any time with different filters. One limitation is you cannot use metatags with database search.
- You can use one API or DB prefilter to iterate over posts, with other searches using prefiltered results. Limitation is you cannot use metatags anywhere except for prefilter.
- [**Cloudflare captcha support**](Cloudflare.md) Note: this is not captcha bypass, you're still need to solve it in a browser with special addon, launched from the same IP address with e621dl.
- **Improved connection stability**. You can plug and unplug network cable and e621dl will continue as if nothing happened.
- Max downloaded files per section limit. You can download only, say, 100 last files.
- **`order:` metatag family support**. With max downloads limit you can get e.g. top 10 most rated or top 25 least favorite.
- **Multithreaded**. 
- **Folder pruning**. All files that are no longer required can be removed on next run. This is **not** a default behavior.
- Easy post blacklisting. Just move files you don't wanna see again to a special folder, and you won't. The files will also be removed from the folder.
- **Authorization via e621 API key**.
- Option to not redownload deleted files

# Installing and Running **e621dl**
## from a Windows executable

- Download [the latest executable release of **e621dl**](https://github.com/lurkbbs/e621dl/releases).
- Double click the e621dl.exe icon to run the program. It will close immediately on completion.
    - You can use e621_noclose.bat to hold console window after e621dl.exe finishes. That way, the window will be present even if e621dl.exe crashes 

## from source

If you want to run from source on Windows and have zero understanding of how to install it all, follow this instruction:

1. Open PowerShell as an Admin. On Win10, you can right-click on Start Button, then select PowerShell (Admin)
2. Paste this and press Enter:

```
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))
```

And confirm everything if needed. This installs chocolatey.

3. Paste this and press Enter in the same or a new console:

```
choco install python
```

And also confirm everything. Obviously, this installs python. If it  doesn't work, close PowerShell then open it and paste-enter again.

4. Paste this and press Enter in the same or a new console:

```
pip install requests colorama natsort brotli
```

This installs all required dependencies

5. [Download source](https://github.com/Wulfre/e621dl/archive/master.zip) and unpack it to a folder, then doubleclick `e621_noclose_py.bat`

## For Windows 10 users

If you want to use hardlinks without admin rights, you can enable "Developer mode" this way

Settings > Update & Security > For Developers and select "Developer mode". Details about Developer Mode can be found [here](https://www.howtogeek.com/292914/what-is-developer-mode-in-windows-10/).

## First Run

The first time you run **e621dl**, you will see the following:

```
[!] New default config file created in folder 'config'.
Please add tag groups to this file.
You can add additional config files,
they will be processed in natural order:
https://en.wikipedia.org/wiki/Natural_sort_order
```

This is normal behavior for a first run, and should not raise any alarm. **e621dl** is telling you that it was unable to find a `configs` folder, so a new was made along with a generic config file.

You can rename this config, also you can add more, they will run one by one in [Natural order](https://en.wikipedia.org/wiki/Natural_sort_order). You can use it to e.g. download only some images first and create a database (see below), and download everything else on second config.

## Add search groups to the config file.

Create sections in the `config.ini` to specify which posts you would like to download. In the default config file, an example is provided for you. This example is replicated below. Each section will have its own directory inside the downloads folder. `;` is just a comment symbol

```ini
;;;;;;;;;;;;;;
;; GENERAL  ;;
;;;;;;;;;;;;;;

;Meaning of these setting described
;In the README.md in Section [Settings]
;These settings are all false by default
;[Settings]
;include_md5 = true
;make_hardlinks = true
;make_cache = true
;db = true
;offline = true
;prune_downloads = true
;prune_cache = true
;login = your e621 login
;api_key = your e621 api key generated in account settings

;These are default settings for all search groups below
;[Defaults]
;days = 1
;min_score = -2147483647
;min_favs = 0
;ratings = s q e
;max_downloads = inf
;post_from = api ;db is for saved database
;format = 

;This is a special prefiltration section.
;If it exists, all subsequent search groups
;use results obtained from prefiltered search.
;Due to some limitations,metatags in other
;search groups are not supported.
;Mostly useful if you have a lot of searches
;that all have something in common.
;[Prefilter]
;tags = 
;condition = 


;There can be multiple prefilters.
;While 'Prefilter' section is saved 
;for backward compatibility, you can
;Iterate e621 api over more than one
;global filter. May be useful if you
;want to e.g. download images before
;videos.
;To denote prefilter place 
;section name between <> brackets.
;[<Another prefilter>]
;tags = 
;condition = 

;[Blacklist]
;tags = invalid_tag

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
; This will create folder "Cats" and
; subfolder "Wildcats" inside "Cats"
; [Cats/WildCats]
; days = 30
; ratings = s
; min_score = 5
; min_favs = 0
; tags = wildcat 

; Example:
; [Cute Cats or Cute Dogs]
; tags =  ~cat ~dog cute

; Example:
; [Cute Cats and no Dogs]
; tags =  cat -dog cute

; Example:
; This condition means this:
; no post with tag "sad" will be downloaded.
; If there is no "sad" tag than if
; there are both tags "cute" and "happy"
; and/or
; there are both tags "smile" and "closed_eyes"
; then post will be downloaded.
; So, condition is
; no "sad" tag and ( ("cute" tag and "happy tag") and/or ("smile" tag and "closed_eyes" tag))
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

; This will download only top 10 highest score posts
; Example:
; [Top Ten Cat]
; tags = order:score cat
; max_downloads = 10

; This will generate filenames like artistname.id.extension,
; e.g. suncelia.1572867.jpg
; Example:
; [Formatted Cat]
; tags = cat
; format = {artist}

; This can be used as a subfolder for 
; a subcategory, details in next section.
; '*' means "don't download this section"
; and it's optional to make subcategory
; beside "tag" option you can use
; "condition", "days", "ratings",
; "min_score", "min_favs"
;
; Example:
; [*wide_eyed_subcat]
; tags = wide_eyed

; Watch closely
; If any post has tag "cat" and also
; corresponds to subcategory
; (has "wide_eyed" tag in our case), than
; it will be downloaded only in subfolder,
; in "cat_with_subfolder/wide_eyed_subcat"
; in our case.
; If there are more than one
; subcategory post corresponds to,
; it will be saved in each one.
; If post is not corresponds with any of
; subcategories, it will be stored in original
; folder, "cat_with_subfolder" in our case.
;
; Example:
; [cat_with_subfolder]
; tags = cat
; subfolders = wide_eyed_subcat
```

The following characters are not allowed in search group names: `:`,  `?`, `"`, `<`, `>`, `|`, as they can cause issues in windows file directories. If any of these characters are used, they will be replaced with the `_` character.

`*` Can be used at the start of a group name to disable its downloading. Useful to skip group for one time and to create subcategory. If an asterisk is in any other part of a group name, it is replaced with `_` in the folder name. Note: you cannot disable `prefilter` section with `*`.

These characters are folder separators: `\` `/`. Use them to create subfolders inside a folder inside `downloads`, for e.g. collection sorting.

Commas or spaces are used to separate tags and ratings.

One side effect of the workaround used to search an unlimited number tags is that you may only use up to 5 meta tags `:` and they must be the first 5 items in the group. See [the e621 cheatsheet](https://e621.net/help/show/cheatsheet) for more information on these special types of tags.

### Search Group Keys, Values, and Descriptions

| Key                          | Acceptable Values                   | Description                                                  |
| ---------------------------- | ----------------------------------- | ------------------------------------------------------------ |
| []                           | Nearly Anything                     | The search group name which will be used to title console output and name folders. See above for restrictions. |
| days                         | Integer from `1` to ∞               | How many days into the past to check for new posts.          |
| ratings                      | Characters `s`, `q`, and/or `e`     | Acceptable explicitness ratings for downloaded posts. Characters stand for safe, questionable, and explicit, respectively. |
| min_score                    | Integer from -∞ to ∞                | Lowest acceptable score for downloaded posts. Posts with higher scores than this number will also be downloaded. |
| min_favs                     | Integer from 0 to ∞                 | Same as _min_score_, but for favorites.                      |
| tags                         | Nearly Anything                     | Tags which will be used to perform the post search. See above for restrictions. |
| blacklisted                  | Nearly Anything                     | Essentially the same as _-tags_ at the and of a tag list.    |
| post_source                  | `api` or `db`                       | If `api`, e621 will be used to search and filter posts and files. If `db`, links to files from local database will be used. See below for details. |
| condition                    | Nearly Anything                     | If you need for a fine-grained filter, you can use boolean conditions where `&` means `and`, `|` means `or` and `-` means `not`. See below for details. |
| max_downloads                | Integer from `1` to ∞               | Limits number of downloaded posts in addition to time of upload. |
| format                       | see below                           | Allows to format filename beside id.extension. See below for details |
| subfolders                   | search group names, space separated | all posts that correspond to searches in the subfolder and to current search are placed in the subfolder and not in main folder. See below for details |
| blacklist_default_subfolders | true/false                          | if true, subfolders from `Defaults` won't be appended to this section's `subfolders` |

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

### Format of filenames

By default, filenames looks like `1572867.jpg`, but you can change it, using with format field. Example:

`format = Artist name -- {artist} and score is {score}`

Will produce this file:

`Artist name -- suncelia and score is 17.1572867.jpg`

Following fields are supported:

* id
* rating
* id
* md5
* file_ext
* score
* fav_count
* artist
* file_size
* width
* height
* author
* creator_id

Notes:

* author is uploader's username, not artist's name. Use artist for that
* creator_id is id of uploader, not artist

There may be more supported fields in the future, but I don't promise anything unless you create a feature request in [Issues](https://github.com/lurkbbs/e621dl/issues).

### Order metatag family

Metatags like `order:score` and other `order:smth` are not compatible with main post iteration mechanism, looking for all posts after some post id. Instead, pagination is use. That means:

* If a post is added or removed between pages, some other post could be skipped
* The can be no more than 750 pages or 750*320 = 240'000 posts

No skip is guaranteed only for first page, that is first 320 posts.

### Subfolders option

Let me demonstrate how it works with some examples.

First, what if we wanted to all `unknown_artist` images to be in separate folder.

```ini
;;;;;;;;;;;;;;
;; GENERAL  ;;
;;;;;;;;;;;;;;

[Settings]
include_md5 = false
make_hardlinks = true
make_cache = true
db = true

;{artists} means filenames will be like
;artist1_artist2.<post id>.jpg
[Defaults]
days = 100
ratings = s
format = {artist}

;;;;;;;;;;;;;;;;;;;
;; SEARCH GROUPS ;;
;;;;;;;;;;;;;;;;;;;

; For now, there should be no spaces in
; subcategory name
[*Unknows_Artist]
tag = unknown_artist

[Cats]
tags = cat
subfolders = Unknows_Artist

[Dogs]
tags = dog
subfolders = Unknows_Artist

[Wolves]
tags = wolf
subfolders = Unknows_Artist
```

For every folder, subfolder `Unknows_Artist` will be created and all images without known artist will be placed there. So, we will have folder tree like this:

```
Downloads
|
|-- Cats
|   |
|   |-- Unknows_Artist
|
|-- Dogs
|   |
|   |-- Unknows_Artist
|
|-- Wolves
    |
    |-- Unknows_Artist
```

Alternatively, we can add subcategory to `Defaults`

```ini
[Defaults]
days = 100
ratings = s
format = {artist}
subfolders = Unknows_Artist

;;;;;;;;;;;;;;;;;;;
;; SEARCH GROUPS ;;
;;;;;;;;;;;;;;;;;;;

; For now, there should be no spaces in
; subcategory name
[*Unknows_Artist]
tag = unknown_artist

[Cats]
tags = cat

[Dogs]
tags = dog

[Wolves]
tags = wolf
```

Result will be the same

Now what about two subcategories. Say, `unknown_artist` and `dragon`

```ini
[*Unknows_Artist]
tag = unknown_artist

[*Dragons]
tag = dragon

[Cats]
tags = cat
subfolders = Unknows_Artist Dragons

[Dogs]
tags = dog
subfolders = Unknows_Artist Dragons

[Wolves]
tags = wolf
subfolders = Unknows_Artist Dragons
```

For now, there is unintuitive behavior with Defaults and two+ subcategories

```ini
[Defaults]
days = 100
ratings = s
format = {artist}
subfolders = Unknows_Artist Dragons

;;;;;;;;;;;;;;;;;;;
;; SEARCH GROUPS ;;
;;;;;;;;;;;;;;;;;;;

; For now, there should be no spaces in
; subcategory name
[*Unknows_Artist]
tag = unknown_artist

[*Dragons]
tag = dragon

[Cats]
tags = cat

[Dogs]
tags = dog

[Wolves]
tags = wolf
```

will lead to 

```
Downloads
|
|-- Cats
|   |
|   |-- Unknows_Artist
|   |    |
|   |    |-- Dragons
|   |
|   |-- Dragons
|       |
|       |-- Unknows_Artist
|
|-- Dogs
|   |
|   |-- Unknows_Artist
|   |    |
|   |    |-- Dragons
|   |
|   |-- Dragons
|       |
|       |-- Unknows_Artist
|
|-- Wolves
    |
    |-- Unknows_Artist
    |    |
    |    |-- Dragons
    |
    |-- Dragons
        |
        |-- Unknows_Artist
```

If have some issue with that, post it [here]( https://github.com/lurkbbs/e621dl/issues ). If not, I'll leave it like this for now.

Also, you can make a subcategory inside of another subcategory. And you can make an empty subcategory, like this

```ini
[*Monster_Rancher]
tags = monster_rancher

[*Pokemon]
tags = pokémon

[*Digimon]
tags = digimon

; Note: nothing except subfolder should be
; in an empty subcategory
[*Mons]
subfolders = Monster_Rancher Pokemon Digimon

[Cats]
tags = cat
subfolders = Mons

[Dogs]
tags = dog
subfolders = Mons

[Wolves]
tags = wolf
subfolders = Mons
```

This will give us

```
Downloads
|
|-- Cats
|   |
|   |-- Mons (should be empty)
|        |
|        |-- Pokemon
|        |
|        |-- Monster_Rancher
|        |
|        |-- Pokemon
|    
|-- Dogs
|   |
|   |-- Mons (should be empty)
|        |
|        |-- Pokemon
|        |
|        |-- Monster_Rancher
|        |
|        |-- Pokemon
|    
|-- Wolves
    |
    |-- Mons (should be empty)
         |
         |-- Pokemon
         |
         |-- Monster_Rancher
         |
         |-- Pokemon
```





## Section [Defaults]

This section sets default values for all search groups and for prefilter. Default values can be set for this search group optinons:
* days
* ratings
* min_score
* min_favs
* post_source
* max_downloads
* format

See details on every option in _Search Group Keys, Values, and Descriptions_.

## Section [Blacklist]

This section have only one option, `tags`, an essentially every tags from here are appended to search string with `-` before tag name. It's here mostly for historical reason than anything else.

## Section [Settings]

Settings for e621dl. All settings are boolean values that accept `true` or `false`.

| Name            | Description                                                  |
| --------------- | ------------------------------------------------------------ |
| include_md5     | Changed in e621dl 5.4.0. If `true`, and format field in [defaults] is not set, default format became id.md5.id.ext instead of id.ext. This way you can deduplicate files and see md5 in a filename |
| make_hardlinks  | If `true`, if a file was already downloaded somewhere else, hardlink will be created. Otherwise, full copy of a file will be created. |
| make_cache      | If `true`, every downloaded file will be hardlinked/copied to `cache` folder. |
| db              | If `true`, every post info will be stored in local database. If it's false, but database already is created, it can be used as a post info source, but no entries will be updated/created. |
| offline         | If `true`, no requests whatsoever will be sent to e621. Tag aliasing is skipped, so if you use `cat` instead of `domestic_cat` and so on, you get incorrect result. Art description will be taken from local database (you have to have one, just use `db=true` at least once). If some files are not in cache or other folders, it won't be downloaded. You can use it to fast recreate folder structure. If you want to just download new section without stopping for one second every 320 art infos, you can use `post_source = db` in default section. Info will be acquired from local database, but tags will be checked and files will be downloaded. This option must be enabled in all configs to work properly. |
| prune_downloads | If `true` in at least one of config files, all files in `downloads` that do not meet any of search criteria will be removed after all configs are processed. It's as if you removed everything and then download only what you need. This option will be true for every configs if set to true in at leas one of them. |
| prune_cache     | If you have a cache folder and if `true` in at least one of config files , than any files that has not a single copy/hardlink in `downloads ` will be deleted after all configs are processed. It's as if we manually removed all files in the cache and then copied it from downloads. This option will be true for every configs if set to true in at leas one of them. |
| login           | Your e621 login                                              |
| api_key         | Your API key, generated in "Account" > "Manage API Access"   |
| no_redownload   | Blocks e621dl from redownloading files from a folder if they were deleted from there. This option will be true for every configs if set to true in at leas one of them. |



```ini
[Settings]
include_md5 = false
make_hardlinks = true
make_cache = true
db = true
```

## Section [Prefilter] or any [\<triangle braked\>]

If these sections exist, filters from here will be used as first step filtering, and search string from here will be the only string to request from either API or DB. Here is an example:

```ini
[Prefilter]
tags = ~cat ~dog ~parrot ~owl

[<Another prefilter>]
tags = ~rabbit ~dolphin ~shark ~kangaroo

[Cats]
tags = cat

[Dogs]
tags = dog

[Parrots]
tags = parrot

[Owls]
tags = owl

[Rabbits]
tags = rabbit

[Dolphins]
tags = dolphin

[Sharks]
tags = shark

[Kangaroos]
tags = kangaroo
```

This way we will iterate over all four tags without redundant overlapping for every tag search string.

Prefilters have exactly the same parameters as regular searches, but days are actually maximum days of all searches. Another limitation is metatags are not supported outside of prefilter sections.

## Normal Operation

Once you have added at least one group to the tags file, you should see something similar to this when you run **e621dl**:

```
status : Just starting
checked tag : None so far
posts so far : None so far
last file downloaded : None so far
current section : None so far
last warning : None so far
connection retries : None so far
already exist : None so far
downloaded : None so far
copied : None so far
filtered : None so far
not found on e621 : None so far
```

*Status* shows what's going on, that is if config is being parsed or if tags are checked or files are being downloaded, things like those.

*Checked* tag shows which tag is checked for validity. It will be set to `all tags are valid` after check completion.

*Posts* so far shows how many posts are processed from api so far. Mostly here to show that the app is still working. It can lag a bit if a lot of new files are in download queue.

*Recent file downloaded*  shows what file has just been downloaded and where. Only files that are actually downloaded will generate text. Every skipped or duplicated will not generate anything.

*Сurrent config* shows config file that is being processed now.

*Current section*  shows which search group is processed now.

*Recent warning*  shows last non-critical info and is mostly for troubleshooting.

*Connection retries* shows how often connections was reopened. This could happen because your ISP reconnected, you pc went into sleep mode/hybernate, your network cable was unplugged or WiFi loosed signal. After 100 retries e621dl will be closed.

*Already exist* shows how many files was already downloaded in exactly the same folder we want it to be.

*Downloaded* shows how many files were actually downloaded from e621 servers.

*Copied* shows how many files were copied/hardlinked from another folder or cache

*Filtered* shows how many processed posts from e621 api were not downloaded because of rating, condition, score etc.

*Not found on e621* shows if there was no such file on e621. This happens mostly with `post_source = db`  or `offline = true`, because post stored in database was deleted from e621 and there was no copy in a cache. On rare occasion post can become deleted in time between link was acquired and actual file was being download.

Note that if e621dl started with double click, its window closes by itself on exit. This is mostly because of some coding shortcuts and because it would be hard to automate it otherwise. If you want for windows to continue after all downloads, you can use `e621_noclose.bat` in Windows, or run it from console directly on any OS.

# Cloudflare Recaptcha

If for some reason Cloudflare thinks your IP is DDOS'ing e621, use this instruction to solve a captcha: [Cloudflare solution](Cloudflare.md)

# Individual post blacklisting

After first download of something, in the app folder there will be folder `to_blocked_posts` and file `blocked_posts.txt`. You can either move/copy blocked files to the folder, or manually add id of an art in the file, one id per line. On next `e621dl` run all files in `to_blocked_posts`  will be removed (but not folders for now), and these files will never be downloaded again. 



# Automation of **e621dl**

It should be recognized that **e621dl**, as a script, can be scheduled to run as often as you like, keeping the your local collections always up-to-date, however, methods for doing so are dependent on your platform, and are outside the scope of this quick-guide.

# Feedback and Requests

If you have any ideas on how to make this script run better, or for features you would like to see in the future, [open an issue](https://github.com/lurkbbs/e621dl/issues) and I will try to read it as soon as possible.

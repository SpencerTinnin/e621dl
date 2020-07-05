VERSION = '5.11.0'

MAX_RESULTS = 320
MAX_RESULTS_OFFLINE = 32000
PARTIAL_DOWNLOAD_EXT = 'request'

# first number: time to establish connection
# second number: max wait between bytes sent
# aka (connect timeout, read timeout)
CONNECTION_TIMEOUT = (6.1, 15.5)

MAX_USER_SEARCH_TAGS = 38 #one for time tag, one for id tag

# 'author' is a field I just don't know anything about
# I'll leave it for now.
# 'creator_id' is now 'uploader_id' in e621 API
DEFAULT_SLOTS = ['id','tags','rating','md5','file_ext','file_url',
                 'score','fav_count','days_ago', 'sources', 'artist', 'description',
                 'file_size', 'width', 'height', 'author',
                 'creator_id', 'created_at', 'created_at_string', 
                 'score_up', 'score_down', 'tag_ex', 'pools' ]

DEFAULT_CONFIG_TEXT = ''';;;;;;;;;;;;;;
;; GENERAL  ;;
;;;;;;;;;;;;;;

;Meaning of these setting described
;In the README.md in Section [Settings]
;These settings are all false by default
;[Settings]
;include_md5 = false
;make_hardlinks = true
;make_cache = true
;db = true
;offline = true
;prune_downloads = true
;prune_cache = true
;login = your e621 login
;api_key = your e621 api key generated in account settings
;no_redownload = true
;pool_download_generate = true

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
'''

DEFAULT_POOLS_CONFIG="""

;[Settings]
;include_md5 = false
;make_hardlinks = true
;make_cache = true
;prune_downloads = true
;prune_cache = true
;login = your e621 login
;api_key = your e621 api key generated in account settings

[Defaults]
days = 365000
min_score = -2147483647
min_favs = 0
ratings = s q e
;format = 
"""

VERSION = '5.0.0'

MAX_RESULTS = 320
PARTIAL_DOWNLOAD_EXT = 'request'

DEFAULT_CONFIG_TEXT = ''';;;;;;;;;;;;;;
;; GENERAL  ;;
;;;;;;;;;;;;;;

[Defaults]
days = 1
ratings = s
min_score = 0
min_favs = 0
post_source = api

[Blacklist]
tags =

; If 'make_hardlinks' options is set,
; same files will not be copied from different folder,
; instead, hardlink will be created
;
; If 'make_cache' options is set,
; cache folder will be created,and there will be copy
; or hardlink of every downloaded files
; it maybe useful if you want do delete all your downloads
; before using new config.ini 
;
; If 'db' options is set,
; useful info of every post will be stored in a database
[Other]
include_md5 = false
make_hardlinks = true
make_cache = true
db = true

; If you uncomment this section and option 'tags',
; post list will be requested all at once using
; tags and condition, and then list will be
; additionally filtered in all search groups.
; You should prepend '\' before symbols '|&()'
; if they are part of a tag in the condition.
; Blacklist will be used from section [Blacklist]
; & is "and", | is "or", -is "not".
; E.g. "condition = traditional_media_\(artwork\) | (digital_media_\(artwork\) & -3d_\(artwork\))"
; means traditional art or digital_media that is not 3d is allowed.
; This may be useful in case of
; [cat]
; tags = cat
; [cat and dog]
; tags = cat dog
; [cat and not mouse]
; tags = cat -mouse
; or something like that.
; '*' and tag aliases are allowed.
; 
; Prefilter works the same as regular directory,
; But directory will not be created and
; only prefilter parameters will be used in
; getting posts' info from e621. 
; [Prefilter]
; tags = tag1 tag2 -tag3 *manytags*
; condition = tag | (tag_with_\&_or_\| or \(with_braces\))

;;;;;;;;;;;;;;;;;;;
;; SEARCH GROUPS ;;
;;;;;;;;;;;;;;;;;;;

; New search groups can be created by writing the following. (Do not include semicolons.):
; 'blacklisted' option is only for convenience, it's the same as '-tag' in tags
; post_source can be 'db' or 'api'. Defaults to 'api'
; if 'db' is chosen, condition will be iterated only on
; existing database, without using e621.api
; it can be useful if you need to restore folders from cache
; or if you need a subset of an existing folder, eg
;
; [cats]
; tag=cat
; [cats and dogs]
; tag=cat dog
; post_source = db
; 
; Warning, if no db = true in Other section,
; no new post info will be appended
;
; [Directory Name]
; days = 1
; ratings = s, q, e
; min_score = -100
; min_favs = 0
; tags = tag1 tag2 tag3 ...
; condition = tag | (tag_with_\&_or_\| & \(with_braces\))
; blacklisted = tag_blocked another_blocked
; ;post_source = db
; post_source = api


; Example:
; [Cute Cats]
; days = 30
; ratings = s
; min_score = 5
; min_favs = 20
; tags = cat cute

; Example:
; [Cat With Dog or Mouse]
; days = 30
; ratings = s
; min_score = 5
; min_favs = 20
; tags = cat
; condition = dog | mouse

; Example:
; if there is at least one of ~tags,
; it is allowed. It is prefferable to only
; have ~tags or not ~tags in first five tags
; [Cat Dog Mouse]
; days = 30
; ratings = s
; min_score = 5
; min_favs = 20
; tags = ~cat ~dog ~mouse

; Example:
; [Cat-something]
; days = 30
; ratings = s
; min_score = 5
; min_favs = 20
; tags = cat*

'''

#!/usr/bin/env python

import datetime
import lib.support as support

DATE_FORMAT = "%Y-%m-%d"
YESTERDAY = datetime.date.fromordinal(datetime.date.today().toordinal() - 1)
LOGGER_FORMAT = "%(name)-11s %(levelname)-8s %(message)s"
MAX_RESULTS = 100
CONFIG = support.get_config('config.ini')
VERSION = '3.0.2 -- Forked from 2.4.6'

DEFAULT_CONFIG_TEXT = ''';;;;;;;;;;;;;;;;;;;
;; MAIN SETTINGS ;;
;;;;;;;;;;;;;;;;;;;

[Settings]
last_run = ''' + YESTERDAY.strftime(DATE_FORMAT) + '''
parallel_downloads = 8

[Blacklist]
tags =

;;;;;;;;;;;;;;;;
;; TAG GROUPS ;;
;;;;;;;;;;;;;;;;

; New tag groups can be created by writing the following:
; [Directory Name]
; tags = tag1, tag2, tag3, ...
;
; Example:
; [Cute Cats]
; tags = rating:s, cat, cute'''

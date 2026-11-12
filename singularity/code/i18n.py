#file: i18n.py
# coding=utf-8
#Copyright (C) 2008 Evil Mr Henry, Phil Bordelon, and FunnyMan3595
#This file is part of Endgame: Singularity.

#Endgame: Singularity is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#Endgame: Singularity is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with Endgame: Singularity; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

#This file contains all functions to internationalize and localize the
#application.
#
#IMPORTANT: A portion of translation is still done with data files in g.

import builtins
import hashlib
import gettext
import os
import locale

import polib

from singularity.code import g, dirs

#Used to determine which data files to load.
#It is required that default language have all data files and all of them
# must have all available entries
default_language = "en_US"

gettext_language = None

# Prepare main locale dir
main_localedir = None

# We have to use lazy initialization, otherwise the tests will break
def _get_main_localedir():
    global main_localedir
    if main_localedir is None:
        main_localedir = dirs.get_writable_file_in_dirs('locale', 'i18n')
    return main_localedir

# Minimize potential name collisions with other projects
TEXTDOMAIN_PREFIX = 'singularity_'


def _detect_default_language():
    """Best-effort guess of the user's preferred language.

    Replaces locale.getdefaultlocale(), which is deprecated since Python 3.11.
    The C library is asked first -- CPython calls setlocale(LC_CTYPE, "") at
    startup, so this already reflects the user's locale on every platform --
    and if that yields nothing we fall back to parsing the same POSIX
    variables that getdefaultlocale() used to read itself.
    """
    try:
        tag = locale.getlocale(locale.LC_CTYPE)[0]
    except (ValueError, TypeError):
        tag = None

    if tag:
        return tag

    for var in ("LC_ALL", "LC_CTYPE", "LANG", "LANGUAGE"):
        value = os.environ.get(var)
        if not value:
            continue
        name = value.split(":", 1)[0]  # LANGUAGE holds a colon-separated list
        name = name.split(".", 1)[0]   # strip the codeset, e.g. .UTF-8
        name = name.split("@", 1)[0]   # strip the modifier, e.g. @euro
        if name and name not in ("C", "POSIX"):
            return name

    return None


language = _detect_default_language() or default_language

def set_language(lang=None, force=False):
    global language # required, since we're going to change it
    if lang is None: lang = language

    if lang == language and not force:
        return

    langs = available_languages()
    if lang in langs:
        language = lang
    else:
        # Let's try to be smart: if base language exists for another for another
        # country, use it. So es_MX => es_ES, pt_PT => pt_BR, etc
        code = lang.split("_")[0]
        languages = [ l for l in langs if code == l.split("_")[0] ]
        if len(languages) > 0:
            language = languages[0]
        else:
            language = default_language

    # Try a few locale settings. First the selected language, then the user's
    # default, then default language. Languages are tried with UTF-8 encoding
    # first, then the default encoding. The user's default language is not
    # paired with UTF-8.
    # If all of that fails, we hope locale magically does the right thing.
    for attempt in [ language + ".UTF-8",
                     language,
                     "",
                     default_language + ".UTF-8",
                     default_language]:
        try:
            locale.setlocale(locale.LC_ALL, attempt)
            break
        except locale.Error:
            continue

    load_data_str()
    load_story_translations()

    _load_mo_file('messages.po')

    # Switch gettext language
    gettext_language = gettext.translation(TEXTDOMAIN_PREFIX + 'messages', _get_main_localedir(), languages=[lang], fallback=True)
    gettext_language.install()

    # Update builtins with the new language
    builtins.__dict__['_'] = gettext_language.gettext
    builtins.__dict__['ngettext'] = gettext_language.ngettext

    # Define available text domains.  Data translations are looked up from the
    # parsed .po files by (context, msgid) instead, so gettext's pgettext() is
    # not involved: https://bugs.python.org/issue2504
    gettext.bindtextdomain(TEXTDOMAIN_PREFIX + 'messages', main_localedir)


def _load_mo_file(pofilename):

    files = dirs.get_readable_i18n_files(pofilename, language, default_language=False)

    for lang, pofile in files:
        try:
            po = polib.pofile(pofile)

            # Use hash to check whether the.po file has changed, then generate .mo file as needed
            sha_base_filename = os.path.basename(os.path.dirname(pofile)) + '_' + os.path.basename(pofile)
            sha_filename = dirs.get_writable_file_in_dirs(sha_base_filename + ".sha1", "i18n")

            previous_hash = ''
            new_hash = ''
            if os.path.exists(sha_filename):
                with open(sha_filename, 'r', encoding='utf-8') as sha_file:
                    previous_hash = sha_file.read()

            with open(pofile, 'rb') as currentpo:
                new_hash = hashlib.sha1(currentpo.read()).hexdigest()

            # Ensure directory exists before writing
            locale_mo_dir = os.path.join(_get_main_localedir(), lang, 'LC_MESSAGES')
            dirs.makedirs_if_not_exist(locale_mo_dir)
            mofile_path = os.path.join(locale_mo_dir, TEXTDOMAIN_PREFIX + os.path.basename(pofile).split('.')[0] + '.mo')

            # Create MO file and write new hash
            if new_hash != previous_hash or not os.path.exists(mofile_path):
                print("Installing translation file: " + mofile_path)
                po.save_as_mofile(mofile_path)
                with open(sha_filename, 'w', encoding='utf-8') as sha_file:
                    sha_file.write(new_hash)

        except IOError:
            # silently ignore non-existing files
            continue


def load_data_str():
    _load_po_file(g.data_strings, 'data_str.po', use_context=True)
    _load_po_file(g.data_strings, 'knowledge.po', use_context=True, clear_translation_table=False)


def load_story_translations():
    _load_po_file(g.story_translations, 'story.po', use_context=True)


# There's no pgettext available for Python < 3.8,
# so we use custom code for data translations
def _load_po_file(translation_table, pofilename, use_context=True, clear_translation_table=True):
    if clear_translation_table:
        translation_table.clear()

    files = dirs.get_readable_i18n_files(pofilename, language, default_language=False)

    for lang, pofile in files:
        try:
            po = polib.pofile(pofile)
        except IOError:
            # silently ignore non-existing files
            continue
        for entry in po.translated_entries():
            key = (entry.msgctxt, entry.msgid) if entry.msgctxt and use_context else entry.msgid
            translation_table[key] = entry.msgstr



def available_languages():
    return [default_language] + \
           [file_name[5:] for file_dir in dirs.get_read_dirs("i18n")
                          if os.path.isdir(file_dir)
                          for file_name in os.listdir(file_dir)
                          if os.path.isdir(os.path.join(file_dir, file_name))
                             and file_name.startswith("lang_")]

def language_searchlist(lang=None, default=True):
    if lang is None: lang = language

    # if lang is in ll_CC format (language_COUNTRY, like en_US), add both ll
    # and ll_CC, in that order, so all generic language entries are loaded first
    # and then overwritten by any country-specific ones
    lang_list = [ lang ]
    if "_" in lang: lang_list.insert(0, lang.split("_",1)[0])

    # If requested and not already in list, add default language as first,
    # so it acts as a fallback and is overwritten with any available entries
    # in the native language
    if default and default_language not in lang_list:
        lang_list.insert(0, default_language)

    return lang_list


def lex_sorting_form(name):
    """For lexicographic sorting when languages use characters not in 7-bit ASCII. e.g. é or ü.

    Use like this:

    listdata.sort(key=lambda an_object: i18n.lex_sorting_form(an_object.name))"""

    # Collator returns wrong keys for DE locale
    if language == 'de' or language.startswith('de_'):
        name = name.replace('Ä', 'Ae').replace('ä', 'ae').replace('Ö', 'Oe').replace('ö', 'oe').replace('Ü', 'Ue').replace('ü', 'ue')

    return locale.strxfrm(name)


# Cyrillic letters in a language's own name, folded to Latin so the menu
# does not list Русский and Српски after every Latin row. Serbian digraphs
# follow recode-sr-latin (Љ→Lj, Њ→Nj, Џ→Dž, Ђ→Đ, Ћ→Ć), which is why Српски
# lands on the same key as Srpski. Tech, knowledge and save lists do not
# use this table.
_CYRILLIC_TO_LATIN = str.maketrans({
    "А": "A", "а": "a", "Б": "B", "б": "b", "В": "V", "в": "v",
    "Г": "G", "г": "g", "Д": "D", "д": "d", "Ђ": "Đ", "ђ": "đ",
    "Е": "E", "е": "e", "Ё": "E", "ё": "e", "Ж": "Ž", "ж": "ž",
    "З": "Z", "з": "z", "И": "I", "и": "i", "Й": "J", "й": "j",
    "Ј": "J", "ј": "j", "К": "K", "к": "k", "Л": "L", "л": "l",
    "Љ": "Lj", "љ": "lj", "М": "M", "м": "m", "Н": "N", "н": "n",
    "Њ": "Nj", "њ": "nj", "О": "O", "о": "o", "П": "P", "п": "p",
    "Р": "R", "р": "r", "С": "S", "с": "s", "Т": "T", "т": "t",
    "Ћ": "Ć", "ћ": "ć", "У": "U", "у": "u", "Ф": "F", "ф": "f",
    "Х": "H", "х": "h", "Ц": "C", "ц": "c", "Ч": "Č", "ч": "č",
    "Џ": "Dž", "џ": "dž", "Ш": "Š", "ш": "š", "Щ": "Š", "щ": "š",
    "Ъ": None, "ъ": None, "Ы": "Y", "ы": "y", "Ь": None, "ь": None,
    "Э": "E", "э": "e", "Ю": "Ju", "ю": "ju", "Я": "Ja", "я": "ja",
})


def language_menu_sort_key(name):
    """Latin sort key for one language-menu row.

    The row shows the native name with the English one in brackets, and this
    key is taken from the native part alone, so the bracketed name cannot move
    a row. Cyrillic is folded first, then the usual locale key is applied, so
    Russian sits with R and the two Serbian rows share a key. Gameplay lists
    keep lex_sorting_form on the text itself.
    """
    return lex_sorting_form(name.translate(_CYRILLIC_TO_LATIN))


# Initialization code
builtins.__dict__['_'] = gettext.gettext
builtins.__dict__['ngettext'] = gettext.ngettext
# Mark string as translatable but defer translation until later.
builtins.__dict__['N_'] = lambda x: x

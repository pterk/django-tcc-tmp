import string
from urlparse import urlparse

from django.contrib.auth.models import User
from django.core.urlresolvers import resolve, reverse
from django.http import Http404
from django.template.defaultfilters import linebreaks
from django.utils.safestring import SafeData, mark_safe
from django.utils.encoding import force_unicode
from django.utils.functional import allow_lazy
from django.utils.html import word_split_re, punctuation_re
from django.utils.http import urlquote

import bleach


def is_acceptable(url, acceptable_urls, force_prepend=True):
    """ checks if the url starts with any """
    for acceptable in acceptable_urls:
        # url is always prepended with http(s)://
        if force_prepend and not (acceptable.startswith('http://') 
                                  or acceptable.startswith('https://')):
            acceptable = "http://" + acceptable
        if url.startswith(acceptable):
            return True
    return False


def urlize(text, trim_url_limit=None, nofollow=False, autoescape=False,
           acceptable_urls=[], callback=None):
    """
    Converts any URLs in text into clickable links.

    Works on http://, https://, www. links and links ending in .org, .net or
    .com. Links can have trailing punctuation (periods, commas, close-parens)
    and leading punctuation (opening parens) and it'll still do the right
    thing.

    If trim_url_limit is not None, the URLs in link text longer than this limit
    will truncated to trim_url_limit-3 characters and appended with an elipsis.

    If nofollow is True, the URLs in link text will get a rel="nofollow"
    attribute.

    If autoescape is True, the link text and URLs will get autoescaped.
    """
    trim_url = lambda x, limit=trim_url_limit: limit is not None and (len(x) > limit and ('%s...' % x[:max(0, limit - 3)])) or x
    safe_input = isinstance(text, SafeData)
    words = word_split_re.split(force_unicode(text))
    nofollow_attr = nofollow and ' rel="nofollow"' or ''
    for i, word in enumerate(words):
        match = None
        if '.' in word or '@' in word or ':' in word:
            match = punctuation_re.match(word)
        if match:
            lead, middle, trail = match.groups()
            # check if url is acceptable without protocol prefix
            if is_acceptable(middle, acceptable_urls, False):
                # then prefix it so it can be processed with the tried
                # and tested code below
                middle = 'http://' + middle
            # Make URL we want to point to.
            url = None
            if middle.startswith('http://') or middle.startswith('https://'):
                url = urlquote(middle, safe='/&=:;#?+*')
            elif middle.startswith('www.') or ('@' not in middle and \
                    middle and middle[0] in string.ascii_letters + string.digits and \
                    (middle.endswith('.org') or middle.endswith('.net') or middle.endswith('.com'))):
                url = urlquote('http://%s' % middle, safe='/&=:;#?+*')
            elif '@' in middle and not ':' in middle and simple_email_re.match(middle):
                url = 'mailto:%s' % middle
                nofollow_attr = ''
            # Make link.
            if url and is_acceptable(url, acceptable_urls):
                cbburl = None
                if callback:
                    cburl = callback(url)
                if cburl:
                    if autoescape and not safe_input:
                        lead, trail = escape(lead), escape(trail)
                    words[i] = mark_safe('%s%s%s' % (lead, cburl, trail))
                else:
                    trimmed = trim_url(middle)
                    if autoescape and not safe_input:
                        lead, trail = escape(lead), escape(trail)
                        url, trimmed = escape(url), escape(trimmed)
                    middle = '<a href="%s"%s>%s</a>' % (url, nofollow_attr, trimmed)
                    words[i] = mark_safe('%s%s%s' % (lead, middle, trail))
            else:
                if safe_input:
                    words[i] = mark_safe(word)
                elif autoescape:
                    words[i] = escape(word)
        elif safe_input:
            words[i] = mark_safe(word)
        elif autoescape:
            words[i] = escape(word)
    return u''.join(words)
urlize = allow_lazy(urlize, unicode)


def iconify(url, url_names=['fashiolista_item']):
    parts = urlparse(url)
    urlpath = parts.path
    try:
        match = resolve(urlpath)
    except Http404:
        return None
    if match.url_name in url_names:
        return '<a href="%s?match=%s" title="%s">%s</a>' % (
            reverse(match.url_name, args=match.args, kwargs=match.kwargs),
            match.url_name, match.url_name, match.url_name)


def process_comment(comment):
    comment = bleach.clean(
        comment, tags=[], attributes=[], styles=[], strip=True)
    return linebreaks(
        urlize(comment, 
               acceptable_urls=['fashiolista.com', 'www.fashiolista.com'],
               callback=iconify))


def admin_callback(comment, action):
    """ Callback to list users that have permissions for <action> on <comment>

    The comment object is passed and the 'action' to be taken which is one of:
    
    open
    close
    approve
    disapprove
    remove
    restore

    The callback should return a list of users (or an empty list) that
    can perform the action on the comment
    """
    if action == 'remove' and isinstance(comment.content_object, User):
        # users can remove comments on their own page
        return [comment.content_object]
    return []

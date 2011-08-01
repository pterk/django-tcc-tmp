from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import connection

# Tree related
MAX_DEPTH = getattr(settings, 'TCC_MAX_DEPTH', 2)
REPLY_LIMIT = getattr(settings, 'TCC_REPLY_LIMIT', 3)
MAX_REPLIES = getattr(settings, 'TCC_MAX_REPLIES', 50)
STEPLEN = getattr(settings, 'TCC_STEPLEN', 6)
# paginator stuff
PER_PAGE = getattr(settings, 'PER_PAGE', 25)
PAGE_WINDOW = getattr(settings, 'PAGE_WINDOW', 3)
PAGE_ORPHANS = getattr(settings, 'PAGE_ORPHANS', REPLY_LIMIT+1)
# special perms
ADMIN_CALLBACK = getattr(settings, 'TCC_ADMIN_CALLBACK', None)
# comment related
COMMENT_MAX_LENGTH = getattr(settings,'COMMENT_MAX_LENGTH',3000)
MODERATED = getattr(settings, 'TCC_MODERATE', False)
TCC_CONTENT_TYPES = getattr(settings, 'TCC_CONTENT_TYPES', [])
CONTENT_TYPES = []
if connection.introspection.table_names() != []:
    # syncdb has run -- can now assume django_content_type table exists
    for label in TCC_CONTENT_TYPES:
        ct = ContentType.objects.get_by_natural_key(*label.split("."))
        CONTENT_TYPES.append(ct.id)


# Wow ... weirdness occurs without the following monkeypatch for python2.6
#
# See http://stackoverflow.com/questions/5614741/cant-use-a-list-of-methods-in
# (actually  http://bugs.python.org/issue1515 -- but that's down a.t.m. )
import sys
if sys.version_info[:2] == (2, 6):
    import copy
    import types

    def _deepcopy_method(x, memo):
        return type(x)(x.im_func, copy.deepcopy(x.im_self, memo), x.im_class)
    copy._deepcopy_dispatch[types.MethodType] = _deepcopy_method


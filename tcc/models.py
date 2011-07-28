from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.db import models
from django.utils.http import base36_to_int, int_to_base36
from django.utils.translation import ugettext_lazy as _

from tcc import tasks
from tcc.settings import (STEPLEN, COMMENT_MAX_LENGTH, MODERATED,
                          REPLY_LIMIT, CONTENT_TYPES, MAX_DEPTH,
                          PRE_SAVE_CALLBACK, ADMIN_CALLBACK)
from tcc.managers import (
    CurrentCommentManager, LimitedCurrentCommentManager,
    RemovedCommentManager, DisapprovedCommentManager,
    )

SITE_ID = getattr(settings, 'SITE_ID', 1)


class Thread(models.Model):
    content_type = models.ForeignKey(
        ContentType, verbose_name=_('content type'),
        related_name="content_type_set_for_tcc_thread")
    object_pk = models.TextField(_('object id'))
    content_object = generic.GenericForeignKey(
        ct_field="content_type", fk_field="object_pk")
    site = models.ForeignKey(Site, default=SITE_ID,
                             related_name='tccthreads')
    is_open = models.BooleanField(_('Open'), default=True)
    is_moderated = models.BooleanField(_('Moderated'), default=MODERATED)


class Comment(models.Model):
    """ A comment table, aimed to be compatible with django.contrib.comments

    """
    # From comments BaseCommentAbstractModel
    content_type = models.ForeignKey(
        ContentType, verbose_name=_('content type'),
        related_name="content_type_set_for_tcc_comment")
    object_pk = models.TextField(_('object id'))
    content_object = generic.GenericForeignKey(
        ct_field="content_type", fk_field="object_pk")
    site = models.ForeignKey(Site, default=SITE_ID,
                             related_name='tcccomments')
    # The actual comment fields
    parent = models.ForeignKey('self', verbose_name= _('Reply to'),
                               null=True, blank=True, related_name='parents')
    user = models.ForeignKey(User, verbose_name='Commenter')
    # These are here mainly for backwards compatibility
    user_name   = models.CharField(_("user's name"), max_length=50, blank=True)
    user_email  = models.EmailField(_("user's email address"), blank=True)
    user_url    = models.URLField(_("user's URL"), blank=True)
    submit_date = models.DateTimeField(_('Date'), default=datetime.now)
    # Protip: Use postgres...
    comment = models.TextField(_('Comment'), max_length=COMMENT_MAX_LENGTH)
    comment_raw = models.TextField(_('Raw Comment'), max_length=COMMENT_MAX_LENGTH)
    # still accepting replies?
    is_open = models.BooleanField(_('Open'), default=True)
    is_removed = models.BooleanField(_('Removed'), default=False)
    is_approved = models.BooleanField(_('Approved'), default=not MODERATED)
    # is_public is rather pointless icw is_removed?
    # Keeping it for compatibility w/ contrib.comments
    is_public = models.BooleanField(_('Public'), default=True)
    path = models.CharField(_('Path'), max_length=MAX_DEPTH*STEPLEN)
    limit = models.DateTimeField(
        _('Show replies from'), null=True, blank=True)
    # denormalized cache
    childcount = models.IntegerField(_('Reply count'), default=0)
    depth = models.IntegerField(_('Depth'), default=0)

    unfiltered = models.Manager()
    objects = CurrentCommentManager()
    limited = LimitedCurrentCommentManager()
    removed = RemovedCommentManager()
    disapproved = DisapprovedCommentManager()

    class Meta:
        ordering = ['path', 'submit_date']

    def __unicode__(self):
        return u"%05d %s % 8s: %s" % (
            self.id, self.submit_date.isoformat(), self.user.username, self.comment[:20])

    def get_absolute_url(self):
        link = reverse('tcc_index',
                       args=(self.content_type.id, self.object_pk))
        return "%s#%s" % (link, self.get_base36())

    def get_root_path(self):
        return self.path[0:STEPLEN]

    def get_thread(self):
        """ returns the entire 'thread' (a 'root' comment and all replies)

        a root comment is a comment without a parent
        """
        return Comment.objects.filter(path__startswith=self.get_root_path())

    def get_replies(self, levels=None, include_self=False):
        if self.parent and self.parent.depth == MAX_DEPTH - 1:
            return Comment.objects.none()
        else:
            replies = Comment.objects.filter(path__startswith=self.path)
            if levels:
                # 'z' is the highest value in base36 (as implemented in django)
                replies.filter(path__lte="%s%s" % (self.path, (levels * STEPLEN * 'z')))
            if not include_self:
                replies = replies.exclude(id=self.id)
            return replies

    def get_root(self):
        if self.parent:
            return Comment.objects.get(path=self.get_root_path())
        return None

    def get_parents(self):
        if self.parent:
            parentpaths = []
            l = len(self.path)
            for i in range(0, l, STEPLEN):
                parentpaths.append(self.path[i:i+STEPLEN])
            return Comment.objects.filter(path__in=parentpaths)
        else:
            return Comment.objects.none()

    def has_changed(self, field):
        """ Checks if a field has changed since the last save

        http://zmsmith.com/2010/05/django-check-if-a-field-has-changed/
        """
        if not self.pk:
            return False
        old_value = self.__class__._default_manager.\
            filter(pk=self.pk).values(field).get()[field]
        return not getattr(self, field) == old_value

    def save(self, *args, **kwargs):
        if self.id:
            must_send_notifications = False
            must_set_path = False

            if self.has_changed('is_removed'):
                self.get_replies().update(is_removed=False)

        else:
            must_set_path = True
            must_send_notifications = True
            
            self.comment_raw = self.comment
            self.comment = PRE_SAVE_CALLBACK(self.comment)

        super(Comment, self).save(*args, **kwargs)

        if REPLY_LIMIT and self.parent:
            self.parent.set_limit()

        if must_set_path:
            self._set_path()

        if must_send_notifications:
            tasks.send_notifications.delay(self.id)

        tasks.spam_check.delay(self.id)
        tasks.prime_cache.delay(self.id)

    def delete(self, *args, **kwargs):
        self.get_replies(include_self=True).delete()
        super(Comment, self).delete(*args, **kwargs)
        if self.parent:
            self.parent.set_limit()

    def set_limit(self):
        replies = self.get_replies(levels=1).order_by('-submit_date')
        n = replies.count()
        self.childcount = n
        if n == 0:
            return
        if n < REPLY_LIMIT:
            self.limit = replies[0].submit_date
        else:
            self.limit = replies[REPLY_LIMIT-1].submit_date
        self.save()

    def get_depth(self):
        return ( len(self.path) / STEPLEN ) - 1

    def reply_allowed(self):
        return self.is_open and ( self.depth < MAX_DEPTH - 1 )

    def can_open(self, user):
        return self.user == user

    def can_close(self, user):
        return self.user == user

    def can_approve(self, user):
        return self.user == user

    def can_disapprove(self, user):
        return self.user == user

    def can_remove(self, user):
        return self.user == user or user in self.get_enabled_users('remove')

    def can_restore(self, user):
        return self.user == user

    def get_base36(self):
        return int_to_base36(self.id)

    def _set_path(self):
        """ This will set the path to a base36 encoding of the comment-id

        Since the depth is limited (to 2  by default) padding to 13 will allow for
        plenty of space (36**13) (sufficient to base36-encode any
        64-bit integer)

        >>> 36**12 > 2**64
        False
        >>> 36**13 > 2**64
        True
        """
        if self.parent:
            self.path = "%s%s" % (self.parent.path, self.get_base36().zfill(STEPLEN))
        else:
            self.path = "%s" % (self.get_base36().zfill(STEPLEN))
        self.depth = self.get_depth()
        self.save()
    
    def get_enabled_users(self, action):
        assert action in ['open', 'close', 'remove', 'restore',
                          'approve', 'disapprove']
        return ADMIN_CALLBACK(self, action)


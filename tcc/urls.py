from django.conf.urls.defaults import *

# URL patterns for tcc

urlpatterns = patterns(
    'tcc.views',
    url(r'^(?P<content_type_id>\d+)/(?P<object_pk>\d+)/$', 'index', name='tcc_index'),
    url(r'^thread/(?P<parent_id>\d+)/$', 'thread', name='tcc_thread'),
    url(r'^post/$', 'post', name='tcc_post'),
    url(r'^remove/(?P<comment_id>\d+)/$', 'remove', name='tcc_remove'),
    url(r'^restore/(?P<comment_id>\d+)/$', 'restore', name='tcc_restore'),
    url(r'^approve/(?P<comment_id>\d+)/$', 'approve', name='tcc_approve'),
    url(r'^disapprove/(?P<comment_id>\d+)/$', 'disapprove', name='tcc_disapprove'),
    url(r'^flag/(?P<comment_id>\d+)/$', 'flag', name='tcc_flag'),
    url(r'^flag/(?P<comment_id>\d+)/$', 'unflag', name='tcc_unflag'),
)

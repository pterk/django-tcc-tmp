from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.conf import settings
from django.http import (HttpResponseBadRequest, HttpResponseRedirect,
                         HttpResponse, Http404)
from django.shortcuts import render, get_object_or_404
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_POST

from tcc import api
from tcc.settings import CONTENT_TYPES
from tcc.forms import CommentForm


def _get_tcc_index(comment):
    return reverse('tcc_index', 
                   args=[comment.content_type_id, comment.object_pk])


def index(request, content_type_id, object_pk):
    if int(content_type_id) not in CONTENT_TYPES:
        raise Http404()
    # extra checks... comment next 5 lines out to save 2 queries
    ct = get_object_or_404(ContentType, id=content_type_id)
    try:
        target = ct.get_object_for_this_type(pk=object_pk)
    except ObjectDoesNotExist:
        raise Http404()
    comments = api.get_comments_limited(content_type_id, object_pk)
    initial = {'content_type': content_type_id,
               'object_pk': object_pk}
    form = CommentForm(target, initial=initial)
    context = {'comments': comments,
            'form': form}
    return render(request, 'tcc/index.html', context)


def thread(request, parent_id):
    comments = api.get_comment_replies(parent_id)
    context = RequestContext(request, {'comments': comments})
    return render_to_response('tcc/thread.html', context)


@login_required
@require_POST
def post(request):
    data = request.POST.copy()
    content_type = data.get('content_type', None)
    if int(content_type) not in CONTENT_TYPES:
        raise Http404()
    ct = get_object_or_404(ContentType, pk=content_type)
    object_pk = data.get('object_pk', None)
    try:
        target = ct.get_object_for_this_type(pk=object_pk)
    except ObjectDoesNotExist:
        raise Http404()
    # inject the user
    data['user'] = request.user.id
    form = CommentForm(target, data)
    if form.is_valid():
        parent = form.cleaned_data.get('parent', None)
        if parent:
            parent_id = parent.id
        else:
            parent_id = None
        message = form.cleaned_data.get('comment', '')
        comment = api.post_comment(content_type_id=content_type,
                                   object_pk=object_pk,
                                   user_id=request.user.id,
                                   comment=message,
                                   parent_id=parent_id)
        if comment:
            if request.is_ajax():
                return render(request, 'tcc/comment.html', {'c': comment})
            next = form.cleaned_data.get('next', comment.get_absolute_url())
            return HttpResponseRedirect(next)
    return HttpResponseRedirect(
        reverse('tcc_index', args=[content_type_id, object_pk]))


@login_required
@require_POST
def flag(request):
    return HttpResponse('TODO')


@login_required
@require_POST
def unflag(request):
    return HttpResponse('TODO')


@login_required
@require_POST
def approve(request, comment_id):
    comment = api.approve_comment(comment_id, request.user)
    if comment:
        return HttpResponseRedirect(comment.get_absolute_url())
    raise Http404()


@login_required
@require_POST
def disapprove(request, comment_id):
    comment = api.disapprove_comment(comment_id, request.user)
    if comment:
        tcc_index = _get_tcc_index(comment)
        return HttpResponseRedirect(tcc_index)
    raise Http404()


@login_required
@require_POST
def remove(request, comment_id):
    comment = api.remove_comment(comment_id, request.user)
    if comment:
        if request.is_ajax():
            return HttpResponse() # 200 OK
        tcc_index = _get_tcc_index(comment)
        return HttpResponseRedirect(tcc_index)
    raise Http404()


@login_required
@require_POST
def restore(request, comment_id):
    comment = api.restore_comment(comment_id, request.user)
    if comment:
        return HttpResponseRedirect(comment.get_absolute_url())
    raise Http404()

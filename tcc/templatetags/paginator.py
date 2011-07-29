from coffin.template import Library
#from framework.utils import to_int
from django.http import Http404
import re
import math
import logging

register = Library()

LEADING_PAGE_RANGE_DISPLAYED = 8
TRAILING_PAGE_RANGE_DISPLAYED = 8
ADJACENT_PAGES = 2
LEADING_PAGE_RANGE = LEADING_PAGE_RANGE_DISPLAYED - ADJACENT_PAGES
TRAILING_PAGE_RANGE = TRAILING_PAGE_RANGE_DISPLAYED - ADJACENT_PAGES
MAX_OBJECTS = 1000

MAX_QUERYSET_RECURSION = 10

def to_int(input, default=0, exception=(ValueError, TypeError), regexp=None):
    '''Convert the given input to an integer or return default

    When trying to convert the exceptions given in the exception parameter
    are automatically catched and the default will be returned.

    The regexp parameter allows for a regular expression to find the digits
    in a string.
    When True it will automatically match any digit in the string.
    When a (regexp) object (has a search method) is given, that will be used.
    WHen a string is given, re.compile will be run over it first

    The last group of the regexp will be used as value
    '''

    if regexp is True:
        regexp = re.compile('(\d+)')
    elif isinstance(regexp, basestring):
        regexp = re.compile(regexp)
    elif hasattr(regexp, 'search'):
        pass
    elif regexp is not None:
        raise TypeError, 'unknown argument for regexp parameter'

    try:
        if regexp:
            match = regexp.search(input)
            if match:
                input = match.groups()[-1]
        return int(input)
    except exception:
        return default


class settings:
    PER_PAGE = 10

class Paginator(object):
    '''Paginator tag to paginate any object with either a count method or a
    __len__ method
    
    >>> objects = range(50)
    >>> paginator = Paginator(objects, {}, per_page=10)
    >>> paginator.first
    0
    >>> paginator.last
    10
    >>> paginator.previous
    >>> paginator.next
    2
    >>> paginator.count
    50
    >>> paginator.left
    []
    >>> paginator.middle
    [1, 2, 3, 4, 5]
    >>> paginator.right
    []
    >>> paginator.pages
    5
    
    >>> paginator = Paginator(objects, {}, per_page=2)
    >>> paginator.pages
    25
    >>> paginator.left
    []
    >>> paginator.middle
    [1, 2, 3, 4, 5, 6, 7, 8]
    >>> paginator.right
    [25]
    >>> paginator.get_objects()
    [0, 1]
    
    >>> paginator = Paginator(objects, {'page': 10}, per_page=2)
    >>> paginator.left
    [1]
    >>> paginator.middle
    [8, 9, 10, 11, 12]
    >>> paginator.right
    [25]
    >>> paginator.page
    10
    >>> paginator.get_objects()
    [18, 19]
    >>> paginator.previous
    9
    >>> paginator.page
    10
    >>> paginator.next
    11

    >>> paginator = Paginator(objects, {'page': 25}, per_page=2)
    >>> paginator.left
    [1]
    >>> paginator.middle
    [18, 19, 20, 21, 22, 23, 24, 25]
    >>> paginator.right
    []
    >>> paginator.get_objects()
    [48, 49]
    
    >>> paginator = Paginator(objects, {'page': 50}, per_page=2)
    >>> paginator.next
    >>> paginator.previous
    49
    >>> paginator.left
    []
    >>> paginator.middle
    []
    >>> paginator.right
    []
    >>> paginator.get_objects()
    []
    
    >>> paginator = Paginator([], {'page': 50}, per_page=2)
    >>> paginator.pages
    0
    >>> paginator.page
    50
    >>> paginator.next
    >>> paginator.previous
    49
    >>> paginator.left
    []
    >>> paginator.middle
    []
    >>> paginator.right
    []
    '''
    def __init__(self, objects, get, per_page=settings.PER_PAGE,
            var_prefix='', count=None, logger=None):
        self.init_logger(logger)
        self.init_get(get, var_prefix)
        self.init_per_page(per_page)
        self.init_objects(objects)
        self.init_count(count)
        self.init_pages()
        self.init_links()

    def init_logger(self, logger):
        if not logger:
            logger = logging.getLogger(self.__class__.__name__)
        self.debug = logger.debug
        self.info = logger.info
        self.warn = logger.warn

    def init_get(self, get, var_prefix):
        self.get = get
        self.var_prefix = var_prefix
        self.page_var = var_prefix + 'page'
        self.page = to_int(self.get.get(self.page_var), 1)
        self.pk_var = var_prefix + 'pk'
        self.pk = to_int(self.get.get(self.pk_var))

    def init_per_page(self, per_page):
        self.per_page = per_page

    def init_objects(self, objects):
        self.objects = objects

    @classmethod
    def _get_sliced_objects(cls, objects, first, last, count):
        # If we've got no count or non-zero count, prefetch queryset
        
        if count is None or count:
            sliced_objects = list(objects[first:last])
        else:
            sliced_objects = []

        return sliced_objects

    def init_count(self, count):
        self.first = (self.page - 1) * self.per_page
        self.last = self.page * self.per_page
        
        self.sliced_objects = self._get_sliced_objects(
            self.objects,
            self.first,
            self.last,
            count,
        )

        if not self.sliced_objects and self.page > 1:
            raise Http404('Page %d has no results' % self.page)

        if len(self.sliced_objects) < self.per_page:
            count = len(self.sliced_objects) + self.first

        elif count is None:
            count = len(self.objects)

        else:
            self.debug('Using preinitialized count: %d', count)

        self.first = min(self.first, count)
        self.last = min(self.last, count)
        self.count = count

    def init_pages(self):
        self.pages = int(math.ceil(float(self.count) / self.per_page))

    def init_links(self):
        '''Init the pagination links based on the available items'''

        # Some defaults if there are no items
        self.left = []
        self.middle = []
        self.right = []
        self.next = None
        self.previous = None
        in_leading_range = in_trailing_range = False

        # Pages outside of the trailing range
        #
        # e.g. if we are on page 20 this will represent the 1 of:
        # 1 .. 19 20 21
        pages_outside_trailing_range = []

        if (self.pages <= LEADING_PAGE_RANGE_DISPLAYED):
            # Still in the leading range
            # e.g. 5 pages with leading range 6: total; 1 2 3 4 5
            self.debug('pages (%d) in leading page range displayed (%d)',
                self.pages, LEADING_PAGE_RANGE_DISPLAYED)

            in_leading_range = in_trailing_range = True
            page_numbers = range(1, self.pages + 1)
        
        elif (self.page <= LEADING_PAGE_RANGE):
            # More pages total than in the leading range but the page is in
            # the leading range
            # (e.g. 10 pages with leading range 6: total; 1 2 3 *4* 5 6
            self.debug('page (%d) in leading page range (%d)',
                self.page, LEADING_PAGE_RANGE)

            in_leading_range = True
            page_numbers = range(
                1,
                min(
                    max(
                        LEADING_PAGE_RANGE_DISPLAYED + 1,
                        self.page + ADJACENT_PAGES + 1,
                    ),
                    self.pages + 1,
                ),
            )
            pages_outside_trailing_range = range(
                self.pages,
                self.pages - 1,
                -1,
            )
        
        #elif (self.page > self.pages - TRAILING_PAGE_RANGE):
        #    # Page in the trailing pages
        #    # (e.g. 20 pages with trailing range 3: total; ... 18 *19* 20
        #    in_trailing_range = True
        #    page_numbers = range(
        #        self.pages - TRAILING_PAGE_RANGE_DISPLAYED + 1,
        #        self.pages + 1,
        #    )
            
        else:
            # not leading, not trailing, only the surrounding for our current
            # page
            self.debug('not leading, not trailing, get the surrounding '
                '(page: %d, pages: %d)', self.page, self.pages)

            page_numbers = range(
                max(1, self.page - ADJACENT_PAGES),
                min(self.pages + 1, self.page + ADJACENT_PAGES + 1),
            )
            pages_outside_trailing_range = [1]
        
        
        if not in_leading_range:
            self.left = pages_outside_trailing_range
            
        self.middle = page_numbers

        if self.page > 1:
            self.previous = self.page - 1

        if self.page < self.pages:
            self.next = self.page + 1

        add_fake_pk = lambda x: [(y, None) for y in x]
        self.left = add_fake_pk(self.left)
        self.middle = add_fake_pk(self.middle)

        if self.next:
            self.next = self.next, None

        if self.previous:
            self.previous = self.previous, None

    def get_objects(self):
        return self.sliced_objects

    def __nonzero__(self):
        return bool(self.count)

    def get_count(self):
        return self.count

    def get_link(self, page, pk=None):
        query = self.get.copy()

        if pk and page != 1:
            query[self.pk_var] = pk
        else:
            query.pop(self.pk_var, None)

        query[self.page_var] = page

        return '?' + query.urlencode()

if __name__ == '__main__':
    import doctest
    doctest.testmod()
    #doctest.testmod(verbose=True)
    
class SolrPaginator(Paginator):
    def __init__(self, objects, get, per_page=settings.PER_PAGE,
            var_prefix='', count=None, max_count=False, logger=None):

        self.init_logger(logger)
        self.init_get(get, var_prefix)
        self.init_per_page(per_page)
        self.init_objects(objects)
        self.init_count(count, max_count)
        self.init_pages()
        self.init_links()
    
    def init_count(self, count, max_count=None):
        self.first = (self.page - 1) * self.per_page
        self.last = self.page * self.per_page
        self.sliced_objects = self._get_sliced_objects(
            self.objects,
            self.first,
            self.last,
            count,
        )

        if not self.sliced_objects and self.page > 1:
            raise Http404('Page %d has no results' % self.page)

        if max_count and self.first > max_count:
            raise Http404('Page %d has no results' % self.page)

        count = len(self.objects)
        
        if max_count:
            count = min(max_count, count)

        self.first = min(self.first, count)
        self.last = min(self.last, count)
        self.count = count

class QuerySetPaginator(Paginator):
    def init_objects(self, objects):
        self.objects = None
        queryset = raw_qs = objects

        # In case of wrapped querysets, try and get the original one
        # the wrapped querysets have a `queryset` attribute that's always
        # set but will be identical to the current queryset if we've reached
        # the end.
        i = 0
        while getattr(raw_qs, 'queryset', raw_qs) is not raw_qs:
            raw_qs = raw_qs.queryset
            
            i += 1
            if i == MAX_QUERYSET_RECURSION:
                raise RuntimeError('Unable to get the raw queryset within %d '
                    'steps. queryset.raw_queryset.raw_queryset seems to loop '
                    'infinitely', MAX_QUERYSET_RECURSION)

        self.queryset = queryset
        self.raw_queryset = raw_qs

    def init_count(self, count, max_count):
        self.first = (self.page - 1) * self.per_page
        self.last = self.page * self.per_page

        if not self.sliced_objects and self.page > 1:
            raise Http404('Page %d has no results' % self.page)

        self.sliced_objects = self._get_sliced_objects(
            self.raw_queryset,
            self.first,
            self.last,
            count,
        )

        if len(self.sliced_objects) < self.per_page:
            # We don't have a full page of objects anymore so we already know
            # the total count now
            count = len(self.sliced_objects) + self.first

        elif count is not None:
            # count is given, no need to do more work
            self.debug('Using preinitialized count: %d', count)

        elif max_count:
            # a max count is given, use a count with a max
            # i.e. SELECT COUNT(*) FROM (SELECT id FROM table LIMIT max_count)
            # requires Django/QuerySet patch to work
            qs = self.raw_queryset[:max_count]
            count = qs.count()
            self.debug('Counting up to %d. Result: %d', max_count, count)

        else:
            count = self.raw_queryset.count()

        self.count = count

    def get_objects(self):
        return self.sliced_objects

class SmartQuerySetPaginator(QuerySetPaginator):
    def __init__(self, objects, get, per_page=settings.PER_PAGE,
            var_prefix='', count=None, max_count=False,
            optional_max_count=None, logger=None):

        self.init_logger(logger)
        self.init_get(get, var_prefix)
        self.init_per_page(per_page)
        self.init_objects(objects)
        self.init_count(count, max_count, optional_max_count)
        self.init_pages()
        self.init_links()

    def init_count(self, count, max_count, optional_max_count):
        if self.pk:
            self.first = 0
            self.last = self.per_page
        else:
            self.first = (self.page - 1) * self.per_page
            self.last = self.page * self.per_page
            
        # Get all the PK's needed for pagination and use that as internal
        # count
        qs = self.raw_queryset

        order_by = (
            qs.query.order_by
            or qs.model._meta.ordering
            or ['id']
        )[0]

        filtered_qs = qs

        field = qs.model._meta.get_field(order_by.lstrip('-'))
        if not field.unique and optional_max_count:
            max_count = optional_max_count

        if field.unique or (count is None and not max_count):
            assert field.unique, ('the paginator requires a queryset thats '
                'ordered by a unique field or a (max_)count parameter')

            filters = []
            if self.pk:
                filters = [
                    {'%s__lte' % field.name: self.pk},
                    {'%s__gte' % field.name: self.pk},
                ]

            if order_by.startswith('-'):
                reverse_order_by = order_by[1:]
            else:
                reverse_order_by = '-' + order_by
                filters = filters[::-1]

            if self.pk:
                filtered_qs = qs.filter(**filters[0])

        self.sliced_objects = self._get_sliced_objects(
            filtered_qs,
            self.first,
            self.last,
            count,
        )

        if not self.sliced_objects and self.page > 1:
            raise Http404('Page %d has no results' % self.page)

        self.pre_pks = []
        self.post_pks = []

        if count is not None and not field.unique:
            # count is given, no need to do more work
            self.debug('Using preinitialized count: %d', count)

        elif max_count:
            # a max count is given, use a count with a max
            # i.e. SELECT COUNT(*) FROM (SELECT id FROM table LIMIT max_count)
            # requires Django/QuerySet patch to work
            qs = self.raw_queryset[:max_count]
            count = qs.count()
            self.debug('Counting up to %d: %d', max_count, count)

        else:
            leading_limit = ADJACENT_PAGES
            trailing_limit = ADJACENT_PAGES
            if self.page <= LEADING_PAGE_RANGE_DISPLAYED:
                leading_limit = self.page - 2
                trailing_limit = max(
                    trailing_limit,
                    TRAILING_PAGE_RANGE_DISPLAYED - self.page,
                )

            leading_limit = leading_limit * self.per_page + 1
            trailing_limit = trailing_limit * self.per_page + 1

            if len(self.sliced_objects) < self.per_page:
                # We don't have a full page of objects anymore so we already
                # know the total count now
                count = len(self.sliced_objects) + (self.page - 1) * self.per_page
                self.post_pks = [self.pk]

            else:
                # Not yet at the end, get the pk's
                self.post_pks = list(
                    filtered_qs
                    .order_by(order_by)
                    .values_list('pk', flat=True)
                    [:trailing_limit:self.per_page])

            if self.pk:
                # only fetching pre-pks if there is something to fetch
                if leading_limit > 1:
                    self.pre_pks = list(
                        qs
                        .filter(**filters[1])
                        .values_list('pk', flat=True)
                        .order_by(reverse_order_by)
                        [self.per_page:leading_limit:self.per_page])
                else:
                    self.pre_pks = []
            else:
                # Without primary key everything should be in post_pks
                self.pre_pks = self.post_pks[:self.page - 1]
                self.post_pks = self.post_pks[self.page - 1:]

            # if there are post pks, strip the current one
            if self.post_pks:
                self.pk = self.post_pks[0]
                self.post_pks = self.post_pks[1:]
            else:
                self.pk = None

            if len(self.sliced_objects):
                count = (len(self.post_pks) + self.page) * self.per_page
            else:
                count = 0

            self.debug('No max count given, counting for %d pages with %d '
                'items per page: %d', TRAILING_PAGE_RANGE_DISPLAYED,
                self.per_page, count)

        self.count = count
        self.max_count = max_count

    def init_links(self):
        QuerySetPaginator.init_links(self)

        def _add_pks(*pages):
            '''Enable PK based navigation, if the PK is available'''
            if self.pk:
                pages = list(pages)
                for i, (page, _) in enumerate(pages):
                    pk = None
                    try:
                        page_delta = page - self.page

                        if page_delta > 0:
                            pk = self.post_pks[page_delta - 1]
                        elif page_delta < 0:
                            pk = self.pre_pks[abs(page_delta) - 1]
                        else:
                            pk = self.pk

                    except IndexError:
                        pass

                    pages[i] = page, pk

            return pages

        if self.left:
            self.left = _add_pks(*self.left)

        if self.middle:
            self.middle = _add_pks(*self.middle)

        if self.right:
            self.right = _add_pks(*self.right)

        if self.previous:
            self.previous = _add_pks(self.previous)[0]

        if self.next:
            self.next = _add_pks(self.next)[0]

    def get_count(self):
        assert self.max_count, ('Counting is disabled, call the '
            'paginator with `max_count` or `count` to enable')

        return QuerySetPaginator.get_count(self)

class Paginator(object):
    def __init__(self, objects, get, results_per_page=10, var_prefix='',
            count=None, slice=True, max_objects=MAX_OBJECTS):
        self.get = get.copy()

        self.objects = objects
        self.results_per_page = results_per_page
        self.max_objects = max_objects
        self.slice = slice
        self.var_prefix = var_prefix
        self.page_var = var_prefix + 'page'
        self.pk_var = var_prefix + 'pk'

        self._init_smart_paging()

        self.count = count

        self._init_paginator()

    def __nonzero__(self):
        return bool(self.count)

    def get_objects(self, slice=None):
        if self._sliced_objects is not None:
            return self._sliced_objects

        if slice is None:
            slice = self.slice

        if slice:
            self._sliced_objects = self._objects[self.first:self.last]
        else:
            self._sliced_objects = self._objects

        return self._sliced_objects

    def set_objects(self, objects):
        self._sliced_objects = None
        self._raw_objects = self._objects = objects
        if hasattr(objects, 'queryset'):
            self._raw_objects = objects.queryset

    objects = property(get_objects, set_objects)

    def _init_paginator(self):
        self.left = []
        self.middle = []
        self.right = []
        self.next = None
        self.previous = None

        in_leading_range = in_trailing_range = False
        pages_outside_leading_range = pages_outside_trailing_range = range(0)

        if (self.pages <= LEADING_PAGE_RANGE_DISPLAYED):
            in_leading_range = in_trailing_range = True
            page_numbers = range(1, self.pages + 1)
        
        elif (self.page <= LEADING_PAGE_RANGE):
            in_leading_range = True
            page_numbers = range(1,
                min(LEADING_PAGE_RANGE_DISPLAYED + 1, self.pages + 1))
            pages_outside_leading_range = range(self.pages,
                self.pages - 1, -1)
        
        elif (self.page > self.pages - TRAILING_PAGE_RANGE):
            in_trailing_range = True
            page_numbers = range(
                self.pages - TRAILING_PAGE_RANGE_DISPLAYED + 1,
                self.pages + 1,
            )
            pages_outside_trailing_range = range(
                1, 2)
            
        else:
            page_numbers = range(
                max(1, self.page - ADJACENT_PAGES),
                min(self.pages + 1, self.page + ADJACENT_PAGES + 1),
            )
            pages_outside_leading_range = range(self.pages,
                self.pages - 1, -1)
            pages_outside_trailing_range = range(
                1, 2)

        def _add_pks(*pages):
            if self.pk:
                pages = list(pages)
                for i, page in enumerate(pages):
                    pk = None
                    try:
                        page_delta = page - self.page

                        if page_delta > 0:
                            pk = self.post_pks[page_delta - 1]
                        elif page_delta < 0:
                            pk = self.pre_pks[abs(page_delta) - 1]
                        else:
                            pk = self.pk

                    except IndexError:
                        pass

                    pages[i] = page, pk
            else:
                pages = [(page, None) for page in pages]

            return pages

        if not in_leading_range:
            self.left = _add_pks(*pages_outside_trailing_range)

        self.middle = _add_pks(*page_numbers)

        if not in_trailing_range and self.count <= MAX_OBJECTS:
            self.right = _add_pks(*pages_outside_leading_range[::-1])

        if self.page > 1:
            self.previous = _add_pks(self.page - 1)[0]

        if self.page < self.pages:
            self.next = _add_pks(self.page + 1)[0]

    def get_link(self, page, pk=None):
        if pk and page != 1:
            self.get[self.pk_var] = pk
        else:
            self.get.pop(self.pk_var, None)

        self.get[self.page_var] = page
        return '?' + self.get.urlencode()

    def _get_results_per_page(self):
        return self._results_per_page

    def _set_results_per_page(self, results_per_page):
        self._results_per_page = int(results_per_page)

    results_per_page = property(_get_results_per_page, _set_results_per_page)

    def _get_page_var(self):
        return self._page_var

    def _set_page_var(self, page_var):
        if not page_var:
            page_var = 'page'
        self._page_var = page_var
        
        page = to_int(self.get.get(page_var))

        if not page:
            page = 1

        self.page = page

    page_var = property(_get_page_var, _set_page_var)

    def _init_smart_paging(self):
        self.pre_pks = []
        self.post_pks = []
        self.pk = None
        filter = {}
        objects = self._raw_objects
        order_by = None

        if hasattr(objects, 'query'):
            order_by = (objects.query.order_by or
                objects.model._meta.ordering or
                [None])[0]

            if order_by in ('pk', '-pk', 'id', '-id'):
                pk = int(self.get.get(self.pk_var, 0))
                pk_list = objects.values_list('pk', flat=True)
                if not pk:
                    start_index = (self.page - 1) * self.results_per_page
                    try:
                        pk = pk_list[start_index:start_index+1][0]
                    except IndexError:
                        pk = 0

                if order_by.startswith('-'):
                    reverse_order_by = order_by[1:]
                    if pk:
                        filter = {'pk__lte': int(pk)}
                        reverse_filter = {'pk__gte': int(pk)}
                else:
                    reverse_order_by = '-' + order_by
                    if pk:
                        filter = {'pk__gte': int(pk)}
                        reverse_filter = {'pk__lte': int(pk)}


                if pk:
                    max_pks = max(
                        LEADING_PAGE_RANGE,
                        LEADING_PAGE_RANGE_DISPLAYED,
                    ) * self.results_per_page

                    self.pre_pks = list(pk_list
                        .filter(**reverse_filter)
                        .order_by(reverse_order_by)
                        [self.results_per_page:max_pks:self.results_per_page])

                max_pks = max(
                    TRAILING_PAGE_RANGE,
                    TRAILING_PAGE_RANGE_DISPLAYED,
                ) * self.results_per_page

                pks = list(pk_list
                    .filter(**filter)
                    .order_by(order_by)
                    [:max_pks:self.results_per_page])

                try:
                    self.pk = pks[0]
                    self.post_pks = pks[1:]
                except IndexError:
                    self.pk = None
                    self.post_pks = []

                self._objects = self._objects.filter(**filter)

    def _get_count(self):
        return self._count

    def _set_count(self, count):
        if count:
            pass

        elif hasattr(self._raw_objects, 'count'):
            try:
                objects = self._objects[:self.max_objects]
                count = int(objects.count())

            except (ValueError, TypeError):
                count = len(self._objects)
        
        else:
            count = len(self._objects)

        if self.pk:
            count += (self.page - 1) * self.results_per_page

        self._count = count

        self.pages = int(math.ceil(float(count) / self.results_per_page))

        if self.pk:
            self.first = 0
            self.last = min(self.results_per_page, self.count)
        else:
            self.first = min((self.page - 1) * self.results_per_page,
                self.count)
            self.last = min(self.page * self.results_per_page, self.count)

    count = property(_get_count, _set_count)

    @property
    def display_count(self):
        count = self.count
        if count == self.max_objects:
            count = '%d+' % count
        return count

register.object(SmartQuerySetPaginator)
#register.object(SolrPaginator)
#register.object(Paginator)
#register.object(SolrPaginator)


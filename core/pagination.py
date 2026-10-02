"""Project-wide DRF pagination."""
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page-number pagination with a client-adjustable page size.

    Frontend list screens pass ``?page_size=N`` for pickers and full
    rosters; capped so a client cannot request unbounded result sets.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

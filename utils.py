import sqlalchemy
from flask_taxonomies.constants import INCLUDE_DELETED, INCLUDE_DESCENDANTS, \
    INCLUDE_DESCENDANTS_COUNT, INCLUDE_STATUS, INCLUDE_SELF
from flask_taxonomies.models import TaxonomyTerm, TermStatusEnum, Representation
from flask_taxonomies.proxies import current_flask_taxonomies
from flask_taxonomies.term_identification import TermIdentification
from flask_taxonomies.views.common import build_descendants
from flask_taxonomies.views.paginator import Paginator
from flask import current_app


def get_taxonomy_json(code=None,
                      slug=None,
                      prefer: Representation = Representation("taxonomy"),
                      page=None,
                      size=None,
                      status_code=200,
                      q=None,
                      request=None):
    taxonomy = current_flask_taxonomies.get_taxonomy(code)
    prefer = taxonomy.merge_select(prefer)

    if request:
        current_flask_taxonomies.permissions.taxonomy_term_read.enforce(request=request,
                                                                        taxonomy=taxonomy,
                                                                        slug=slug)

    if INCLUDE_DELETED in prefer:
        status_cond = sqlalchemy.sql.true()
    else:
        status_cond = TaxonomyTerm.status == TermStatusEnum.alive

    return_descendants = INCLUDE_DESCENDANTS in prefer

    if return_descendants:
        query = current_flask_taxonomies.descendants_or_self(
            TermIdentification(taxonomy=code, slug=slug),
            levels=prefer.options.get('levels', None),
            status_cond=status_cond,
            return_descendants_count=INCLUDE_DESCENDANTS_COUNT in prefer,
            return_descendants_busy_count=INCLUDE_STATUS in prefer
        )
    else:
        query = current_flask_taxonomies.filter_term(
            TermIdentification(taxonomy=code, slug=slug),
            status_cond=status_cond,
            return_descendants_count=INCLUDE_DESCENDANTS_COUNT in prefer,
            return_descendants_busy_count=INCLUDE_STATUS in prefer
        )
    if q:
        query = current_flask_taxonomies.apply_term_query(query, q, code)
    paginator = Paginator(
        prefer,
        query, page if return_descendants else None,
        size if return_descendants else None,
        json_converter=lambda data:
        build_descendants(data, prefer, root_slug=None),
        allow_empty=INCLUDE_SELF not in prefer, single_result=INCLUDE_SELF in prefer,
        has_query=q is not None
    )
    return paginator


def taxonomy_term_to_json(term):
    """
    Converts taxonomy term to default JSON. Use only if the term
    has ancestors pre-populated, otherwise it is not an efficient
    implementation - use the one from API instead.
    :param term:    term to serialize
    :return:        array of json terms
    """
    ret = []

    while term:
        data = {
            **(term.extra_data or {}),
            'slug': term.slug,
            'level': term.level + 1,
        }
        if term.obsoleted_by_id:
            data['obsoleted_by'] = term.obsoleted_by.slug

        data['links'] = {
            'self': 'https://' + \
                    current_app.config['SERVER_NAME'] + \
                    current_app.config['FLASK_TAXONOMIES_URL_PREFIX'] + \
                    term.slug
        }

        ret.append(data)
        term = term.parent

    return ret
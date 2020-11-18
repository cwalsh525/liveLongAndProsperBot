import config.default as default

"""
date needed as to query after i started using good filters
"""
def build_get_note_id_query():
    return "select distinct loan_note_id from notes";

def get_url_get_request_note(note_id):
    return "{base_url}/notes/{note_id}".format(base_url=default.config['prosper']['prosper_base_url'], note_id=note_id)

def get_url_get_request_notes_by_date(offset, min_date, limit):
    return "{base_url}/notes/?offset={offset}&limit={limit}&origination_date_min={min_date}".format(base_url=default.config['prosper']['prosper_base_url'], offset=offset, min_date=min_date, limit=limit)

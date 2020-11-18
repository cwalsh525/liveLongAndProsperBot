from notes.update_missing_notes import UpdateMissingNotes
"""
Used for dev to populate notes table
Would only update in prod if there was a bug
"""
UpdateMissingNotes().execute()

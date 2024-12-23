class MissingColumnsError(Exception):
    def __init__(self, missing_columns):
        self.missing_columns = missing_columns

class MissingRowsError(Exception):
    def __init__(self, missing_rows):
        self.missing_rows = missing_rows

class TermCreationError(Exception):
    pass
class CompilerError(Exception):
    def __init__(self, message, line=None, column=None):
        self.line = line
        self.column = column
        loc = ""
        if line is not None and column is not None:
            loc = f" [line {line}:{column}]"
        elif line is not None:
            loc = f" [line {line}]"
        super().__init__(f"{message}{loc}")

class LexerError(CompilerError):
    pass


class ParserError(CompilerError):
    pass


class SemanticError(CompilerError):
    pass
import ast
from ast import NodeVisitor


class SymbolVisitor(NodeVisitor):

    def __init__(self):
        super().__init__()
        self.classes = []
        self.functions = []
        self.imports = []
        self.current_class = None 

    def visit_ClassDef(self, node):
        name = node.name
        start_line = node.lineno
        end_line = node.end_lineno
        docstring = ast.get_docstring(node)
        inheritance = [ast.unparse(base) for base in node.bases]

       
        previous_class = self.current_class
        self.current_class = node.name

        self.classes.append({
            "name": name,
            "base_classes": inheritance,
            "docstring": docstring,
            "start_line": start_line,
            "end_line": end_line
        })

        self.generic_visit(node)
        self.current_class = previous_class 

    def visit_FunctionDef(self, node):
        name = node.name
        start_line = node.lineno
        end_line = node.end_lineno
        docstring = ast.get_docstring(node)

        symbol_type = "method" if self.current_class is not None else "function"
        args = [ast.unparse(arg) for arg in node.args.args]

        self.functions.append({
            "name": name,
            "type": symbol_type,
            "parent_class": self.current_class,  
            "docstring": docstring,
            "start_line": start_line,
            "end_line": end_line,
            "args": args
        })

        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append({
                "module": alias.name,
                "imported_names": []
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""  
        imported_names = [alias.name for alias in node.names]
        self.imports.append({
            "module": module,
            "imported_names": imported_names
        })
        self.generic_visit(node)

def parse_python_file(file_path):
    """Parses a single Python file into AST and returns extracted symbols."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code, filename=str(file_path))
        visitor = SymbolVisitor()
        visitor.visit(tree)
        return {
            "classes": visitor.classes,
            "functions": visitor.functions,
            "imports": visitor.imports
        }
    except (SyntaxError, UnicodeDecodeError, Exception) as e:
        print(f"Warning: Failed to parse AST for {file_path}: {e}")
        return {
            "classes": [],
            "functions": [],
            "imports": []
        }
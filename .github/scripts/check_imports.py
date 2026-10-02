"""Betikleri calistirmadan import ve modul ozniteligi kontrolu.

Her .py dosyasinin AST'si okunur:
  * Her import gercekten yuklenir; `from x import y` icin `y` dogrulanir.
  * `try/except ImportError` icindeki importlar opsiyonel sayilir (fallback
    zincirleri, yalnizca Windows'ta olan winsound vb.); birinin cozulmesi yeter.
  * `cv2.imshow`, `mp.ImageFormat.SRGB` gibi modul oznitelik zincirleri, kurulu
    kutuphane surumunde var mi diye kontrol edilir.

Kullanim: python check_imports.py dosya1.py [dosya2.py ...]
"""

import ast
import importlib
import inspect
import sys

IMPORT_ERRORS = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


def guards_import(handler):
    if handler.type is None:
        return True
    names = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(n, ast.Name) and n.id in IMPORT_ERRORS for n in names)


def load(name):
    try:
        return importlib.import_module(name), None
    except Exception as e:  # kurulum bozuksa (or. cv2 cakismasi) ImportError disi hatalar da olur
        return None, f"{type(e).__name__}: {e}"


def resolve_from(module, name):
    mod, err = load(module)
    if mod is None:
        return None, err
    if hasattr(mod, name):
        return getattr(mod, name), None
    sub, err = load(f"{module}.{name}")
    if sub is None:
        return None, f"'{module}' icinde '{name}' yok"
    return sub, None


class Checker(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.errors = []
        self.aliases = {}  # yerel ad -> yuklenen modul/nesne
        self.guarded = 0

    def fail(self, node, msg):
        self.errors.append(f"{self.path}:{node.lineno}: {msg}")

    def visit_Try(self, node):
        guarded = any(guards_import(h) for h in node.handlers)
        if guarded:
            self.guarded += 1
        for stmt in node.body:
            self.visit(stmt)
        if guarded:
            self.guarded -= 1
        for part in (node.handlers, node.orelse, node.finalbody):
            for stmt in part:
                self.visit(stmt)

    visit_TryStar = visit_Try

    def visit_Import(self, node):
        for a in node.names:
            mod, err = load(a.name)
            if mod is None:
                if not self.guarded:
                    self.fail(node, f"import {a.name} -> {err}")
                continue
            if a.asname:
                self.aliases[a.asname] = mod
            else:
                top = a.name.split(".")[0]
                self.aliases[top] = sys.modules[top]

    def visit_ImportFrom(self, node):
        if node.level:
            return
        for a in node.names:
            if a.name == "*":
                continue
            obj, err = resolve_from(node.module, a.name)
            if obj is None:
                if not self.guarded:
                    self.fail(node, f"from {node.module} import {a.name} -> {err}")
                continue
            self.aliases[a.asname or a.name] = obj

    def visit_Attribute(self, node):
        chain = []
        cur = node
        while isinstance(cur, ast.Attribute):
            chain.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name) and cur.id in self.aliases:
            obj = self.aliases[cur.id]
            dotted = cur.id
            for attr in reversed(chain):
                if not (inspect.ismodule(obj) or inspect.isclass(obj)):
                    break  # ornek nesneler uzerindeki oznitelikleri kontrol etme
                if hasattr(obj, attr):
                    obj = getattr(obj, attr)
                elif inspect.ismodule(obj) and load(f"{obj.__name__}.{attr}")[0] is not None:
                    obj = sys.modules[f"{obj.__name__}.{attr}"]
                else:
                    self.fail(node, f"'{dotted}' uzerinde '{attr}' yok")
                    break
                dotted += f".{attr}"
            return  # zincir islendi, alt dugumleri tekrar gezme
        self.generic_visit(node)


def main(paths):
    errors = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        checker = Checker(path)
        checker.visit(tree)
        errors += checker.errors
        print(f"{'HATA' if checker.errors else 'OK  '} {path}")
    for e in errors:
        print(e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

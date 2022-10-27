from __future__ import annotations

import cmath
import math
import sys
from fractions import Fraction
from functools import reduce
from typing import TYPE_CHECKING

import numpy as np

from auto_editor.analyze import (
    audio_levels,
    get_all,
    get_none,
    motion_levels,
    pixeldiff_levels,
    random_levels,
    to_threshold,
)
from auto_editor.objs.edit import (
    Audio,
    Motion,
    Pixeldiff,
    Random,
    audio_builder,
    motion_builder,
    pixeldiff_builder,
    random_builder,
)
from auto_editor.objs.util import _Vars, parse_dataclass
from auto_editor.utils.func import apply_margin, cook, remove_small

if TYPE_CHECKING:
    from fractions import Fraction
    from typing import Any, Callable, Union

    from numpy.typing import NDArray

    from auto_editor.ffwrapper import FileInfo
    from auto_editor.output import Ensure
    from auto_editor.utils.bar import Bar
    from auto_editor.utils.log import Log

    BoolList = NDArray[np.bool_]
    BoolOperand = Callable[[BoolList, BoolList], BoolList]

    Node = Union[Compound, Var, ManyOp, Num, Str, Bool, BoolArr]


class MyError(Exception):
    pass


def boolop(a: BoolList, b: BoolList, call: BoolOperand) -> BoolList:
    if len(a) > len(b):
        b = np.resize(b, len(a))
    if len(b) > len(a):
        a = np.resize(a, len(b))

    return call(a, b)


def print_arr(arr: BoolList) -> str:
    rs = "(boolarr"
    for item in arr:
        rs += " 1" if item else " 0"
    rs += ")\n"
    return rs


def is_boolarr(arr: object) -> bool:
    """boolarr?"""
    if isinstance(arr, np.ndarray):
        return arr.dtype.kind == "b"
    return False


def is_bool(val: object) -> bool:
    """boolean?"""
    return isinstance(val, bool)


def is_num(val: object) -> bool:
    """number?"""
    return not isinstance(val, bool) and isinstance(
        val, (int, float, Fraction, complex)
    )


def is_real(val: object) -> bool:
    """real?"""
    return not isinstance(val, bool) and isinstance(val, (int, float, Fraction))


def exact_int(val: object) -> bool:
    """exact-integer?"""
    return not isinstance(val, bool) and isinstance(val, int)


def is_exact(val: object) -> bool:
    """exact?"""
    return isinstance(val, (int, Fraction))


def is_str(val: object) -> bool:
    """string?"""
    return isinstance(val, str)


def check_args(
    op: Token, values: list[Any], arity: tuple[int, int | None], types: list[Any] | None
) -> None:
    lower, upper = arity
    amount = len(values)
    o = op.value
    if upper is not None and lower > upper:
        raise ValueError("lower must be less than upper")
    if lower == upper:
        if len(values) != lower:
            raise MyError(f"{o}: Arity mismatch. Expected {lower}, got {amount}")

    if upper is None and amount < lower:
        raise MyError(f"{o}: Arity mismatch. Expected at least {lower}, got {amount}")
    if upper is not None and (amount > upper or amount < lower):
        raise MyError(
            f"{o}: Arity mismatch. Expected between {lower} and {upper}, got {amount}"
        )

    if types is None:
        return

    for i, val in enumerate(values):
        check = types[-1] if i >= len(types) else types[i]
        if not check(val):
            raise MyError(f"{o} expects: {' '.join([_t.__doc__ for _t in types])}")


###############################################################################
#                                                                             #
#  LEXER                                                                      #
#                                                                             #
###############################################################################

METHODS = ("audio", "motion", "pixeldiff", "random", "none", "all")
SEC_UNITS = ("s", "sec", "secs", "second", "seconds")
METHOD_ATTRS_SEP = ":"

DEF, SET, ID, DIS = "DEF", "SET", "ID", "DIS"
NUM, STR, ARR, SEC, LPAREN, RPAREN, EOF = "NUM", "STR", "ARR", "SEC", "(", ")", "EOF"
NOT, OR, AND, XOR, BOOL = "NOT", "OR", "AND", "XOR", "BOOL"
PLUS, MINUS, MUL, DIV = "PLUS", "MINUS", "MUL", "DIV"
ROND, EROND, CEIL, ECEIL, FLR, EFLR = "ROND", "EROND", "CEIL", "ECEIL", "FLR", "EFLR"
A1, S1, MOD, ABS = "A1", "S1", "MOD", "ABS"
SA, SU, SD, ST, SL = "SA", "SU", "SD", "ST", "SL"
NUMQ, REALQ, STRQ, BOOLQ, BOOLARRQ = "NUMQ", "REALQ", "STRQ", "BOOLQ", "BOOLARRQ"
EQN, GR, LT, GRE, LTE = "EQN", "GR", "LT", "GRE", "LTE"
SQRT, POS, NEG, ZERO, EQ = "SQRT", "POS", "NEG", "ZERO", "EQ"
MARGIN, MCUT, MCLIP, COOK, BOOLARR = "MARGIN", "MCUT", "MCLIP", "COOK", "BOOLARR"
LEN, CNZ, EXACTQ, NTS, EINT = "LEN", "CNZ", "EXACTQ", "NTS", "EINT"

func_map = {
    "define": DEF,
    "set!": SET,
    "length": LEN,
    "display": DIS,
    "not": NOT,
    "or": OR,
    "and": AND,
    "xor": XOR,
    "+": PLUS,
    "-": MINUS,
    "*": MUL,
    "/": DIV,
    ">": GR,
    ">=": GRE,
    "<": LT,
    "<=": LTE,
    "=": EQN,
    "round": ROND,
    "exact-round": EROND,
    "ceiling": CEIL,
    "exact-ceiling": ECEIL,
    "floor": FLR,
    "exact-floor": EFLR,
    "modulo": MOD,
    "abs": ABS,
    "sqrt": SQRT,
    "add1": A1,
    "sub1": S1,
    "string-append": SA,
    "string-upcase": SU,
    "string-downcase": SD,
    "string-titlecase": ST,
    "string-length": SL,
    "number->string": NTS,
    "number?": NUMQ,
    "real?": REALQ,
    "exact-integer?": EINT,
    "string?": STRQ,
    "exact?": EXACTQ,
    "boolean?": BOOLQ,
    "positive?": POS,
    "negative?": NEG,
    "zero?": ZERO,
    "equal?": EQ,
    # ae extensions
    "margin": MARGIN,
    "mcut": MCUT,
    "mincut": MCUT,
    "mclip": MCLIP,
    "minclip": MCLIP,
    "cook": COOK,
    "boolarr": BOOLARR,
    "boolarr?": BOOLARRQ,
    "count-nonzero": CNZ,
}


class Token:
    __slots__ = ("type", "value")

    def __init__(self, type: str, value: Any):
        self.type = type
        self.value = value

    def __str__(self) -> str:
        return f"(Token {self.type} {self.value})"


class Lexer:
    __slots__ = ("log", "text", "pos", "char")

    def __init__(self, text: str):
        self.text = text
        self.pos: int = 0
        if len(text) == 0:
            self.char: str | None = None
        else:
            self.char = self.text[self.pos]

    def char_is_norm(self) -> bool:
        # , and # need to be included to not cause infinite loop
        return (
            self.char is not None and self.char not in "()[]{}\"'`;|\\ \t\n\r\x0b\x0c"
        )

    def advance(self) -> None:
        self.pos += 1
        if self.pos > len(self.text) - 1:
            self.char = None
        else:
            self.char = self.text[self.pos]

    def peek(self) -> str | None:
        peek_pos = self.pos + 1
        if peek_pos > len(self.text) - 1:
            return None
        else:
            return self.text[peek_pos]

    def skip_whitespace(self) -> None:
        while self.char is not None and self.char in " \t\n\r\x0b\x0c":
            self.advance()

    def string(self) -> str:
        result = ""
        while self.char is not None and self.char != '"':
            if self.char == "\\":
                self.advance()
                if self.char in 'nt"\\':
                    if self.char == "n":
                        result += "\n"
                    if self.char == "t":
                        result += "\t"
                    if self.char == '"':
                        result += '"'
                    if self.char == "\\":
                        result += "\\"
                    self.advance()
                    continue

                if self.char is None:
                    raise MyError("Unexpected EOF while parsing")
                raise MyError(
                    f"Unexpected character {self.char} during escape sequence"
                )
            else:
                result += self.char
            self.advance()

        self.advance()
        return result

    def number(self) -> Token:
        result = ""
        token = NUM

        while self.char is not None and self.char in "+-0123456789./":
            result += self.char
            self.advance()

        unit = ""
        if self.char_is_norm():
            while self.char_is_norm():
                assert self.char is not None
                unit += self.char
                self.advance()

            if unit in SEC_UNITS:
                token = SEC
            elif unit != "i":
                return Token(ID, result + unit)

        if unit == "i":
            try:
                return Token(NUM, complex(result + "j"))
            except ValueError:
                return Token(ID, result + unit)

        if "/" in result:
            try:
                return Token(token, Fraction(result))
            except ValueError:
                return Token(ID, result + unit)

        if "." in result:
            try:
                return Token(token, float(result))
            except ValueError:
                return Token(ID, result + unit)

        try:
            return Token(token, int(result))
        except ValueError:
            return Token(ID, result + unit)

    def get_next_token(self) -> Token:
        while self.char is not None:
            self.skip_whitespace()
            if self.char is None:
                continue

            if self.char == ";":
                while self.char is not None and self.char != "\n":
                    self.advance()
                continue

            if self.char == '"':
                self.advance()
                return Token(STR, self.string())
            if self.char == "(":
                self.advance()
                return Token(LPAREN, "(")
            if self.char == ")":
                self.advance()
                return Token(RPAREN, ")")

            if self.char in "+-":
                _peek = self.peek()
                if _peek is not None and _peek in "0123456789.":
                    return self.number()

            if self.char in "0123456789.":
                return self.number()

            result = ""
            while self.char_is_norm():
                result += self.char
                self.advance()

            if result in ("#t", "#true"):
                return Token(BOOL, True)
            if result in ("#f", "#false"):
                return Token(BOOL, False)
            if result in func_map:
                return Token(func_map[result], result)

            for method in METHODS:
                if result == method or result.startswith(method + ":"):
                    return Token(ARR, result)

            return Token(ID, result)

        return Token(EOF, "EOF")


###############################################################################
#                                                                             #
#  PARSER                                                                     #
#                                                                             #
###############################################################################


class Compound:
    __slots__ = "children"

    def __init__(self, children: list[Node]):
        self.children = children

    def __str__(self) -> str:
        s = "{Compound"
        for child in self.children:
            s += f" {child}"
        s += "}"
        return s


class ManyOp:
    __slots__ = ("op", "children")

    def __init__(self, op: Token, children: list[Node]):
        self.op = op
        self.children = children

    def __str__(self) -> str:
        s = f"(ManyOp {self.op}"
        for child in self.children:
            s += f" {child}"
        s += ")"
        return s


class Atom:
    pass


class Var(Atom):
    def __init__(self, token: Token):
        assert token.type == ID
        self.token = token
        self.value = token.value

    def __str__(self) -> str:
        return f"(Var {self.value})"


class Num(Atom):
    __slots__ = "val"

    def __init__(self, val: int | float | Fraction | complex):
        self.val = val

    def __str__(self) -> str:
        return f"(num {self.val})"


class Bool(Atom):
    __slots__ = "val"

    def __init__(self, val: bool):
        self.val = val

    def __str__(self) -> str:
        b = "#t" if self.val else "#f"
        return f"(bool {b})"


class Str(Atom):
    __slots__ = "val"

    def __init__(self, val: str):
        self.val = val

    def __str__(self) -> str:
        return f"(str {self.val})"


class BoolArr(Atom):
    __slots__ = "val"

    def __init__(self, val: str):
        self.val = val

    def __str__(self) -> str:
        return f"(boolarr {self.val})"


class Parser:
    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.current_token = self.lexer.get_next_token()

    def eat(self, token_type: str) -> None:
        if self.current_token.type != token_type:
            raise MyError(f"Expected {token_type}, got {self.current_token.type}")

        self.current_token = self.lexer.get_next_token()

    def comp(self) -> Compound:
        comp_kids = []
        while self.current_token.type not in (EOF, RPAREN):
            comp_kids.append(self.expr())
        return Compound(comp_kids)

    def expr(self) -> Node:
        token = self.current_token

        if token.type == ID:
            self.eat(ID)
            return Var(token)

        matches = {ARR: BoolArr, BOOL: Bool, NUM: Num, STR: Str}
        if token.type in matches:
            self.eat(token.type)
            return matches[token.type](token.value)

        if token.type == SEC:
            self.eat(SEC)
            return ManyOp(
                Token(EROND, "exact-round"),
                [
                    ManyOp(
                        Token(MUL, "*"), [Num(token.value), Var(Token(ID, "timebase"))]
                    )
                ],
            )

        if token.type == LPAREN:
            self.eat(LPAREN)
            if self.current_token.type in (ARR, BOOL, NUM, STR, SEC):
                raise MyError("Expected procedure")
            node = self.expr()
            self.eat(RPAREN)
            return node

        token = self.current_token
        self.eat(token.type)

        childs = []
        while self.current_token.type not in (RPAREN, EOF):
            childs.append(self.expr())

        return ManyOp(token, children=childs)

    def __str__(self) -> str:
        result = str(self.comp())

        self.lexer.pos = 0
        self.lexer.char = self.lexer.text[0]
        self.current_token = self.lexer.get_next_token()

        return result


###############################################################################
#                                                                             #
#  INTERPRETER                                                                #
#                                                                             #
###############################################################################


class Interpreter:

    GLOBAL_SCOPE: dict[str, Any] = {
        "true": True,
        "false": False,
        "pi": math.pi,
    }

    def __init__(
        self,
        parser: Parser,
        src: FileInfo,
        ensure: Ensure,
        strict: bool,
        tb: Fraction,
        bar: Bar,
        temp: str,
        log: Log,
    ):

        self.parser = parser
        self.src = src
        self.ensure = ensure
        self.strict = strict
        self.tb = tb
        self.bar = bar
        self.temp = temp
        self.log = log

        self.GLOBAL_SCOPE["timebase"] = self.tb

    def visit(self, node: Node) -> Any:
        if isinstance(node, Atom):
            if isinstance(node, (Num, Str, Bool)):
                return node.val

            if isinstance(node, Var):
                val = self.GLOBAL_SCOPE.get(node.value)
                if val is None:
                    raise MyError(f"{node.value} is undefined")
                return val

            if isinstance(node, BoolArr):
                src, ensure, strict, tb = self.src, self.ensure, self.strict, self.tb
                bar, temp, log = self.bar, self.temp, self.log

                if METHOD_ATTRS_SEP in node.val:
                    method, attrs = node.val.split(METHOD_ATTRS_SEP)
                    if method not in METHODS:
                        log.error(f"'{method}' not allowed to have attributes")
                else:
                    method, attrs = node.val, ""

                if method == "none":
                    return get_none(ensure, src, tb, temp, log)

                if method == "all":
                    return get_all(ensure, src, tb, temp, log)

                if method == "random":
                    robj = parse_dataclass(attrs, (Random, random_builder), log)
                    return to_threshold(
                        random_levels(ensure, src, robj, tb, temp, log), robj.threshold
                    )

                if method == "audio":
                    aobj = parse_dataclass(attrs, (Audio, audio_builder), log)
                    s = aobj.stream
                    if s == "all":
                        total_list: BoolList | None = None
                        for s in range(len(src.audios)):
                            audio_list = to_threshold(
                                audio_levels(
                                    ensure, src, s, tb, bar, strict, temp, log
                                ),
                                aobj.threshold,
                            )
                            if total_list is None:
                                total_list = audio_list
                            else:
                                total_list = boolop(
                                    total_list, audio_list, np.logical_or
                                )
                        if total_list is None:
                            if strict:
                                log.error("Input has no audio streams.")
                            stream_data = get_all(ensure, src, tb, temp, log)
                        else:
                            stream_data = total_list
                    else:
                        stream_data = to_threshold(
                            audio_levels(ensure, src, s, tb, bar, strict, temp, log),
                            aobj.threshold,
                        )

                    return stream_data

                if method == "motion":
                    if src.videos:
                        _vars: _Vars = {"width": src.videos[0].width}
                    else:
                        _vars = {"width": 1}

                    mobj = parse_dataclass(attrs, (Motion, motion_builder), log, _vars)
                    return to_threshold(
                        motion_levels(ensure, src, mobj, tb, bar, strict, temp, log),
                        mobj.threshold,
                    )

                if method == "pixeldiff":
                    pobj = parse_dataclass(attrs, (Pixeldiff, pixeldiff_builder), log)
                    return to_threshold(
                        pixeldiff_levels(ensure, src, pobj, tb, bar, strict, temp, log),
                        pobj.threshold,
                    )

                raise ValueError("Unreachable")

            raise ValueError("Unreachable")

        if isinstance(node, ManyOp):
            if node.op.type in (DEF, SET):
                check_args(node.op, node.children, (2, 2), None)

                if not isinstance(node.children[0], Var):
                    raise MyError(
                        f"Variable must be set with a symbol, got {node.children[0]}"
                    )

                var_name = node.children[0].value
                if node.op.type == SET and var_name not in self.GLOBAL_SCOPE:
                    raise MyError(f"Cannot set variable {var_name} before definition")

                self.GLOBAL_SCOPE[var_name] = self.visit(node.children[1])
                return None

            values = []
            types: set[Any] = set()
            for child in node.children:
                _val = self.visit(child)
                types.add(type(_val))
                values.append(_val)

            if node.op.type == LEN:
                check_args(node.op, values, (1, 1), [is_boolarr])
                return len(values[0])
            if node.op.type == CNZ:
                check_args(node.op, values, (1, 1), [is_boolarr])
                return np.count_nonzero(values[0])
            if node.op.type == SQRT:
                check_args(node.op, values, (1, 1), [is_num])
                _result = cmath.sqrt(values[0])
                if _result.imag == 0:
                    _real = _result.real
                    if int(_real) == _real:
                        return int(_real)
                    return _real
                return _result
            if node.op.type == EXACTQ:
                check_args(node.op, values, (1, 1), [is_num])
                return is_exact(values[0])
            if node.op.type == REALQ:
                check_args(node.op, values, (1, 1), None)
                return is_real(values[0])
            if node.op.type == NUMQ:
                check_args(node.op, values, (1, 1), None)
                return is_num(values[0])
            if node.op.type == STRQ:
                check_args(node.op, values, (1, 1), None)
                return is_str(values[0])
            if node.op.type == BOOLQ:
                check_args(node.op, values, (1, 1), None)
                return is_bool(values[0])
            if node.op.type == BOOLARRQ:
                check_args(node.op, values, (1, 1), None)
                return is_boolarr(val)

            if node.op.type == ZERO:
                check_args(node.op, values, (1, 1), [is_real])
                return values[0] == 0
            if node.op.type == POS:
                check_args(node.op, values, (1, 1), [is_real])
                return values[0] > 0
            if node.op.type == NEG:
                check_args(node.op, values, (1, 1), [is_real])
                return values[0] < 0
            if node.op.type == ABS:
                check_args(node.op, values, (1, 1), [is_real])
                return abs(values[0])
            if node.op.type == CEIL:
                check_args(node.op, values, (1, 1), [is_real])
                if isinstance(values[0], float):
                    return float(math.ceil(values[0]))
                return math.ceil(values[0])
            if node.op.type == ECEIL:
                check_args(node.op, values, (1, 1), [is_real])
                return math.ceil(values[0])
            if node.op.type == FLR:
                check_args(node.op, values, (1, 1), [is_real])
                if isinstance(values[0], float):
                    return float(math.floor(values[0]))
                return math.floor(values[0])
            if node.op.type == EFLR:
                check_args(node.op, values, (1, 1), [is_real])
                return math.floor(values[0])
            if node.op.type == ROND:
                check_args(node.op, values, (1, 1), [is_real])
                if isinstance(values[0], float):
                    return float(round(values[0]))
                return round(values[0])
            if node.op.type == EROND:
                check_args(node.op, values, (1, 1), [is_real])
                return round(values[0])
            if node.op.type == A1:
                check_args(node.op, values, (1, 1), [is_num])
                return values[0] + 1
            if node.op.type == S1:
                check_args(node.op, values, (1, 1), [is_num])
                return values[0] - 1
            if node.op.type == SU:
                check_args(node.op, values, (1, 1), [is_str])
                return values[0].upper()
            if node.op.type == SD:
                check_args(node.op, values, (1, 1), [is_str])
                return values[0].lower()
            if node.op.type == ST:
                check_args(node.op, values, (1, 1), [is_str])
                return values[0].title()
            if node.op.type == SL:
                check_args(node.op, values, (1, 1), [is_str])
                return len(values[0])
            if node.op.type == NTS:
                check_args(node.op, values, (1, 1), [is_num])
                return str(values[0])

            if node.op.type == EQ:
                check_args(node.op, values, (2, 2), None)
                if isinstance(values[0], float) and not isinstance(values[1], float):
                    return False
                if isinstance(values[1], float) and not isinstance(values[0], float):
                    return False
                return values[0] == values[1]

            if node.op.type == GR:
                check_args(node.op, values, (2, 2), [is_real, is_real])
                return values[0] > values[1]

            if node.op.type == GRE:
                check_args(node.op, values, (2, 2), [is_real, is_real])
                return values[0] >= values[1]

            if node.op.type == LT:
                check_args(node.op, values, (2, 2), [is_real, is_real])
                return values[0] < values[1]

            if node.op.type == LTE:
                check_args(node.op, values, (2, 2), [is_real, is_real])
                return values[0] <= values[1]

            if node.op.type == MCLIP:
                check_args(node.op, values, (2, 2), [exact_int, is_boolarr])
                return remove_small(values[1], values[0], replace=1, with_=0)

            if node.op.type == MCUT:
                check_args(node.op, values, (2, 2), [exact_int, is_boolarr])
                return remove_small(values[1], values[0], replace=0, with_=1)

            if node.op.type == MARGIN:
                check_args(node.op, values, (2, 2), [exact_int, is_boolarr])
                return apply_margin(values[1], len(values[1]), values[0], values[0])

            if node.op.type == MOD:
                check_args(node.op, values, (2, 2), [exact_int, exact_int])
                return values[0] % values[1]

            if node.op.type == DIS:
                check_args(node.op, values, (1, 1), None)
                if (val := values[0]) is None:
                    return None
                if is_boolarr(val):
                    val = print_arr(val)
                sys.stdout.write(str(val))
                return None

            if node.op.type == NOT:
                check_args(node.op, values, (1, 1), None)
                if is_boolarr(val := values[0]):
                    return np.logical_not(val)
                if is_bool(val):
                    return not val
                raise MyError(f"{node.op.value} expects: boolean? or boolarr?")

            if node.op.type == COOK:
                check_args(node.op, values, (3, 3), [exact_int, exact_int, is_boolarr])
                return cook(values[2], values[1], values[0])

            if node.op.type == MARGIN:
                check_args(node.op, values, (3, 3), [exact_int, exact_int, is_boolarr])
                return apply_margin(values[2], len(values[2]), values[0], values[1])

            if node.op.type == EQN:
                check_args(node.op, values, (1, None), [is_num])
                for i in range(1, len(values)):
                    if values[0] != values[i]:
                        return False
                return True

            if node.op.type == BOOLARR and not {np.ndarray, str, complex}.intersection(
                types
            ):
                return np.array(values, dtype=np.bool_)

            if node.op.type == SA and types == {str}:
                return reduce(lambda a, b: a + b, values)

            if types == {bool}:
                if node.op.type == OR:
                    return reduce(lambda a, b: a or b, values)
                if node.op.type == AND:
                    return reduce(lambda a, b: a and b, values)
                if node.op.type == XOR:
                    return reduce(lambda a, b: a ^ b, values)

            if types == {np.ndarray}:
                if node.op.type == OR:
                    return reduce(lambda a, b: boolop(a, b, np.logical_or), values)
                if node.op.type == AND:
                    return reduce(lambda a, b: boolop(a, b, np.logical_and), values)
                if node.op.type == XOR:
                    return reduce(lambda a, b: boolop(a, b, np.logical_xor), values)

            if not {np.ndarray, str}.intersection(types):
                if node.op.type == PLUS:
                    if len(values) == 0:
                        return 0
                    return reduce(lambda a, b: a + b, values)
                if node.op.type == MINUS:
                    if len(values) == 0:
                        raise MyError("-: Arity mismatch, expected 1")
                    if len(values) == 1:
                        return -values[0]
                    return reduce(lambda a, b: a - b, values)
                if node.op.type == MUL:
                    if len(values) == 0:
                        return 1
                    return reduce(lambda a, b: a * b, values)
                if node.op.type == DIV:
                    if len(values) == 0:
                        raise MyError("/: Arity mismatch, expected 1")
                    if len(values) == 1:
                        values.insert(0, 1)
                    if not {float, complex}.intersection(types):
                        return reduce(lambda a, b: Fraction(a, b), values)
                    return reduce(lambda a, b: a / b, values)

            raise MyError(f"{node.op.value} got wrong type")

        if isinstance(node, Compound):
            results = []
            for child in node.children:
                results.append(self.visit(child))
            return results

        raise ValueError(f"Unknown node type: {node}")

    def interpret(self) -> Any:
        return self.visit(self.parser.comp())


def run_interpreter(
    text: str,
    src: FileInfo,
    ensure: Ensure,
    strict: bool,
    tb: Fraction,
    bar: Bar,
    temp: str,
    log: Log,
) -> BoolList:

    try:
        lexer = Lexer(text)
        parser = Parser(lexer)
        if log.debug:
            log.debug(f"edit: {parser}")

        interpreter = Interpreter(parser, src, ensure, strict, tb, bar, temp, log)
        results = interpreter.interpret()
    except MyError as e:
        log.error(e)

    if len(results) == 0:
        log.error("Expression in --edit must return a boolarr")

    result = results[-1]
    if not is_boolarr(results[-1]):
        log.error("Expression in --edit must return a boolarr")

    assert isinstance(result, np.ndarray)
    return result

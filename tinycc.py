# The MIT License (MIT)
#
# Copyright (c) 2016 Joerg Breitbart
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
__author__ = 'Joerg Breitbart'
__copyright__ = 'Copyright (C) 2016 Joerg Breitbart'
__license__ = 'MIT'
__version__ = '0.1.0'

import os
import sys
import ctypes
import types

PY3 = False
if sys.version_info >= (3, 0):
    PY3 = True
    unicode = str

# basic type mapping (array types are not supported)
TYPE_MAPPER = {
    # stdint.h
    ctypes.c_int8: 'int8_t',
    ctypes.c_int16: 'int16_t',
    ctypes.c_int32: 'int32_t',
    ctypes.c_int64: 'int64_t',
    ctypes.c_uint8: 'unsigned int8_t',
    ctypes.c_uint16: 'unsigned int16_t',
    ctypes.c_uint32: 'unsigned int32_t',
    ctypes.c_uint64: 'unsigned int64_t',

    # stddef.h
    ctypes.c_size_t: 'size_t',
    ctypes.c_ssize_t: 'ssize_t',

    # basic types
    ctypes.c_int: 'int',
    ctypes.c_uint: 'unsigned int',
    ctypes.c_long: 'long',
    ctypes.c_longlong: 'long long',
    ctypes.c_short: 'short',
    ctypes.c_ulong: 'unsigned long',
    ctypes.c_ulonglong: 'unsigned long long',
    ctypes.c_ushort: 'unsigned short',
    ctypes.c_double: 'double',
    ctypes.c_float: 'float',
    #ctypes.c_longdouble: 'long double', # long double not working in PyPy
    ctypes.c_bool: '_Bool',
    ctypes.c_byte: 'char',
    ctypes.c_ubyte: 'unsigned char',
    ctypes.c_char: 'char',
    ctypes.c_wchar: 'wchar_t'
}
# add basic pointer types
TYPE_MAPPER.update({ctypes.POINTER(k): v+' *' for k, v in TYPE_MAPPER.items()})
# add basic special types
TYPE_MAPPER.update({
    None: 'void',
    ctypes.c_char_p: 'char *',
    ctypes.c_wchar_p: 'wchar_t *',
    ctypes.c_void_p: 'void *'
})

MODULEDIR = os.path.dirname(__file__)
TCCPATH = os.path.join(MODULEDIR, './linux/lib/tcc')
TCCLIB = os.path.join(MODULEDIR, './linux/lib/libtcc.so')
OUTPUT_TYPES = {
    'memory': 1,
    'exe'   : 2,
    'dll'   : 3,
    'obj'   : 4
}
WINDOWS = False
if sys.platform == 'win32':
    WINDOWS = True
    TCCPATH = os.path.join(MODULEDIR, 'win32')
    TCCLIB = os.path.join(MODULEDIR, 'win32\libtcc.dll')


# tcc error function type
ERROR_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_char_p)


class Declaration(object):
    def __init__(self, code, decl=''):
        self._c_decl = decl
        self._c_code = code


class InlineGeneratorException(Exception):
    pass


class TccException(Exception):
    pass


class _ScopedStructureBase(type(ctypes.Structure)):
    """
    Metaclass for a ScopedStructure class.
    It creates the C declarations for the struct and their
    c_method and callable_method decorated methods.

    Naming:
    A Python class name `Test` translates to `struct Test`
    in C (no typedef declaration is added).
    A decorated instance method `Test.method(self, ...) is
    declared as `Test_method(struct Test * self, ...)` in C.
    """
    _state_ = None
    _sname_ = ''
    _fields_ = []

    def __init__(cls, name, bases, dct):
        dct['_c_decl'] = _ScopedStructureBase._c_decl
        dct['_c_code'] = _ScopedStructureBase._c_code
        super(_ScopedStructureBase, cls).__init__(name, bases, dct)
        if cls.__name__ not in ('CStructure', 'ScopedStructure'):
            if not cls._sname_:
                cls._sname_ = cls.__name__
            TYPE_MAPPER[cls] = 'struct %s' % cls._sname_
            TYPE_MAPPER[ctypes.POINTER(cls)] = 'struct %s *' % cls._sname_
            cls._state_.parts.append(cls)
            for k, v in dct.items():
                if (isinstance(v, types.FunctionType) and
                        getattr(v, '_cmethod', False)):
                    v._proto(ctypes.POINTER(cls), cls._sname_)

    @property
    def _c_decl(cls):
        return 'struct %s;' % cls._sname_

    @property
    def _c_code(cls):
        def members(fields):
            for name, ctype in fields:
                if issubclass(ctype, ctypes.Array):
                    yield '    %s %s[%s];' % (
                        TYPE_MAPPER[ctype._type_], name, ctype._length_)
                else:
                    yield '    %s %s;' % (TYPE_MAPPER[ctype], name)

        return 'struct %s\n{\n%s\n};' % (
            cls._sname_, '\n'.join(members(cls._fields_)))


class InlineGenerator(object):
    """
    Class to handle inline C definitions and
    prepare symbol import and export to C.

    Code generation:
    The code is generated by collecting all
    defined parts and writing them into 3 sections:

        top section
        The section gets not autofilled by the generator.
        Use it with `add_topdeclaration` for any early stuff
        like including header files and such.

        forward section
        Used by the generator to do forward declarations
        of the inline definitions.

        definition section
        Used by the generator to place the inline
        definitions. With `add_definition` you can add
        any code to this section.

    Symbols:
    For the provided decorators `c_function`, `c_method`,
    `callable_function` and `callable_method` symbols are
    automatically resolved between Python and C.
    Make sure to bind the generator object to a relocated
    memory state before using those functions.

    NOTE: Due to the awkward handling of arrays in C
    the decorators don't support C arrays as arguments or restype.
    You would have to fall back to a pointer and
    length argument anyways.

    Example:
        >>> from tinycc import TinyCC, InlineGenerator
        >>> from ctypes import c_int
        >>>
        >>> gen = InlineGenerator()
        >>>
        >>> # C function to be used from Python
        ... @gen.c_function(c_int, c_int, c_int, c_int)
        ... def add_mul(a, b, c):
        ...     "return mul(a + b, c);" #  calls the Python function mul
        ...
        >>> # Python function to be used from C
        ... @gen.callable_function(c_int, c_int, c_int)
        ... def mul(a, b):
        ...     return a * b
        ...
        >>> # compile the code
        ... state = TinyCC().create_state()
        >>> state.compile(gen.code)
        >>> state.relocate()
        >>>
        >>> # bind to state for symbol resolution
        ... gen.bind_state(state)
        >>>
        >>> # use it
        ... add_mul(23, 42, 7)
    """
    def __init__(self):
        self.parts = []
        self.headerparts = []
        self.state = None
        self.symbols = []

    def bind_state(self, state):
        """
        Bind to the compiler state `state`.
        Enables the symbol resolution between C and Python.
        `state` must be of the memory type.
        """
        if not isinstance(state, TccStateMemory):
            raise InlineGeneratorException('state must be a memory type')
        if not state._relocated:
            raise InlineGeneratorException('state is not relocated')
        self.state = state
        # reset code parts (reimport symbols to Python lazy)
        for part in self.parts:
            part._c_func = None
        # add callable symbols to state (export to C)
        for symbol in self.symbols:
            self.state.set_symbol(*symbol)

    def add_topdeclaration(self, declaration):
        """
        Add `declaration` to the top section.
        """
        self.headerparts.append(Declaration(declaration))

    def add_definition(self, code, forward=''):
        """
        Add `code` to the definition section. Optional
        write `forward` to the forward section.
        """
        self.parts.append(Declaration(code, forward))

    @property
    def code(self):
        """
        Property for the generated C code.
        """
        pre = '/* inline generated code */'
        end = '/*\n * inline generated code end\n */'
        top = '/*\n * top section\n */\n\n'
        top += '\n'.join(part._c_code for part in self.headerparts)
        forward = '/*\n * forward section\n */\n\n'
        forward += '\n'.join(part._c_decl for part in self.parts)
        definition = '/*\n * definitions\n */\n\n'
        definition += '\n\n'.join(part._c_code for part in self.parts)
        return '\n\n\n'.join(filter(bool, [pre, top, forward, definition, end]))

    @property
    def ScopedStructure(self):
        """
        Structure with decorators for c_method and callable_method.
        Use this as parent class to define a struct which is usable
        in C and Python.
        """
        return _ScopedStructureBase(
            'ScopedStructure', (ctypes.Structure,), {'_state_': self})

    def _create_func(self, fname, restype, cargs, code):
        """
        Construct C function source.
        """
        PROTO = '%s %s(%s)'
        restype_c = TYPE_MAPPER[restype]
        cargs_c = ', '.join('%s %s' % (TYPE_MAPPER[ctype], name)
                            for name, ctype in cargs)
        proto = PROTO % (restype_c, fname, cargs_c or 'void')
        return proto + ';', proto + '\n{%s\n}' % code

    def c_function(self, restype, *argtypes):
        """
        Decorator for defining a C function.
        `restype` denotes the ctype of the return value,
        `argtypes` the ctypes of the arguments.
        Use the docstring for the actual code.
        """
        def wrap(f):
            def inner(*args, **kwargs):
                # TODO: apply args and kwargs appropriate to Python
                if not f._c_func:
                    f._c_func = f._c_func_proto()
                return f._c_func(*args)
            if PY3:
                name = f.__name__
                varnames = f.__code__.co_varnames
            else:
                name = f.func_name
                varnames = f.func_code.co_varnames
            cargs = zip(varnames, argtypes)
            f._c_decl, f._c_code = self._create_func(name, restype, cargs, f.__doc__)
            f._c_func_proto = lambda: self.state.get_symbol(name,
                                          ctypes.CFUNCTYPE(restype, *argtypes))
            f._c_func = None
            self.parts.append(f)
            return inner
        return wrap

    def c_method(self, restype, *argtypes, **ckwargs):
        """
        Decorator for declaring a C function with the first
        argument as pointer to the current ScopedStructure object.
        It is used to mimic method like behavior in C.
        The function is named as Classname_methodname, e.g.
        an instance method `Test.do_something(self, ...)` in Python
        translates to `Test_do_something(struct Test *self, ...)` in C.
        """
        def wrap(f):
            def inner(self, *args, **kwargs):
                # TODO: apply args and kwargs appropriate to Python
                if not f._c_func:
                    f._c_func = f._c_func_proto()
                return f._c_func(self, *args)

            def proto(pointer, clsname):
                if PY3:
                    name = f.__name__
                    varnames = f.__code__.co_varnames
                else:
                    name = f.func_name
                    varnames = f.func_code.co_varnames
                args = [pointer] + list(argtypes)
                cargs = zip(varnames, args)
                fname = clsname + '_' + name
                decl, code = self._create_func(fname, restype, cargs, f.__doc__)
                f._c_decl = decl
                f._c_code = code
                self.parts.append(f)
                f._c_func_proto = lambda: self.state.get_symbol(fname,
                                              ctypes.CFUNCTYPE(restype, *args))
                f._c_func = None

            inner._cmethod = True
            inner._proto = proto
            return inner
        return wrap

    def callable_function(self, restype, *argtypes):
        """
        Decorator to make a Python function callable from C.
        """
        def wrap(f):
            f._c_code = ''
            name = f.__name__ if PY3 else f.func_name
            cargs_c = ', '.join('%s' % TYPE_MAPPER[ctype] for ctype in argtypes)
            f._c_decl = '%s (*%s)(%s);' % (TYPE_MAPPER[restype], name, cargs_c or 'void')
            self.symbols.append((name, ctypes.CFUNCTYPE(restype, *argtypes)(f)))
            self.parts.append(f)
            return f
        return wrap

    def callable_method(self, restype, *argtypes, **ckwargs):
        """
        Decorator to make a ScopedStruture method callable from C.
        Follows the naming convention of the c_method decorator in C.
        """
        def wrap(f):
            def inner(self, *args, **kwargs):
                return f(self.contents, *args, **kwargs)

            def proto(pointer, clsname):
                name = f.__name__ if PY3 else f.func_name
                args = tuple([pointer] + list(argtypes))
                fname = clsname + '_' + name
                f._c_code = ''
                cargs_c = ', '.join('%s' % TYPE_MAPPER[ctype] for ctype in args)
                f._c_decl = '%s (*%s)(%s);' % (TYPE_MAPPER[restype], fname, cargs_c or 'void')
                self.symbols.append((fname, ctypes.CFUNCTYPE(restype, *args)(inner)))
                self.parts.append(f)

            f._cmethod = True
            f._proto = proto
            return f
        return wrap


class TccState(object):
    """
    Base class for compile states.
    Handles the low level stuff to work with tcc.
    """
    def __init__(self, tcc, libpath, encoding):
        self.tcc = tcc
        self.encoding = encoding
        self.ctx = self.tcc.lib.tcc_new()
        self.tcc.states.append(self.ctx)
        self._set_tcc_path(libpath)
        self.tcc.lib.tcc_set_error_func(self.ctx, 0, self._error())
        self.output = 0
        self.tcc_path = libpath
        self.options = []
        self.defines = {}
        self.include_paths = []
        self.libraries = []
        self.link_paths = []
        self.files = []
        self._compiled = False

    def _encode(self, value):
        if isinstance(value, unicode):
            return value.encode(self.encoding)
        return value

    def _set_output(self, output):
        self.tcc.lib.tcc_set_output_type(self.ctx, output)
        self.output = output

    def _error(self):
        def cb(_, msg):
            # TODO: better error msg handling
            print(msg)
        self._error_function = ERROR_FUNC(cb)
        return self._error_function

    def _set_tcc_path(self, path):
        self.tcc_path = path
        self.tcc.lib.tcc_set_lib_path(self.ctx, self._encode(self.tcc_path))

    def add_option(self, option):
        """
        Add a commandline option to the state.
        """
        self.options.append(option)
        self.tcc.lib.tcc_set_options(self.ctx, self._encode(option))

    def define(self, symbol, value=None):
        """
        Define preprocessor `symbol` with optional `value`.
        """
        self.defines[symbol] = None
        self.tcc.lib.tcc_define_symbol(self.ctx, symbol, self._encode(value))

    def undefine(self, symbol):
        """
        Undefine preprocessor `symbol`.
        """
        try:
            del self.defines[symbol]
        except KeyError:
            raise TccException(b'define' + symbol + b'not set')
        self.tcc.lib.tcc_undefine_symbol(self.ctx, self._encode(symbol))

    def add_include_path(self, path):
        """
        Add an include path (equivalent to -Ipath).
        """
        self.include_paths.append(path)
        self.tcc.lib.tcc_add_include_path(self.ctx, self._encode(path))

    def add_library(self, name):
        """
        Add a library. `name` is the same as the argument of the '-l' option.
        """
        self.libraries.append(name)
        self.tcc.lib.tcc_add_library(self.ctx, self._encode(name))

    def add_link_path(self, path):
        """
        Add a linker path (equivalent to -Lpath).
        """
        self.link_paths.append(path)
        self.tcc.lib.tcc_add_library_path(self.ctx, self._encode(path))
    
    def add_file(self, path):
        """
        Add a file ressource to the compile state.
        """
        if self.tcc.lib.tcc_add_file(self.ctx, self._encode(path)) == -1:
            raise TccException('error adding file')

    def _add_symbol(self, symbol, value):
        """
        Add a `symbol` with `value` to the compiler state.
        `value` must be a pointer type to the actual value.

        Use this with caution as it is likely to fail on some
        architectures (ARM at least).

        To avoid problems during compilation with imported
        Python symbols better use the `set_symbol` method.
        """
        if self.tcc.lib.tcc_add_symbol(self.ctx, self._encode(symbol), value) == -1:
            raise TccException('error while adding symbol')

    def compile(self, source):
        """
        Compile the sourcecode in `source`.
        """
        if self.tcc.lib.tcc_compile_string(self.ctx, self._encode(source)) == -1:
            raise TccException('compile error')
        self._compiled = True


class TccStateFile(TccState):
    """
    Compile state for file output. Used for 'exe', 'dll' and 'obj' states.
    """
    def __init__(self, tcc, libpath, output, encoding='UTF-8'):
        TccState.__init__(self, tcc, libpath, encoding)
        self._set_output(OUTPUT_TYPES[output])

    def write_file(self, filename):
        """
        Link and write to `filename`.
        """
        if self.tcc.lib.tcc_output_file(self.ctx, self._encode(filename)) == -1:
            raise TccException('error while linking/writing file')


class TccStateMemory(TccState):
    """
    Compile state for in memory builds.
    Use this state to compile and load c code into the current process.
    After compilation the symbols are accessible via `get_symbol`.
    """
    def __init__(self, tcc, libpath, encoding='UTF-8'):
        TccState.__init__(self, tcc, libpath, encoding)
        self._set_output(OUTPUT_TYPES['memory'])
        self._relocated = False

    def relocate(self):
        """
        Relocate symbols for further usage. Must be done after
        compiling the source before accessing the symbols with `get_symbol`.
        """
        # NOTE: only TCC_RELOCATE_AUTO is supported
        if not self._compiled:
            raise TccException('need to compile first')
        if self._relocated:
            raise TccException('already relocated')
        if self.tcc.lib.tcc_relocate(self.ctx, 1) == -1:
            raise TccException('relocate error')
        self._relocated = True

    def _get_address(self, symbol):
        if not self._compiled:
            raise TccException('need to compile/relocate first')
        if not self._relocated:
            raise TccException('need to relocate first')
        address = self.tcc.lib.tcc_get_symbol(self.ctx, self._encode(symbol))
        if not address:
            raise TccException('symbol not found')
        return address

    def get_symbol(self, symbol, ctype):
        """
        Resolve a symbol at runtime and attach to type `ctype`.
        """
        if issubclass(ctype, ctypes._CFuncPtr):
            return ctype(self._get_address(symbol))
        if issubclass(ctype, (ctypes._SimpleCData, ctypes.Structure,
                              ctypes.Union, ctypes._Pointer, ctypes.Array)):
            return ctype.from_address(self._get_address(symbol))
        raise TccException('cannot handle type information')

    def set_symbol(self, symbol, value):
        """
        Set a symbol to `value` at runtime.
        This is more reliable on different architectures than
        injecting symbols directly by the `_add_symbol` method.

        Unlike `_add_symbol` this method injects a value
        after compilation. Therefore the symbol must be declared in C.

        Example for importing a Python function to C:
            - create a Python function
              def test(a, b):
                  return a + b
            - declare the function in C as a function pointer, eg.
              `int (*test)(int, int);`
            - compile and relocate
            - create a C function type of the Python function
              cfunc = CFUNCTYPE(c_int, c_int, c_int)(test)
            - set the function pointer
              set_function('test', cfunc)
        """
        ctypes.pointer(
            type(value).from_address(self._get_address(symbol))
        )[0] = value


class TccStateRun(TccState):
    """
    Compile state for direct running of the code.
    Calling `run` will enter the main function of the code.
    """
    def __init__(self, tcc, libpath, encoding='UTF-8'):
        TccState.__init__(self, tcc, libpath, encoding)
        self._set_output(OUTPUT_TYPES['memory'])
        self._relocated = False
        self._run = False

    def run(self, arguments):
        """
        Call the main function of the compiled code with `arguments`.
        """
        if not self._compiled:
            raise TccException('not compiled')
        if self._run:
            raise TccException('can only run once')
        argc = len(arguments)
        argv = (ctypes.POINTER(ctypes.c_char) * argc)()
        argv[:] = [ctypes.create_string_buffer(self._encode(s)) for s in arguments]
        return self.tcc.lib.tcc_run(self.ctx, argc, argv)


class TinyCC(object):
    """
    Class for the TCC environment initialization.
    With the optional arguments `shared_library` and `tccpath` the used
    tcc can be customized. By default they point to the libtcc and tcc folder
    in the tinycc package.

    Call `create_state` for a compile state to work with.

    example for run state:
    >>> state = TinyCC().create_state('run')
    >>> c_code = '''#include <stdio.h>\nvoid main(void){printf("Hello World!");}'''
    >>> state.compile(c_code)
    >>> state.run([])

    example for memory state:
    >>> state = TinyCC().create_state()  # defaults to 'memory'
    >>> c_code = '''#include <stdio.h>\nvoid main(void){printf("Hello World!");}'''
    >>> state.compile(c_code)
    >>> state.relocate()
    >>> main = state.get_symbol('main', ctypes.CFUNCTYPE(None))
    >>> main()
    >>> main()  # unlike in run state main can be called multiple times

    example to write an executable:
    >>> state = TinyCC().create_state('exe')
    >>> c_code = '''#include <stdio.h>\nvoid main(void){printf("Hello World!");}'''
    >>> state.compile(c_code)
    >>> state.write_file('./hello')
    """
    instance = None

    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            cls.instance = object.__new__(cls)
        return cls.instance

    def __init__(self, shared_library=TCCLIB, tccpath=TCCPATH, encoding='UTF-8'):
        self.lib = ctypes.CDLL(shared_library)
        self.libpath = tccpath
        self.lib.tcc_get_symbol.restype = ctypes.c_int
        self.states = []
        self.encoding = encoding

    def create_state(self, output_type='memory', encoding=None):
        """
        Convenient method to create a compile state.
        `output_type` supports the following values:
            'memory' -  default, memory build for loading into the current process
                        with support for inspecting exported symbols
            'run'    -  memory build for direct calling of the main function
                        (no further symbol inspection possible)
            'obj'    -  state for writing an object file
            'exe'    -  state for writing an executable
            'dll'    -  state for writing a shared library
        """
        if not encoding:
            encoding = self.encoding
        if output_type == 'memory':
            state = TccStateMemory(self, self.libpath, encoding=encoding)
        elif output_type == 'run':
            state = TccStateRun(self, self.libpath, encoding=encoding)
        else:
            state = TccStateFile(self, self.libpath, output_type, encoding=encoding)
        return state

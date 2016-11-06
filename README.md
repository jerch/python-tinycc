# python-tinycc

Module to use the Tiny C Compiler for inline C in Python.
Tested with Ubuntu 14 (x86_64), WinXP (x86) and Raspbian (Raspberry Pi 3, ARMv7).


### Get the Tiny C Compiler

#### Linux
Run the following commands:
```bash
cd <modulepath>
git clone git://repo.or.cz/tinycc.git
mkdir build
cd build
../tinycc/configure --prefix=../linux --with-libgcc --disable-static
make all
make install
```

#### Windows

For Windows the repo contains a binary version (x86 only).
It was build from source with MinGW:
```bash
cd <modulepath>
git clone git://repo.or.cz/tinycc.git
mkdir build
cd build
../tinycc/configure --prefix=../win32 --disable-static --extra-ldflags=-static-libgcc
make all
make install
```

### Examples
A simple example with the 'run' state:
```python
>>> from tinycc import TinyCC
>>> c_code = '#include <stdio.h>'
>>> c_code += 'void main(void) {'
>>> c_code += '    printf("Hello World!\n");'
>>> c_code += '}'
>>> state = TinyCC().create_state('run')
>>> state.compile(c_code)
>>> state.run([])
```

Example with inline code:
```python
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
455
```
See the example files for more usage ideas.

### TODO
* Testing
* Python 3 support
* PyPI package
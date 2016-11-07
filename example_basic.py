# Example to show basic usage.
# The first version calls the main function with the run state
# while the second version does the same with the memory state
# by symbol resolution with some additional access tests.
# A third version (commented out) shows how to write an executable.

from tinycc import TinyCC
from ctypes import (CFUNCTYPE, c_int, c_void_p, Structure, c_ubyte,
                    POINTER, c_char, create_string_buffer, cast)

C_CODE = '''
#include <stdio.h>

/* a struct with some bytes and a length */
typedef struct Test {
    int length;
    unsigned char *bytes;
} Test;

/* some globals */

#ifdef STANDALONE
Test test = {10, "standalone"};
#else
Test test = {26, "abcdefghijklmnopqrstuvwxyz"};
#endif

int value = 12345;

int main(int argc, char **argv) {
    int i;
    char **pos = argv;

    printf("Hello Python world from C!\n");

    /* list arguments */
    for (i=0; i<argc; ++i, ++pos) {
        printf("arg %d: %s\n", i, *pos);
    }

    /* byte printing the hard way ;) */
    printf("test.value: '");
    for (i=0; i<test.length; ++i)
        printf("%c", *(test.bytes+i));
    printf("'");


    if (*test.bytes == 'a')
        printf(" - not so impressive.\n");
    else if (*test.bytes == 's')
        printf(" - ok.\n");
    else
        printf(" - Busted!\n");
    return 0;
}
'''


# reassemble struct Test
class Test(Structure):
    _fields_ = [('length', c_int),
                ('_bytes', c_void_p)]

    @property
    def bytes(self):
        return bytearray((c_ubyte * self.length).from_address(self._bytes))

    @bytes.setter
    def bytes(self, bytes):
        self._saved_ref = (c_ubyte * len(bytes))()
        self._saved_ref[:] = bytes
        self._bytes = cast(self._saved_ref, c_void_p)
        self.length = len(bytes)


if __name__ == '__main__':
    tcc = TinyCC()

    # 1st version - simple direct run of main function
    print 'simple "run" state:'
    state = tcc.create_state('run')
    state.compile(C_CODE)
    result = state.run(['stuff', 'from', 'the', 'cmdline'])
    print 'result:', result

    print

    # 2nd version - more complex run via symbols
    print '"memory" state with symbol access:'
    state = tcc.create_state() # defaults to 'memory'
    state.compile(C_CODE)
    state.relocate()

    # resolve symbols
    main = state.get_symbol('main', CFUNCTYPE(c_int, c_int, c_void_p))
    test = state.get_symbol('test', Test)
    value = state.get_symbol('value', c_int)

    # alter test.bytes
    test.bytes = bytearray('Python was here...')

    # prepare main arguments
    arguments = ['this', 'is', 'more', 'interactive...']
    argc = len(arguments)
    argv = (POINTER(c_char) * argc)()
    argv[:] = [create_string_buffer(s) for s in arguments]

    # call main
    result = main(argc, argv)
    print 'result:', result

    # read exported globals
    print 'global "test.bytes"', repr(test.bytes)
    print 'global "value":', repr(value)

    # 3rd version - write an executable
    #state = tcc.create_state('exe')
    #state.define('STANDALONE')
    #state.compile(C_CODE)
    #state.write_file('hello_world')

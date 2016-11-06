from tinycc import TinyCC, InlineGenerator
from ctypes import c_int, POINTER, cast, CFUNCTYPE, Structure, c_int64, addressof, c_void_p, c_long, byref, _CFuncPtr
import ctypes

gen = InlineGenerator()
gen.add_topdeclaration('#include <stdio.h>')
gen.add_definition('''

volatile int aaa;
volatile int * husten;

int (*volatile bbb)(int, int);
int (*volatile xxx)(int, int);
int arr[5];
''')

@gen.c_function(c_int64)
def ccc():
    """
    printf("aaa: %d %p\n", aaa, &aaa);
    printf("addresses bbb/ppp: %p %p\n", &bbb, &ppp);
    bbb(1,200);
    xxx(567,789);
    return ppp();
    """

@gen.callable_function(c_int)
def ppp():
    print 'ppp'
    return 12345

def bbb(a, b):
    print 'bbb', a ,b


#gen.add_definition('int (*ppp)(void) = (int (*)(void)) %s;' % hex(cast(CFUNCTYPE(c_int)(ppp), c_void_p).value))
gen.add_definition('int (*volatile bbb)(int, int) = (int (*)(int, int)) %s;' % hex(cast(CFUNCTYPE(None, c_int, c_int)(bbb), c_void_p).value))
gen.add_definition('int (*volatile xxx)(int, int) = (int (*)(int, int)) %s;' % hex(cast(CFUNCTYPE(None, c_int, c_int)(bbb), c_void_p).value))


from itertools import imap
print '\n'.join(imap(lambda l, s: '%s: %s' % (l, s), range(1, 300), gen.code.split('\n')))
print gen.parts
print gen.symbols
cs = TinyCC().create_state()
#gen.bind_state(cs)

cs.compile(gen.code)

cs.relocate()
gen.bind_state(cs)

#print cs._get_address('ppp'), c_void_p.from_address(cs._get_address('ppp')), c_void_p.from_address(cs._get_address('aaa'))
#cs.get_symbol('ppp', c_void_p).value = cast(CFUNCTYPE(c_int)(ppp), c_void_p).value

#CFUNCTYPE(c_int).from_address(cs._get_address('ppp'))


#cs.set_function('ppp', CFUNCTYPE(c_int)(ppp))

print cs.get_symbol('aaa', c_int)

#cs.set_symbol('ppp', CFUNCTYPE(c_int)(ppp))
cs.set_symbol('aaa', c_int(7878))

print 'a', cs.get_symbol('aaa', c_int)
print 'a', cs.get_symbol('aaa', c_int)
#print cs.get_symbol('husten', POINTER(c_int)).contents

p = POINTER(c_int)(c_int(99999))
cs.set_symbol('husten', p)
print 'husten', cs.get_symbol('husten', POINTER(c_int)).contents
print 'husten', cs.get_symbol('husten', POINTER(c_int)).contents

print 'arr', cs.get_symbol('arr', c_int*5)
new_arr = (c_int*5)(*[1,2,3,4,5])
cs.set_symbol('arr', new_arr)
print 'arr', list(cs.get_symbol('arr', c_int*5))
print 'arr', list(cs.get_symbol('arr', c_int*5))

print cs.get_symbol('ccc', CFUNCTYPE(c_int))()

print ccc()
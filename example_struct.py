# Example to show inlining with a struct.
from __future__ import print_function

from tinycc import TinyCC, InlineGenerator
from ctypes import c_int, addressof, c_long

gen = InlineGenerator()
gen.add_topdeclaration('#include <stdio.h>')


class Test(gen.ScopedStructure):
    _fields_ = [('a', c_int,), ('b', c_int)]

    @gen.c_method(c_long)
    def get_address(self):
        """
        return (long) self;
        """

    @gen.c_method(c_int, c_int)
    def add_a(self, num):
        """
        printf("add_a:\n");
        self->a += num;
        return self->a;
        """

    @gen.c_method(c_int)
    def adder_c(self):
        """
        printf("Test.adder_c: %d + %d = %d\n",
               self->a, self->b, self->a + self->b);
        return self->a + self->b;
        """

    @gen.callable_method(c_int)
    def adder_py(self):
        print('Test.adder_py: %d + %d = %d' % (self.a, self.b, self.a+self.b))
        return self.a + self.b

    @gen.c_method(c_int)
    def call_methods_c(self):
        """
        Test_add_a(self, 100);
        return Test_adder_py(self);
        """


@gen.c_function(Test, c_int, c_int)
def struct_as_return(a, b):
    # Test as return type in C
    """
    return (struct Test) {a, b};
    """


if __name__ == '__main__':
    state = TinyCC().create_state()

    print(gen.code)

    state.compile(gen.code)
    state.relocate()

    gen.bind_state(state)

    # usage
    test = Test(1, 2)
    print('addresses equal:', addressof(test) == test.get_address())
    print(test.add_a(10))
    print(test.adder_c())
    print(test.adder_py())
    print(test.call_methods_c())

    # return struct: bug in TCC 0.9.26 zip release
    test2 = struct_as_return(23, 24)
    print(test2, test2.a, test2.b)

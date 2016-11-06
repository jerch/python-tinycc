# Example to show basic inlining with the function decorators
# of InlineGenerator.
#
# Use `c_function` to declare a C function. The function is
# callable from Python.
# Use `callable_function` to import a Python function into the
# C namespace.
#
# NOTE: For trivial tasks the overhead of the ctype conversions
#       will let the C code run slower than a CPython equivalent.

from tinycc import TinyCC, InlineGenerator
from ctypes import c_int

# create a generator object first
gen = InlineGenerator()


# do the inline definitions with the provided decorators

@gen.callable_function(c_int, c_int)
def r_fib_py(n):
    if n <= 2:
        return 1
    return r_fib_py(n-1) + r_fib_py(n-2)


@gen.c_function(c_int, c_int)
def r_fib_c(n):
    """
    if (n <= 2)
        return 1;
    return r_fib_c(n-1) + r_fib_c(n-2);
    """


@gen.callable_function(c_int, c_int)
def l_fib_py(a):
    result = 0
    if a <= 2:
        return 1
    last = next_to_last = 1
    for i in range(2, a):
        result = last + next_to_last
        next_to_last = last
        last = result
    return result


@gen.c_function(c_int, c_int)
def l_fib_c(a):
    """
    int last, next_to_last, result = 0;
    if(a <= 2)
        return 1;
    last = next_to_last = 1;
    for(int i=2; i<a; ++i) {
        result = last + next_to_last;
        next_to_last = last;
        last = result;
    }
    return result;
    """


@gen.c_function(c_int, c_int)
def c_runner_r(n):
    """
    int i, sum = 0;
    for (i=0; i<n; ++i) {
        sum += r_fib_py(20);
    }
    return sum;
    """


@gen.c_function(c_int, c_int)
def c_runner_l(n):
    """
    int i, sum = 0;
    for (i=0; i<n; ++i) {
        sum += l_fib_py(20);
    }
    return sum;
    """


def py_runner_r(n):
    sum = 0
    for _ in xrange(n):
        sum += r_fib_py(20)
    return sum


def py_runner_l(n):
    sum = 0
    for _ in xrange(n):
        sum += l_fib_py(20)
    return sum


@gen.c_function(c_int, c_int)
def c_runner_rc(n):
    """
    int i, sum = 0;
    for (i=0; i<n; ++i) {
        sum += r_fib_c(20);
    }
    return sum;
    """


@gen.c_function(c_int, c_int)
def c_runner_lc(n):
    """
    int i, sum = 0;
    for (i=0; i<n; ++i) {
        sum += l_fib_c(20);
    }
    return sum;
    """


def py_runner_rc(n):
    sum = 0
    for _ in xrange(n):
        sum += r_fib_c(20)
    return sum


def py_runner_lc(n):
    sum = 0
    for _ in xrange(n):
        sum += l_fib_c(20)
    return sum


if __name__ == '__main__':
    state = TinyCC().create_state()

    # compile the generated code
    state.compile(gen.code)
    state.relocate()

    # bind state to the generator object
    # needed to resolve symbols from and to C
    gen.bind_state(state)

    # ready to use

    assert(r_fib_py(20) == r_fib_c(20))
    assert(l_fib_py(20) == l_fib_c(20))
    assert (r_fib_c(20) == l_fib_c(20))

    from timeit import timeit
    py = timeit('r_fib_py(20)', setup='from __main__ import r_fib_py', number=100)
    c = timeit('r_fib_c(20)', setup='from __main__ import r_fib_c', number=100)
    print 'recursive Python/C:', py, c, float(py) / c

    py = timeit('l_fib_py(20)', setup='from __main__ import l_fib_py', number=100)
    c = timeit('l_fib_c(20)', setup='from __main__ import l_fib_c', number=100)
    print 'looped Python/C:', py, c, float(py) / c

    # some call tests Python <--> C
    print 'workload - sum(100x fib(20)):'
    assert(c_runner_l(100) == py_runner_l(100))
    assert(c_runner_l(100) == py_runner_r(100))
    assert(c_runner_l(100) == c_runner_rc(100))
    assert(c_runner_l(100) == c_runner_lc(100))
    assert(c_runner_l(100) == py_runner_rc(100))
    assert(c_runner_l(100) == py_runner_lc(100))

    assert(c_runner_r(100) == c_runner_l(100))
    r = timeit('c_runner_r(100)', setup='from __main__ import c_runner_r', number=1)
    l = timeit('c_runner_l(100)', setup='from __main__ import c_runner_l', number=1)
    print 'fib_py from C (rec/loop):', r, l, float(r) / l

    assert(py_runner_r(100) == py_runner_l(100))
    r = timeit('py_runner_r(100)', setup='from __main__ import py_runner_r', number=1)
    l = timeit('py_runner_l(100)', setup='from __main__ import py_runner_l', number=1)
    print 'fib_py from Py (rec/loop):', r, l, float(r) / l

    assert(c_runner_rc(100) == c_runner_lc(100))
    r = timeit('c_runner_rc(100)', setup='from __main__ import c_runner_rc', number=1)
    l = timeit('c_runner_lc(100)', setup='from __main__ import c_runner_lc', number=1)
    print 'fib_c from C (rec/loop):', r, l, float(r) / l

    assert(py_runner_rc(100) == py_runner_lc(100))
    r = timeit('py_runner_rc(100)', setup='from __main__ import py_runner_rc', number=1)
    l = timeit('py_runner_lc(100)', setup='from __main__ import py_runner_lc', number=1)
    print 'fib_c from Py (rec/loop):', r, l, float(r) / l
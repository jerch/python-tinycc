# Basic example with loading of a foreign library
# and a callback invocation.
# NOTE: For Windows the package contains a binary version
# of the SDL2 library. 
from __future__ import print_function

from tinycc import TinyCC
from ctypes import CFUNCTYPE, c_int, c_void_p, CDLL
import sys


C_CODE = '''
#include <stdio.h>
#define SDL_DISABLE_IMMINTRIN_H
#include <SDL2/SDL.h>

/* callback definition */
typedef void (*Callback)(int, int, int);
static Callback callback = NULL;

void set_callback(void (*cb)(int, int, int)) {
    callback = cb;
}

void run_sdl(int width, int height) {
    int i;
    SDL_Window* window = NULL;
    SDL_Surface* screenSurface = NULL;

    if(SDL_Init(SDL_INIT_VIDEO) < 0 ) {
        printf("SDL could not initialize! SDL_Error: %s\\n", SDL_GetError());
        return;
    }

    window = SDL_CreateWindow("SDL Example",
                              SDL_WINDOWPOS_UNDEFINED,
                              SDL_WINDOWPOS_UNDEFINED,
                              width, height,
                              SDL_WINDOW_SHOWN);
    if(!window) {
        printf("Window could not be created! SDL_Error: %s\\n", SDL_GetError());
        return;
    }

    screenSurface = SDL_GetWindowSurface(window);
    for (i=0; i<256; ++i) {
        SDL_FillRect(screenSurface, NULL,
                     SDL_MapRGB(screenSurface->format, i, i, i));
        SDL_UpdateWindowSurface(window);
        /* invoke python callback */
        if (callback)
            callback(i, i, i);
        SDL_Delay(5);
    }

    SDL_FreeSurface(screenSurface);
    SDL_DestroyWindow(window);
    SDL_Quit();
}
'''


# callback called from C
@CFUNCTYPE(None, c_int, c_int, c_int)
def get_color(r, g, b):
    print('color is rgb(%d, %d, %d)' % (r, g, b))


if __name__ == '__main__':
    tcc = TinyCC()
    state = tcc.create_state()

    # link additional libraries
    # depending on your system TCC might need further settings
    # like additional linker paths to find the libraries
    # here: take the SDL2 header and library from the
    #       SDL2-win32 folder in Windows
    if sys.platform == 'win32':
        state.add_include_path('SDL2-win32\\include')
        state.add_link_path('SDL2-win32')
        # load library by hand
        # this is needed for 2 reasons:
        # - TCC's add_library loads only the .def files in Windows
        #   and leaves the actual DLL loading to Windows
        # - SDL2.dll is not in the common search paths of Windows
        #   therefore the autoloading will fail
        sdl = CDLL('SDL2-win32\SDL2.dll')
    state.add_library('SDL2')

    state.compile(C_CODE)
    state.relocate()

    # resolve symbols of interest
    set_callback = state.get_symbol('set_callback', CFUNCTYPE(None, c_void_p))
    run_sdl = state.get_symbol('run_sdl', CFUNCTYPE(None, c_int, c_int))

    # register callback
    set_callback(get_color)

    # call the C function
    run_sdl(640, 480)



#!/usr/bin/env python
from curses import wrapper
import argparse
import code
import curses
import itertools
import json
import os
import random
import sys

try:
    LINES, COLS = [int(d) for d in os.popen('stty size', 'r').read().split()]
except:
    LINES, COLS = 30,30
DEBUG = True

"""
spacetime generation
"""
def gen_mid_spacetime(w): 
    spacetime = [[0]*w]
    spacetime[0][w//2-1] = 1
    return spacetime

read_schemes_from_file = lambda fp: json.load(open(fp))

gen_space_combo = lambda w: list(itertools.product([0, 1], repeat=w))       # all possible configurations for w-wide space

"""
get rule transitions as an array indexed by neighbor configuration, like so:
# 111 110 101 100 011 010 001 000
#  y0  y1  y2  y3  y4  y5  y6  y7
"""
get_rule_transitions = lambda r: [int(y) for y in format(r,'#010b')[2:]]

"""
returns what rule should be applied for this combination of neighbors
"""
get_transition_ix = lambda ln,mn,rn: 7 - ((ln << 2) + (mn << 1) + rn)

get_neighbors = lambda x,space: [space[x-1], space[x], space[(x+1)%len(space)]]

def print_spacetime(spacetime, zero=0, one=1):
    for space in spacetime:
        [print(one if cell else zero, end='') for cell in space]
        print()

def render_image(spacetime, t, w, rule, ranks, measure_complexity=False):
    from PIL import Image
    im = Image.new('RGB', (w, t))
    pixels = []
    for iy,space in enumerate([list(space) for space in spacetime]):
        if measure_complexity:
            compl = (10*measure_complexity(space)) % 255
        for ix,cell in enumerate(space):
            pixels += [(0,0,0) if cell else (255-compl if measure_complexity else 255, (0 if measure_complexity else 255), (0 if measure_complexity else 255))]
    im.putdata(pixels)
    if ranks:
        ranks = '-' + ''.join([str(r) for r in ranks])
    im.save(f'{rule}-{w}x{t}{ranks}.png')

def run_sync(rule, t, w, init_space=None):
    """
    returns spacetime after executing the rule synchronously for t steps in a w-wide space
    """
    rule_transitions = get_rule_transitions(rule)
    space = init_space if init_space else list(gen_mid_spacetime(w)[0])
    yield space
    for _ in range(t):
        future_space = list(space)
        for ci in range(w):                             # iterate over the present space's cells
            ln,mn,rn = get_neighbors(ci, space)         # get neighborhood
            ix_transition = get_transition_ix(ln,mn,rn) # get transition ix
            y = rule_transitions[ix_transition]         # get next cell state
            future_space[ci] = y                        # update cell
        space = list(future_space)                      # update space
        yield future_space

def run_async(rule, t, w, ranks, init_space=None):
    rule_transitions = get_rule_transitions(rule)
    assert len(ranks) == 8
    space = init_space if init_space else list(gen_mid_spacetime(w)[0])
    yield space
    giotbr = grouped_indexes_of_transitions_by_rank = [[ix for ix,rank in enumerate(ranks) if rank == i] \
            for i in range(1,8)]
    for _ in range(t):
        future_space = list(space)
        for transition_indexes in giotbr:
            if transition_indexes:
                for ci in range(w):
                    ln,mn,rn = get_neighbors(ci, space)
                    ix = get_transition_ix(ln,mn,rn)
                    if ix in transition_indexes:
                        future_space[ci] = rule_transitions[ix]
            space = future_space
        yield future_space

def run_async(rule, t, w, ranks, init_space=None):
    rule_transitions = get_rule_transitions(rule)
    assert len(ranks) == 8
    space = init_space if init_space else list(gen_mid_spacetime(w)[0])
    yield space
    giotbr = grouped_indexes_of_transitions_by_rank = [[ix for ix,rank in enumerate(ranks) if rank == i] \
            for i in range(1,8)] 
    for _ in range(t):
        future_space = list(space)
        for transition_indexes in giotbr:
            if transition_indexes:
                for ci in range(w):
                    ln,mn,rn = get_neighbors(ci, space)
                    ix = get_transition_ix(ln,mn,rn)
                    if ix in transition_indexes:
                        future_space[ci] = rule_transitions[ix]
                space = future_space
        yield future_space

def is_spacetime_conservative(spacetime):
    # code.interact(local=globals().update(locals()) or globals())
    energy = next(spacetime).count(1)
    for space in spacetime:
        if space.count(1) != energy:
            return False
    return True

def is_rule_conservative(rule, t, w, ranks=None):
    init_spaces = gen_space_combo(w)
    ranks = ranks if ranks else [1]*8
    for init_space in init_spaces:
        final_spacetime = run_async(rule, t, w, ranks, init_space=init_space)
        if not is_spacetime_conservative(final_spacetime):
            return False
    return True

i=0
def create_anim(spacetime, t, w):
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    fig = plt.figure()
    fig.tight_layout()
    np_spacetime = np.array(list(spacetime)).reshape(t,w)
    im = plt.imshow(np_spacetime[0:100].reshape(100, w), cmap='binary')
    def updatefig(*args):
        global i
        i += 1
        im.set_data(np_spacetime[i:i+100])
        return im,
    ani = animation.FuncAnimation(fig, updatefig, interval=1, blit=False)
    plt.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)
    plt.gca().axes.get_yaxis().set_visible(False)
    plt.gca().axes.get_xaxis().set_visible(False)
    # ani.save('myAnimation.gif', writer='imagemagick', fps=30)
    plt.show()

def measure_complexity(space):
    import zlib
    return len(zlib.compress(bytes(space)))

stringify = lambda space: ' '.join([str(c) for c in space])

def interactive(stdscr,args):
    # code.interact(local=globals().update(locals()) or globals())
    # args.width = args.width//3 - 2
    curses.noecho()
    curses.cbreak()
    def syn(args):
        rule_transitions = get_rule_transitions(args.rule)
        space = gen_mid_spacetime(args.width)[0]
        spacetime = [space]
        for t in range(args.timesteps):
            future_space = list(spacetime[-1])
            for i in range(args.width):
                stdscr.erase()
                stdscr.border(0)
                for z,sp in enumerate(spacetime if t > curses.LINES-5 else spacetime[-curses.LINES+3:]):
                    space_str = stringify(sp)
                    stdscr.addstr(1+z, curses.COLS // 2 - len(space_str) // 2 - 1, space_str)
                    stdscr.addstr(2+z, curses.COLS // 2 - len(space_str) // 2 + i*2 - 1, "^")
                ln,mn,rn = get_neighbors(i, spacetime[-1])
                tr_ix = get_transition_ix(ln,mn,rn)
                future_space[i] = rule_transitions[tr_ix]
                future_space_str = stringify(future_space)
                stdscr.addstr(2+len(spacetime), curses.COLS // 2 - len(future_space_str) // 2 - 1, stringify(future_space[:i]))
                stdscr.addstr(2+len(spacetime), curses.COLS // 2 - len(future_space_str) // 2 + i*2 - 1, str(future_space[i]))
                stdscr.addstr(curses.LINES-4, 1, '111 110 101 100 011 010 001 000')
                stdscr.addstr(curses.LINES-3, 2, '   '.join([str(t) for t in rule_transitions]))
                stdscr.addstr(curses.LINES-2, 2+tr_ix*4, "^")
                stdscr.refresh()
                stdscr.getkey()
            spacetime += [future_space]
    def asyn(args):
        rule_transitions = get_rule_transitions(args.rule)
        space = args.initial_configuration if args.initial_configuration else gen_mid_spacetime(args.width)[0] 
        spacetime = [space]
        true_spacetime = [space]
        str_len = len(stringify(space))
        x_pole = 0
        for t in range(args.timesteps):
            future_space = list(spacetime[-1])
            giotbr = grouped_indexes_of_transitions_by_rank = [[tr_ix for tr_ix,rank in enumerate(args.scheme) if rank == i] \
                    for i in range(1,8)] 
            for pri,transition_indexes in enumerate(giotbr):
                micro_timestep = list(future_space)
                if transition_indexes:
                    for ci in range(args.width):
                        stdscr.erase()
                        stdscr.border(0)
                        for z,sp in enumerate(spacetime):
                            space_str = stringify(sp)
                            stdscr.addstr(1+z, x_pole + curses.COLS // 2 - len(space_str) // 2 - 1, space_str)
                            if z % sum([int(bool(g)) for g in giotbr]) == 0:
                                stdscr.addstr(1+z, x_pole + curses.COLS // 2 - len(space_str) // 2 - 4, f'-')
                        stdscr.addstr(1+len(spacetime), x_pole + curses.COLS // 2 - len(space_str) // 2 + ci*2 - 1, "^")
                        stdscr.addstr(2+len(spacetime), x_pole + curses.COLS // 2 - len(space_str) // 2 - 5, f'[{pri+1}]')
                        ln,mn,rn = get_neighbors(ci, future_space)
                        tr_ix = get_transition_ix(ln,mn,rn)
                        if tr_ix in transition_indexes:
                            micro_timestep[ci] = rule_transitions[tr_ix]
                            micro_str = stringify(micro_timestep)
                            stdscr.addstr(curses.LINES-5, 2+tr_ix*4, "V")
                        stdscr.addstr(2+len(spacetime), x_pole + curses.COLS // 2 - len(space_str) // 2 - 1, stringify(micro_timestep[:ci]))
                        stdscr.addstr(2+len(spacetime), x_pole + curses.COLS // 2 - len(space_str) // 2 + ci*2 - 1, str(micro_timestep[ci]))
                        # stdscr.addstr(curses.LINES-5, 2, '   '.join([str(p) for p in args.scheme]))
                        stdscr.addstr(curses.LINES-4, 2, '   '.join([str(p) for p in args.scheme]))
                        stdscr.addstr(curses.LINES-3, 1, '111 110 101 100 011 010 001 000')
                        stdscr.addstr(curses.LINES-2, 2, '   '.join([str(t) for t in rule_transitions]))
                        stdscr.refresh()
                        key = stdscr.getkey()
                        if key == 'KEY_LEFT':
                            x_pole -= 1
                        if key == 'KEY_RIGHT':
                            x_pole += 1
                    spacetime += [micro_timestep]
                true_spacetime += [spacetime[-1]]
    if args.scheme:
        asyn(args)
    else:
        syn(args)
    curses.nocbreak()
    curses.endwin()
    
def main(args):
    if args.initial_configuration:
        args.initial_configuration = [int(c) for c in args.initial_configuration]
        args.width = len(args.initial_configuration)
    if args.scheme:
        if all([str.isdigit(c) for c in args.scheme]):
            args.scheme = [int(c) for c in args.scheme]
        else:
            schemes = read_schemes_from_file(args.scheme)
    if args.interactive:
        stdscr = curses.initscr()
        wrapper(interactive, args)
    if args.scheme:
        spacetime = run_async(args.rule, args.timesteps - 1, args.width, scheme)
        spacetime = list(spacetime)
        if args.png_render:
            render_image(spacetime, args.timesteps, args.width, args.rule, scheme, measure_complexity=args.measure_complexity)
        if args.terminal_render:
            print_spacetime(spacetime, args.zero, args.one)
        if args.conservative_check:
            print('Is conservative:', is_spacetime_conservative(spacetime))
    elif schemes:
        schemes = read_schemes_from_file(args.scheme)
        for scheme in schemes:
            spacetime = run_async(args.rule, args.timesteps - 1, args.width, scheme)
            if args.png_render:
                render_image(spacetime, args.timesteps, args.width, args.rule, scheme, measure_complexity=args.measure_complexity)
            if args.terminal_render:
                print_spacetime(spacetime, args.zero, args.one)
            if args.conservative_check:
                print('Is conservative:', is_spacetime_conservative(spacetime))
    else:
        spacetime = run_sync(args.rule, args.timesteps - 1, args.width)
        spacetime = list(spacetime)
        if args.animation:
            create_anim(spacetime, args.timesteps, args.width)
        if args.terminal_render:
            print_spacetime(spacetime, args.zero, args.one)
        if args.png_render:
            render_image(spacetime, args.timesteps, args.width, args.rule, '', measure_complexity=args.measure_complexity)
        if args.conservative_check:
            print('Is conservative:', is_spacetime_conservative(spacetime))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='aeca', description='Asynchronous Elementary Cellular Automata')
    parser.add_argument('-s', '--scheme',               default=None,   metavar='ASYNCHRONOUS-SCHEME', help='async scheme to run (p0,p1,p2,p3,p4,p5,p6,p7) for pn in [1,7]')
    parser.add_argument('-r', '--rule',                 default=30,     metavar='RULE-ID',             help='rule in the Wolfram classification scheme', type=int)
    parser.add_argument('-t', '--timesteps',            default=LINES,  metavar='TIMESTEPS',           help='timesteps to run', type=int)
    parser.add_argument('-w', '--width',                default=COLS,   metavar='WIDTH',               help='space width', type=int)
    parser.add_argument('-0', '--zero',                 default='0',    metavar='CHAR',                help='replace zeroes by CHAR')
    parser.add_argument('-1', '--one',                  default='1',    metavar='CHAR',                help='replace ones by CHAR')
    parser.add_argument('-c', '--conservative-check',   action='store_true',                           help='show whether automata generated are conservative')
    parser.add_argument('-o', '--terminal-render',      action='store_true',                           help='render in terminal')
    parser.add_argument('-O', '--png-render',           action='store_true',                           help='render to file')
    parser.add_argument('-a', '--animation',            action='store_true',                           help='render animation')
    parser.add_argument('-m', '--measure-complexity',   action='store_true',                           help='measure complexity')
    parser.add_argument('-i', '--interactive',          action='store_true',                           help='interactive mode')
    parser.add_argument('-I', '--initial-configuration',metavar='CONFIG',                              help='use CONFIG as initial configuration')
    args = parser.parse_args()
    main(args)

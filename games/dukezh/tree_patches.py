"""Build patches for the decomp tree on Windows (Git Bash + ezwinports make). usage: python -m games.dukezh.tree_patches <tree>"""
import sys

PATCHES = {
    'Makefile': [
        # make must use sh, and the escaped quotes of -D__FILE__ get mangled: the cpp shim adds them
        ('### Build Options ###\n', '### Build Options ###\nSHELL := sh\n'),
        ('-D__FILE__=\\"$(notdir $<)\\"', '-D__FILE__=$(notdir $<)'),
    ],
}
# clean tree only: there is no base ROM in the clean room
CLEAN = {
    'Makefile': [
        ("$(error Baserom `$(BASEROM)' not found.)", ''),
        ('COMPARE      ?= 1', 'COMPARE      ?= 0'),
    ],
}


def apply(tree, clean=False):
    n = 0
    for rel, subs in PATCHES.items():
        subs = subs + (CLEAN.get(rel, []) if clean else [])
        p = '%s/%s' % (tree, rel)
        s = open(p, encoding='utf-8', newline='').read()
        for a, b in subs:
            if b and b in s:
                continue
            if a not in s:
                print('MISSING', rel, a[:50])
                continue
            s = s.replace(a, b, 1)
            n += 1
        open(p, 'w', encoding='utf-8', newline='').write(s)
    print('tree patches applied:', n)


if __name__ == '__main__':
    apply(sys.argv[1], '--clean' in sys.argv)

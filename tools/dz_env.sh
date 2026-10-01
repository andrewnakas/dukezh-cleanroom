# source me: KMC gcc 2.7.2 (Windows build from the snowboardkids session) + mips cross shims
TC=/d/n64work/dukezh/tc
export PATH="$TC/cross:$HOME/bin:$PATH"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
export KMC_TMP=D:/n64work/dukezh/tc/ktmp TMPDIR=D:/n64work/dukezh/tc/ktmp TEMP=D:/n64work/dukezh/tc/ktmp TMP=D:/n64work/dukezh/tc/ktmp
# install_kmc <tree>: put the KMC toolchain where the decomp Makefile expects it (DETECTED_OS=windows)
install_kmc() { mkdir -p "$1/tools/gcc_2.7.2/windows"; cp -f $TC/kmc/* "$1/tools/gcc_2.7.2/windows/"; cp -f $TC/kmc/as.exe "$1/tools/gcc_2.7.2/windows/as"; }
# make with retries (Windows AV/file locks make parallel steps fail randomly)
mk() { for i in 1 2 3 4 5 6; do find build -size 0 -type f -delete 2>/dev/null; make CHECK=0 "$@" && return 0; echo "== make retry $i"; done; return 1; }

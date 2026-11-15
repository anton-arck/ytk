import sys, os, time, importlib.util
spec=importlib.util.spec_from_file_location("ytk","/home/anton/claude-projects/yt-kitty/ytk.py"); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
png=open(os.path.expanduser("~/.cache/ytk/aqz-KE-bpKQ.png"),"rb").read()
variant=sys.argv[1]
sys.stdout.write("\x1b[?1049h\x1b[2J")
m.gfx_transmit(1, png)
if variant=="del": sys.stdout.write("\x1b_Ga=d,d=a,q=2\x1b\\")
sys.stdout.write("\x1b[3;5H"); m.gfx_place(1, 30, 9)
sys.stdout.write("\x1b[14;5Hvariante "+variant)
sys.stdout.flush(); time.sleep(5)
sys.stdout.write("\x1b[?1049l")

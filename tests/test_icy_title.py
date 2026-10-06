"""Build 148: station song titles with an apostrophe ("Don't", "Let's") are read in full from
the raw ICY block (StreamTitle.icyTitle), not cut off at the apostrophe.
Run: python3 tests/test_icy_title.py (compiles StreamTitle.java with javac and runs the checks)"""
import os, subprocess, tempfile, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(HERE, '..', 'android', 'app', 'src', 'main', 'java', 'com', 'markcoleman', 'amplify', 'StreamTitle.java')
d = tempfile.mkdtemp()
try:
    subprocess.run(['javac', '-nowarn', '-d', d, src, os.path.join(HERE, 'java', 'IcyTitleTest.java')], check=True)
    out = subprocess.run(['java', '-cp', d, 'IcyTitleTest'], capture_output=True, text=True).stdout
    print(out)
    sys.exit(0 if 'ALL PASSED' in out else 1)
finally:
    shutil.rmtree(d)

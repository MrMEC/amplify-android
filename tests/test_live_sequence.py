"""Build 650: a channel's movies come up all day. Pulls liveChSequence out of www/index.html and runs it in node:
3 shows with hundreds of episodes + 5 movies must have a movie in every 12 hours of the schedule, and a lone list is unchanged.
Run: python3 tests/test_live_sequence.py"""
import re, subprocess, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
h = open(os.path.join(HERE, '..', 'www', 'index.html')).read()
a = h.index('  var LIVE_CH_EXTRA_GAP'); b = h.index('  // A channel\'s videos in order', a)
js = h[a:b] + """
function eps(n, tag){ var o = []; for(var i = 0; i < n; i++) o.push({ id: tag + i, slot: 22 }); return o; }
var shows = [eps(300, 'a'), eps(250, 'b'), eps(40, 'c')], mv = [0, 1, 2, 3, 4].map(function(i){ return { id: 'm' + i, slot: 100 }; });
var out = liveChSequence(shows, mv);
var t = 0, starts = []; out.forEach(function(v, i){ if(/^m/.test(v.id)) starts.push(t); t += v.slot; });
var gaps = []; for(var i = 1; i < starts.length; i++) gaps.push(starts[i] - starts[i - 1]);
var firstMovies = starts.slice(0, 3);
console.log(JSON.stringify({ n: out.length, movies: starts.length, maxGapMin: Math.max.apply(null, gaps), first: firstMovies, only: liveChSequence([eps(3, 'z')], []).length, noShows: liveChSequence([], mv).length, fewEps: liveChSequence([eps(3, 'q')], mv).length }));
"""
r = json.loads(subprocess.check_output(['node', '-e', js]).decode())
print(r)
ok = r['maxGapMin'] <= 8 * 22 + 100 + 22 * 3 and r['movies'] >= 60 and r['only'] == 3 and r['noShows'] == 5 and r['fewEps'] == 8
print('PASS' if ok else 'FAIL', 'movie at least every', r['maxGapMin'] / 60.0, 'hours')

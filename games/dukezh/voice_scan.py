"""DIRTY ROOM: find the speech samples and their words. usage: python -m games.dukezh.voice_scan <dirty tree> <out.json>

Decodes each unlooped sample of 0.4-9 s and asks Whisper (stock model, nothing trained here) for the words. Only the
words, confidence and assumed rate are written; they become the text facts in games/dukezh/voice_lines.json.
"""
import json
import os
import sys

import numpy as np

from cleanroom.audio import vadpcm
from games.dukezh import sounds


def main(tree, out):
    from faster_whisper import WhisperModel
    from scipy.signal import resample_poly
    model = WhisperModel('small.en', device='cpu', compute_type='int8', cpu_threads=4)
    spec = json.load(open(os.path.join(os.path.dirname(__file__), 'spec/sounds.json')))
    res = {}
    for bank in spec:
        d = os.path.join(tree, 'assets/us/sounds')
        ptr, wbk = open(os.path.join(d, bank + '.ptr.bin'), 'rb').read(), open(os.path.join(d, bank + '.wbk.bin'), 'rb').read()
        for n, w in enumerate(sounds.waves(ptr)):
            frames = w['len'] // 9 * 16
            if w['loop'] or not 0.4 * 22050 <= frames <= 9 * 22050:
                continue
            pcm = vadpcm.decode(wbk[w['base']:w['base'] + w['len']], sounds._book(ptr, w['book']), frames)
            x = (np.asarray(pcm, np.float32) / 32768)
            best = None
            for rate, (up, dn) in ((22050, (320, 441)), (11025, (640, 441))):
                segs, _ = model.transcribe(resample_poly(x, up, dn).astype(np.float32), language='en', beam_size=1,
                                           condition_on_previous_text=False)
                segs = list(segs)
                if not segs:
                    continue
                lp = float(np.mean([s.avg_logprob for s in segs]))
                ns = float(np.mean([s.no_speech_prob for s in segs]))
                text = ' '.join(s.text.strip() for s in segs)
                if best is None or lp > best['lp']:
                    best = {'text': text, 'lp': round(lp, 2), 'ns': round(ns, 2), 'rate': rate, 'frames': frames}
            if best:
                res['%s/%d' % (bank, n)] = best
        print(bank, len(res), flush=True)
        json.dump(res, open(out, 'w'), indent=0)


if __name__ == '__main__':
    main(*sys.argv[1:3])

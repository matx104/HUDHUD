// A question said aloud, recorded in the browser as 16 kHz mono 16-bit WAV: what Azure AI Speech's
// short-audio speech to text takes (court/speech.py). Shared by the studio and the Ask page. The
// audio goes to the studio once and is kept nowhere.
(function (root) {
  const RATE = 16000;

  // Start recording; resolves to a recording whose finish() stops it and gives the WAV.
  async function start() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    const context = new AudioContext({ sampleRate: RATE });
    const source = context.createMediaStreamSource(stream);
    const tap = context.createScriptProcessor(4096, 1, 1);
    const chunks = [];
    tap.onaudioprocess = (e) => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    source.connect(tap);
    tap.connect(context.destination);
    return {
      async finish() {
        source.disconnect();
        tap.disconnect();
        for (const track of stream.getTracks()) track.stop();
        const rate = context.sampleRate;
        await context.close();
        return wav(resample(join(chunks), rate, RATE), RATE);
      },
    };
  }

  function join(chunks) {
    const all = new Float32Array(chunks.reduce((n, c) => n + c.length, 0));
    let at = 0;
    for (const chunk of chunks) { all.set(chunk, at); at += chunk.length; }
    return all;
  }

  // Where a browser won't record at 16 kHz, the samples are brought down to it.
  function resample(samples, from, to) {
    if (from === to) return samples;
    const out = new Float32Array(Math.floor((samples.length * to) / from));
    for (let i = 0; i < out.length; i++) {
      const x = (i * from) / to;
      const j = Math.floor(x);
      const next = samples[Math.min(j + 1, samples.length - 1)];
      out[i] = samples[j] + (next - samples[j]) * (x - j);
    }
    return out;
  }

  // 16-bit PCM WAV, mono.
  function wav(samples, rate) {
    const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
    const ascii = (at, text) => [...text].forEach((ch, i) => view.setUint8(at + i, ch.charCodeAt(0)));
    ascii(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    ascii(8, "WAVEfmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, rate, true);
    view.setUint32(28, rate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    ascii(36, "data");
    view.setUint32(40, samples.length * 2, true);
    samples.forEach((sample, i) => view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, sample)) * 0x7fff, true));
    return new Blob([view.buffer], { type: "audio/wav" });
  }

  root.Voice = { start, available: () => Boolean(root.navigator?.mediaDevices?.getUserMedia) };
})(globalThis);

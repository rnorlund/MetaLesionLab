/* Naming Assessment: copies microphone samples to the page in blocks, each tagged with the audio
   clock frame of its first sample, so a picture's onset can be placed in the recording exactly. */
class TLCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buf = new Float32Array(2048);
    this.n = 0;
    this.start = 0;
  }
  flush() {
    if (this.n) this.port.postMessage({ frame: this.start, samples: this.buf.slice(0, this.n) });
    this.n = 0;
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch && ch.length) {
      if (this.n && currentFrame !== this.start + this.n) this.flush();  // a gap in the stream
      if (!this.n) this.start = currentFrame;
      this.buf.set(ch, this.n);
      this.n += ch.length;
      if (this.n + ch.length > this.buf.length) this.flush();
    }
    return true;
  }
}
registerProcessor('tl-capture', TLCapture);

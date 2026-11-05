// 采集并重采样到 PCM16 / 16kHz / 单声道，每 1600 样本（100ms）抛出
class PCM16Processor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._out = []
    this._acc = 0
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0]
    if (!ch) return true
    const ratio = sampleRate / 16000 // 当前上下文采样率 / 目标 16k
    for (let i = 0; i < ch.length; i += 1) {
      this._acc += 1
      // 简单线性抽取/插值：按 ratio 累积，达到 1 输出一个 16k 样本
      if (this._acc >= ratio) {
        this._acc -= ratio
        let s = Math.max(-1, Math.min(1, ch[i]))
        this._out.push(s < 0 ? s * 0x8000 : s * 0x7fff)
        if (this._out.length >= 1600) {
          const arr = new Int16Array(this._out)
          // 噪声门：整帧能量过低（静音/底噪）就不上报，减少噪声干扰
          let sum = 0
          for (let k = 0; k < arr.length; k += 1) {
            const v = arr[k] / 32768
            sum += v * v
          }
          const rms = Math.sqrt(sum / arr.length)
          if (rms >= 0.015) this.port.postMessage(arr.buffer, [arr.buffer])
          this._out = []
        }
      }
    }
    return true
  }
}
registerProcessor('pcm16', PCM16Processor)

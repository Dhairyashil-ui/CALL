class AudioVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.isActive = false;
    this.phase = 0;
    this.animId = null;

    // Handle canvas resolution for Retina/HiDPI
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    this.width = rect.width || 450;
    this.height = rect.height || 90;
    this.canvas.width = this.width * dpr;
    this.canvas.height = this.height * dpr;
    this.ctx.scale(dpr, dpr);

    this.start();
  }

  setActive(active) {
    this.isActive = active;
  }

  start() {
    const render = () => {
      this.draw();
      this.animId = requestAnimationFrame(render);
    };
    render();
  }

  draw() {
    const { ctx, width, height } = this;
    ctx.clearRect(0, 0, width, height);

    this.phase += this.isActive ? 0.08 : 0.02;

    const bars = 48;
    const barWidth = width / bars - 2;
    const centerY = height / 2;

    for (let i = 0; i < bars; i++) {
      const progress = i / bars;
      // Calculate wave amplitude
      let amp;
      if (this.isActive) {
        // High dynamic range when talking
        amp = (Math.sin(this.phase + i * 0.35) * 0.5 + 0.5) * (height * 0.42);
        amp += Math.cos(this.phase * 1.5 + i * 0.2) * (height * 0.15);
      } else {
        // Gentle breathing idle wave
        amp = (Math.sin(this.phase + i * 0.15) * 0.5 + 0.5) * (height * 0.12) + 4;
      }

      const x = i * (barWidth + 2) + 1;
      const topY = centerY - amp / 2;

      // Gradient color based on position
      const gradient = ctx.createLinearGradient(0, topY, 0, centerY + amp / 2);
      if (this.isActive) {
        gradient.addColorStop(0, '#06b6d4'); // Cyan
        gradient.addColorStop(0.5, '#8b5cf6'); // Purple
        gradient.addColorStop(1, '#ec4899'); // Pink
      } else {
        gradient.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
        gradient.addColorStop(1, 'rgba(6, 182, 212, 0.1)');
      }

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.roundRect(x, topY, barWidth, Math.max(amp, 3), 2);
      ctx.fill();
    }
  }
}

window.AudioVisualizer = AudioVisualizer;

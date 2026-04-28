// Tiny signature pad — vanilla JS, no deps.
// Usage:
//   const pad = new SignaturePad(canvasEl);
//   pad.clear(); pad.isEmpty(); pad.toDataURL(); pad.loadDataURL(url);
class SignaturePad {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this._dirty = false;
        this._drawing = false;
        this._setup();
        this._bind();
    }

    _setup() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = Math.round(rect.width * dpr);
        this.canvas.height = Math.round(rect.height * dpr);
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.strokeStyle = '#0f172a';
        this.ctx.lineWidth = 2.2;
    }

    _pos(e) {
        const rect = this.canvas.getBoundingClientRect();
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    _bind() {
        const c = this.canvas;
        c.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            this._drawing = true;
            const p = this._pos(e);
            this.ctx.beginPath();
            this.ctx.moveTo(p.x, p.y);
            try { c.setPointerCapture(e.pointerId); } catch (_) {}
        });
        c.addEventListener('pointermove', (e) => {
            if (!this._drawing) return;
            const p = this._pos(e);
            this.ctx.lineTo(p.x, p.y);
            this.ctx.stroke();
            this._dirty = true;
        });
        const end = () => { this._drawing = false; };
        c.addEventListener('pointerup', end);
        c.addEventListener('pointerleave', end);
        c.addEventListener('pointercancel', end);
    }

    clear() {
        const dpr = window.devicePixelRatio || 1;
        this.ctx.save();
        this.ctx.setTransform(1, 0, 0, 1, 0, 0);
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.restore();
        this._dirty = false;
    }

    isEmpty() { return !this._dirty; }

    toDataURL() {
        // Trim transparent edges so the embedded PNG sits tight.
        const trimmed = this._trim();
        return trimmed.toDataURL('image/png');
    }

    loadDataURL(url) {
        if (!url) return;
        const img = new Image();
        img.onload = () => {
            const rect = this.canvas.getBoundingClientRect();
            // Fit image into the visible canvas area, preserving aspect.
            const scale = Math.min(rect.width / img.width, rect.height / img.height, 1);
            const w = img.width * scale;
            const h = img.height * scale;
            this.ctx.drawImage(img, 0, 0, w, h);
            this._dirty = true;
        };
        img.src = url;
    }

    _trim() {
        const w = this.canvas.width;
        const h = this.canvas.height;
        const data = this.ctx.getImageData(0, 0, w, h).data;
        let top = h, left = w, right = 0, bottom = 0, found = false;
        for (let y = 0; y < h; y++) {
            for (let x = 0; x < w; x++) {
                if (data[(y * w + x) * 4 + 3] > 0) {
                    found = true;
                    if (y < top) top = y;
                    if (y > bottom) bottom = y;
                    if (x < left) left = x;
                    if (x > right) right = x;
                }
            }
        }
        if (!found) return this.canvas;
        const pad = 6;
        const tw = Math.min(w, right - left + pad * 2);
        const th = Math.min(h, bottom - top + pad * 2);
        const out = document.createElement('canvas');
        out.width = tw;
        out.height = th;
        out.getContext('2d').drawImage(
            this.canvas,
            Math.max(0, left - pad), Math.max(0, top - pad), tw, th,
            0, 0, tw, th,
        );
        return out;
    }
}

window.SignaturePad = SignaturePad;

// List of fonts available for typed signatures (must match @font-face in CSS).
window.SIGNATURE_FONTS = [
    { id: 'Caveat',         label: 'Caveat',          weight: 600 },
    { id: 'Dancing Script', label: 'Dancing Script',  weight: 600 },
    { id: 'Great Vibes',    label: 'Great Vibes',     weight: 400 },
    { id: 'Sacramento',     label: 'Sacramento',      weight: 400 },
];

// Render `text` in `fontFamily` to a transparent PNG data URL.
// Returns '' if text is empty.
window.renderTypedSignature = async function (text, fontFamily, opts) {
    text = (text || '').trim();
    if (!text) return '';
    const o = Object.assign({ size: 96, color: '#0f172a', weight: 600,
                              padding: 12 }, opts || {});

    // Make sure the font is loaded before measuring/drawing.
    try { await document.fonts.load(`${o.weight} ${o.size}px "${fontFamily}"`); }
    catch (_) {}

    // Measure on a temp canvas
    const measure = document.createElement('canvas').getContext('2d');
    measure.font = `${o.weight} ${o.size}px "${fontFamily}"`;
    const m = measure.measureText(text);
    const w = Math.ceil(m.width) + o.padding * 2;
    const h = Math.ceil(o.size * 1.4) + o.padding * 2;

    const dpr = window.devicePixelRatio || 1;
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.font = `${o.weight} ${o.size}px "${fontFamily}"`;
    ctx.fillStyle = o.color;
    ctx.textBaseline = 'middle';
    ctx.fillText(text, o.padding, h / 2);
    return canvas.toDataURL('image/png');
};

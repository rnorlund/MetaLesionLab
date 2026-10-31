/* The opening animation's firelit cave (WebGL, no libraries). Loaded by splash.js only when the intro plays.

   A per-pixel rock wall (fractal noise relief) lit by a dancing, flickering point fire at the front right; the objects
   drifting across between the fire and the wall throw soft shadows (penumbra from many light samples, drawn into a
   2D mask that the shader reads); a heat haze warps the shadows; smoke drifts near the fire; warm grading, vignette.
   The chair's shadow slides from the left to the stage centre exactly where splash.js's DOM chair (the `actor`) sits,
   so that splash.js can hand over to the DOM chair without a jump.

   window.PCCave = {
     load(base, ms)    -> Promise<boolean>  the 18 object sprites + the chair; true when WebGL and everything is ready
     start(stage, o)   -> boolean           puts the canvas in `stage`'s scene and starts drawing (false: use the DOM cave)
     fadeOut(ms)       fades the canvas out, then stops
     stop()            cancels the frame loop, drops the textures and loses the context (safe to call twice)
   }
   o = { before: element the canvas goes in front of, chair: {x, y, size, lean} (px; size = the shadow's width on screen,
         lean in degrees), slide: ms the chair takes to arrive, k: size factor for the objects }. */
(function () {
  'use strict';
  var NAMES = ['brain', 'laptop', 'light-bulb', 'microchip', 'dna', 'amphora', 'lyre', 'scroll', 'owl', 'horse', 'greek-bust',
               'hourglass', 'key', 'cat', 'book', 'bird', 'ship', 'teapot'];
  var SLOTS = 8, LOOP = 14, DPR_MAX = 1.5;
  /* The heat haze and the small wavering of the shadows run at HALF the prototype's speed (Roger's call): every
     time that drives them is multiplied by this. The flame's flicker (fire()) and the smoke are not slowed. */
  var WAVER_SPEED = 0.5;
  var PARALLAX_H0 = 1.3;
  var SIZE = { dna: 0.78, key: 0.8, scroll: 0.85, hourglass: 0.9, amphora: 0.9, 'light-bulb': 0.9, bird: 1.08, laptop: 1.05, lyre: 0.95,
               owl: 0.95, 'greek-bust': 0.95, microchip: 0.95, cat: 0.95 };

  var SP = null, cv, gl, prog, tex, U = {}, mc, mx, raf = 0, stopped = true, t0 = 0, opts, Hr = 0.5625, L0, curLoop = 0, perms = {};
  var seed0 = Math.floor(Math.random() * 1e9);  // a new shuffled set each visit
  var MW = 1024, MH = 576, lost = null;

  function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
  function smooth(a, b, x) { x = clamp((x - a) / (b - a), 0, 1); return x * x * (3 - 2 * x); }

  // ---- one shared fire signal: 1/f-like smoothed noise, ~0.5-8 Hz ----
  function hash(n) { n = Math.sin(n * 127.1 + 311.7) * 43758.5453; return n - Math.floor(n); }
  function vn(x, seed) {
    var i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
    return (hash(i + seed * 17.3) * (1 - u) + hash(i + 1 + seed * 17.3) * u) * 2 - 1;
  }
  var BANDS = [[0.6, 1], [2, 0.95], [3.3, 0.8], [5.1, 0.55], [7.7, 0.35]];
  function fn(t, seed) { var s = 0, a = 0; BANDS.forEach(function (b) { s += b[1] * vn(t * b[0] + seed * 3.1, seed + b[0]); a += b[1]; }); return s / a * 2.2; }
  function fire(t) {
    return { I: clamp(1 + 0.27 * fn(t, 1), 0.5, 1.45), I2: clamp(1 + 0.3 * fn(t, 7), 0.5, 1.45),
             dx: 0.012 * fn(t, 2), dy: 0.022 * fn(t, 3), dz: 0.05 * fn(t, 4), size: fn(t, 5) };
  }

  // ---- the choreography (as cave() in splash.js's DOM version) ----
  var DRIFT = [];
  for (var i = 0; i < SLOTS; i++) DRIFT.push({ i: i, dir: i % 2 ? -1 : 1, scale: 0.65 + (i % 3) * 0.22, ytop: 0.14 + (i * 0.37 % 0.5), period: 4500 + i * 520, delay: i * 320 - 400 });
  function rng(seed) { var a = seed >>> 0; return function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function perm(k) {
    var r = rng(seed0 + k * 7919), a = NAMES.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(r() * (i + 1)), x = a[i]; a[i] = a[j]; a[j] = x; }
    return a;
  }
  function pick(loop, slot) { var j = loop * SLOTS + slot, k = Math.floor(j / NAMES.length); return (perms[k] || (perms[k] = perm(k)))[j % NAMES.length]; }
  function scene(t) {  // t: seconds since the cave began
    var g = smooth(0, 0.7, t) * (1 - smooth(LOOP - 1.4, LOOP - 0.2, t % LOOP));
    var drift = DRIFT.map(function (d) {
      var f = (((t * 1000 - d.delay) / d.period) % 1 + 1) % 1, name = pick(curLoop, d.i);
      return { i: d.i, dir: d.dir, scale: d.scale, ytop: d.ytop, period: d.period, delay: d.delay, f: f, name: name, m: SIZE[name] || 1,
               xo: d.dir > 0 ? -0.25 + 1.3 * f : 1.05 - 1.3 * f };
    });
    var u = clamp(t * 1000 / opts.slide, 0, 1), e = 1 - Math.pow(1 - u, 3.2);
    return { g: g, drift: drift, chair: { x: 0.5 - 0.62 * (1 - e), moving: 1 - e } };
  }

  // ---- shadows: casters in the room between the fire and the wall (units: stage widths; the wall is z = 0, y down) ----
  function lightNow(F) { return { x: L0.x + F.dx, y: L0.y + F.dy, z: L0.z + F.dz, size: F.size, I: F.I }; }
  function mkCaster(img, xw, yw, s0, ws, A, id) {
    return { img: img, id: id, ox: L0.x + (xw - L0.x) / s0, oy: L0.y + (yw - L0.y) / s0, oz: L0.z * (1 - 1 / s0), ws: ws, A: A, center: false, wob: 1 };
  }
  function casters(sc, I) {
    var out = [], k = clamp(1 + 0.6 * (I - 1), 0.55, 1.15);
    sc.drift.forEach(function (o) {
      var dx = o.xo - L0.x, near = 1 - Math.min(1, Math.abs(dx));
      var s0 = 1.15 + 0.55 * near, ws = 0.15 * opts.k * o.scale * 0.85 * o.m;
      var yc = o.ytop * Hr + ws * s0 / 2 + (o.dir > 0 ? 0.005 : -0.005) * o.f;
      var c = mkCaster(SP[o.name], o.xo, yc, s0, ws, (0.42 + 0.33 * near) * k * sc.g, o.i);
      c.ox = o.xo;
      out.push(c);
    });
    // the chair: its shadow is as wide as the DOM chair's, centred where the DOM chair is, skewed about its centre
    // The shader reads the mask a little off (rock-relief parallax: shift = (p - light) / z * relief * 0.025, relief about
    // PARALLAX_H0 on average), so the chair is drawn pre-shifted by that much and lands where the DOM chair sits.
    var shx = (sc.chair.x - L0.x) / (0.5 * L0.z) * PARALLAX_H0 * 0.025;
    var shy = ((1 - opts.chair.y / Hr) - (1 - L0.y / Hr)) / (0.5 * L0.z) * PARALLAX_H0 * 0.025;
    var ch = opts.chair, s0 = 1.3, c = mkCaster(SP.chair, sc.chair.x + shx, ch.y - shy * Hr, s0, ch.size / s0, 0.66 * k * sc.g, 99);
    c.center = true; c.wob = 0.35; c.leanTan = Math.tan((ch.lean + 8 * sc.chair.moving) * Math.PI / 180);
    out.push(c);
    return out;
  }
  function drawMask(ctx, pw, cs, Lt, N, now) {
    var R = 0.012 * (0.85 + 0.25 * Lt.size), rot = now / 900, wt = now * WAVER_SPEED;  // wt: the wavering's clock
    cs.forEach(function (c) {
      if (c.A <= 0.002) return;
      var s = Lt.z / (Lt.z - c.oz), size = c.ws * s * pw;
      var lean = c.center ? c.leanTan + 0.03 * c.wob * vn(wt / 310 + c.id * 5, c.id)
                          : clamp(-(c.ox - Lt.x) / 0.6, -0.47, 0.47) + 0.03 * vn(wt / 310 + c.id * 5, c.id);
      var a = 1 - Math.pow(1 - clamp(c.A, 0, 0.97), 1 / N);
      var wx = 0.003 * c.wob * vn(wt / 260 + c.id * 3.1, c.id + 9), wy = 0.002 * c.wob * vn(wt / 290 + c.id * 1.7, c.id + 4);
      ctx.globalAlpha = a;
      for (var j = 0; j < N; j++) {
        var ang = j * 2.39996 + rot, r = Math.sqrt((j + 0.5) / N) * R;
        var lx = Lt.x + Math.cos(ang) * r, ly = Lt.y + Math.sin(ang) * r * 0.8;
        var cx = (lx + (c.ox - lx) * s + wx) * pw, cy = (ly + (c.oy - ly) * s + wy) * pw;
        if (c.center) { ctx.setTransform(1, 0, lean, 1, cx, cy); ctx.drawImage(c.img, -size / 2, -size / 2, size, size); }
        else { ctx.setTransform(1, 0, lean, 1, cx, cy + size / 2); ctx.drawImage(c.img, -size / 2, -size, size, size); }
      }
    });
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
  }

  // ---- the shader: the rock, the fire's light, the shadows, haze, smoke, grade ----
  var VS = 'attribute vec2 a;varying vec2 vUv;void main(){vUv=a*.5+.5;gl_Position=vec4(a,0.,1.);}';
  var FS = [
    'precision highp float;',
    'varying vec2 vUv; uniform vec2 uRes; uniform float uT,uW,uI,uI2,uSz; uniform vec3 uL; uniform sampler2D uSh;',  // uW: the wavering's clock (WAVER_SPEED x uT)
    'const mat2 M=mat2(.8,.6,-.6,.8);',
    'float h21(vec2 p){p=50.*fract(p*0.3183099+vec2(.71,.113));return fract(p.x*p.y*(p.x+p.y));}',
    'float vn(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*f*(f*(f*6.-15.)+10.);return mix(mix(h21(i),h21(i+vec2(1,0)),f.x),mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x),f.y);}',
    'float fbm(vec2 p){float s=0.,a=.5;for(int i=0;i<5;i++){s+=a*vn(p);p=M*p*2.03+vec2(17.1,9.7);a*=.5;}return s;}',
    'float sabs(float t){return sqrt(t*t+0.012);}',
    'float hgt(vec2 p){',
    '  float bulge=fbm(p*.8+11.);',
    '  float b=fbm(p*2.3);',
    '  float r=0.,a=.4;vec2 q=p*4.2;',
    '  for(int i=0;i<5;i++){float v=vn(q);r+=a*(1.-sabs(2.*v-1.));q=M*q*2.1+vec2(5.3,1.7);a*=.5;}',
    '  float bl=sabs(2.*fbm(p*4.5+3.)-1.);',
    '  return bulge*1.3+b*.35+r*.9+bl*.12;',
    '}',
    'void main(){',
    '  float asp=uRes.x/uRes.y; vec2 p=vec2(vUv.x*asp,vUv.y);',
    '  vec3 Lw=vec3(uL.x*asp,uL.y,uL.z);',
    '  float e=1.2/uRes.y;',
    '  float h0=hgt(p), hx=hgt(p+vec2(e,0.)), hy=hgt(p+vec2(0.,e));',
    '  vec2 gr=vec2(hx-h0,hy-h0)/e;',
    '  vec3 n=normalize(vec3(-gr*0.085,1.));',
    '  vec3 v=Lw-vec3(p,h0*0.05); float d=length(v); vec3 ld=v/d;',
    '  float diff=max(dot(n,ld),0.);',
    '  float att=1./(1.+5.0*d*d);',
    '  float prox=exp(-length(p-Lw.xy)*0.9);',
    '  vec2 q=vec2(vUv.x*13.,vUv.y*8.-uW*1.9);',  // the heat haze, on the slowed clock uW
    '  vec2 w=vec2(vn(q)-.5,vn(q+vec2(7.3,2.1)+uW*.4)-.5)+0.5*vec2(vn(q*2.3+uW*1.3)-.5,vn(q*2.3+9.)-.5);',
    '  vec2 wuv=vUv+w*(0.0045+0.006*prox)*(0.7+0.5*uI);',
    '  wuv+=((p-Lw.xy)/Lw.z)*(h0*0.025)*vec2(1./asp,1.);',
    '  float sm=texture2D(uSh,wuv).a;',
    '  sm=smoothstep(0.0,1.0,sm);',
    '  vec3 lc=mix(vec3(1.,.42,.13),vec3(1.,.72,.34),clamp(att*2.4,0.,1.));',
    '  float E=uI*2.6*diff*att;',
    '  vec3 alb=mix(vec3(.30,.22,.16),vec3(.52,.42,.32),fbm(p*4.+2.));',
    '  alb*=0.8+0.4*vn(M*p*34.);',
    '  vec3 col=alb*(vec3(.030,.022,.016)+lc*E*(1.-sm*0.96));',
    '  col+=alb*vec3(.5,.3,.18)*att*0.05*uI*sm;',
    '  vec2 fp=Lw.xy; float dd=length((p-fp)*vec2(.8,1.2));',
    '  float sk=fbm(p*vec2(2.0,2.8)+vec2(uT*.035,-uT*.11));',
    '  float sk2=fbm(p*vec2(4.5,5.5)+vec2(-uT*.05,-uT*.18)+5.);',
    '  float smoke=smoothstep(.42,.85,sk)*exp(-dd*1.5)*.5+smoothstep(.5,.9,sk2)*exp(-dd*2.4)*.35;',
    '  col+=vec3(.95,.55,.28)*smoke*.22*uI;',
    '  col+=vec3(.5,.45,.4)*smoothstep(.55,.85,sk)*.015;',
    '  col+=vec3(1.,.55,.2)*exp(-dd*dd*9.)*.35*uI*uI+vec3(1.,.7,.35)*exp(-dd*dd*60.)*.4*uI;',
    '  col=1.-exp(-col*1.5);',
    '  col=pow(col,vec3(.95,1.02,1.12))*vec3(1.06,.98,.88);',
    '  float vg=length((vUv-vec2(.62,.32))*vec2(1.15,1.));',
    '  col*=1.-smoothstep(.35,1.05,vg)*.85;',
    '  col+=(h21(gl_FragCoord.xy+fract(uT))-.5)/200.;',
    '  gl_FragColor=vec4(col,1.);',
    '}'].join('\n');

  function shader(type, src) {
    var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
    return s;
  }

  // ---- sprites: loaded once; faint stray alpha cleared so no sprite box ever shows ----
  function loadSprites(base) {
    var all = NAMES.concat('chair'), got = {};
    return Promise.all(all.map(function (n) {
      return new Promise(function (resolve, reject) {
        var im = new Image();
        im.onload = function () {
          var c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight;
          var x = c.getContext('2d'); x.drawImage(im, 0, 0);
          var d = x.getImageData(0, 0, c.width, c.height);
          for (var i = 3; i < d.data.length; i += 4) if (d.data[i] < 40) d.data[i] = 0;
          x.putImageData(d, 0, 0); got[n] = c; resolve();
        };
        im.onerror = function () { reject(new Error('sprite ' + n)); };
        im.src = n === 'chair' ? base + 'shadow_chair.webp' : base + 'shadows/' + n + '.webp';
      });
    })).then(function () { SP = got; });
  }

  // Resolves true once WebGL works (a throwaway context compiles the shader) and the sprites are in; false otherwise,
  // or if that takes longer than `ms`.
  function load(base, ms) {
    var timer, slow = new Promise(function (resolve) { timer = setTimeout(function () { resolve(false); }, ms || 3000); });
    var ok = loadSprites(base).then(function () {
      var probe = document.createElement('canvas'), g = probe.getContext('webgl');
      if (!g) return false;
      var s = g.createShader(g.FRAGMENT_SHADER); g.shaderSource(s, FS); g.compileShader(s);
      var good = !!g.getShaderParameter(s, g.COMPILE_STATUS);
      var ext = g.getExtension('WEBGL_lose_context'); if (ext) ext.loseContext();
      return good;
    }).catch(function () { return false; });
    return Promise.race([ok, slow]).then(function (r) { clearTimeout(timer); return r; });
  }

  function start(stage, o) {
    stop();
    try {
      opts = { before: o.before, chair: o.chair, slide: o.slide || 3200, k: o.k || 1 };
      var W = window.innerWidth, H = window.innerHeight, d = Math.min(window.devicePixelRatio || 1, DPR_MAX);
      Hr = H / W; MH = Math.max(1, Math.round(MW * Hr));
      L0 = { x: 0.93, y: 0.96 * Hr, z: 1.0 };  // the fire, in stage widths (the prototype's 0.54 was 0.96 of its 9/16 height)
      var c = opts.chair;  // px -> stage widths
      opts.chair = { x: c.x / W, y: c.y / W, size: c.size / W, lean: c.lean };
      cv = document.createElement('canvas');
      cv.className = 'sp-cave';
      cv.setAttribute('aria-hidden', 'true');
      cv.width = Math.round(W * d); cv.height = Math.round(H * d);  // sized once: the intro finishes on resize
      cv.style.opacity = 0;
      gl = cv.getContext('webgl', { antialias: false, alpha: false });
      if (!gl) throw new Error('no webgl');
      prog = gl.createProgram(); gl.attachShader(prog, shader(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
      gl.useProgram(prog);
      var b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
      var loc = gl.getAttribLocation(prog, 'a'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      ['uRes', 'uT', 'uW', 'uI', 'uI2', 'uSz', 'uL', 'uSh'].forEach(function (n) { U[n] = gl.getUniformLocation(prog, n); });
      tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.uniform1i(U.uSh, 0);
      gl.viewport(0, 0, cv.width, cv.height);
      mc = document.createElement('canvas'); mc.width = MW; mc.height = MH; mx = mc.getContext('2d');
      var parent = (o.before && o.before.parentNode) || stage;
      parent.insertBefore(cv, o.before || null);
    } catch (e) {
      console.warn('PCCave: WebGL cave unavailable, using the DOM cave', e);
      stop();
      return false;
    }
    stopped = false; perms = {}; curLoop = 0;
    t0 = performance.now();
    requestAnimationFrame(function () { if (cv) cv.style.opacity = 1; });  // fades in (the stage's CSS sets the transition)
    raf = requestAnimationFrame(frame);
    return true;
  }

  function frame(now) {
    if (stopped) return;
    raf = requestAnimationFrame(frame);
    try {
      var el = (now - t0) / 1000;
      curLoop = Math.floor(el / LOOP);
      var F = fire(now / 1000), Lt = lightNow(F), sc = scene(el % LOOP);
      mx.clearRect(0, 0, MW, MH);
      var cs = casters(sc, F.I).map(function (c) { c.A = Math.min(0.97, c.A * 1.3); return c; });
      drawMask(mx, MW, cs, Lt, 14, now);
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, mc);
      gl.uniform2f(U.uRes, cv.width, cv.height);
      gl.uniform1f(U.uT, now / 1000); gl.uniform1f(U.uW, now / 1000 * WAVER_SPEED);
      gl.uniform1f(U.uI, F.I); gl.uniform1f(U.uI2, F.I2);
      gl.uniform3f(U.uL, Lt.x, 1 - Lt.y / Hr, 0.5 * Lt.z);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    } catch (e) { console.error('PCCave frame', e); stop(); }
  }

  function fadeOut(ms) {
    if (!cv) return;
    cv.style.transition = 'opacity ' + ms + 'ms ease';
    cv.style.opacity = 0;
    clearTimeout(lost);
    lost = setTimeout(stop, ms + 50);
  }

  function stop() {
    stopped = true;
    cancelAnimationFrame(raf); raf = 0;
    clearTimeout(lost); lost = null;
    if (gl) {
      try {
        if (tex) gl.deleteTexture(tex);
        if (prog) gl.deleteProgram(prog);
        var ext = gl.getExtension('WEBGL_lose_context'); if (ext) ext.loseContext();
      } catch (e) { /* already gone */ }
    }
    if (cv && cv.parentNode) cv.parentNode.removeChild(cv);
    gl = cv = tex = prog = mc = mx = null;
  }

  window.PCCave = { load: load, start: start, fadeOut: fadeOut, stop: stop, WAVER_SPEED: WAVER_SPEED };
})();

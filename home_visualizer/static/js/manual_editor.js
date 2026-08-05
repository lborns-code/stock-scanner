// עורך הדמיה ידני — עובד לגמרי בדפדפן, בלי שרת ובלי API.
// טוענים תמונת בית + תמונת פריט, וממקמים/מתאימים גודל/מסובבים/מרצפים
// את הפריט מעל תמונת הבית, ואז מורידים את התוצאה כתמונה.
(function () {
  "use strict";

  const canvas = document.getElementById("editorCanvas");
  const ctx = canvas.getContext("2d");
  const placeholder = document.getElementById("canvasPlaceholder");

  const houseInput = document.getElementById("manualHouseImage");
  const itemInput = document.getElementById("manualItemImage");
  const opacityInput = document.getElementById("opacityRange");
  const blendSelect = document.getElementById("blendMode");
  const tileCheckbox = document.getElementById("tileEnabled");
  const tileSizeRow = document.getElementById("tileSizeRow");
  const tileSizeInput = document.getElementById("tileSizeRange");
  const resetBtn = document.getElementById("resetAreaBtn");
  const downloadBtn = document.getElementById("downloadBtn");
  const hint = document.getElementById("manualHint");

  const MAX_W = 900;
  const MAX_H = 620;
  const HANDLE_R = 9;
  const ROTATE_OFFSET = 34;

  let houseImg = null;
  let itemImg = null;
  let tileCanvas = null;
  let area = null; // {x, y, w, h, rot}
  let drag = null; // {mode, startPointer, startArea}

  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = reader.result;
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function fitCanvasToHouse() {
    const ratio = Math.min(MAX_W / houseImg.width, MAX_H / houseImg.height, 1);
    canvas.width = Math.round(houseImg.width * ratio);
    canvas.height = Math.round(houseImg.height * ratio);
  }

  function initArea() {
    const w = canvas.width * 0.45;
    const h = w * (itemImg.height / itemImg.width);
    area = {
      x: canvas.width / 2,
      y: canvas.height / 2,
      w: w,
      h: Math.min(h, canvas.height * 0.6),
      rot: 0,
    };
  }

  function rebuildTileCanvas() {
    if (!itemImg) return;
    const size = parseInt(tileSizeInput.value, 10) || 120;
    const tw = size;
    const th = Math.max(1, Math.round(size * (itemImg.height / itemImg.width)));
    tileCanvas = document.createElement("canvas");
    tileCanvas.width = tw;
    tileCanvas.height = th;
    const tctx = tileCanvas.getContext("2d");
    tctx.drawImage(itemImg, 0, 0, tw, th);
  }

  function toLocal(px, py) {
    const dx = px - area.x;
    const dy = py - area.y;
    const cos = Math.cos(-area.rot);
    const sin = Math.sin(-area.rot);
    return { x: dx * cos - dy * sin, y: dx * sin + dy * cos };
  }

  function handleGlobalPositions() {
    // corner (resize) handle at local (w/2, h/2), rotate handle above center
    const corner = rotatePoint(area.w / 2, area.h / 2, area.rot);
    const rotateHandle = rotatePoint(0, -area.h / 2 - ROTATE_OFFSET, area.rot);
    return {
      corner: { x: area.x + corner.x, y: area.y + corner.y },
      rotate: { x: area.x + rotateHandle.x, y: area.y + rotateHandle.y },
    };
  }

  function rotatePoint(x, y, rot) {
    const cos = Math.cos(rot);
    const sin = Math.sin(rot);
    return { x: x * cos - y * sin, y: x * sin + y * cos };
  }

  function render(showHandles) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!houseImg) return;
    ctx.drawImage(houseImg, 0, 0, canvas.width, canvas.height);

    if (itemImg && area) {
      ctx.save();
      ctx.globalAlpha = parseFloat(opacityInput.value);
      ctx.globalCompositeOperation = blendSelect.value;
      ctx.translate(area.x, area.y);
      ctx.rotate(area.rot);
      if (tileCheckbox.checked && tileCanvas) {
        const pattern = ctx.createPattern(tileCanvas, "repeat");
        ctx.fillStyle = pattern;
        ctx.fillRect(-area.w / 2, -area.h / 2, area.w, area.h);
      } else {
        ctx.drawImage(itemImg, -area.w / 2, -area.h / 2, area.w, area.h);
      }
      ctx.restore();
    }

    if (showHandles && area) {
      ctx.save();
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
      ctx.translate(area.x, area.y);
      ctx.rotate(area.rot);
      ctx.strokeStyle = "#b5824a";
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.strokeRect(-area.w / 2, -area.h / 2, area.w, area.h);
      ctx.setLineDash([]);
      ctx.restore();

      const pos = handleGlobalPositions();

      // line from top-center to rotate handle
      const topCenter = rotatePoint(0, -area.h / 2, area.rot);
      ctx.beginPath();
      ctx.moveTo(area.x + topCenter.x, area.y + topCenter.y);
      ctx.lineTo(pos.rotate.x, pos.rotate.y);
      ctx.strokeStyle = "#b5824a";
      ctx.lineWidth = 2;
      ctx.stroke();

      drawHandle(pos.corner, "#8f6534");
      drawHandle(pos.rotate, "#2e7d32");
    }
  }

  function drawHandle(pt, color) {
    ctx.beginPath();
    ctx.arc(pt.x, pt.y, HANDLE_R, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  function getPointer(evt) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const src = evt.touches && evt.touches.length ? evt.touches[0] : evt;
    return {
      x: (src.clientX - rect.left) * scaleX,
      y: (src.clientY - rect.top) * scaleY,
    };
  }

  function dist(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  function hitTest(pt) {
    if (!area) return null;
    const pos = handleGlobalPositions();
    if (dist(pt, pos.corner) <= HANDLE_R + 6) return "resize";
    if (dist(pt, pos.rotate) <= HANDLE_R + 6) return "rotate";
    const local = toLocal(pt.x, pt.y);
    if (Math.abs(local.x) <= area.w / 2 && Math.abs(local.y) <= area.h / 2) return "move";
    return null;
  }

  function onPointerDown(evt) {
    if (!area) return;
    const pt = getPointer(evt);
    const mode = hitTest(pt);
    if (!mode) return;
    evt.preventDefault();
    drag = {
      mode: mode,
      start: pt,
      area: Object.assign({}, area),
    };
  }

  function onPointerMove(evt) {
    if (!drag) return;
    evt.preventDefault();
    const pt = getPointer(evt);

    if (drag.mode === "move") {
      area.x = drag.area.x + (pt.x - drag.start.x);
      area.y = drag.area.y + (pt.y - drag.start.y);
    } else if (drag.mode === "resize") {
      const local = toLocal(pt.x, pt.y);
      area.w = Math.max(20, Math.abs(local.x) * 2);
      area.h = Math.max(20, Math.abs(local.y) * 2);
    } else if (drag.mode === "rotate") {
      const angle = Math.atan2(pt.y - area.y, pt.x - area.x);
      area.rot = angle + Math.PI / 2;
    }
    render(true);
  }

  function onPointerUp() {
    drag = null;
  }

  function updatePlaceholder() {
    placeholder.style.display = houseImg ? "none" : "flex";
    canvas.style.display = houseImg ? "block" : "none";
    downloadBtn.disabled = !(houseImg && itemImg);
    hint.style.display = houseImg && itemImg ? "block" : "none";
  }

  houseInput.addEventListener("change", async () => {
    const file = houseInput.files[0];
    if (!file) return;
    houseImg = await loadImage(file);
    fitCanvasToHouse();
    if (itemImg) initArea();
    updatePlaceholder();
    render(!!itemImg);
  });

  itemInput.addEventListener("change", async () => {
    const file = itemInput.files[0];
    if (!file) return;
    itemImg = await loadImage(file);
    rebuildTileCanvas();
    if (houseImg) {
      initArea();
      render(true);
    }
    updatePlaceholder();
  });

  opacityInput.addEventListener("input", () => render(true));
  blendSelect.addEventListener("change", () => render(true));
  tileCheckbox.addEventListener("change", () => {
    tileSizeRow.style.display = tileCheckbox.checked ? "block" : "none";
    if (tileCheckbox.checked) rebuildTileCanvas();
    render(true);
  });
  tileSizeInput.addEventListener("input", () => {
    rebuildTileCanvas();
    render(true);
  });

  resetBtn.addEventListener("click", () => {
    if (!itemImg) return;
    initArea();
    render(true);
  });

  downloadBtn.addEventListener("click", () => {
    if (!houseImg || !itemImg) return;
    render(false);
    const link = document.createElement("a");
    link.download = "home-visualization.png";
    link.href = canvas.toDataURL("image/png");
    link.click();
    render(true);
  });

  canvas.addEventListener("mousedown", onPointerDown);
  window.addEventListener("mousemove", onPointerMove);
  window.addEventListener("mouseup", onPointerUp);
  canvas.addEventListener("touchstart", onPointerDown, { passive: false });
  window.addEventListener("touchmove", onPointerMove, { passive: false });
  window.addEventListener("touchend", onPointerUp);

  updatePlaceholder();
})();

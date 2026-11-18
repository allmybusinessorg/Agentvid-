/* Handcrafted Creative Creature UI Controls: Custom Dropdowns, Precision Sliders & Color Swatches */
window.AVControls = (() => {
  let activeMenu = null;
  let activeWrapper = null;

  function closeAllMenus() {
    if (activeMenu) {
      activeMenu.remove();
      activeMenu = null;
    }
    if (activeWrapper) {
      activeWrapper.classList.remove("open");
      activeWrapper = null;
    }
  }

  document.addEventListener("click", e => {
    if (activeWrapper && !activeWrapper.contains(e.target) && (!activeMenu || !activeMenu.contains(e.target))) {
      closeAllMenus();
    }
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeAllMenus();
  });
  window.addEventListener("resize", closeAllMenus);
  window.addEventListener("scroll", closeAllMenus, true);

  function enhanceSelects(root = document) {
    root.querySelectorAll("select.select").forEach(sel => {
      if (sel.dataset.avEnhanced === "1") return;
      sel.dataset.avEnhanced = "1";

      const isCompact = (sel.getAttribute("style") || "").includes("width:auto");
      const wrap = document.createElement("div");
      wrap.className = "av-dd" + (isCompact ? " compact" : "");
      sel.parentNode.insertBefore(wrap, sel);
      wrap.appendChild(sel);
      sel.classList.add("av-native-hidden");

      const trigger = document.createElement("button");
      trigger.type = "button";
      trigger.className = "av-dd-trigger";
      trigger.disabled = sel.disabled;

      const labelSpan = document.createElement("span");
      labelSpan.className = "av-dd-label";
      const updateLabel = () => {
        const opt = sel.options[sel.selectedIndex];
        labelSpan.textContent = opt ? opt.textContent : "";
      };
      updateLabel();

      const chev = document.createElement("span");
      chev.className = "av-dd-chev";
      chev.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`;

      trigger.appendChild(labelSpan);
      trigger.appendChild(chev);
      wrap.appendChild(trigger);

      trigger.addEventListener("click", e => {
        e.stopPropagation();
        if (sel.disabled) return;
        const wasOpen = activeWrapper === wrap;
        closeAllMenus();
        if (wasOpen) return;

        wrap.classList.add("open");
        activeWrapper = wrap;

        const menu = document.createElement("div");
        menu.className = "av-dd-menu";
        Array.from(sel.options).forEach((opt, idx) => {
          const item = document.createElement("button");
          item.type = "button";
          item.className = "av-dd-opt" + (idx === sel.selectedIndex ? " selected" : "");
          const txt = document.createElement("span");
          txt.textContent = opt.textContent;
          const chk = document.createElement("span");
          chk.className = "av-dd-check";
          chk.innerHTML = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;
          item.appendChild(txt);
          item.appendChild(chk);
          item.addEventListener("click", ev => {
            ev.stopPropagation();
            sel.selectedIndex = idx;
            sel.value = opt.value;
            updateLabel();
            closeAllMenus();
            sel.dispatchEvent(new Event("change", { bubbles: true }));
          });
          menu.appendChild(item);
        });

        document.body.appendChild(menu);
        activeMenu = menu;

        // Smart viewport positioning (flip upward if near bottom edge)
        const rect = trigger.getBoundingClientRect();
        const menuW = Math.max(rect.width, 180);
        menu.style.width = `${menuW}px`;
        const menuH = Math.min(260, menu.scrollHeight + 10);
        const spaceBelow = window.innerHeight - rect.bottom - 10;
        const top = spaceBelow < menuH && rect.top > menuH
          ? Math.max(8, rect.top - menuH - 6)
          : rect.bottom + 6;
        const left = Math.min(window.innerWidth - menuW - 8, Math.max(8, rect.left));
        menu.style.top = `${top}px`;
        menu.style.left = `${left}px`;
      });
    });
  }

  function updateRangeFill(inp) {
    const min = Number(inp.min || 0);
    const max = Number(inp.max || 100);
    const val = Number(inp.value || 0);
    const pct = max > min ? ((val - min) / (max - min)) * 100 : 0;
    inp.style.setProperty("--pct", `${Math.max(0, Math.min(100, pct))}%`);
  }

  function enhanceRanges(root = document) {
    root.querySelectorAll('input[type="range"]').forEach(inp => {
      updateRangeFill(inp);
      if (inp.dataset.avRange === "1") return;
      inp.dataset.avRange = "1";
      inp.addEventListener("input", () => updateRangeFill(inp));
    });
  }

  const QUICK_SWATCHES = ["#FFFFFF", "#0066FF", "#2E84FF", "#FACC15", "#22C55E"];

  function enhanceColors(root = document) {
    root.querySelectorAll('input[type="color"]').forEach(inp => {
      if (inp.dataset.avColor === "1") return;
      inp.dataset.avColor = "1";

      const wrap = document.createElement("div");
      wrap.className = "av-color-wrap";
      const dot = document.createElement("label");
      dot.className = "av-color-dot";
      dot.style.background = inp.value || "#FFFFFF";

      const hex = document.createElement("span");
      hex.className = "av-color-hex";
      hex.textContent = String(inp.value || "#FFFFFF").toUpperCase();

      const presets = document.createElement("div");
      presets.className = "av-color-presets";
      QUICK_SWATCHES.forEach(c => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "av-swatch-mini";
        b.style.background = c;
        b.title = c;
        b.addEventListener("click", () => {
          inp.value = c;
          dot.style.background = c;
          hex.textContent = c;
          inp.dispatchEvent(new Event("change", { bubbles: true }));
        });
        presets.appendChild(b);
      });

      inp.parentNode.insertBefore(wrap, inp);
      dot.appendChild(inp);
      wrap.appendChild(dot);
      wrap.appendChild(hex);
      wrap.appendChild(presets);

      inp.addEventListener("input", () => {
        dot.style.background = inp.value;
        hex.textContent = String(inp.value).toUpperCase();
      });
    });
  }

  function enhance(root = document) {
    closeAllMenus();
    enhanceSelects(root);
    enhanceRanges(root);
    enhanceColors(root);
  }

  return { enhance, closeAllMenus };
})();
